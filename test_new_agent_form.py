#!/usr/bin/env python3
"""Test new agent registration form with updated schema"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@12345"

def login():
    """Login as admin to get token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    )
    
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"❌ Login failed: {response.status_code}")
        print(response.text)
        return None

def test_agent_creation(token):
    """Test creating a new agent with updated schema"""
    
    # Generate unique identifiers
    timestamp = int(datetime.now().timestamp() * 1000)
    phone = f"098{timestamp % 10000000:07d}"
    agent_code = f"AG-{timestamp}"
    
    # Test data with new schema requirements
    agent_data = {
        "username": phone,
        "password": "Test@Password123",
        "password_confirm": "Test@Password123",
        "full_name": "Nguyễn Văn Test",
        "agent_name": "Đại Lý Test New Form",  # NEW FIELD
        "phone": phone,
        "agent_code": agent_code,
        "agent_type": "individual",
        "status": "pending"
    }
    
    print("📋 Testing agent creation with new schema:")
    print(json.dumps(agent_data, indent=2, ensure_ascii=False))
    print()
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/agents/with-user",
        json=agent_data,
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200 or response.status_code == 201:
        result = response.json()
        print("✅ Agent created successfully!")
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return True
    else:
        print("❌ Failed to create agent")
        print(response.text)
        return False

def test_password_mismatch(token):
    """Test password confirmation validation"""
    
    timestamp = int(datetime.now().timestamp() * 1000)
    phone = f"099{timestamp % 10000000:07d}"
    agent_code = f"AG-{timestamp}-nomatch"
    
    agent_data = {
        "username": phone,
        "password": "Test@Password123",
        "password_confirm": "Different@Password456",  # Doesn't match!
        "full_name": "Nguyễn Văn Mismatch",
        "agent_name": "Đại Lý Test Mismatch",
        "phone": phone,
        "agent_code": agent_code,
        "agent_type": "individual",
        "status": "pending"
    }
    
    print("\n🔐 Testing password confirmation validation (should fail):")
    print(f"Password: Test@Password123")
    print(f"Confirm: Different@Password456")
    print()
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/agents/with-user",
        json=agent_data,
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200 and response.status_code != 201:
        print("✅ Validation correctly rejected mismatched passwords!")
        print(response.text)
        return True
    else:
        print("❌ Should have rejected mismatched passwords")
        return False

def test_missing_agent_name(token):
    """Test that agent_name is required"""
    
    timestamp = int(datetime.now().timestamp() * 1000)
    phone = f"097{timestamp % 10000000:07d}"
    agent_code = f"AG-{timestamp}-noname"
    
    agent_data = {
        "username": phone,
        "password": "Test@Password123",
        "password_confirm": "Test@Password123",
        "full_name": "Nguyễn Văn NoName",
        # Missing: "agent_name" - REQUIRED FIELD
        "phone": phone,
        "agent_code": agent_code,
        "agent_type": "individual",
        "status": "pending"
    }
    
    print("\n⚠️  Testing missing agent_name validation (should fail):")
    print("Missing 'agent_name' field (required)")
    print()
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/agents/with-user",
        json=agent_data,
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200 and response.status_code != 201:
        print("✅ Validation correctly required agent_name field!")
        print(response.text)
        return True
    else:
        print("❌ Should have required agent_name field")
        return False

if __name__ == "__main__":
    print("🚀 Testing New Agent Registration Form\n")
    print("=" * 60)
    
    # Login
    token = login()
    if not token:
        exit(1)
    
    print(f"✅ Logged in as admin\n")
    print("=" * 60)
    
    # Run tests
    test1 = test_agent_creation(token)
    test2 = test_password_mismatch(token)
    test3 = test_missing_agent_name(token)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"  ✅ Agent creation (new schema): {'PASS' if test1 else 'FAIL'}")
    print(f"  ✅ Password validation: {'PASS' if test2 else 'FAIL'}")
    print(f"  ✅ Required agent_name: {'PASS' if test3 else 'FAIL'}")
    print("=" * 60)
