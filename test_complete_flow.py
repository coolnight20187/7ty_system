#!/usr/bin/env python3
"""
Test complete login and dashboard flow
Simulate exactly what browser does
"""
import requests
import json
import time

# Create session to maintain cookies/state
session = requests.Session()

print("="*60)
print("TESTING COMPLETE LOGIN FLOW")
print("="*60)

# Step 1: Get login page
print("\n[1] Fetching login page...")
r = session.get('http://localhost:8000/static/login.html', timeout=5)
print(f"    Status: {r.status_code}")
print(f"    ✓ Login page loaded" if r.status_code == 200 else f"    ✗ Failed")

# Step 2: Login
print("\n[2] Submitting login (admin/Admin@12345)...")
r = session.post(
    'http://localhost:8000/api/auth/login',
    json={'username': 'admin', 'password': 'Admin@12345'},
    timeout=5
)
print(f"    Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    token = data['access_token']
    print(f"    ✓ Login successful")
    print(f"    Token: {token[:40]}...")
else:
    print(f"    ✗ Login failed: {r.text}")
    exit(1)

# Step 3: Check localStorage would have token by now in real browser
# Simulate: add token to session headers
print("\n[3] Navigating to / (dashboard)...")
r = session.get('http://localhost:8000/', timeout=5)
print(f"    Status: {r.status_code}")
if r.status_code == 200:
    print(f"    ✓ / returns app.html")
    # Check for key elements
    checks = [
        ('loading-screen' in r.text, 'Has loading-screen element'),
        ('appState' in r.text, 'Has appState variable'),
        ('DOMContentLoaded' in r.text, 'Has DOMContentLoaded handler'),
        ('loadDashboardData' in r.text, 'Has loadDashboardData function'),
    ]
    for check, desc in checks:
        print(f"      {'✓' if check else '✗'} {desc}")
else:
    print(f"    ✗ Failed: {r.status_code}")

# Step 4: Test dashboard APIs with token
print("\n[4] Testing dashboard APIs (with token)...")
headers = {'Authorization': f'Bearer {token}'}
apis = [
    '/api/users/me',
    '/api/system/dashboard',
    '/api/agents',
    '/api/bills',
    '/api/customers',
    '/api/notifications/unread-count',
]

all_ok = True
for api in apis:
    r = session.get(f'http://localhost:8000{api}', headers=headers, timeout=5)
    status_ok = r.status_code == 200
    all_ok = all_ok and status_ok
    symbol = '✓' if status_ok else '✗'
    print(f"      {symbol} {api:40} {r.status_code}")

print("\n" + "="*60)
if all_ok:
    print("✓ ALL TESTS PASSED - Dashboard should load correctly!")
else:
    print("✗ Some APIs failed - Dashboard may have issues")
print("="*60)
