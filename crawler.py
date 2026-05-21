"""
启信宝爬虫核心模块
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
    load_config,
    parse_cookie_string,
    random_delay,
    human_like_typing,
    extract_text_content,
    compute_qixin_signature,
    qixin_json,
)


class QixinbaoCrawler:
    """启信宝爬虫类"""

    # ── 请求限速 ─────────────────────────────────────
    _last_api_time: float = 0.0
    _current_delay: float = 0.3  # 300ms 起步，异常时自动递增
    _max_delay: float = 5.0
    _min_delay: float = 0.2

    def __init__(self, config_path: str = 'config.json'):
        """
        初始化爬虫

        Args:
            config_path: 配置文件路径
        """
        self.config = load_config(config_path)
        self.browser_manager = BrowserManager(self.config)
        self.cookie = parse_cookie_string(
            self.config.get('cookie', ''),
            domain='.qixin.com'
        )
        self.delays = self.config.get('delays', {'min': 1.0, 'max': 3.0})
        self.base_url = "https://www.qixin.com"

    async def search_company(self, page: Page, company_name: str) -> bool:
        """
        搜索公司（直接导航到搜索URL）

        Args:
            page: 页面对象
            company_name: 公司名称

        Returns:
            是否成功搜索到结果
        """
        try:
            print(f"正在搜索: {company_name}")

            # 先访问首页确保 Cookie 和登录态生效
            await page.goto(f"{self.base_url}/", wait_until='domcontentloaded', timeout=30000)
            await random_delay(1, 2)

            # 直接跳转到搜索页面（绕开搜索框交互）
            search_url = f"{self.base_url}/search?key={company_name}"
            print(f"[调试] 直接导航到搜索URL")
            await page.goto(search_url, wait_until='domcontentloaded', timeout=30000)

            # 等待搜索结果渲染
            await asyncio.sleep(3)

            try:
                await page.wait_for_load_state('networkidle', timeout=10000)
            except:
                pass

            await asyncio.sleep(2)  # 额外等待动态内容
            print(f"[调试] 搜索页 URL: {page.url}")
            return True

        except Exception as e:
            print(f"搜索失败: {e}")
            return False

    async def click_first_result(self, page: Page) -> bool:
        """
        点击第一个搜索结果

        Args:
            page: 页面对象

        Returns:
            是否成功点击
        """
        try:
            print("[调试] 等待搜索结果列表渲染...")
            # 等待搜索结果列表完全渲染（关键改进）
            await asyncio.sleep(3)  # 初始等待 3 秒

            # 等待包含"查询结果"或类似文字的容器出现
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

            # 尝试多个可能的结果选择器（按优先级排序）
            result_selectors = [
                'a.company-name',                    # 方案 A: 最直接
                '.search-result-list .item:first-child a',  # 方案 B: 列表容器
                'a[href*="/company/"]',              # 方案 C: 属性选择器
                '.company-item a',                   # 备用 1
                '.search-result-item a',             # 备用 2
                '.company-list-item:first-child a',  # 备用 3
                '.result-item:first-child a',        # 备用 4
                'div[class*="item"] a:first-child',  # 备用 5: 模糊匹配
                'a[class*="company"]'                # 备用 6: 模糊匹配
            ]

            link_element = None
            used_selector = None

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

            if not link_element:
                print("[!] 未找到搜索结果链接")
                # 截图保存当前页面状态，方便调试
                await page.screenshot(path="search_page_debug.png")
                print("[调试] 已保存搜索页面截图: search_page_debug.png")
                return False

            # 处理新窗口打开问题（关键改进）
            print("[调试] 检测链接是否会在新窗口打开...")

            # 使用 JavaScript 强制在当前窗口打开
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

            # 记录当前 URL，用于后续验证跳转
            old_url = page.url
            print(f"[调试] 点击前 URL: {old_url}")

            # 点击链接
            print(f"[调试] 正在点击链接: {used_selector}")
            await link_element.click(timeout=5000)

            # 等待页面跳转或加载（关键改进）
            print("[调试] 等待页面跳转...")

            # 等待 URL 变化（通常会跳转到详情页）
            try:
                await page.wait_for_url(
                    lambda url: url != old_url and "/company/" in url,
                    timeout=8000
                )
                print(f"[调试] URL 已变化: {old_url} -> {page.url}")
            except:
                print("[调试] URL 未变化，检查是否弹出新窗口...")

                # 检查是否有新窗口打开
                try:
                    contexts = page.context.pages
                    if len(contexts) > 1:
                        print(f"[调试] 检测到 {len(contexts)} 个标签页，切换到新标签页")
                        # 切换到新打开的页面
                        new_page = contexts[-1]
                        # 关闭旧页面，使用新页面
                        await page.close()
                        # 更新 page 引用（这里需要特殊处理，暂时只记录）
                        print(f"[调试] 新页面 URL: {new_page.url}")
                        return True
                except:
                    print("[调试] 没有检测到新窗口")

            # 等待详情页加载完成（关键改进）
            await asyncio.sleep(2)
            print("[调试] 等待详情页网络空闲...")
            try:
                await page.wait_for_load_state('networkidle', timeout=10000)
                print("[调试] 详情页加载完成")
            except:
                print("[调试] 网络未完全空闲，继续执行...")

            # 验证是否真的进入了详情页
            current_url = page.url
            print(f"[调试] 当前页面 URL: {current_url}")

            # 检查 URL 是否包含公司详情页的特征
            if '/company/' in current_url or '/firm/' in current_url or '/ent/' in current_url:
                print("[OK] 成功进入公司详情页")
                return True
            else:
                print("[!] 警告: URL 不像详情页，但继续尝试提取数据")

                # 截图保存当前状态
                await page.screenshot(path="after_click_debug.png")
                print("[调试] 已保存点击后截图: after_click_debug.png")

                return True  # 继续尝试提取

        except Exception as e:
            print(f"[X] 点击结果失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def click_first_result_with_page_switch(self, page: Page) -> Optional[Page]:
        """
        用 JS 查找搜索结果中第一个公司链接并直接导航

        Args:
            page: 搜索结果页面对象

        Returns:
            详情页的 Page 对象
        """
        try:
            await asyncio.sleep(2)

            # 用 JS 查找第一个有效公司详情页链接
            detail_url = await page.evaluate('''() => {
                const links = document.querySelectorAll('a[href*="/company/"]');
                for (let a of links) {
                    if (a.href && a.href.includes('/company/') && a.textContent.trim()) {
                        return a.href;
                    }
                }
                return null;
            }''')

            if not detail_url:
                print("[!] 未找到搜索结果中的公司链接")
                await page.screenshot(path="search_page_debug.png")
                print("[调试] 已保存搜索页面截图: search_page_debug.png")
                return None

            print(f"[调试] 找到详情页 URL: {detail_url}")

            # 直接导航到详情页
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
        提取公司基本信息

        Args:
            page: 页面对象

        Returns:
            基本信息字典
        """
        info = {}

        # 先等待页面加载
        await asyncio.sleep(1)

        # 定义要提取的字段和对应的选择器（增加了更多备选选择器）
        fields = {
            'company_name': [
                'h1',                                # 最直接
                '.company-name h1',
                'h1.company-title',
                '.detail-title h1',
                '.ent-name',
                '[class*="company-name"]',
                '[class*="ent-name"]',
                'title'                              # 最后备选：页面标题
            ],
            'legal_person': [
                '[data-key="legalPerson"]',
                '.legal-person',
                '.faren',
                'td:has-text("法定代表人") + td',
                'td:has-text("法人") + td',
                'div:has-text("法定代表人") + div',
                '[class*="legal-person"]',
                '[class*="faren"]'
            ],
            'registered_capital': [
                '[data-key="capital"]',
                '.registered-capital',
                '.zhuceziben',
                'td:has-text("注册资本") + td',
                'td:has-text("资本") + td',
                'div:has-text("注册资本") + div',
                '[class*="capital"]'
            ],
            'establish_date': [
                '[data-key="establishDate"]',
                '.establish-date',
                '.chengliriqi',
                'td:has-text("成立日期") + td',
                'td:has-text("成立时间") + td',
                'div:has-text("成立日期") + div',
                '[class*="establish"]'
            ],
            'status': [
                '.company-status',
                '.status',
                '.jingyingzhuangtai',
                'td:has-text("经营状态") + td',
                'td:has-text("状态") + td',
                '[class*="status"]',
                '[class*="state"]'
            ],
            'organization_code': [
                '.organization-code',
                '.tyshxydm',
                'td:has-text("统一社会信用代码") + td',
                'td:has-text("信用代码") + td',
                'td:has-text("税号") + td',
                '[class*="code"]'
            ],
            'business_scope': [
                '.business-scope',
                '.jingyingfanwei',
                'td:has-text("经营范围") + td',
                'div:has-text("经营范围") + div',
                '[class*="scope"]'
            ],
            'industry': [
                '.industry',
                '.hangye',
                'td:has-text("所属行业") + td',
                'td:has-text("行业") + td',
                '[class*="industry"]'
            ],
            'taxpayer_type': [
                '.taxpayer-type',
                '.nsrhzz',
                'td:has-text("纳税人资质") + td',
                'td:has-text("纳税人") + td',
                '[class*="taxpayer"]'
            ]
        }

        # 尝试每个字段的多个选择器
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
        提取联系方式

        Args:
            page: 页面对象

        Returns:
            联系方式字典
        """
        contacts = {}

        # 检查是否需要VIP权限才能查看
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

        # 提取联系方式
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

        Args:
            page: 页面对象

        Returns:
            股东信息列表
        """
        shareholders = []

        try:
            # 点击股东信息标签
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

            # 提取股东列表
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
        提取主要人员信息

        Args:
            page: 页面对象

        Returns:
            高管信息列表
        """
        executives = []

        try:
            # 点击主要人员标签
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

            # 提取高管列表
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
        """将 Playwright 格式的 cookie 转为 {name: value} 字典."""
        return {c["name"]: c["value"] for c in self.cookie}

    @staticmethod
    def _cookies_from_config() -> Dict[str, str]:
        """直接从配置加载 cookie 字典."""
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
        """通过 getEquityConfig 验证当前 cookie 是否有效."""
        cookies = QixinbaoCrawler._cookies_from_config()
        body = "{}"
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
        高级搜索（直接调用 API，无需浏览器）。

        参数含义对照:
          status:     经营状态 1=存续 2=注销 3=吊销 4=撤销 5=迁出 6=设立中 7=清算中 8=停业
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
        """
        cookies = self._cookies_from_config()

        # 构建请求体
        body = {"page": page, "size": page_size}
        if keyword:
            body["key"] = keyword
        if status:
            body["status"] = status
        if province:
            body["province"] = province
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

        # ── 请求限速 ─────────────────────────────────────
        elapsed = time.time() - QixinbaoCrawler._last_api_time
        if elapsed < QixinbaoCrawler._current_delay:
            time.sleep(QixinbaoCrawler._current_delay - elapsed)

        resp = requests.post(
            "https://www.qixin.com/api-proxy/search/advanced",
            headers=headers,
            cookies=cookies,
            data=json_body,
            timeout=15,
        )
        resp.raise_for_status()

        # ── 更新计时 & 异常检测 ──────────────────────────
        QixinbaoCrawler._last_api_time = time.time()
        data = resp.json()

        # 被限速时自动降速
        if data.get("isLimit"):
            old = QixinbaoCrawler._current_delay
            QixinbaoCrawler._current_delay = min(
                QixinbaoCrawler._current_delay * 2, QixinbaoCrawler._max_delay
            )
            print(f"[限速] 触发限速，间隔从 {old:.1f}s 升至 {QixinbaoCrawler._current_delay:.1f}s")
        else:
            # 平稳运行时逐渐恢复到最小值
            QixinbaoCrawler._current_delay = max(
                QixinbaoCrawler._current_delay * 0.95, QixinbaoCrawler._min_delay
            )

        return data

    async def crawl_single_company(self, company_name: str) -> Optional[Dict]:
        """
        爬取单个公司的完整信息

        Args:
            company_name: 公司名称

        Returns:
            公司数据字典
        """
        page = None

        try:
            # 创建页面
            page = await self.browser_manager.create_page(cookies=self.cookie)

            # 搜索公司
            if not await self.search_company(page, company_name):
                return None

            # 点击第一个结果（可能会打开新窗口）
            # 注意：click_first_result 现在会返回一个可能的新页面
            detail_page = await self.click_first_result_with_page_switch(page)

            if not detail_page:
                return None

            # 执行类人操作
            await self.browser_manager.human_like_actions(detail_page)

            # 提取各类信息（使用详情页）
            basic_info = await self.extract_basic_info(detail_page)
            await random_delay(1, 2)

            contact_info = await self.extract_contact_info(detail_page)
            await random_delay(1, 2)

            shareholders = await self.extract_shareholders(detail_page)
            await random_delay(1, 2)

            executives = await self.extract_executives(detail_page)

            # 合并数据
            company_data = {
                **basic_info,
                **contact_info,
                'shareholders': '; '.join(shareholders) if shareholders else 'N/A',
                'executives': '; '.join(executives) if executives else 'N/A',
                'crawl_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            print(f"[OK] 成功爬取: {company_name}")

            # 关闭详情页（如果不同于搜索页）
            if detail_page != page:
                await detail_page.close()

            return company_data

        except Exception as e:
            print(f"[X] 爬取失败 {company_name}: {e}")
            return None

        finally:
            if page:
                await self.browser_manager.close_page(page)

    async def crawl_batch(self, company_names: List[str], progress_callback=None):
        """
        批量爬取公司信息

        Args:
            company_names: 公司名称列表
            progress_callback: 进度回调函数
        """
        results = []
        total = len(company_names)

        for i, company_name in enumerate(company_names, 1):
            print(f"\n[{i}/{total}] 正在处理: {company_name}")

            data = await self.crawl_single_company(company_name)

            if data:
                results.append(data)

            # 调用进度回调
            if progress_callback:
                await progress_callback(i, total, company_name, data is not None)

            # 增加延迟，避免频繁请求
            if i < total:
                await random_delay(3, 6)

        return results

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.browser_manager.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.browser_manager.stop()
