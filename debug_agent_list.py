#!/usr/bin/env python3
"""Debug: Check why agents aren't showing in the list"""

import requests
import json
import sys
import io

# Fix encoding for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = "http://localhost:8000"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@12345"

# Login
print("1. Logging in as admin...")
response = requests.post(
    f"{BASE_URL}/api/auth/login",
    json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
)

if response.status_code != 200:
    print(f"❌ Login failed: {response.status_code}")
    print(response.text)
    exit(1)

token = response.json()["access_token"]
print("✅ Logged in\n")

# Check agents endpoint
headers = {"Authorization": f"Bearer {token}"}

print("2. Checking /api/agents endpoint...")
response = requests.get(f"{BASE_URL}/api/agents", headers=headers)
print(f"Status: {response.status_code}")
print(f"Response type: {type(response.json())}")
print("\nFull response:")
print(json.dumps(response.json(), indent=2, ensure_ascii=False, default=str))
print()

# Check with different parameters
print("3. Trying with explicit pagination params...")
response = requests.get(f"{BASE_URL}/api/agents?page=1&limit=100", headers=headers)
print(f"Status: {response.status_code}")
print(json.dumps(response.json(), indent=2, ensure_ascii=False, default=str))
print()

# Direct database query
print("4. Checking database directly...")
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://7ty_admin:7ty_password_secure@localhost:5432/7ty_vn_db"

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) as count FROM agents"))
        count = result.fetchone()[0]
        print(f"Total agents in database: {count}")
        
        result = conn.execute(text("""
            SELECT a.id, a.agent_code, a.agent_name, a.agent_type, a.status, u.username, u.full_name
            FROM agents a
            LEFT JOIN users u ON a.user_id = u.id
            ORDER BY a.created_at DESC
            LIMIT 10
        """))
        
        print("\nAgents in database:")
        for row in result:
            print(f"  - ID: {row[0]}, Code: {row[1]}, Name: {row[2]}, Type: {row[3]}, Status: {row[4]}, User: {row[5]} ({row[6]})")
            
except Exception as e:
    print(f"❌ Database query failed: {e}")
