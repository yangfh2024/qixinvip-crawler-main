"""
工具函数模块

各种零散但常用的功能都放在这里：
1. 加载配置文件（含 Cookie 读取）
2. 解析 Cookie 字符串
3. 模拟人类操作（随机延迟、打字、鼠标移动、滚动）
4. 文件名处理
5. 启信宝 API 的签名算法（逆向工程反编译得来的）
"""

import os
import json
import random
import asyncio
import hmac
import hashlib
from typing import Dict, List, Optional, Tuple
from datetime import datetime


def load_config(config_path: str = 'config.json') -> Dict:
    """
    加载配置文件

    Cookie 有两个来源，按优先级排列：
    1. cookie.txt 文件（优先级高）—— 用 qr_login.py 扫码登录后会自动生成
    2. config.json 中的 "cookie" 字段（优先级低）

    cookie.txt 支持 # 开头的注释行，方便管理多个 Cookie。
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 如果存在 cookie.txt，优先使用它（扫码登录生成的）
        if os.path.exists('cookie.txt'):
            print("[提示] 发现 cookie.txt 文件，优先使用")
            with open('cookie.txt', 'r', encoding='utf-8') as cf:
                lines = cf.readlines()
                cookie_lines = []
                for line in lines:
                    line = line.strip()
                    # 跳过注释行（#开头）和空行
                    if line and not line.startswith('#'):
                        cookie_lines.append(line)

                # 把多行合并为一个 Cookie 字符串
                cookie_from_file = ' '.join(cookie_lines).strip()

                if cookie_from_file:
                    config['cookie'] = cookie_from_file
                    print("[OK] 已从 cookie.txt 加载 Cookie")

        return config
    except FileNotFoundError:
        print(f"配置文件 {config_path} 未找到")
        raise
    except json.JSONDecodeError as e:
        print(f"配置文件格式错误: {e}")
        raise


def parse_cookie_string(cookie_string: str, domain: str = '.qixin.com') -> List[Dict]:
    """
    解析 Cookie 字符串为 Playwright 能用的格式

    浏览器复制的 Cookie 是 "key1=value1; key2=value2" 这种格式，
    Playwright 需要的是 [{name, value, domain, path}, ...] 这种列表格式。

    Args:
        cookie_string: 从浏览器复制的 Cookie 字符串
        domain: Cookie 所属域名（默认 .qixin.com）

    Returns:
        Playwright 格式的 Cookie 字典列表
    """
    cookies = []
    for item in cookie_string.split(';'):
        item = item.strip()
        if '=' in item:
            name, value = item.split('=', 1)
            cookies.append({
                'name': name.strip(),
                'value': value.strip(),
                'domain': domain,
                'path': '/'
            })
    return cookies


async def random_delay(min_sec: float = 1.0, max_sec: float = 3.0):
    """
    随机等待一段时间——模拟人类操作节奏

    真实用户的操作之间会有间隔，程序执行太快反而会被网站识别为爬虫。

    Args:
        min_sec: 最短等待秒数
        max_sec: 最长等待秒数
    """
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)


async def human_like_typing(page, selector: str, text: str, delay_range: tuple = (0.05, 0.15)):
    """
    模拟人类打字——逐字输入，每个字之间有随机延迟

    和直接把文本粘贴进去不同，逐字输入更接近真实用户的行为。

    Args:
        page: Playwright 页面对象
        selector: 输入框的 CSS 选择器
        text: 要输入的文本
        delay_range: 每个字符之间的延迟范围（秒）
    """
    await page.click(selector)
    for char in text:
        await page.type(selector, char, delay=random.uniform(*delay_range))


async def random_mouse_move(page):
    """
    随机鼠标移动——模拟真实用户的鼠标轨迹

    真实用户的鼠标不是直线瞬移的，而是有抖动和弧度。
    这里把移动分成多段，每段加随机噪声，看起来更像人手操作。
    """
    try:
        viewport_size = page.viewport_size
        if not viewport_size:
            return
        w, h = viewport_size['width'], viewport_size['height']

        # 随机选一个终点
        end_x = random.randint(0, w)
        end_y = random.randint(0, h)

        # 分多步移动，模拟真实鼠标轨迹（不是瞬移）
        steps = random.randint(6, 15)
        for i in range(1, steps + 1):
            t = i / steps
            # 线性插值 + 随机噪声（模仿手抖）
            x = end_x * t + random.randint(-4, 4)
            y = end_y * t + random.randint(-4, 4)
            x = max(0, min(w, x))
            y = max(0, min(h, y))
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.008, 0.025))
    except:
        pass


async def random_scroll(page, distance_range: tuple = (100, 500)):
    """
    随机滚动页面

    Args:
        page: Playwright 页面对象
        distance_range: 滚动距离范围（像素）
    """
    try:
        distance = random.randint(*distance_range)
        await page.evaluate(f'window.scrollBy(0, {distance})')
        await asyncio.sleep(random.uniform(0.5, 1.5))
    except:
        pass


def generate_timestamp() -> str:
    """生成时间戳字符串，用于导出文件名（如 20250101_143025）"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def sanitize_filename(filename: str) -> str:
    """
    清理文件名——移除 Windows 不允许的字符

    Windows 文件名不能包含：< > : " / \ | ? *
    """
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename


def extract_text_content(element, default: str = "N/A") -> str:
    """
    安全地提取元素文本内容

    如果 element 为 None 或提取出错，返回默认值而不是崩溃。

    Args:
        element: Playwright 元素对象
        default: 提取失败返回的默认值

    Returns:
        元素的文本内容
    """
    try:
        if element:
            text = element.text_content()
            return text.strip() if text else default
        return default
    except:
        return default


# ── 启信宝 API 签名算法 ────────────────────────────────────
#
# 启信宝的 API 请求需要带一个自定义签名头（header），
# 这个签名是通过 HMAC-SHA256 算法算出来的。
#
# 算法是逆向工程从 Vue.js 前端代码的 Axios 拦截器里反编译出来的，
# 具体函数名叫 codeBook()。
#
# 代码对照表（0-19 映射到 20 个字符）
_QIXIN_CODES = {
    0: "a", 1: "z", 2: "p", 3: "W", 4: "V", 5: "3", 6: "K", 7: "W",
    8: "j", 9: "p", 10: "S", 11: "X", 12: "S", 13: "d", 14: "a",
    15: "u", 16: "V", 17: "l", 18: "Y", 19: "T",
}
_QIXIN_PROXY_BASE = "/api-proxy"


def _qixin_get_key(url_path: str) -> str:
    """
    生成 HMAC 密钥

    算法：把 URL 路径加倍后，每个字符取 ASCII 码模20，
    然后用映射表转成一个字符，拼起来就是密钥。
    """
    doubled = url_path + url_path
    return "".join(_QIXIN_CODES[ord(ch) % 20] for ch in doubled)


def _qixin_build_q(base_url: str, url_path: str) -> str:
    """
    构建待签名字符串

    匹配前端 Vue.js 的逻辑：
    q = BROWSER_API_BASE_URL + 路径剩余部分 + B（POST 请求体）

    具体逻辑在 Axios 拦截器里，看不懂是正常的，这是逆向出来的。
    """
    parts = base_url.split(_QIXIN_PROXY_BASE)
    rest = parts[1] if len(parts) > 1 else ""
    return (_QIXIN_PROXY_BASE + rest + url_path).lower()


def compute_qixin_signature(
    url_path: str,
    json_body: str = "{}",
    base_url: str = None,
) -> Tuple[str, str]:
    """
    计算启信宝 API 请求的自定义认证头

    每个 API 请求都要带这个签名头，否则会返回 403 拒绝访问。
    算法是 HMAC-SHA256，密钥由 URL 路径经过特殊变换生成。

    Args:
        url_path: API 路径，如 "/search/advanced"
        json_body: JSON 请求体（必须是紧凑格式，和 JS JSON.stringify 一致）
        base_url: API 基础路径，默认 "/api-proxy"

    Returns:
        (header_name, header_value)，如 ("04d73", "8373a7c9...")
    """
    if base_url is None:
        base_url = _QIXIN_PROXY_BASE

    q = _qixin_build_q(base_url, url_path)
    key = _qixin_get_key(q)

    name = hmac.new(key.encode(), q.encode(), hashlib.sha256).hexdigest()[:5]
    value = hmac.new(key.encode(), (q + json_body).encode(), hashlib.sha256).hexdigest()
    return name, value


def qixin_json(data) -> str:
    """
    JSON 序列化——行为要和 JS 的 JSON.stringify 完全一致

    区别在于：
    - Python 默认会在 : 后面加空格
    - JS 的 JSON.stringify 是紧凑的（没空格）
    - Python 默认会转义非 ASCII 字符（如中文变 \\uXXXX）
    - JS 不会

    所以这里用 separators=(",", ":") 紧凑格式，ensure_ascii=False 不转义中文。
    """
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
