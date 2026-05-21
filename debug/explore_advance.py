"""
Click a search-page filter option and check if results update
"""
import asyncio, json, sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from utils import load_config, parse_cookie_string
from playwright.async_api import async_playwright


async def explore():
    config = load_config()
    cookies = parse_cookie_string(config.get("cookie", ""), domain=".qixin.com")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        await context.add_cookies(cookies)
        page = await context.new_page()

        # Track ALL navigation and api events
        events = []

        async def on_request(req):
            if "api-proxy" in req.url:
                events.append(("API_REQ", req.method, req.url))

        async def on_response(resp):
            if "api-proxy" in resp.url:
                try:
                    d = await resp.json()
                    events.append(("API_RES", resp.url, d))
                    print(f"\n[API] {resp.url.split('/')[-1]}: {json.dumps(d, ensure_ascii=False)[:300]}")
                except:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        # Navigate to search page
        print("[1] Search page...", flush=True)
        await page.goto("https://www.qixin.com/search?key=腾讯",
                        wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(4)

        # Clear events from initial load
        events.clear()

        # Get initial count
        text = await page.evaluate("() => document.body.innerText")
        counts = re.findall(r'找到\s*([\d,.]+\s*[万]?)\s*条', text)
        print(f"Initial results: {counts[0] if counts else 'unknown'}", flush=True)

        # Get first 3 company names before filter
        companies_before = await page.evaluate('''() => {
            const items = document.querySelectorAll('[class*="search-result-item"], [class*="company-item"], .result-item');
            return Array.from(items).slice(0, 3).map(el => el.textContent.trim().substring(0, 100));
        }''')
        print(f"Companies before: {companies_before}", flush=True)

        # Look for text-option elements (the filter tags)
        print("\n[2] Looking for filter options...", flush=True)
        filter_opts = await page.query_selector_all('span.text-option')

        # Find "上海" or "广东" filter option
        target = None
        for opt in filter_opts:
            text = await opt.text_content()
            if text and "广东" in text:
                target = opt
                print(f"Found filter: 广东", flush=True)
                break

        if target:
            old_url = page.url
            print(f"Clicking 广东... (old URL: {old_url})", flush=True)
            await target.click(no_wait_after=True, timeout=5000)
            await asyncio.sleep(6)
            print(f"URL after click: {page.url}", flush=True)
            print(f"URL changed: {page.url != old_url}", flush=True)

            # Check URL and results after click
            print(f"URL after filter: {page.url}", flush=True)
            text = await page.evaluate("() => document.body.innerText")
            counts = re.findall(r'找到\s*([\d,.]+\s*[万]?)\s*条', text)
            print(f"Results after: {counts[0] if counts else 'unknown'}", flush=True)

            companies_after = await page.evaluate('''() => {
                const items = document.querySelectorAll('[class*="search-result-item"], .result-item');
                return Array.from(items).slice(0, 3).map(el => el.textContent.trim().substring(0, 100));
            }''')
            print(f"Companies after: {companies_after}", flush=True)
        else:
            print("No '广东' filter found", flush=True)

        print(f"\nEvents captured: {len(events)}", flush=True)
        for ev in events[:10]:
            print(f"  {ev[0]}: {ev[1]} {ev[2][:80]}", flush=True)

        await asyncio.sleep(3)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(explore())
