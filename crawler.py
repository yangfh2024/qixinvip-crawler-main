"""
启信宝爬虫核心模块

这个文件是爬虫的大脑，负责：
1. 搜索公司（在启信宝上搜索公司名称）
2. 进入公司详情页
3. 提取基本资料、联系方式、股东、高管等信息
4. 高级搜索（直接调 API，不用浏览器）
5. 验证 Cookie 是否有效
"""

import asyncio
import json
import time
import requests
from typing import Dict, List, Optional
from datetime import datetime
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from browser import BrowserManager
from utils import (
    load_config,            # 加载配置文件
    parse_cookie_string,     # 把 Cookie 字符串转成 Playwright 能用的格式
    random_delay,            # 随机等待，模拟人类操作
    human_like_typing,       # 模拟真人打字
    extract_text_content,    # 安全提取元素文本
    compute_qixin_signature, # 计算启信宝 API 签名
    qixin_json,             # JSON 序列化（和 JS 保持一致）
)


class QixinbaoCrawler:
    """启信宝爬虫类——所有爬取操作都封装在这里"""

    # ── 请求限速（防止被封 IP） ────────────────────────────
    _last_api_time: float = 0.0        # 上一次调 API 的时间戳
    _current_delay: float = 1.5        # 当前请求间隔，1.5s 起步（启信宝限速较严）
    _max_delay: float = 10.0           # 最长间隔，最多等 10 秒
    _min_delay: float = 1.0            # 最短间隔，1s（低于此值易触发限速）

    def __init__(self, config_path: str = 'config.json'):
        """
        初始化爬虫

        Args:
            config_path: 配置文件路径（默认 config.json）
        """
        self.config = load_config(config_path)               # 加载配置
        self.browser_manager = BrowserManager(self.config)    # 创建浏览器管理器
        self.cookie = parse_cookie_string(                    # 解析 Cookie
            self.config.get('cookie', ''),
            domain='.qixin.com'
        )
        self.delays = self.config.get('delays', {'min': 1.0, 'max': 3.0})  # 操作延迟
        self.base_url = "https://www.qixin.com"               # 启信宝网址

    async def search_company(self, page: Page, company_name: str) -> bool:
        """
        搜索公司——直接跳转到搜索 URL

        流程：
        1. 先访问首页，让 Cookie 生效
        2. 跳转到搜索页面
        3. 等待搜索结果加载完毕

        Args:
            page: Playwright 页面对象
            company_name: 要搜索的公司名称

        Returns:
            True=搜索成功, False=搜索失败
        """
        try:
            print(f"正在搜索: {company_name}")

            # 第1步：先访问首页，确保 Cookie 和登录状态生效
            await page.goto(f"{self.base_url}/", wait_until='domcontentloaded', timeout=30000)
            await random_delay(1, 2)

            # 第2步：直接跳转到搜索页面（不用手动填搜索框，更快更稳定）
            search_url = f"{self.base_url}/search?key={company_name}"
            print(f"[调试] 直接导航到搜索URL")
            await page.goto(search_url, wait_until='domcontentloaded', timeout=30000)

            # 第3步：等待搜索结果渲染出来
            await asyncio.sleep(3)

            try:
                await page.wait_for_load_state('networkidle', timeout=10000)
            except:
                pass  # 网络没完全空闲也没关系，继续往下走

            await asyncio.sleep(2)  # 额外等待，给 JS 渲染留时间
            print(f"[调试] 搜索页 URL: {page.url}")
            return True

        except Exception as e:
            print(f"搜索失败: {e}")
            return False

    async def click_first_result(self, page: Page) -> bool:
        """
        点击第一个搜索结果——进入公司详情页

        因为启信宝经常改版，这里准备了十几个备选 CSS 选择器，
        哪个能用就用哪个。

        Args:
            page: 页面对象

        Returns:
            True=成功进入详情页, False=没找到结果
        """
        try:
            print("[调试] 等待搜索结果列表渲染...")
            await asyncio.sleep(3)

            # ── 找"搜索结果"容器 ──────────────────────────
            result_container_selectors = [
                '.search-result-list',
                '.company-list',
                '.result-list',
                '[class*="result"]',
                '[class*="list"]'
            ]

            container_found = False
            for container_selector in result_container_selectors:
                try:
                    await page.wait_for_selector(container_selector, timeout=3000)
                    print(f"[调试] 找到结果容器: {container_selector}")
                    container_found = True
                    break
                except:
                    continue

            if not container_found:
                print("[调试] 未找到结果容器，尝试直接查找第一条结果")

            # ── 找第一个结果的链接 ────────────────────────
            # 按优先级排列了十几个备选选择器，应对网站改版
            result_selectors = [
                'a.company-name',                    # 方案A: 最直接
                '.search-result-list .item:first-child a',  # 方案B: 列表容器
                'a[href*="/company/"]',              # 方案C: 属性选择器
                '.company-item a',                   # 备用1
                '.search-result-item a',             # 备用2
                '.company-list-item:first-child a',  # 备用3
                '.result-item:first-child a',        # 备用4
                'div[class*="item"] a:first-child',  # 备用5: 模糊匹配
                'a[class*="company"]'                # 备用6: 模糊匹配
            ]

            link_element = None
            used_selector = None

            # 挨个尝试，直到找到能用的选择器
            for idx, selector in enumerate(result_selectors):
                try:
                    print(f"[调试] 尝试选择器 {idx + 1}/{len(result_selectors)}: {selector}")
                    link_element = await page.wait_for_selector(selector, timeout=3000)
                    if link_element:
                        used_selector = selector
                        print(f"[调试] 找到链接元素: {selector}")
                        break
                except Exception as e:
                    print(f"[调试] 选择器 {selector} 未找到: {str(e)[:50]}")
                    continue

            # 全都找不到 -> 截图保存现场，方便调试
            if not link_element:
                print("[!] 未找到搜索结果链接")
                await page.screenshot(path="search_page_debug.png")
                print("[调试] 已保存搜索页面截图: search_page_debug.png")
                return False

            # ── 处理新窗口问题 ────────────────────────────
            # 如果链接有 target="_blank" 会弹出新窗口，我们强制在当前窗口打开
            print("[调试] 检测链接是否会在新窗口打开...")
            try:
                await page.evaluate(
                    f'''
                    () => {{
                        const links = document.querySelectorAll("{used_selector}");
                        links.forEach(link => {{
                            link.target = "_self";
                            link.setAttribute("target", "_self");
                        }});
                    }}
                    '''
                )
                print("[调试] 已强制链接在当前窗口打开")
            except Exception as e:
                print(f"[调试] JS 执行失败（非致命）: {e}")

            # ── 点击 ─────────────────────────────────────
            old_url = page.url
            print(f"[调试] 点击前 URL: {old_url}")
            print(f"[调试] 正在点击链接: {used_selector}")
            await link_element.click(timeout=5000)

            # ── 等待页面跳转 ──────────────────────────────
            print("[调试] 等待页面跳转...")
            try:
                await page.wait_for_url(
                    lambda url: url != old_url and "/company/" in url,
                    timeout=8000
                )
                print(f"[调试] URL 已变化: {old_url} -> {page.url}")
            except:
                print("[调试] URL 未变化，检查是否弹出新窗口...")
                try:
                    contexts = page.context.pages
                    if len(contexts) > 1:
                        print(f"[调试] 检测到 {len(contexts)} 个标签页，切换到新标签页")
                        new_page = contexts[-1]
                        await page.close()
                        print(f"[调试] 新页面 URL: {new_page.url}")
                        return True
                except:
                    print("[调试] 没有检测到新窗口")

            # 等详情页加载完
            await asyncio.sleep(2)
            print("[调试] 等待详情页网络空闲...")
            try:
                await page.wait_for_load_state('networkidle', timeout=10000)
                print("[调试] 详情页加载完成")
            except:
                print("[调试] 网络未完全空闲，继续执行...")

            # ── 验证是否真的进了详情页 ─────────────────────
            current_url = page.url
            print(f"[调试] 当前页面 URL: {current_url}")

            if '/company/' in current_url or '/firm/' in current_url or '/ent/' in current_url:
                print("[OK] 成功进入公司详情页")
                return True
            else:
                print("[!] 警告: URL 不像详情页，但继续尝试提取数据")
                await page.screenshot(path="after_click_debug.png")
                print("[调试] 已保存点击后截图: after_click_debug.png")
                return True  # 继续尝试，不放弃

        except Exception as e:
            print(f"[X] 点击结果失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def click_first_result_with_page_switch(self, page: Page) -> Optional[Page]:
        """
        用 JS 直接找到第一个公司链接并导航过去（更稳健）

        比 click_first_result 更可靠，因为它：
        1. 用 JS 在 DOM 里直接找 /company/ 链接
        2. 找到了直接 page.goto 导航，不用模拟点击
        3. 避免了新窗口 / 弹窗的麻烦

        Args:
            page: 搜索结果页面的 Page 对象

        Returns:
            详情页的 Page 对象（和传入的可能是同一个）
        """
        try:
            await asyncio.sleep(2)

            # 用 JavaScript 在页面里找到第一个公司详情页的链接
            detail_url = await page.evaluate('''() => {
                const links = document.querySelectorAll('a[href*="/company/"]');
                for (let a of links) {
                    if (a.href && a.href.includes('/company/') && a.textContent.trim()) {
                        return a.href;
                    }
                }
                return null;
            }''')

            # 没找到 -> 截图保存
            if not detail_url:
                print("[!] 未找到搜索结果中的公司链接")
                await page.screenshot(path="search_page_debug.png")
                print("[调试] 已保存搜索页面截图: search_page_debug.png")
                return None

            print(f"[调试] 找到详情页 URL: {detail_url}")

            # 直接导航到详情页（相当于在浏览器地址栏输入 URL 回车）
            await page.goto(detail_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(2)

            try:
                await page.wait_for_load_state('networkidle', timeout=10000)
            except:
                pass

            print(f"[OK] 成功进入详情页: {page.url}")
            return page

        except Exception as e:
            print(f"[X] 进入详情页失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def extract_basic_info(self, page: Page) -> Dict:
        """
        提取公司基本信息（公司名、法人、注册资本、成立日期等9个字段）

        每个字段都有多个备选 CSS 选择器，当网站改版时，
        只要有一个还能用就能继续工作。

        Args:
            page: 公司详情页的 Page 对象

        Returns:
            包含基本信息的字典，如 {company_name: "腾讯科技", legal_person: "马化腾", ...}
        """
        info = {}
        await asyncio.sleep(1)

        # 定义要提取的字段和对应的备选选择器列表
        # 每个选择器按优先级排列，排前面的优先尝试
        fields = {
            'company_name': [          # 公司名称
                'h1',                   # 最直接：h1 标签
                '.company-name h1',
                'h1.company-title',
                '.detail-title h1',
                '.ent-name',
                '[class*="company-name"]',
                '[class*="ent-name"]',
                'title'                 # 最后备选：页面标题
            ],
            'legal_person': [          # 法定代表人
                '[data-key="legalPerson"]',
                '.legal-person',
                '.faren',
                'td:has-text("法定代表人") + td',
                'td:has-text("法人") + td',
                'div:has-text("法定代表人") + div',
                '[class*="legal-person"]',
                '[class*="faren"]'
            ],
            'registered_capital': [    # 注册资本
                '[data-key="capital"]',
                '.registered-capital',
                '.zhuceziben',
                'td:has-text("注册资本") + td',
                'td:has-text("资本") + td',
                'div:has-text("注册资本") + div',
                '[class*="capital"]'
            ],
            'establish_date': [        # 成立日期
                '[data-key="establishDate"]',
                '.establish-date',
                '.chengliriqi',
                'td:has-text("成立日期") + td',
                'td:has-text("成立时间") + td',
                'div:has-text("成立日期") + div',
                '[class*="establish"]'
            ],
            'status': [                # 经营状态（存续/注销/吊销等）
                '.company-status',
                '.status',
                '.jingyingzhuangtai',
                'td:has-text("经营状态") + td',
                'td:has-text("状态") + td',
                '[class*="status"]',
                '[class*="state"]'
            ],
            'organization_code': [     # 统一社会信用代码
                '.organization-code',
                '.tyshxydm',
                'td:has-text("统一社会信用代码") + td',
                'td:has-text("信用代码") + td',
                'td:has-text("税号") + td',
                '[class*="code"]'
            ],
            'business_scope': [        # 经营范围
                '.business-scope',
                '.jingyingfanwei',
                'td:has-text("经营范围") + td',
                'div:has-text("经营范围") + div',
                '[class*="scope"]'
            ],
            'industry': [              # 所属行业
                '.industry',
                '.hangye',
                'td:has-text("所属行业") + td',
                'td:has-text("行业") + td',
                '[class*="industry"]'
            ],
            'taxpayer_type': [         # 纳税人资质
                '.taxpayer-type',
                '.nsrhzz',
                'td:has-text("纳税人资质") + td',
                'td:has-text("纳税人") + td',
                '[class*="taxpayer"]'
            ]
        }

        # 遍历每个字段，尝试它的备选选择器
        for field_name, selectors in fields.items():
            value = "N/A"
            for idx, selector in enumerate(selectors):
                try:
                    element = await page.query_selector(selector)
                    if element:
                        value = await element.text_content()
                        if value:
                            value = value.strip()
                            if value and value != "N/A":
                                print(f"[调试] {field_name}: 使用选择器 {idx + 1}/{len(selectors)}: {selector}")
                                break
                except Exception as e:
                    continue

            info[field_name] = value if value else "N/A"

        print(f"[OK] 基本信息: {info.get('company_name', 'Unknown')}")
        return info

    async def extract_contact_info(self, page: Page) -> Dict:
        """
        提取联系方式（电话、邮箱、地址）

        先检查是否被 VIP 锁挡住，如果被锁了就返回"需要VIP"。

        Args:
            page: 公司详情页的 Page 对象

        Returns:
            联系方式字典
        """
        contacts = {}

        # ── 检查是否被 VIP 锁挡住 ───────────────────────────
        # 启信宝的联系方式可能要 VIP 才能看
        vip_selectors = [
            '.vip-lock',
            '.need-vip',
            '[data-vip-required="true"]',
            'text=开通VIP查看'
        ]

        for selector in vip_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    print("[!] 联系方式需要VIP权限")
                    return {
                        'phone': '需要VIP',
                        'email': '需要VIP',
                        'address': '需要VIP'
                    }
            except:
                continue

        # ── 提取联系方式 ────────────────────────────────────
        contact_fields = {
            'phone': [
                '.phone-number',
                '.contact-phone',
                'td:has-text("电话") + td',
                '[data-key="phone"]'
            ],
            'email': [
                '.email',
                '.contact-email',
                'td:has-text("邮箱") + td',
                '[data-key="email"]'
            ],
            'address': [
                '.address',
                '.company-address',
                'td:has-text("地址") + td',
                '[data-key="address"]'
            ]
        }

        for field_name, selectors in contact_fields.items():
            value = "N/A"
            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        value = await element.text_content()
                        if value:
                            value = value.strip()
                            if value:
                                break
                except:
                    continue

            contacts[field_name] = value if value else "N/A"

        print(f"[OK] 联系方式: {contacts.get('phone', 'N/A')}")
        return contacts

    async def extract_shareholders(self, page: Page) -> List[str]:
        """
        提取股东信息

        先点击"股东信息"标签页，再提取股东列表。

        Args:
            page: 公司详情页的 Page 对象

        Returns:
            股东信息字符串列表
        """
        shareholders = []

        try:
            # ── 点击"股东信息"标签 ──────────────────────────
            tab_selectors = [
                'text=股东信息',
                'a:has-text("股东")',
                '[data-tab="shareholders"]',
                '.tab-shareholders'
            ]

            for selector in tab_selectors:
                try:
                    await page.click(selector, timeout=2000)
                    await random_delay(1, 2)
                    break
                except:
                    continue

            # ── 提取股东列表 ────────────────────────────────
            shareholder_selectors = [
                '.shareholder-item',
                '.shareholder-row',
                'tr.shareholder',
                '.shareholder-list li'
            ]

            for selector in shareholder_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        for element in elements:
                            text = await element.text_content()
                            if text:
                                shareholders.append(text.strip())
                        if shareholders:
                            break
                except:
                    continue

            print(f"[OK] 股东信息: {len(shareholders)} 条")

        except Exception as e:
            print(f"提取股东信息失败: {e}")

        return shareholders

    async def extract_executives(self, page: Page) -> List[str]:
        """
        提取主要人员（高管）信息

        先点击"主要人员"标签页，再提取人员列表。

        Args:
            page: 公司详情页的 Page 对象

        Returns:
            高管信息字符串列表
        """
        executives = []

        try:
            # ── 点击"主要人员"标签 ──────────────────────────
            tab_selectors = [
                'text=主要人员',
                'text=高管信息',
                'a:has-text("人员")',
                '[data-tab="executives"]',
                '.tab-executives'
            ]

            for selector in tab_selectors:
                try:
                    await page.click(selector, timeout=2000)
                    await random_delay(1, 2)
                    break
                except:
                    continue

            # ── 提取高管列表 ────────────────────────────────
            executive_selectors = [
                '.executive-item',
                '.executive-row',
                'tr.executive',
                '.executive-list li'
            ]

            for selector in executive_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        for element in elements:
                            text = await element.text_content()
                            if text:
                                executives.append(text.strip())
                        if executives:
                            break
                except:
                    continue

            print(f"[OK] 高管信息: {len(executives)} 条")

        except Exception as e:
            print(f"提取高管信息失败: {e}")

        return executives

    def _parse_cookies_to_dict(self) -> Dict[str, str]:
        """把 Playwright 格式的 cookie 列表转成 {name: value} 字典"""
        return {c["name"]: c["value"] for c in self.cookie}

    @staticmethod
    def _cookies_from_config() -> Dict[str, str]:
        """
        直接从配置文件加载 cookie，转成字典格式

        用于 advanced_search 等不走浏览器的场景（直接调 API）
        """
        cfg = load_config()
        raw = cfg.get("cookie", "")
        result = {}
        for part in raw.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                result[k.strip()] = v.strip()
        return result

    @staticmethod
    def check_cookie_valid() -> bool:
        """
        验证当前 Cookie 是否有效

        调启信宝的 getEquityConfig API，如果能返回 vipCount > 0 就说明 VIP 登录有效。
        这个 API 需要加自定义签名头才能调。
        """
        cookies = QixinbaoCrawler._cookies_from_config()
        body = "{}"
        # 计算启信宝特有的 API 签名
        header_name, header_value = compute_qixin_signature(
            "/v4/internal/user/getEquityConfig", body, "/api-proxy/app"
        )
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
            ),
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.qixin.com",
            "Referer": "https://www.qixin.com/",
            header_name: header_value,
        }
        try:
            resp = requests.post(
                "https://www.qixin.com/api-proxy/app/v4/internal/user/getEquityConfig",
                headers=headers, cookies=cookies, data=body, timeout=10,
            )
            return resp.json().get("vipCount", 0) > 0
        except Exception:
            return False

    def advanced_search(
        self,
        keyword: str = "",
        status: Optional[List[int]] = None,
        province: Optional[List[str]] = None,
        industry: Optional[List[str]] = None,
        reg_capi: Optional[List[str]] = None,
        paid_capi: Optional[List[str]] = None,
        establish: Optional[List[str]] = None,
        company_type: Optional[List[str]] = None,
        org_type: Optional[List[str]] = None,
        employee: Optional[List[str]] = None,
        insured: Optional[List[str]] = None,
        listing: Optional[List[str]] = None,
        scale: Optional[List[str]] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Dict:
        """
        高级搜索——直接调启信宝 API，不需要打开浏览器

        比浏览器爬取快得多（0.1-0.5 秒出结果），适合批量筛选公司。

        参数对照:
          status:     经营状态 [1=存续, 2=注销, 3=吊销, 4=撤销, 5=迁出, 6=设立中, 7=清算中, 8=停业]
          reg_capi:   注册资本 ["0-100", "100-200", "200-500", "500-1000", "1000-"]
          paid_capi:  实缴资本 (同上范围 + "has"/"no")
          establish:  成立年限 ["1y", "1-5y", "5-10y", "10-15y", "15y+"]
          company_type: 公司类型 ["state-owned", "collective", "cooperative", ...]
          org_type:   组织类型 ["new三板", "listed", "social", "law-firm", ...]
          employee:   员工人数 ["<50", "50-99", "100-499", "500+"]
          insured:    参保人数 (同上)
          listing:    上市状态 ["a-share", "us-stock", "hk-stock", "star-market", "new三板"]
          scale:      规上企业 ["construction", "service", "industrial", ...]
          province:   省份地区代码列表
          industry:   行业分类代码列表
          page:       页码（从1开始）
          page_size:  每页条数（1-100）

        返回:
          包含 items（公司列表）、totalNum（总数）、hasNextPage（是否有下一页）等字段的字典
        """
        cookies = self._cookies_from_config()

        # ── 按参数构建请求体 ──────────────────────────────
        body = {"page": page, "size": page_size, "key": keyword}
        if status:
            body["status"] = status
        if province:
            body["areas"] = province       # 网页用的是 areas 不是 province
        if industry:
            body["industry"] = industry
        if reg_capi:
            body["regCapi"] = reg_capi
        if paid_capi:
            body["paidCapi"] = paid_capi
        if establish:
            body["establish"] = establish
        if company_type:
            body["companyType"] = company_type
        if org_type:
            body["orgType"] = org_type
        if employee:
            body["employee"] = employee
        if insured:
            body["insured"] = insured
        if listing:
            body["listingStatus"] = listing
        if scale:
            body["scale"] = scale

        # ── 计算签名，调 API ─────────────────────────────
        json_body = qixin_json(body)
        header_name, header_value = compute_qixin_signature(
            "/search/advanced", json_body,
        )

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
            ),
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.qixin.com",
            "Referer": "https://www.qixin.com/search/advance",
            header_name: header_value,
        }

        # ── 请求限速（防止触发风控） ──────────────────────
        elapsed = time.time() - QixinbaoCrawler._last_api_time
        if elapsed < QixinbaoCrawler._current_delay:
            time.sleep(QixinbaoCrawler._current_delay - elapsed)

        # 发请求（不抛异常，检查状态码自行处理）
        resp = requests.post(
            "https://www.qixin.com/api-proxy/search/advanced",
            headers=headers,
            cookies=cookies,
            data=json_body,
            timeout=15,
        )

        # ── 更新计时 & 异常检测 ──────────────────────────
        QixinbaoCrawler._last_api_time = time.time()

        # 403 说明请求被 WAF 拦截，不是频率问题
        if resp.status_code == 403:
            return {"items": [], "isLimit": True, "_forbidden": True}

        # 其他非 200 也统一处理
        if resp.status_code != 200:
            return {"items": [], "isLimit": True}

        data = resp.json()

        # 如果被限速了，自动加长间隔
        if data.get("isLimit"):
            old = QixinbaoCrawler._current_delay
            QixinbaoCrawler._current_delay = min(
                QixinbaoCrawler._current_delay * 2, QixinbaoCrawler._max_delay
            )
            print(f"[限速] 触发限速，间隔从 {old:.1f}s 升至 {QixinbaoCrawler._current_delay:.1f}s")
        else:
            # 平稳运行时逐渐恢复最短间隔
            QixinbaoCrawler._current_delay = max(
                QixinbaoCrawler._current_delay * 0.95, QixinbaoCrawler._min_delay
            )

        return data

    async def crawl_single_company(self, company_name: str) -> Optional[Dict]:
        """
        爬取单个公司的完整信息——这是核心流程

        完整流程：
        1. 创建浏览器页面
        2. 搜索公司
        3. 点击第一个结果进入详情页
        4. 模仿人类操作（随机鼠标移动、滚动）
        5. 提取基本资料、联系方式、股东、高管
        6. 合并数据返回

        Args:
            company_name: 公司名称

        Returns:
            包含所有信息的字典，失败返回 None
        """
        page = None

        try:
            # 第1步：创建浏览器页面
            page = await self.browser_manager.create_page(cookies=self.cookie)

            # 第2步：搜索公司
            if not await self.search_company(page, company_name):
                return None

            # 第3步：点击第一个结果，进入详情页
            detail_page = await self.click_first_result_with_page_switch(page)

            if not detail_page:
                return None

            # 第4步：模拟人类操作（随机移动鼠标、滚动页面）
            await self.browser_manager.human_like_actions(detail_page)

            # 第5步：提取各类信息
            basic_info = await self.extract_basic_info(detail_page)
            await random_delay(1, 2)

            contact_info = await self.extract_contact_info(detail_page)
            await random_delay(1, 2)

            shareholders = await self.extract_shareholders(detail_page)
            await random_delay(1, 2)

            executives = await self.extract_executives(detail_page)

            # 第6步：合并数据为一个大字典
            company_data = {
                **basic_info,                     # 基本资料（9个字段）
                **contact_info,                   # 联系方式（3个字段）
                'shareholders': '; '.join(shareholders) if shareholders else 'N/A',
                'executives': '; '.join(executives) if executives else 'N/A',
                'crawl_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 爬取时间
            }

            print(f"[OK] 成功爬取: {company_name}")

            # 如果详情页和搜索页不是同一个页面，关闭详情页
            if detail_page != page:
                await detail_page.close()

            return company_data

        except Exception as e:
            print(f"[X] 爬取失败 {company_name}: {e}")
            return None

        finally:
            # 不管成功还是失败，都要关闭页面释放资源
            if page:
                await self.browser_manager.close_page(page)

    async def crawl_batch(self, company_names: List[str], progress_callback=None):
        """
        批量爬取多家公司

        遍历公司列表，逐个爬取，每爬完一个调用 progress_callback 报告进度。

        Args:
            company_names: 公司名称列表
            progress_callback: 进度回调函数，签名 (current, total, company_name, success)
        """
        results = []
        total = len(company_names)

        for i, company_name in enumerate(company_names, 1):
            print(f"\n[{i}/{total}] 正在处理: {company_name}")

            data = await self.crawl_single_company(company_name)

            if data:
                results.append(data)

            # 报告进度
            if progress_callback:
                await progress_callback(i, total, company_name, data is not None)

            # 公司之间加延迟，避免触发风控
            if i < total:
                await random_delay(3, 6)

        return results

    async def __aenter__(self):
        """异步上下文管理器入口——支持 async with 语法"""
        await self.browser_manager.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出——自动关闭浏览器"""
        await self.browser_manager.stop()
