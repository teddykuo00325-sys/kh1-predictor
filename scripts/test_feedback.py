"""Integration test for the feedback endpoint using Python requests."""
import sys, time
import requests

BASE  = "http://127.0.0.1:5000"
TOKEN = "local-test-token-9472"

def line(s): print("\n--- " + s + " ---")

line("1) GET /feedback")
r = requests.get(BASE + "/feedback")
print(f"   {r.status_code}, has form? {'<form' in r.text}")

line("2) POST valid submission")
r = requests.post(BASE + "/feedback", data={
    "name":    "測試用戶",
    "contact": "test@example.com",
    "message": "這是一則測試留言！希望系統能順利收到。",
}, allow_redirects=False)
print(f"   {r.status_code} → Location: {r.headers.get('Location')}")

line("3) Wait 61s so rate limit clears, then submit again with honeypot")
time.sleep(61)
r = requests.post(BASE + "/feedback", data={
    "name":    "spambot",
    "message": "spam content here",
    "website": "http://spam.example.com",  # honeypot
}, allow_redirects=False)
print(f"   {r.status_code} → Location: {r.headers.get('Location')}  (should be /feedback/thanks)")

line("4) Empty message rejection")
r = requests.post(BASE + "/feedback", data={"message": ""}, allow_redirects=False)
print(f"   {r.status_code} → Location: {r.headers.get('Location')}  (should contain error=)")

line("5) Admin without token")
r = requests.get(BASE + "/admin/feedback", allow_redirects=False)
print(f"   {r.status_code}  (should be 404)")

line("6) Admin with WRONG token")
r = requests.get(BASE + "/admin/feedback?key=wrong", allow_redirects=False)
print(f"   {r.status_code}  (should be 404)")

line("7) Admin with CORRECT token")
r = requests.get(BASE + "/admin/feedback?key=" + TOKEN)
print(f"   {r.status_code}")
print(f"   contains 測試用戶: {'測試用戶' in r.text}")
print(f"   contains spambot:  {'spambot'  in r.text} (should be False — honeypot dropped)")

line("8) Export JSON")
r = requests.get(BASE + "/admin/feedback/export?key=" + TOKEN)
print(f"   {r.status_code}, content-type: {r.headers.get('Content-Type')}")
print(f"   payload: {r.text[:400]}")
