"""
Script to test admin login
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_login():
    """Test admin login"""
    login_data = {
        "username": "admin",
        "password": "Admin@12345"
    }
    
    print("Testing login with:")
    print(f"  Username: {login_data['username']}")
    print(f"  Password: {login_data['password']}")
    print()
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=login_data,
            timeout=10
        )
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Body:")
        print(json.dumps(response.json(), indent=2))
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_login()
