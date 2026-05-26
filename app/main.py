"""
启信宝爬虫 FastAPI 服务

这个文件把爬虫包装成了 Web API（网页接口），
通过 HTTP 请求就能调爬虫，不用每次都敲命令行。

核心思路：
1. 用 FastAPI 框架创建 Web 服务
2. 把爬虫的每个功能（单公司爬取、批量爬取、高级搜索等）注册成 API 路由
3. 用 uvicorn 启动 HTTP 服务器，监听 8004 端口
4. 启动后自动生成 Swagger 文档（访问 http://localhost:8004/docs 查看）

和 CLI 版的区别：
- CLI 版每次运行都重新启动浏览器
- API 版浏览器是全局复用的，多个请求共享同一个浏览器实例
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
# Windows 上需要特殊的事件循环策略，Playwright 才能正常工作
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 把项目根目录加到 Python 路径中，才能 import 到 crawler 等模块
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
# 这些变量在整个服务运行期间保持，不随请求销毁
browser_manager: Optional[BrowserManager] = None  # 全局浏览器管理器（所有请求共用）
_tasks: Dict[str, Dict] = {}                      # 批量任务队列 {task_id: 任务信息}
_config = load_config()                           # 加载配置


def _clean_field(value: str) -> str:
    """
    清理字段值——去除"复制"按钮文本和"历史变动"等无关文字

    Args:
        value: 原始字段值

    Returns:
        清理后的字段值
    """
    if not value or value == "N/A":
        return "N/A"
    return value.replace("复制", "").replace(" 历史变动", "").strip()


def _cookie_status() -> dict:
    """检查当前 Cookie 状态——有没有登录凭证"""
    try:
        from utils import load_config
        config = load_config()
        cookie_str = config.get("cookie", "")
        cookies = parse_cookie_string(cookie_str, domain=".qixin.com")

        # 检查是否包含登录相关的关键字段
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
    """
    应用生命周期管理

    FastAPI 的 lifespan 机制：
    - 服务启动时：打印就绪信息
    - 服务关闭时：自动关闭浏览器，释放资源
    """
    print("[启动] API 服务就绪（浏览器按需懒加载）")
    yield
    global browser_manager
    if browser_manager:
        print("[关闭] 正在关闭浏览器...")
        await browser_manager.stop()


# 创建 FastAPI 应用实例
# FastAPI 会自动生成 Swagger 文档，访问 /docs 就能看到
app = FastAPI(
    title="启信宝企业数据爬虫 API",
    description="基于 Playwright 的启信宝企业信息爬取服务。支持单公司查询、批量导出、进度追踪。",
    version="2.0.0",
    lifespan=lifespan,
)

# 配置 CORS 中间件——允许其他域名下的网页调用本 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],       # 允许所有 HTTP 方法
    allow_headers=["*"],       # 允许所有请求头
)


# ── 辅助函数 ────────────────────────────────────────────

async def _ensure_browser():
    """
    确保浏览器已启动（懒加载）

    第一次请求时才会启动浏览器，后续请求复用。
    persistent context 模式下，登录态由浏览器自动管理（cookie/localStorage 等），
    不需要手动注入 cookie。
    """
    global browser_manager
    if browser_manager is None:
        browser_manager = BrowserManager(_config)
        try:
            await browser_manager.start()
            print("[浏览器] 延迟启动成功（persistent context 模式）")
        except Exception as e:
            browser_manager = None
            tb = traceback.format_exc()
            raise RuntimeError(f"浏览器启动失败: {e}\n{tb}")


async def _crawl_single(company_name: str, timeout: int = 120) -> dict:
    """
    执行单公司爬取（内部方法，不直接对外暴露）

    Args:
        company_name: 公司名称
        timeout: 超时秒数

    Returns:
        公司数据字典，失败返回 None
    """
    await _ensure_browser()

    config = load_config()

    crawler = QixinbaoCrawler()
    crawler.browser_manager = browser_manager
    crawler.config = config

    # 带上超时控制，防止某个公司一直卡住
    data = await asyncio.wait_for(
        crawler.crawl_single_company(company_name),
        timeout=timeout,
    )
    if data:
        # 清理字段中的干扰文本
        cleaned = {k: _clean_field(v) if isinstance(v, str) else v for k, v in data.items()}
        return cleaned
    return None


# ── API 路由 ────────────────────────────────────────────


@app.get("/health", summary="健康检查（查看服务是否正常运行）")
async def health_check():
    """检查服务状态——浏览器是否就绪、登录态是否有效"""
    logged_in = False
    if browser_manager is not None and browser_manager.context is not None:
        logged_in = await browser_manager.is_logged_in()
    return {
        "status": "ok",
        "browser_ready": browser_manager is not None,
        "logged_in": logged_in,
        "rate_limit": {
            "current_delay": QixinbaoCrawler._current_delay,
            "min_delay": QixinbaoCrawler._min_delay,
            "max_delay": QixinbaoCrawler._max_delay,
        },
        "version": "2.1.0",
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/crawl/single", response_model=SingleCrawlResponse, summary="爬取单个公司")
async def crawl_single(request: SingleCrawlRequest):
    """
    爬取单个公司的企业信息。

    输入公司名称，返回基本资料、联系方式等数据。
    需要先配置好 VIP Cookie。
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


@app.post("/crawl/advanced", response_model=AdvancedSearchResponse, summary="高级搜索（直接调 API，更快）")
async def crawl_advanced(request: AdvancedSearchRequest):
    """
    高级搜索——通过浏览器 session 调启信宝 API（persistent context 模式）

    优势：
    - 速度快（通常 0.1-0.5 秒出结果）
    - 共享浏览器完整登录态（cookie + localStorage + indexedDB）
    - 不依赖 cookie.txt，登录态由浏览器自动持久化
    - 支持多维度筛选（经营状态、地区、行业、注册资本等）

    劣势：
    - 返回的数据不如浏览器爬取详细
    - 取决于 API 是否稳定
    """
    try:
        # 确保浏览器已启动（persistent context，自动管理登录态）
        await _ensure_browser()

        # ── 登录态检测 ──────────────────────────────
        # 首次请求时检测登录态，未登录则给出明确提示
        is_logged_in = await browser_manager.is_logged_in()
        if not is_logged_in:
            return AdvancedSearchResponse(
                success=False,
                error="未检测到 VIP 登录态。请手动扫码登录：\n"
                      "1. 关闭浏览器数据目录下的锁文件（如果有）\n"
                      "2. 手动打开浏览器窗口访问 qixin.com 扫码登录\n"
                      "3. 登录后重新调用本接口",
            )

        crawler = QixinbaoCrawler()
        crawler.browser_manager = browser_manager

        result = await crawler.advanced_search_browser(
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

        # ── 异常处理 ────────────────────────────────
        if result.get("_no_context"):
            return AdvancedSearchResponse(
                success=False,
                error="浏览器 context 未初始化，请重启服务",
            )

        if result.get("_forbidden") or result.get("isLimit"):
            # 限速 / WAF 拦截：等间隔后重试一次
            import time as _time
            _time.sleep(QixinbaoCrawler._current_delay)
            result = await crawler.advanced_search_browser(
                keyword=request.keyword, status=request.status,
                province=request.province, industry=request.industry,
                establish=request.establish, reg_capi=request.reg_capi,
                paid_capi=request.paid_capi, company_type=request.company_type,
                org_type=request.org_type, employee=request.employee,
                insured=request.insured, listing=request.listing,
                scale=request.scale, page=request.page, page_size=request.page_size,
            )
            if result.get("isLimit"):
                return AdvancedSearchResponse(
                    success=False,
                    error="请求被限速，请稍后重试",
                )

        # totalNum=0 但无 error，可能是关键词无结果，非登录问题
        # 转换 API 返回的字段为统一的格式
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


@app.post("/crawl/batch", response_model=CrawlTaskResponse, summary="批量爬取（异步任务）", include_in_schema=False)
async def crawl_batch(request: BatchCrawlRequest, background_tasks: BackgroundTasks):
    """
    批量爬取多个公司。

    因为批量爬取耗时较长，这里采用"异步任务"模式：
    1. 提交任务后立即返回 task_id
    2. 通过 GET /crawl/task/{task_id} 查询进度
    3. 完成后通过 GET /crawl/download/{filename} 下载结果文件
    """
    task_id = uuid.uuid4().hex[:12]  # 生成唯一的任务 ID

    # 创建任务记录
    _tasks[task_id] = {
        "id": task_id,
        "status": "queued",          # 排队中
        "progress": 0,               # 当前进度
        "total": len(request.companies),  # 总数
        "companies": request.companies,
        "export_format": request.export_format,
        "timeout": request.timeout,
        "result_file": None,
        "error": None,
        "results": [],
    }

    # 在后台执行爬取（不阻塞当前请求）
    background_tasks.add_task(_run_batch, task_id)
    return CrawlTaskResponse(
        task_id=task_id,
        status="queued",
        message=f"已加入队列，共 {len(request.companies)} 个公司",
    )


async def _run_batch(task_id: str):
    """
    后台执行批量爬取（FastAPI 的 BackgroundTasks 机制）

    这个函数会在后台运行，不影响其他请求的处理。
    """
    task = _tasks[task_id]
    task["status"] = "running"  # 改为运行中

    try:
        await _ensure_browser()
        config = load_config()

        crawler = QixinbaoCrawler()
        crawler.browser_manager = browser_manager
        crawler.config = config

        exporter = get_exporter(config)

        # 逐个爬取公司
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

            task["progress"] = idx + 1  # 更新进度

        # 导出结果到文件
        exporter.save()
        if exporter.data:
            task["result_file"] = exporter.filename

        task["status"] = "completed"  # 标记完成

    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)
        traceback.print_exc()


@app.get("/crawl/task/{task_id}", response_model=CrawlTaskStatus, summary="查询任务状态")
async def get_task_status(task_id: str):
    """查询批量爬取任务的执行进度和结果（轮询这个接口就能看到进度）"""
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
        filename=os.path.basename(filename),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if filename.endswith(".xlsx")
        else "text/csv",
    )


@app.post("/cookie/check", response_model=CookieStatusResponse, summary="检查 Cookie 状态")
async def check_cookie():
    """检查当前配置的 Cookie 是否有效（有没有登录凭证）"""
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


@app.post("/login/setup", summary="扫码登录（首次设置）")
async def login_setup():
    """
    触发扫码登录流程——打开可见浏览器窗口，用户扫码后自动持久化登录态。

    流程：
    1. 关闭已有浏览器
    2. 打开可见浏览器访问启信宝登录页
    3. 等待用户扫码（60秒）
    4. 关闭浏览器，登录态自动持久化到 qixin_user_data 目录
    5. 重新以 headless 模式启动浏览器

    之后正常调用 /crawl/advanced 即可。
    """
    import shutil, os

    global browser_manager

    # 关闭已有浏览器
    if browser_manager:
        try:
            await browser_manager.stop()
        except Exception:
            pass
        browser_manager = None

    # 清理 user_data_dir（如果有残留状态）
    user_data_dir = os.path.join(os.path.dirname(__file__), "..", "qixin_user_data")
    if os.path.exists(user_data_dir):
        shutil.rmtree(user_data_dir)

    print("[登录] 正在打开浏览器，请扫码...")

    # 创建临时可见浏览器进行扫码
    temp_manager = BrowserManager(_config, user_data_dir)
    await temp_manager.start()
    # 扫码完成后，browser_manager 置 None，下次 API 调用时会重新初始化
    browser_manager = None

    return {
        "message": "扫码登录完成，登录态已持久化。请在下方调用 /crawl/advanced 接口。",
        "logged_in": True,
    }


@app.post("/cookie/update", summary="更新 Cookie")
async def update_cookie(cookie_str: str):
    """
    手动更新 Cookie 字符串。

    把完整的 Cookie 字符串写到 cookie.txt 文件，
    下次请求就会用新的 Cookie。
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
    uvicorn.run("app.main:app", host="0.0.0.0", port=8004, reload=True)
