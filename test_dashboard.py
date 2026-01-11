import requests
import json

# Test 1: Login
print("Testing login...")
r = requests.post(
    'http://localhost:8000/api/auth/login',
    json={'username': 'admin', 'password': 'Admin@12345'},
    timeout=10
)

if r.status_code != 200:
    print(f"Login failed: {r.status_code}")
    print(r.text)
    exit(1)

token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}
print(f"Token: {token[:30]}...")

# Test 2: All APIs
print("\nTesting dashboard APIs...")
apis = [
    '/api/users/me',
    '/api/system/dashboard',
    '/api/agents',
    '/api/bills',
    '/api/customers',
    '/api/notifications/unread-count',
]

for api in apis:
    try:
        r = requests.get(f'http://localhost:8000{api}', headers=headers, timeout=5)
        print(f"{api:40} {r.status_code}")
        if r.status_code != 200:
            print(f"  Error: {r.text[:200]}")
    except Exception as e:
        print(f"{api:40} ERROR: {e}")
