"""Try internal API directly with cookies"""
import asyncio, json
from utils import load_config, parse_cookie_string
import httpx

async def main():
    config = load_config()
    cookie_str = config.get("cookie", "")
    cookies_list = parse_cookie_string(cookie_str, domain=".qixin.com")

    # Convert to cookie dict for httpx
    cookie_dict = {c['name']: c['value'] for c in cookies_list}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.qixin.com",
        "Referer": "https://www.qixin.com/search/advance",
    }

    # Try the count API first (known from summary)
    count_payload = {
        "key": "腾讯",
        "status": [],
        "econType": [],
        "organizationType": [],
        "secuCode": ""
    }

    async with httpx.AsyncClient() as client:
        # Try different API endpoints
        apis = [
            ("POST", "https://www.qixin.com/api-proxy/search/getColligateSearchCount", count_payload),
        ]

        for method, url, payload in apis:
            print(f"\n--- {method} {url.split('/')[-1]} ---")
            try:
                if method == "POST":
                    resp = await client.post(url, json=payload, cookies=cookie_dict, headers=headers, timeout=15)
                else:
                    resp = await client.get(url, cookies=cookie_dict, headers=headers, timeout=15)

                print(f"Status: {resp.status_code}")
                print(f"Body: {resp.text[:1000]}")

                # Try to parse as JSON
                try:
                    data = resp.json()
                    print(f"JSON keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
                    print(f"JSON: {json.dumps(data, ensure_ascii=False)[:500]}")
                except:
                    pass
            except Exception as e:
                print(f"Error: {e}")

asyncio.run(main())
