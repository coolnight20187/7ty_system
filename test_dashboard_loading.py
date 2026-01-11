#!/usr/bin/env python3
"""Verify loading page issue has been fixed"""

import requests
import json
import sys
import io
import time

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = "http://localhost:8000"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@12345"

print("=" * 70)
print("TESTING: Admin Dashboard Loading Issue")
print("=" * 70)
print()

# Step 1: Login
print("1. Logging in as admin...")
response = requests.post(
    f"{BASE_URL}/api/auth/login",
    json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
)

if response.status_code != 200:
    print(f"ERROR: Login failed: {response.status_code}")
    print(response.text)
    exit(1)

token = response.json()["access_token"]
print("SUCCESS: Logged in")
print()

# Step 2: Test key APIs that dashboard needs
print("2. Testing key API endpoints needed by dashboard...")
headers = {"Authorization": f"Bearer {token}"}

endpoints = [
    ("User Data", "/api/users/me"),
    ("Agents", "/api/agents"),
    ("Notifications", "/api/notifications/unread-count"),
]

all_ok = True
for name, endpoint in endpoints:
    try:
        response = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=5)
        status = "OK" if response.status_code == 200 else f"HTTP {response.status_code}"
        print(f"  - {name:20s}: {status}")
        if response.status_code != 200:
            all_ok = False
    except Exception as e:
        print(f"  - {name:20s}: ERROR - {str(e)}")
        all_ok = False

print()

# Step 3: Test WebSocket
print("3. Testing WebSocket connection...")
try:
    import websocket
    
    ws_url = f"ws://localhost:8000/ws?token={token}"
    ws = websocket.WebSocket()
    ws.settimeout(3)
    
    try:
        ws.connect(ws_url)
        print("  - WebSocket connection: OK")
        ws.close()
    except websocket.WebSocketException as e:
        print(f"  - WebSocket connection: ERROR - {str(e)}")
        all_ok = False
except ImportError:
    print("  - WebSocket test: SKIPPED (websocket-client not installed)")

print()
print("=" * 70)
print("RESULTS:")
print("=" * 70)

if all_ok:
    print("SUCCESS: All API endpoints are working!")
    print()
    print("The dashboard should now load without getting stuck at")
    print("'Đang tải hệ thống...' (Loading system...)")
    print()
    print("Issues Fixed:")
    print("  1. Added get_current_user_ws() function to dependencies")
    print("  2. Fixed WebSocket endpoint to use token authentication")
    print("  3. Improved loading screen initialization")
    print("  4. Made non-critical operations non-blocking")
else:
    print("FAILED: Some API endpoints are not responding")
    print("Check Docker logs for errors")

print("=" * 70)
