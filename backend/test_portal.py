"""Integration tests for the public portal endpoints."""
import urllib.request
import urllib.error
import json
import sys

BASE = "http://127.0.0.1:8765"
results = []

def request(url, expected_status=200):
    try:
        r = urllib.request.urlopen(url, timeout=10)
        code = r.status
        body = r.read().decode()
        return code, body
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as ex:
        return None, str(ex)

def test(name, url, expected_status, check_fn=None):
    code, body = request(url)
    ok = (code == expected_status)
    if ok and check_fn:
        try:
            ok = check_fn(body)
        except Exception as ex:
            ok = False
            body = str(ex)
    status = "PASS" if ok else "FAIL"
    results.append((status, name, code, body[:200] if body else ""))
    print(f"[{status}] {name} → HTTP {code}")

# 1. Health
test("API health", f"{BASE}/api/health", 200,
     lambda b: json.loads(b).get("status") == "ok")

# 2. Config
test("API config", f"{BASE}/api/config", 200,
     lambda b: "college_name" in json.loads(b))

# 3. Portal HTML served at /portal/
test("Portal HTML /portal/", f"{BASE}/portal/", 200,
     lambda b: "Exam Allotment Portal" in b)

# 4. /portal redirects to /portal/
code, body = request(f"{BASE}/portal")
# A redirect returns 302; urllib follows it, so we may get 200 from the final destination
redir_ok = code in (200, 302)
results.append(("PASS" if redir_ok else "FAIL", "/portal redirect", code, body[:100]))
print(f"[{'PASS' if redir_ok else 'FAIL'}] /portal redirect → HTTP {code}")

# 5. Lookup non-existent register number
test("Lookup unknown reg", f"{BASE}/api/lookup/ZZZZZZZZ9999", 404)

# 6. Invalid register number
test("Lookup invalid reg", f"{BASE}/api/lookup/!!!bad!!!", 422)

# 7. Direct URL param (portal page has ?reg= support, served as static)
test("Portal with ?reg= in URL", f"{BASE}/portal/?reg=922525106", 200,
     lambda b: "Exam Allotment Portal" in b)

print("\n=== SUMMARY ===")
passed = sum(1 for r in results if r[0] == "PASS")
failed = sum(1 for r in results if r[0] == "FAIL")
print(f"Passed: {passed}/{len(results)}")
if failed:
    print("FAILED tests:")
    for r in results:
        if r[0] == "FAIL":
            print(f"  - {r[1]}: HTTP {r[2]}, {r[3][:100]}")
sys.exit(0 if failed == 0 else 1)
