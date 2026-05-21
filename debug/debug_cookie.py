"""
Diagnose cookie issue - check what domains cookies are set on
and verify login state
"""
import asyncio, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
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

        # Go to homepage
        await page.goto("https://www.qixin.com/", wait_until="domcontentloaded")
        await asyncio.sleep(3)

        print("=== All Cookies ===")
        cookies = await context.cookies()
        for c in cookies:
            print(f"  {c['name']} = {c['value'][:30]}... domain={c['domain']} path={c['path']} secure={c['secure']} httponly={c.get('httpOnly', False)}")

        print(f"\nTotal cookies: {len(cookies)}")

        # Navigate to a few more pages to trigger cookie setting
        print("\n=== Navigating to login page... ===")
        await page.goto("https://www.qixin.com/login", wait_until="domcontentloaded")
        await asyncio.sleep(3)

        print("\n点击扫码登录标签...")
        # Look for QR login tab/button
        qr_tab = await page.query_selector('text=扫码登录')
        if qr_tab:
            await qr_tab.click()
            print("点击了扫码登录")
        else:
            # Try alternative
            tabs = await page.query_selector_all('.login-tab, .tab, [class*="tab"]')
            for t in tabs:
                text = await t.text_content()
                if "扫码" in text:
                    await t.click()
                    print(f"点击了tab: {text}")
                    break

        print("\n等待扫码登录（60秒）...")
        logged_in = False
        for i in range(30):
            await asyncio.sleep(2)
            try:
                text = await page.evaluate("() => document.body.innerText")
                if "登录" not in text[:500]:
                    logged_in = True
                    print(f"检测到登录! ({i*2}秒)")
                    await asyncio.sleep(3)
                    break
            except:
                pass

        if logged_in:
            print("\n=== Cookies after login ===")
            cookies = await context.cookies()
            for c in cookies:
                print(f"  {c['name']} = {c['value'][:40]}... domain={c['domain']} httponly={c.get('httpOnly', False)}")

            # Try reloading homepage
            print("\n=== Navigate to search page ===")
            await page.goto("https://www.qixin.com/search?key=腾讯", wait_until="domcontentloaded")
            await asyncio.sleep(5)

            print("\n=== Cookies after search nav ===")
            cookies = await context.cookies()
            for c in cookies:
                print(f"  {c['name']} = {c['value'][:40]}... domain={c['domain']}")

            # Try getting cookie by specific API
            print("\n=== Try extracting cookies via JS ===")
            js_cookies = await page.evaluate("() => document.cookie")
            print(f"  document.cookie: {js_cookies[:200]}")

            print(f"\nTotal cookies: {len(cookies)}")
        else:
            print("登录未检测到")

        await asyncio.sleep(5)
        await browser.close()


asyncio.run(main())
