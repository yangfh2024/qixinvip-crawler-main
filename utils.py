"""
工具函数模块
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

    支持两种 Cookie 配置方式：
    1. config.json 中的 "cookie" 字段
    2. cookie.txt 文件（优先级更高）
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 如果存在 cookie.txt，优先使用
        if os.path.exists('cookie.txt'):
            print("[提示] 发现 cookie.txt 文件，优先使用")
            with open('cookie.txt', 'r', encoding='utf-8') as cf:
                # 读取所有行，过滤掉注释和空行
                lines = cf.readlines()
                cookie_lines = []
                for line in lines:
                    line = line.strip()
                    # 跳过注释行和空行
                    if line and not line.startswith('#'):
                        cookie_lines.append(line)

                # 将所有行合并为一个 Cookie 字符串
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
    解析Cookie字符串为Playwright格式

    Args:
        cookie_string: 浏览器复制的Cookie字符串
        domain: Cookie的域名

    Returns:
        Cookie字典列表
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
    """随机延迟，模拟人类操作"""
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)


async def human_like_typing(page, selector: str, text: str, delay_range: tuple = (0.05, 0.15)):
    """
    模拟人类打字输入

    Args:
        page: Playwright页面对象
        selector: 输入框选择器
        text: 要输入的文本
        delay_range: 每个字符的延迟范围(秒)
    """
    await page.click(selector)
    for char in text:
        await page.type(selector, char, delay=random.uniform(*delay_range))


async def random_mouse_move(page):
    """随机鼠标移动，模拟真实用户"""
    try:
        viewport_size = page.viewport_size
        if viewport_size:
            x = random.randint(0, viewport_size['width'])
            y = random.randint(0, viewport_size['height'])
            await page.mouse.move(x, y)
    except:
        pass


async def random_scroll(page, distance_range: tuple = (100, 500)):
    """随机滚动页面"""
    try:
        distance = random.randint(*distance_range)
        await page.evaluate(f'window.scrollBy(0, {distance})')
        await asyncio.sleep(random.uniform(0.5, 1.5))
    except:
        pass


def generate_timestamp() -> str:
    """生成时间戳字符串"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除非法字符"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename


def extract_text_content(element, default: str = "N/A") -> str:
    """
    安全地提取元素文本内容

    Args:
        element: Playwright元素对象
        default: 提取失败时的默认值

    Returns:
        提取的文本内容
    """
    try:
        if element:
            text = element.text_content()
            return text.strip() if text else default
        return default
    except:
        return default


# ── 启信宝 API 签名算法 ────────────────────────────────────
# 逆向自 Vue.js Axios 拦截器的 codeBook() 函数

_QIXIN_CODES = {
    0: "a", 1: "z", 2: "p", 3: "W", 4: "V", 5: "3", 6: "K", 7: "W",
    8: "j", 9: "p", 10: "S", 11: "X", 12: "S", 13: "d", 14: "a",
    15: "u", 16: "V", 17: "l", 18: "Y", 19: "T",
}
_QIXIN_PROXY_BASE = "/api-proxy"


def _qixin_get_key(url_path: str) -> str:
    """生成 HMAC 密钥: 将 URL 加倍后逐字符映射到 codes 表."""
    doubled = url_path + url_path
    return "".join(_QIXIN_CODES[ord(ch) % 20] for ch in doubled)


def _qixin_build_q(base_url: str, url_path: str) -> str:
    """
    构建待签名字符串，匹配 Vue 端逻辑:
      q = BROWSER_API_BASE_URL
          + _.get(_.split(N, BROWSER_API_BASE_URL), "[1]")
          + B
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
    计算启信宝 API 请求的自定义认证头。

    Args:
        url_path: API 路径, 如 "/search/advanced"
        json_body: JSON 请求体（需与 JS JSON.stringify 行为一致：紧凑、不转义非 ASCII）
        base_url: API 基础路径, 默认 "/api-proxy"

    Returns:
        (header_name, header_value), 如 ("04d73", "8373a7c9...")
    """
    if base_url is None:
        base_url = _QIXIN_PROXY_BASE

    q = _qixin_build_q(base_url, url_path)
    key = _qixin_get_key(q)

    name = hmac.new(key.encode(), q.encode(), hashlib.sha256).hexdigest()[:5]
    value = hmac.new(key.encode(), (q + json_body).encode(), hashlib.sha256).hexdigest()
    return name, value


def qixin_json(data) -> str:
    """JSON 序列化，行为与 JS JSON.stringify 一致（紧凑、不转义非 ASCII）. """
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
