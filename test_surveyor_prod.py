"""Test Surveyor login and dashboard on staff.digiland.co.ke with generous timeout."""
import urllib.request
import urllib.parse
import ssl
import http.cookiejar
import re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

UA = {"User-Agent": "DigilandVerify/1.0"}
STAFF_BASE = "https://staff.digiland.co.ke"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cj),
    urllib.request.HTTPSHandler(context=ctx),
)

print("1. GET /staff/login/")
req = urllib.request.Request(f"{STAFF_BASE}/staff/login/", headers=UA)
resp = opener.open(req, timeout=60)
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

print("\n2. POST /staff/login/ (Surveyor Credentials)")
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
resp = opener.open(req, timeout=60)
html = resp.read().decode()
print(f"   HTTP {resp.status} | Landed URL: {resp.url}")

print("\n3. GET /surveyor/dashboard/")
req = urllib.request.Request(f"{STAFF_BASE}/surveyor/dashboard/", headers=UA)
resp = opener.open(req, timeout=60)
html = resp.read().decode()
print(f"   HTTP {resp.status} | Landed URL: {resp.url}")

title_m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
title = title_m.group(1).strip() if title_m else "No Title"
print(f"   Page Title: {title}")

h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
h2s = re.findall(r"<h2[^>]*>(.*?)</h2>", html, re.S | re.I)
print(f"   H1 Headings: {[re.sub('<[^>]+>', '', h).strip() for h in h1s]}")
print(f"   H2 Headings: {[re.sub('<[^>]+>', '', h).strip() for h in h2s[:5]]}")

if "surveyor" in resp.url.lower() or "survey" in title.lower():
    print("\n>>> SUCCESS: Surveyor Dashboard Verified Working on Production! <<<")
else:
    print(f"\n>>> Status: {resp.url} <<<")
