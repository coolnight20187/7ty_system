import requests
import json

# Login
login_response = requests.post(
    'http://localhost:8000/api/auth/login',
    json={'username': 'admin', 'password': 'Admin@12345'},
    timeout=10
)

token = login_response.json()['access_token']

# Test agents endpoint
response = requests.get(
    'http://localhost:8000/api/agents?page=1&limit=10',
    headers={'Authorization': f'Bearer {token}'},
    timeout=10
)

print(f'Status: {response.status_code}')
print(json.dumps(response.json(), indent=2))
