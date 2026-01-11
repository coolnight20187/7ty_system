import requests
import json

# Test complete login flow
print("1. Testing login...")
r = requests.post(
    'http://localhost:8000/api/auth/login',
    json={'username': 'admin', 'password': 'Admin@12345'},
    timeout=10
)

print(f"   Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"   ✓ Login success")
    print(f"   Token: {data.get('access_token', 'NO TOKEN')[:40]}...")
    print(f"   access_token in response: {'access_token' in data}")
    print(f"   user_id in response: {'user_id' in data}")
    print(f"   Response keys: {list(data.keys())}")
else:
    print(f"   ✗ Login failed")
    print(f"   Response: {r.text}")

# Test 2: Check / route
print("\n2. Testing / route...")
r = requests.get('http://localhost:8000/', timeout=5)
print(f"   Status: {r.status_code}")
print(f"   Content-Type: {r.headers.get('content-type')}")
print(f"   Is HTML: {'html' in r.headers.get('content-type', '').lower()}")
print(f"   File size: {len(r.text)} bytes")
print(f"   Contains DOMContentLoaded: {'DOMContentLoaded' in r.text}")
print(f"   Contains appState: {'appState' in r.text}")
