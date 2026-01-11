import requests
import time

# Login
login_resp = requests.post('http://localhost:8000/api/auth/login', json={
    'username': 'admin',
    'password': 'Admin@12345'
})
token = login_resp.json()['access_token']

# Create agent
timestamp = int(time.time() * 1000)
agent_data = {
    'username': f'agent_sync_{timestamp}',
    'password': 'Test@1234',
    'password_confirm': 'Test@1234',
    'full_name': 'Original Name',
    'phone': '0987654321',
    'agent_name': 'Agency Name',
    'agent_code': f'AG{timestamp}',
    'agent_type': 'individual',
    'status': 'pending'
}

create_resp = requests.post(
    'http://localhost:8000/api/agents/with-user',
    headers={'Authorization': f'Bearer {token}'},
    json=agent_data
)

print(f'Create agent: {create_resp.status_code}')
if create_resp.status_code == 200:
    agent = create_resp.json()
    agent_id = agent.get('id')
    print(f'  Agent ID: {agent_id}')
    print(f'  Full Name: {agent.get("user", {}).get("full_name")}')
    print(f'  Agent Name: {agent.get("agent_name")}')
    
    # Update agent
    update_data = {
        'full_name': 'Updated Full Name',
        'agent_name': 'Updated Agent Name',
        'status': 'active'
    }
    
    update_resp = requests.put(
        f'http://localhost:8000/api/agents/{agent_id}',
        headers={'Authorization': f'Bearer {token}'},
        json=update_data
    )
    
    print(f'\nUpdate agent: {update_resp.status_code}')
    if update_resp.status_code == 200:
        updated = update_resp.json()
        print(f'  Full Name: {updated.get("user", {}).get("full_name")}')
        print(f'  Agent Name: {updated.get("agent_name")}')
        print(f'  Status: {updated.get("status")}')
        
        # Verify by fetching again
        get_resp = requests.get(
            f'http://localhost:8000/api/agents/{agent_id}',
            headers={'Authorization': f'Bearer {token}'}
        )
        print(f'\nFetch agent: {get_resp.status_code}')
        if get_resp.status_code == 200:
            fetched = get_resp.json()
            print(f'  Full Name: {fetched.get("user", {}).get("full_name")}')
            print(f'  Agent Name: {fetched.get("agent_name")}')
            print(f'  Status: {fetched.get("status")}')
            
            # Check if everything matches
            if (fetched.get("user", {}).get("full_name") == 'Updated Full Name' and
                fetched.get("agent_name") == 'Updated Agent Name' and
                fetched.get("status") == 'active'):
                print('\n✅ ALL FIELDS SYNCED CORRECTLY!')
            else:
                print('\n❌ Some fields not synced')
    else:
        print(f'  Error: {update_resp.json()}')
else:
    print(f'  Error: {create_resp.json()}')
