import requests
import json
import time

# Login
login_resp = requests.post('http://localhost:8000/api/auth/login', json={
    'username': 'admin',
    'password': 'Admin@12345'
})
token = login_resp.json()['access_token']

# Test: Create 2 agents with same phone (should work now with unique usernames)
for i in range(2):
    # Generate unique username and agent code
    timestamp = int(time.time() * 1000)
    unique_id = f"{timestamp}_{i}"
    
    agent_data = {
        'username': f'agent_{unique_id}',
        'password': 'Test@1234',
        'password_confirm': 'Test@1234',
        'full_name': f'Test Agent {i}',
        'phone': '0987654321',  # Same phone
        'agent_name': f'Agency {unique_id}',
        'agent_code': f'AGN{unique_id}',
        'agent_type': 'individual',
        'status': 'pending'
    }
    
    resp = requests.post(
        'http://localhost:8000/api/agents/with-user',
        headers={'Authorization': f'Bearer {token}'},
        json=agent_data
    )
    print(f'Agent {i}: {resp.status_code}')
    if resp.status_code != 200:
        print(f'  Error: {resp.json()}')
    else:
        data = resp.json()
        print(f'  Success: agent_code={data.get("agent_code")}')
