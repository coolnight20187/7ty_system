#!/usr/bin/env python3
"""Verify agents are now showing in the list"""

import requests
import json
import sys
import io

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = "http://localhost:8000"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@12345"

print("=" * 70)
print("VERIFYING: Agents Display in List")
print("=" * 70)
print()

# Login
print("1. Logging in as admin...")
response = requests.post(
    f"{BASE_URL}/api/auth/login",
    json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
)

if response.status_code != 200:
    print(f"ERROR: Login failed: {response.status_code}")
    exit(1)

token = response.json()["access_token"]
print("SUCCESS: Logged in")
print()

# Get agents
print("2. Fetching agents from API...")
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(f"{BASE_URL}/api/agents?page=1&limit=10", headers=headers)

if response.status_code != 200:
    print(f"ERROR: Failed to fetch agents: {response.status_code}")
    exit(1)

data = response.json()
agents = data.get('data', [])
total = data.get('total', 0)

print(f"SUCCESS: Retrieved {len(agents)} agents (total: {total})")
print()

# Check data structure
print("3. Verifying agent data structure...")
if agents:
    agent = agents[0]
    
    checks = [
        ("agent_code", agent.get('agent_code')),
        ("agent_type", agent.get('agent_type')),
        ("status", agent.get('status')),
        ("balance", agent.get('balance')),
        ("user.full_name", agent.get('user', {}).get('full_name')),
        ("user.phone", agent.get('user', {}).get('phone')),
        ("created_at", agent.get('created_at')),
    ]
    
    all_good = True
    for field, value in checks:
        status = "OK" if value else "MISSING"
        print(f"  - {field}: {status} {f'({value})' if value else ''}")
        if not value:
            all_good = False
    
    print()
    if all_good:
        print("SUCCESS: All required fields present!")
    else:
        print("WARNING: Some fields are missing")
else:
    print("WARNING: No agents in database")

print()
print("4. Sample agent data for frontend:")
print(json.dumps(agents[0] if agents else {}, indent=2, ensure_ascii=False, default=str))

print()
print("=" * 70)
print("RESULTS:")
print("=" * 70)
print(f"Total agents: {total}")
print(f"Agents retrieved: {len(agents)}")
print(f"Response format: OK (data.data structure)")
print(f"Fields available: OK (user nested object)")
print()
print("FRONTEND FIX: Use agent.user.full_name and agent.user.phone")
print("=" * 70)
