import requests
r = requests.get('http://localhost:8000/')
print(f'Status: {r.status_code}')
print(f'Content length: {len(r.text)}')
print(f'Has DOCTYPE: {"DOCTYPE" in r.text}')
print(f'Has DOMContentLoaded: {"DOMContentLoaded" in r.text}')
print(f'Has loading-screen: {"loading-screen" in r.text}')
print(f'First 200 chars: {r.text[:200]}')
