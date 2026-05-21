"""
Test the qixin.com request signature algorithm
Replicates the codeBook() function from the Vue.js app's Axios interceptor
"""
import hmac, hashlib, json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BROWSER_API_BASE_URL = "/api-proxy"

CODES = {
    0: "a", 1: "z", 2: "p", 3: "W", 4: "V", 5: "3", 6: "K", 7: "W",
    8: "j", 9: "p", 10: "S", 11: "X", 12: "S", 13: "d", 14: "a",
    15: "u", 16: "V", 17: "l", 18: "Y", 19: "T",
}


def get_key(url_path: str) -> str:
    """Generate the HMAC key 'j' by doubling the URL and mapping each char through codes table."""
    doubled = url_path + url_path
    result = ""
    for ch in doubled:
        idx = ord(ch) % 20
        result += CODES[idx]
    return result


def build_q(base_url: str, url_path: str) -> str:
    """
    Build the string to sign.
    Matches the JS code:
      q = BROWSER_API_BASE_URL + _.get(_.split(N, BROWSER_API_BASE_URL), "[1]") + B
    where N = baseURL (e.g., "/api-proxy") and B = url (e.g., "/search/advanced")
    """
    parts = base_url.split(BROWSER_API_BASE_URL)
    path_after_proxy = parts[1] if len(parts) > 1 else ""
    q = BROWSER_API_BASE_URL + path_after_proxy + url_path
    return q.lower()


def to_json(data) -> str:
    """JSON serialize matching JS JSON.stringify behavior (keep Chinese chars, no spaces)."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def compute_signature(url_path: str, json_body: str = "{}", base_url: str = None) -> tuple:
    """
    Compute the custom auth header name and value for a qixin.com API request.
    Returns: (header_name, header_value)
    """
    if base_url is None:
        base_url = BROWSER_API_BASE_URL

    q = build_q(base_url, url_path)
    j = get_key(q)

    header_name = hmac.new(
        j.encode('utf-8'), q.encode('utf-8'), hashlib.sha256
    ).hexdigest()[:5]

    msg = q + json_body
    header_value = hmac.new(
        j.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256
    ).hexdigest()

    return header_name, header_value


def test():
    """Test against known values from the real Chrome session."""

    # Test 1: getEquityConfig (known b0203 header)
    url = "/v4/internal/user/getEquityConfig"
    base = "/api-proxy/app"
    body = "{}"
    name, val = compute_signature(url, body, base)
    print(f"getEquityConfig:")
    print(f"  Header: {name}:{val}")
    expected_n = "b0203"
    expected_v = "d8e6a1dd35ff1a190cec940b0dd5fac41b477798efb588b89c7aac6f3288b6cc"
    print(f"  Name match: {'PASS' if name == expected_n else 'FAIL'} (expected {expected_n}, got {name})")
    print(f"  Value match: {'PASS' if val == expected_v else 'FAIL'}")
    print(f"  Expected: {expected_v}")
    print(f"  Got:      {val}")

    # Test 2: search/advanced (known 04d73 header)
    url = "/search/advanced"
    base = "/api-proxy"
    body = to_json({"status": [1], "key": "科技", "page": 1})
    name2, val2 = compute_signature(url, body, base)
    print(f"\nsearch/advanced:")
    print(f"  Header: {name2}:{val2}")

    # Test 3: searchHeader (known 33931 header)
    url = "/web/v8/ent/enterprise/searchHeader"
    base = "/api-proxy/web"
    body3 = '{"keyword":"计算机","start":0,"hit":6}'
    name3, val3 = compute_signature(url, body3, base)
    print(f"\nsearchHeader:")
    print(f"  Header: {name3}:{val3}")


if __name__ == "__main__":
    test()
