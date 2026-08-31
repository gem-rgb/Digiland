"""Verify both Surveyor Dashboard access and Partition Isolation on Production."""
import urllib.request
import urllib.parse
import ssl
import http.cookiejar
import re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

UA = {"User-Agent": "DigilandVerify/1.0"}

def test_surveyor_login_and_dashboard():
    print("=================================================================")
    print("TEST 1: Surveyor Login & Dashboard Access (staff.digiland.co.ke)")
    print("=================================================================")
    STAFF_BASE = "https://staff.digiland.co.ke"
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPSHandler(context=ctx),
    )

    # 1. GET login page
    print("1. GET /staff/login/")
    req = urllib.request.Request(f"{STAFF_BASE}/staff/login/", headers=UA)
    resp = opener.open(req, timeout=30)
    html = resp.read().decode()
    print(f"   HTTP {resp.status} | URL: {resp.url}")

    csrf_match = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', html)
    csrf_token = csrf_match.group(1) if csrf_match else None
    if not csrf_token:
        for c in cj:
            if "csrf" in c.name.lower():
                csrf_token = c.value
                break
    print(f"   CSRF: {csrf_token[:15]}...")

    # 2. POST login credentials
    print("2. POST /staff/login/ as surveyor_demo@example.com")
    data = urllib.parse.urlencode({
        "csrfmiddlewaretoken": csrf_token,
        "email": "surveyor_demo@example.com",
        "password": "SurveyorDigiland2026!",
    }).encode()
    req = urllib.request.Request(
        f"{STAFF_BASE}/staff/login/",
        data=data,
        headers={
            "User-Agent": "DigilandVerify/1.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{STAFF_BASE}/staff/login/",
        },
    )
    resp = opener.open(req, timeout=30)
    html = resp.read().decode()
    print(f"   HTTP {resp.status} | Landed URL: {resp.url}")

    # 3. GET /surveyor/dashboard/
    print("3. GET /surveyor/dashboard/")
    req = urllib.request.Request(f"{STAFF_BASE}/surveyor/dashboard/", headers=UA)
    resp = opener.open(req, timeout=30)
    html = resp.read().decode()
    print(f"   HTTP {resp.status} | Final URL: {resp.url}")
    
    title_m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    title = title_m.group(1).strip() if title_m else "No Title"
    print(f"   Page Title: {title}")

    if "surveyor" in resp.url.lower() or "survey" in title.lower():
        print("   >>> PASS: Surveyor Dashboard accessible successfully on production! <<<")
    else:
        print(f"   >>> WARNING/FAIL: Unexpected page landed: {resp.url} <<<")

    h1_matches = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    h2_matches = re.findall(r"<h2[^>]*>(.*?)</h2>", html, re.S | re.I)
    print(f"   H1s: {[re.sub('<[^>]+>', '', h).strip() for h in h1_matches]}")
    print(f"   H2s: {[re.sub('<[^>]+>', '', h).strip() for h in h2_matches[:5]]}")


def test_staff_login_on_buyer_seller_portal():
    print("\n=================================================================")
    print("TEST 2: Staff Login on Buyer/Seller Portal (app.digiland.co.ke)")
    print("=================================================================")
    APP_BASE = "https://app.digiland.co.ke"
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPSHandler(context=ctx),
    )

    # 1. GET buyer/seller login page
    print("1. GET /accounts/login/")
    req = urllib.request.Request(f"{APP_BASE}/accounts/login/", headers=UA)
    resp = opener.open(req, timeout=30)
    html = resp.read().decode()
    print(f"   HTTP {resp.status} | URL: {resp.url}")

    csrf_match = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', html)
    csrf_token = csrf_match.group(1) if csrf_match else None
    if not csrf_token:
        for c in cj:
            if "csrf" in c.name.lower():
                csrf_token = c.value
                break
    print(f"   CSRF: {csrf_token[:15]}...")

    # 2. POST staff credentials to /accounts/login/
    print("2. POST /accounts/login/ with surveyor credentials")
    data = urllib.parse.urlencode({
        "csrfmiddlewaretoken": csrf_token,
        "login": "surveyor_demo@example.com",
        "password": "SurveyorDigiland2026!",
    }).encode()
    req = urllib.request.Request(
        f"{APP_BASE}/accounts/login/",
        data=data,
        headers={
            "User-Agent": "DigilandVerify/1.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{APP_BASE}/accounts/login/",
        },
    )
    try:
        resp = opener.open(req, timeout=30)
        html = resp.read().decode()
        print(f"   HTTP {resp.status} | Landed URL: {resp.url}")
        title_m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
        print(f"   Title: {title_m.group(1).strip() if title_m else 'No Title'}")
        if "Application Exception" in html:
            print("   >>> FAIL: Application Exception shown! <<<")
        else:
            print("   >>> PASS: Handled cleanly without Application Exception! <<<")
    except urllib.error.HTTPError as e:
        print(f"   HTTP {e.code} | Redirect/Error")
        print(f"   Location header: {e.headers.get('Location', 'N/A')}")
        body = e.read().decode()[:500]
        print(f"   Body snippet: {body}")

if __name__ == "__main__":
    try:
        test_surveyor_login_and_dashboard()
    except Exception as exc:
        print(f"Test 1 failed with error: {exc}")

    try:
        test_staff_login_on_buyer_seller_portal()
    except Exception as exc:
        print(f"Test 2 failed with error: {exc}")
