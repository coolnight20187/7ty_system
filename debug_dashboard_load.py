#!/usr/bin/env python3
"""Debug dashboard loading step by step"""

import requests
import json
import sys
import io

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = "http://localhost:8000"

print("=" * 70)
print("DEBUGGING: Dashboard Loading Issues")
print("=" * 70)
print()

# Login first
print("1. Logging in...")
response = requests.post(
    f"{BASE_URL}/api/auth/login",
    json={"username": "admin", "password": "Admin@12345"}
)

if response.status_code != 200:
    print(f"ERROR: Login failed: {response.status_code}")
    exit(1)

data = response.json()
token = data.get("access_token")
print(f"SUCCESS: Token received")
print()

headers = {"Authorization": f"Bearer {token}"}

# Test each API that dashboard calls
print("2. Testing APIs called during initialization...")
print()

apis = [
    ("GET /api/users/me", "GET", "/api/users/me"),
    ("GET /api/system/dashboard", "GET", "/api/system/dashboard"),
    ("GET /api/agents", "GET", "/api/agents"),
    ("GET /api/bills", "GET", "/api/bills"),
    ("GET /api/customers", "GET", "/api/customers"),
    ("GET /api/notifications/unread-count", "GET", "/api/notifications/unread-count"),
    ("GET /api/notifications/unread", "GET", "/api/notifications/unread"),
]

failed = []

for name, method, endpoint in apis:
    try:
        if method == "GET":
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=5)
        else:
            response = requests.post(f"{BASE_URL}{endpoint}", headers=headers, timeout=5)
        
        status_color = "OK" if response.status_code == 200 else f"HTTP {response.status_code}"
        
        if response.status_code == 200:
            # Parse response
            try:
                resp_data = response.json()
                # Show sample of response
                if isinstance(resp_data, dict):
                    keys = list(resp_data.keys())[:3]
                    print(f"  ✓ {name:35s} 200 OK (keys: {', '.join(keys)})")
                else:
                    print(f"  ✓ {name:35s} 200 OK")
            except:
                print(f"  ✓ {name:35s} 200 OK")
        else:
            print(f"  ✗ {name:35s} {status_color}")
            failed.append((name, status_color))
            # Show error
            try:
                error_data = response.json()
                print(f"     Error: {json.dumps(error_data, ensure_ascii=False)[:100]}")
            except:
                print(f"     Response: {response.text[:100]}")
                
    except requests.exceptions.Timeout:
        print(f"  ✗ {name:35s} TIMEOUT")
        failed.append((name, "TIMEOUT"))
    except requests.exceptions.ConnectionError as e:
        print(f"  ✗ {name:35s} CONNECTION ERROR: {str(e)[:50]}")
        failed.append((name, "CONNECTION ERROR"))
    except Exception as e:
        print(f"  ✗ {name:35s} ERROR: {str(e)[:50]}")
        failed.append((name, str(e)[:50]))

print()
print("=" * 70)
print("ANALYSIS:")
print("=" * 70)
print()

if not failed:
    print("All APIs are working correctly!")
    print()
    print("If dashboard is still hanging, the issue might be:")
    print("  1. Browser JavaScript error (check browser console)")
    print("  2. API response format not matching expected schema")
    print("  3. WebSocket connection timeout")
    print("  4. JavaScript execution stuck in a loop")
else:
    print(f"FOUND {len(failed)} FAILING ENDPOINTS:")
    for name, status in failed:
        print(f"  - {name}: {status}")

print("=" * 70)
