import requests
import json
import time

# Login
resp = requests.post('http://localhost:8000/api/auth/login', json={
    'username': 'admin',
    'password': 'Admin@12345'
})
token = resp.json()['access_token']

# Create full agent
timestamp = int(time.time() * 1000)
agent_data = {
    'username': f'agent_full_{timestamp}',
    'password': 'Test@1234',
    'password_confirm': 'Test@1234',
    'full_name': 'Test Agent Full Name',
    'phone': '0912345678',
    'agent_name': 'Test Agent Company',
    'agent_code': f'AG{timestamp}',
    'agent_type': 'company',
    'company_name': 'Test Company Ltd',
    'tax_code': '1234567890',
    'address': '123 Main St',
    'city': 'Ho Chi Minh',
    'district': 'District 1',
    'ward': 'Ward 1',
    'commission_rate': 5.5,
    'status': 'pending'
}

resp = requests.post(
    'http://localhost:8000/api/agents/with-user',
    headers={'Authorization': f'Bearer {token}'},
    json=agent_data
)

if resp.status_code == 200:
    agent = resp.json()
    print('✅ CREATE - All Fields:')
    print(f'  agent_code: {agent.get("agent_code")} ✓' if agent.get("agent_code") == agent_data["agent_code"] else f'  agent_code: {agent.get("agent_code")} ❌')
    print(f'  agent_name: {agent.get("agent_name")} ✓' if agent.get("agent_name") == agent_data["agent_name"] else f'  agent_name: {agent.get("agent_name")} ❌')
    print(f'  agent_type: {agent.get("agent_type")} ✓' if agent.get("agent_type") == agent_data["agent_type"] else f'  agent_type: {agent.get("agent_type")} ❌')
    print(f'  company_name: {agent.get("company_name")} ✓' if agent.get("company_name") == agent_data["company_name"] else f'  company_name: {agent.get("company_name")} ❌')
    print(f'  tax_code: {agent.get("tax_code")} ✓' if agent.get("tax_code") == agent_data["tax_code"] else f'  tax_code: {agent.get("tax_code")} ❌')
    print(f'  full_name: {agent.get("user", {}).get("full_name")} ✓' if agent.get("user", {}).get("full_name") == agent_data["full_name"] else f'  full_name: {agent.get("user", {}).get("full_name")} ❌')
    print(f'  status: {agent.get("status")} ✓' if agent.get("status") == agent_data["status"] else f'  status: {agent.get("status")} ❌')
    
    agent_id = agent.get('id')
    
    # Update agent
    print('\n✅ UPDATE - Changing fields:')
    update_data = {
        'full_name': 'Updated Full Name',
        'agent_name': 'Updated Agent Name',
        'company_name': 'Updated Company',
        'tax_code': '9876543210',
        'address': '456 New St',
        'status': 'active'
    }
    
    resp = requests.put(
        f'http://localhost:8000/api/agents/{agent_id}',
        headers={'Authorization': f'Bearer {token}'},
        json=update_data
    )
    
    if resp.status_code == 200:
        agent = resp.json()
        print(f'  full_name: {agent.get("user", {}).get("full_name")} ✓' if agent.get("user", {}).get("full_name") == update_data["full_name"] else f'  full_name: {agent.get("user", {}).get("full_name")} ❌')
        print(f'  agent_name: {agent.get("agent_name")} ✓' if agent.get("agent_name") == update_data["agent_name"] else f'  agent_name: {agent.get("agent_name")} ❌')
        print(f'  company_name: {agent.get("company_name")} ✓' if agent.get("company_name") == update_data["company_name"] else f'  company_name: {agent.get("company_name")} ❌')
        print(f'  tax_code: {agent.get("tax_code")} ✓' if agent.get("tax_code") == update_data["tax_code"] else f'  tax_code: {agent.get("tax_code")} ❌')
        print(f'  address: {agent.get("address")} ✓' if agent.get("address") == update_data["address"] else f'  address: {agent.get("address")} ❌')
        print(f'  status: {agent.get("status")} ✓' if agent.get("status") == update_data["status"] else f'  status: {agent.get("status")} ❌')
        
        # Fetch again
        print('\n✅ FETCH - Verify persistence:')
        resp = requests.get(
            f'http://localhost:8000/api/agents/{agent_id}',
            headers={'Authorization': f'Bearer {token}'}
        )
        
        if resp.status_code == 200:
            agent = resp.json()
            print(f'  full_name: {agent.get("user", {}).get("full_name")} ✓' if agent.get("user", {}).get("full_name") == update_data["full_name"] else f'  full_name: {agent.get("user", {}).get("full_name")} ❌')
            print(f'  agent_name: {agent.get("agent_name")} ✓' if agent.get("agent_name") == update_data["agent_name"] else f'  agent_name: {agent.get("agent_name")} ❌')
            print(f'  company_name: {agent.get("company_name")} ✓' if agent.get("company_name") == update_data["company_name"] else f'  company_name: {agent.get("company_name")} ❌')
            print(f'  tax_code: {agent.get("tax_code")} ✓' if agent.get("tax_code") == update_data["tax_code"] else f'  tax_code: {agent.get("tax_code")} ❌')
            print(f'  address: {agent.get("address")} ✓' if agent.get("address") == update_data["address"] else f'  address: {agent.get("address")} ❌')
            print(f'  status: {agent.get("status")} ✓' if agent.get("status") == update_data["status"] else f'  status: {agent.get("status")} ❌')
        else:
            print(f'  Error: {resp.status_code}')
    else:
        print(f'  Error: {resp.status_code}')
else:
    print(f'Error: {resp.status_code}')
    print(resp.json())
