"""
启信宝爬虫 FastAPI 服务
"""
import asyncio
import os
import uuid
import json
import traceback
from contextlib import asynccontextmanager
from typing import Dict, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from crawler import QixinbaoCrawler
from browser import BrowserManager
from exporter import get_exporter
from utils import load_config, parse_cookie_string

from app.schemas import (
    SingleCrawlRequest,
    BatchCrawlRequest,
    SingleCrawlResponse,
    CrawlTaskResponse,
    CrawlTaskStatus,
    CompanyData,
    CookieStatusResponse,
    AdvancedSearchRequest,
    AdvancedSearchResponse,
    AdvancedSearchItem,
)

# ── 全局状态 ──────────────────────────────────────────────
browser_manager: Optional[BrowserManager] = None
_tasks: Dict[str, Dict] = {}  # task_id -> task info
_config = load_config()


def _clean_field(value: str) -> str:
    """清理字段值中的复制按钮文本"""
    if not value or value == "N/A":
        return "N/A"
    return value.replace("复制", "").replace(" 历史变动", "").strip()


def _cookie_status() -> dict:
    """检查当前 Cookie 状态"""
    try:
        from utils import load_config
        config = load_config()
        cookie_str = config.get("cookie", "")
        cookies = parse_cookie_string(cookie_str, domain=".qixin.com")

        auth_keywords = ["session", "token", "sid", "auth", "uin", "ETK", "RK", "p_skey", "pt4_token"]
        has_auth = any(
            any(kw in c["name"].lower() for kw in auth_keywords)
            for c in cookies
        )
        return {"valid": has_auth, "count": len(cookies), "has_auth": has_auth}
    except Exception as e:
        return {"valid": False, "count": 0, "has_auth": False}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    print("[启动] API 服务就绪（浏览器按需懒加载）")
    yield
    global browser_manager
    if browser_manager:
        print("[关闭] 正在关闭浏览器...")
        await browser_manager.stop()


app = FastAPI(
    title="启信宝企业数据爬虫 API",
    description="基于 Playwright 的启信宝企业信息爬取服务。支持单公司查询、批量导出、进度追踪。",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 辅助函数 ────────────────────────────────────────────

async def _ensure_browser():
    """确保浏览器已启动"""
    global browser_manager
    if browser_manager is None:
        browser_manager = BrowserManager(_config)
        try:
            await browser_manager.start()
            print("[浏览器] 延迟启动成功")
        except Exception as e:
            browser_manager = None
            raise RuntimeError(f"浏览器启动失败: {e}")


async def _crawl_single(company_name: str, timeout: int = 120) -> dict:
    """执行单公司爬取（内部方法）"""
    await _ensure_browser()

    config = load_config()
    cookie = parse_cookie_string(config.get("cookie", ""), domain=".qixin.com")

    crawler = QixinbaoCrawler()
    crawler.browser_manager = browser_manager
    crawler.cookie = cookie
    crawler.config = config

    # 超时控制
    data = await asyncio.wait_for(
        crawler.crawl_single_company(company_name),
        timeout=timeout,
    )
    if data:
        # 清理字段
        cleaned = {k: _clean_field(v) if isinstance(v, str) else v for k, v in data.items()}
        return cleaned
    return None


# ── API 路由 ────────────────────────────────────────────


@app.get("/health", summary="健康检查")
async def health_check():
    """检查服务状态"""
    cookie_info = _cookie_status()
    return {
        "status": "ok",
        "browser_ready": browser_manager is not None,
        "cookie_valid": cookie_info["valid"],
        "cookie_count": cookie_info["count"],
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/crawl/single", response_model=SingleCrawlResponse, summary="爬取单个公司")
async def crawl_single(request: SingleCrawlRequest):
    """
    爬取单个公司的企业信息。

    返回公司基本信息、联系方式等数据。
    """
    try:
        data = await _crawl_single(request.company_name, timeout=request.timeout)
        if data:
            return SingleCrawlResponse(success=True, data=CompanyData(**data))
        else:
            return SingleCrawlResponse(
                success=False,
                error="爬取失败，请检查公司名称是否正确或 Cookie 是否有效",
            )
    except asyncio.TimeoutError:
        return SingleCrawlResponse(
            success=False,
            error=f"爬取超时（{request.timeout}秒），请稍后重试",
        )
    except Exception as e:
        traceback.print_exc()
        return SingleCrawlResponse(success=False, error=str(e))


@app.post("/crawl/advanced", response_model=AdvancedSearchResponse, summary="高级搜索")
async def crawl_advanced(request: AdvancedSearchRequest):
    """
    高级搜索（直接调用 API，无需浏览器启动）。

    支持多维筛选：关键词、经营状态、地区、行业、注册资本、成立年限等全部筛选项。
    搜索速度快（通常 0.1-0.5 秒），不消耗浏览器资源。
    """
    try:
        crawler = QixinbaoCrawler()
        result = crawler.advanced_search(
            keyword=request.keyword,
            status=request.status,
            province=request.province,
            industry=request.industry,
            establish=request.establish,
            reg_capi=request.reg_capi,
            paid_capi=request.paid_capi,
            company_type=request.company_type,
            org_type=request.org_type,
            employee=request.employee,
            insured=request.insured,
            listing=request.listing,
            scale=request.scale,
            page=request.page,
            page_size=request.page_size,
        )

        import re as _re
        _strip_em = lambda s: _re.sub(r"</?em>", "", s) if isinstance(s, str) else s

        # ── Cookie 过期检测 ──────────────────────────
        # totalNum=0 时可能是指标不匹配，也可能是 cookie 失效
        if result.get("totalNum") == 0 and not result.get("isLimit"):
            cookie_ok = QixinbaoCrawler.check_cookie_valid()
            if not cookie_ok:
                return AdvancedSearchResponse(
                    success=False,
                    error="Cookie 已过期或无效，请重新扫码登录后更新 cookie.txt",
                )

        items = []
        for item in result.get("items", []):
            items.append(AdvancedSearchItem(
                company_name=_strip_em(item.get("name", "N/A")),
                legal_person=_strip_em(item.get("oper_name", "N/A")),
                registered_capital=_strip_em(item.get("reg_capi", "N/A")),
                establish_date=_strip_em(item.get("start_date", "N/A")),
                status=_strip_em(item.get("status", "N/A")),
                credit_code=_strip_em(item.get("credit_no", "N/A")),
                phone=_strip_em(item.get("phone", "N/A")),
                email=_strip_em(item.get("email", "N/A")),
                address=_strip_em(item.get("address", "N/A")),
                industry=_strip_em(item.get("domain", "N/A")),
                eid=item.get("eid", ""),
            ))

        return AdvancedSearchResponse(
            success=True,
            total=result.get("total", "0"),
            total_num=result.get("totalNum", 0),
            search_time=result.get("searchTime", 0),
            items=items,
            page=request.page,
            has_next=result.get("hasNextPage", False),
        )
    except Exception as e:
        traceback.print_exc()
        return AdvancedSearchResponse(
            success=False,
            error=str(e),
        )


@app.post("/crawl/batch", response_model=CrawlTaskResponse, summary="批量爬取（异步）")
async def crawl_batch(request: BatchCrawlRequest, background_tasks: BackgroundTasks):
    """
    批量爬取多个公司。

    创建异步任务后立即返回 task_id，通过 GET /crawl/task/{task_id} 查询进度，
    完成后通过 GET /crawl/download/{filename} 下载结果文件。
    """
    task_id = uuid.uuid4().hex[:12]

    _tasks[task_id] = {
        "id": task_id,
        "status": "queued",
        "progress": 0,
        "total": len(request.companies),
        "companies": request.companies,
        "export_format": request.export_format,
        "timeout": request.timeout,
        "result_file": None,
        "error": None,
        "results": [],
    }

    background_tasks.add_task(_run_batch, task_id)
    return CrawlTaskResponse(
        task_id=task_id,
        status="queued",
        message=f"已加入队列，共 {len(request.companies)} 个公司",
    )


async def _run_batch(task_id: str):
    """后台执行批量爬取"""
    task = _tasks[task_id]
    task["status"] = "running"

    try:
        await _ensure_browser()
        config = load_config()
        cookie = parse_cookie_string(config.get("cookie", ""), domain=".qixin.com")

        crawler = QixinbaoCrawler()
        crawler.browser_manager = browser_manager
        crawler.cookie = cookie
        crawler.config = config

        exporter = get_exporter(config)

        for idx, company in enumerate(task["companies"]):
            try:
                data = await asyncio.wait_for(
                    crawler.crawl_single_company(company),
                    timeout=task["timeout"],
                )
                if data:
                    cleaned = {k: _clean_field(v) if isinstance(v, str) else v for k, v in data.items()}
                    task["results"].append(cleaned)
                    exporter.add_company(cleaned)
            except asyncio.TimeoutError:
                task["results"].append({
                    "company_name": company,
                    "error": f"超时（{task['timeout']}秒）",
                })
            except Exception as e:
                task["results"].append({"company_name": company, "error": str(e)})

            task["progress"] = idx + 1

        # 导出文件
        exporter.save()
        if exporter.data:
            task["result_file"] = exporter.filename

        task["status"] = "completed"

    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)
        traceback.print_exc()


@app.get("/crawl/task/{task_id}", response_model=CrawlTaskStatus, summary="查询任务状态")
async def get_task_status(task_id: str):
    """查询批量爬取任务的执行进度和结果"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return CrawlTaskStatus(
        task_id=task["id"],
        status=task["status"],
        progress=task["progress"],
        total=task["total"],
        result_file=task.get("result_file"),
        error=task.get("error"),
    )


@app.get("/crawl/download/{filename:path}", summary="下载结果文件")
async def download_file(filename: str):
    """下载爬取结果文件（Excel 或 CSV）"""
    filepath = os.path.join(os.path.dirname(__file__), "..", filename)
    filepath = os.path.abspath(filepath)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="文件不存在或已过期")

    return FileResponse(
        filepath,
        filename=os.path.basename(filepath),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if filename.endswith(".xlsx")
        else "text/csv",
    )


@app.post("/cookie/check", response_model=CookieStatusResponse, summary="检查 Cookie 状态")
async def check_cookie():
    """检查当前配置的 Cookie 是否有效（包含登录凭证）"""
    info = _cookie_status()
    msg = "Cookie 有效，包含登录凭证" if info["has_auth"] else \
          "Cookie 未包含登录凭证，请重新登录" if info["count"] > 0 else \
          "未配置 Cookie"
    return CookieStatusResponse(
        valid=info["has_auth"],
        cookie_count=info["count"],
        has_auth_cookies=info["has_auth"],
        message=msg,
    )


@app.post("/cookie/update", summary="更新 Cookie")
async def update_cookie(cookie_str: str):
    """
    手动更新 Cookie 字符串。

    将完整的 Cookie 字符串写入 cookie.txt 文件，
    下次请求时生效。
    """
    if not cookie_str or len(cookie_str) < 10:
        raise HTTPException(status_code=400, detail="Cookie 字符串无效")
    try:
        with open("cookie.txt", "w", encoding="utf-8") as f:
            f.write(cookie_str)
        return {"success": True, "message": "Cookie 已更新", "length": len(cookie_str)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入失败: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
