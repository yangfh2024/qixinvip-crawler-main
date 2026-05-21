"""
Test direct API call to qixin.com using the replicated signature algorithm
"""
import hmac, hashlib, json, requests, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BROWSER_API_BASE_URL = "/api-proxy"

CODES = {
    0: "a", 1: "z", 2: "p", 3: "W", 4: "V", 5: "3", 6: "K", 7: "W",
    8: "j", 9: "p", 10: "S", 11: "X", 12: "S", 13: "d", 14: "a",
    15: "u", 16: "V", 17: "l", 18: "Y", 19: "T",
}


def to_json(data) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def get_key(url_path: str) -> str:
    doubled = url_path + url_path
    return "".join(CODES[ord(ch) % 20] for ch in doubled)


def build_q(base_url: str, url_path: str) -> str:
    parts = base_url.split(BROWSER_API_BASE_URL)
    path_after_proxy = parts[1] if len(parts) > 1 else ""
    return (BROWSER_API_BASE_URL + path_after_proxy + url_path).lower()


def compute_signature(url_path: str, json_body: str = "{}", base_url: str = None) -> tuple:
    if base_url is None:
        base_url = BROWSER_API_BASE_URL
    q = build_q(base_url, url_path)
    j = get_key(q)
    header_name = hmac.new(j.encode(), q.encode(), hashlib.sha256).hexdigest()[:5]
    header_value = hmac.new(j.encode(), (q + json_body).encode(), hashlib.sha256).hexdigest()
    return header_name, header_value


def make_api_call(endpoint: str, data: dict, cookies: dict, base_url: str = None) -> dict:
    """Make a signed API call to qixin.com."""
    if base_url is None:
        full_url = f"https://www.qixin.com/api-proxy{endpoint}"
        base_url_for_sig = BROWSER_API_BASE_URL
    else:
        full_url = f"https://www.qixin.com{base_url}{endpoint}"
        base_url_for_sig = base_url

    json_body = to_json(data) if data else "{}"
    header_name, header_value = compute_signature(endpoint, json_body, base_url_for_sig)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.qixin.com",
        "Referer": "https://www.qixin.com/",
        header_name: header_value,
    }

    resp = requests.post(full_url, headers=headers, cookies=cookies,
                         data=json_body, timeout=10)
    return resp.json()


# Test with cookies extracted from the real Chrome session
cookies_str = "web-canary=never; web-fpid=76e57e3a1642c43fb9d5b20485ac0d58; adv-banner_visible=%5B%5D; pc-web-fpid=ffdb3aaf7bc02b2aebcbd6a1878f8913; acw_tc=781bad7217793275271303135e006f675d2a454d94bf35e24768edc8e67db9; aliyungf_tc=9829ae9f976651286479af0fa9c0ac0ea4f44c045d5f35c5e29eea6b6eee59df; Hm_lvt_52d64b8d3f6d42a2e416d59635df3f71=1779297897,1779298318,1779328587; HMACCOUNT=0B74D9466E992166; pdid=s%3AsfZF6v-nSq_igAUufItEjetorHfkYg1o.aHRnN9MbhJxNmXnvVChc9seSOccR9HX%2FbAOvuNK7Xq8; Hm_lpvt_52d64b8d3f6d42a2e416d59635df3f71=1779328761"
cookies = {}
for part in cookies_str.split(";"):
    if "=" in part:
        k, v = part.strip().split("=", 1)
        cookies[k] = v

print("=" * 60)
print("Testing direct API call with computed signature")
print("=" * 60)

# Test 1: getEquityConfig
print("\n[1] getEquityConfig:")
try:
    result = make_api_call(
        "/v4/internal/user/getEquityConfig",
        None,
        cookies,
        base_url="/api-proxy/app"
    )
    if "vipCount" in result:
        print(f"  ✅ VIP authenticated! vipCount={result.get('vipCount')}, svipCount={result.get('svipCount')}")
    else:
        print(f"  ❌ Auth failed: {json.dumps(result, ensure_ascii=False)[:200]}")
except Exception as e:
    print(f"  ❌ Error: {e}")

# Test 2: search/advanced
print("\n[2] search/advanced (keyword=科技, status=存续):")
try:
    result = make_api_call(
        "/search/advanced",
        {"status": [1], "key": "科技", "page": 1},
        cookies,
    )
    items = result.get("items", [])
    total = result.get("total", "unknown")
    print(f"  ✅ Total results: {total}, returned: {len(items)}")
    for item in items[:3]:
        print(f"     - {item.get('name', 'N/A')} ({item.get('status', 'N/A')})")
except Exception as e:
    print(f"  ❌ Error: {e}")
