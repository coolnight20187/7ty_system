#!/usr/bin/env python3
"""Test complete login and dashboard loading flow"""
import requests
import json
import time

print("=" * 60)
print("Testing Login and Dashboard Loading")
print("=" * 60)

# Step 1: Login
print("\n[Step 1] Login with admin credentials...")
r = requests.post(
    'http://localhost:8000/api/auth/login',
    json={'username': 'admin', 'password': 'Admin@12345'},
    timeout=5
)

if r.status_code != 200:
    print(f"✗ Login failed: {r.status_code}")
    print(f"  {r.text}")
    exit(1)

data = r.json()
token = data.get('access_token')
print(f"✓ Login successful")
print(f"  Token: {token[:30]}...")

# Step 2: Test root route (should serve app.html)
print("\n[Step 2] Testing / route (should serve app.html)...")
r = requests.get('http://localhost:8000/', timeout=5)
if r.status_code == 200 and 'DOCTYPE html' in r.text:
    print(f"✓ / route returns app.html (200 OK)")
else:
    print(f"✗ / route failed: {r.status_code}")

# Step 3: Test all dashboard APIs with token
print("\n[Step 3] Testing dashboard APIs with token...")
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
    r = requests.get(f'http://localhost:8000{api}', headers=headers, timeout=5)
    if r.status_code == 200:
        print(f"  ✓ {api:40} 200 OK")
    else:
        print(f"  ✗ {api:40} {r.status_code}")
        all_ok = False

print("\n" + "=" * 60)
if all_ok:
    print("✓ All checks passed! Dashboard should load.")
else:
    print("✗ Some APIs failed. Dashboard may hang.")
print("=" * 60)
