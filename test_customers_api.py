import requests

# Login
r = requests.post('http://localhost:8000/api/auth/login', 
                  json={'username': 'admin', 'password': 'Admin@12345'})
                  
if r.status_code == 200:
    token = r.json()['access_token']
    print('✓ Login successful')
    
    # Test /api/customers with token
    headers = {'Authorization': f'Bearer {token}'}
    r = requests.get('http://localhost:8000/api/customers', headers=headers)
    
    if r.status_code == 200:
        data = r.json()
        count = len(data) if isinstance(data, list) else len(data.get('items', []))
        print(f'✓ /api/customers: {r.status_code} ({count} items)')
    else:
        print(f'✗ /api/customers: {r.status_code}')
        print(f'  {r.text[:300]}')
else:
    print(f'✗ Login failed: {r.status_code}')
    print(r.text[:300])
