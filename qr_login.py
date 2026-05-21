"""
启信宝扫码登录 - 扫码后自动检测登录，保存完整Cookie
"""
import asyncio, sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests
from playwright.async_api import async_playwright


def check_cookies_valid(cookie_str: str) -> bool:
    """调 getEquityConfig API 验证 cookie 是否真实有效"""
    try:
        from utils import compute_qixin_signature
        cookies = {}
        for part in cookie_str.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                cookies[k.strip()] = v.strip()

        body = "{}"
        header_name, header_value = compute_qixin_signature(
            "/v4/internal/user/getEquityConfig", body, "/api-proxy/app"
        )
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.qixin.com",
            "Referer": "https://www.qixin.com/",
            header_name: header_value,
        }
        resp = requests.post(
            "https://www.qixin.com/api-proxy/app/v4/internal/user/getEquityConfig",
            headers=headers, cookies=cookies, data=body, timeout=10,
        )
        data = resp.json()
        vip = data.get("vipCount", 0)
        print(f"    API验证: vipCount={vip}", flush=True)
        return vip > 0
    except Exception as e:
        print(f"    API验证失败: {e}", flush=True)
        return False


async def save_cookies(context, label=""):
    cookies = await context.cookies()
    domains = set(c["domain"] for c in cookies)
    print(f"  [{label}] 共 {len(cookies)} 个Cookie, 域名: {domains}", flush=True)

    cookie_str = "; ".join(f'{c["name"]}={c["value"]}' for c in cookies)
    with open("cookie.txt", "w", encoding="utf-8") as f:
        f.write(cookie_str)
    with open("storage_state.json", "w", encoding="utf-8") as f:
        json.dump(await context.storage_state(), f, ensure_ascii=False)

    valid = check_cookies_valid(cookie_str)
    if valid:
        print(f"    ✅ Cookie有效！VIP登录正常", flush=True)
    else:
        print(f"    ❌ Cookie无效（或未登录VIP）", flush=True)
    return valid


async def main():
    print("=" * 60)
    print("    Qixinbao QR Code Login")
    print("=" * 60)
    print()

    async with async_playwright() as p:
        print("[1/4] Opening browser...")

        chrome_paths = [
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
            os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe"),
        ]

        chrome_exe = None
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_exe = path
                break

        if chrome_exe:
            print(f"  Using local Chrome: {chrome_exe}", flush=True)
            browser = await p.chromium.launch(
                executable_path=chrome_exe,
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
        else:
            print("  Using Playwright Chromium", flush=True)
            browser = await p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        page = await context.new_page()

        print("\n[2/4] Opening qixin.com homepage...", flush=True)
        await page.goto("https://www.qixin.com/", wait_until="domcontentloaded")
        await asyncio.sleep(3)

        print("\n[3/4] Waiting for QR code scan and login...", flush=True)
        print("    (Browser window may need you to click the login button first)", flush=True)

        logged_in = False
        for i in range(120):
            await asyncio.sleep(2)
            try:
                text = await page.evaluate("() => document.body.innerText")
                if "登录" not in text[:500]:
                    print(f"\n  Login detected! ({i*2}s)", flush=True)
                    logged_in = True
                    break
            except:
                pass
            if i % 10 == 0:
                print(f"  Waiting... ({i*2}s)", flush=True)

        if not logged_in:
            print("\n  Login not detected after 4 minutes.", flush=True)
            print("  Try again or copy cookies manually from Chrome DevTools.", flush=True)
        else:
            print(f"  URL: {page.url}", flush=True)

        print("\n[4/4] Visiting pages to capture cookies...", flush=True)
        urls = [
            ("UserCenter", "https://www.qixin.com/usercenter"),
            ("Member", "https://www.qixin.com/member"),
            ("Search", "https://www.qixin.com/search?key=%E8%85%BE%E8%AE%AF"),
            ("Settings", "https://www.qixin.com/setting"),
            ("Messages", "https://www.qixin.com/msg"),
        ]
        got_valid = False
        for name, url in urls:
            try:
                print(f"  Visiting {name}...", flush=True)
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(2)
                got_valid = await save_cookies(context, name)
                if got_valid:
                    break
            except Exception as e:
                print(f"  Skip {name}: {str(e)[:50]}", flush=True)

        print(f"\n{'='*60}")
        if got_valid:
            print("  ✅ Login successful! Cookie saved to cookie.txt")
            print("  You can now run start.bat to start the API server.")
        else:
            print("  ❌ Cookie still not valid after login.")
            print("  Manual method: Chrome -> F12 -> Network -> copy cookie -> paste into cookie.txt")
        print(f"{'='*60}")

        await asyncio.sleep(3)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
