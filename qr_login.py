"""
启信宝扫码登录 - 登录后遍历多个页面触发完整Cookie
"""
import asyncio, sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright

AUTH_KEYS = ["pt4_token", "p_skey", "RK", "ETK", "pt_login_sig", "uin"]


async def save_cookies(context, label=""):
    # 获取全部域名下的所有cookie
    cookies = await context.cookies()

    # 按域名分组显示
    domains = set(c["domain"] for c in cookies)
    print(f"  [{label}] 共 {len(cookies)} 个Cookie, 域名: {domains}")

    # 保存到文件
    cookie_str = "; ".join(f'{c["name"]}={c["value"]}' for c in cookies)
    with open("cookie.txt", "w", encoding="utf-8") as f:
        f.write(cookie_str)
    with open("storage_state.json", "w", encoding="utf-8") as f:
        json.dump(await context.storage_state(), f, ensure_ascii=False)

    # 检查认证cookie
    auth = [c for c in cookies if c["name"] in AUTH_KEYS]
    if auth:
        for c in auth:
            print(f"    ✅ {c['name']} = {c['value'][:30]}... domain={c['domain']}")
    else:
        print(f"   ❌ 无认证Cookie")
        for c in cookies:
            print(f"      {c['name']} (domain={c['domain']})")
    return len(auth) > 0


async def main():
    print("=" * 60)
    print("    启信宝扫码登录（遍历触发版）")
    print("=" * 60)
    print()

    async with async_playwright() as p:
        # 尝试使用用户本地Chrome（可能已登录）
        print("[尝试1] 使用本地Chrome浏览器...")

        # 查找Chrome可执行文件路径
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
            print(f"  找到Chrome: {chrome_exe}")
            browser = await p.chromium.launch(
                executable_path=chrome_exe,
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
        else:
            print("  使用默认Playwright Chromium")
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

        # Step 1: Go to homepage - check if already logged in
        print("\n[1/5] 打开首页检查登录状态...")
        await page.goto("https://www.qixin.com/", wait_until="domcontentloaded")
        await asyncio.sleep(3)
        has_auth = await save_cookies(context, "初始")

        if not has_auth:
            # Step 2: Wait for scan
            print("\n[2/5] 请在浏览器中扫码登录（等待中）...")
            logged_in = False
            for i in range(120):
                await asyncio.sleep(2)
                try:
                    text = await page.evaluate("() => document.body.innerText")
                    if "登录" not in text[:500]:
                        print(f"  检测到登录！({i*2}秒)")
                        logged_in = True
                        break
                except:
                    pass
                if i % 15 == 0:
                    print(f"  等待扫码... ({i*2}秒)")

            if not logged_in:
                print("  未检测到登录")
            else:
                print(f"  URL: {page.url}")

        # Step 3: Visit pages to trigger cookies
        print("\n[3/5] 遍历页面触发Cookie...")
        urls = [
            ("个人中心", "https://www.qixin.com/usercenter"),
            ("会员中心", "https://www.qixin.com/member"),
            ("搜索", "https://www.qixin.com/search?key=腾讯"),
            ("设置", "https://www.qixin.com/setting"),
            ("消息", "https://www.qixin.com/msg"),
        ]
        for name, url in urls:
            try:
                print(f"  访问 {name}...", flush=True)
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(3)
                has_auth = await save_cookies(context, name)
                if has_auth:
                    break
            except Exception as e:
                print(f"  跳过: {str(e)[:50]}")
                await save_cookies(context, f"{name}(err)")

        # Step 4: Final report
        print(f"\n[4/4] 最终:")
        has_auth = await save_cookies(context, "最终")

        if has_auth:
            print("\n✅ Cookie就绪！可以开始爬取")
        else:
            print("\n❌ 仍未获取到认证Cookie")
            print("   建议：在Chrome中登录后，")
            print("   F12 → Application → Cookies → 右键复制所有cookie")
            print("   粘贴到 cookie.txt")

        await asyncio.sleep(10)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
