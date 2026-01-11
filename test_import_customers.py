import requests
import json

r = requests.post('http://localhost:8000/api/auth/login', 
                  json={'username': 'admin', 'password': 'Admin@12345'},
                  timeout=5)
                  
print(f'Status: {r.status_code}')
print('Response:')
print(json.dumps(r.json(), indent=2))
