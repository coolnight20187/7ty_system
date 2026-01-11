#!/usr/bin/env python3
"""Test which routes are registered in FastAPI app"""

from main import app

print('=' * 60)
print('FastAPI Routes Report')
print('=' * 60)

print(f'\nTotal routes: {len(app.routes)}')

print('\nSearching for /api/customers routes:')
found_customers = False
for route in app.routes:
    if hasattr(route, 'path'):
        if 'customers' in route.path.lower():
            print(f'  FOUND: {route.path}')
            print(f'    Methods: {getattr(route, "methods", "N/A")}')
            found_customers = True

if not found_customers:
    print('  ✗ NO /api/customers routes found in app.routes')

print('\nAll /api routes:')
api_routes = [r for r in app.routes if hasattr(r, 'path') and r.path.startswith('/api')]
print(f'  Total /api routes: {len(api_routes)}')
for route in api_routes[:20]:
    methods = getattr(route, 'methods', [])
    print(f'    {route.path:30} {methods}')

print('\nChecking route order (last 5):')
for route in app.routes[-5:]:
    path = getattr(route, 'path', 'no path')
    methods = getattr(route, 'methods', [])
    print(f'    {path:40} {methods}')

print('\n' + '=' * 60)
