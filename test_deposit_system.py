import requests
import json
import time

# Login
resp = requests.post('http://localhost:8000/api/auth/login', json={
    'username': 'admin',
    'password': 'Admin@12345'
})
token = resp.json()['access_token']

# Create test agent
timestamp = int(time.time() * 1000)
agent_data = {
    'username': f'test_deposit_{timestamp}',
    'password': 'Test@1234',
    'password_confirm': 'Test@1234',
    'full_name': 'Test Deposit Agent',
    'phone': '0988888888',
    'agent_name': 'Test Deposit Agency',
    'agent_code': f'AGDEP{timestamp}',
    'agent_type': 'individual',
    'status': 'pending'
}

resp = requests.post(
    'http://localhost:8000/api/agents/with-user',
    headers={'Authorization': f'Bearer {token}'},
    json=agent_data
)

if resp.status_code != 200:
    print(f'Failed to create agent: {resp.status_code}')
    print(resp.json())
    exit(1)

agent = resp.json()
agent_id = agent.get('id')
print(f'✅ Created agent {agent_id}: {agent.get("agent_name")}')
print(f'   Initial balance: {agent.get("balance")}')

# Test 1: Get wallet info
print('\n=== TEST 1: GET WALLET INFO ===')
resp = requests.get(
    f'http://localhost:8000/api/agents/{agent_id}/wallet',
    headers={'Authorization': f'Bearer {token}'}
)
if resp.status_code == 200:
    wallet = resp.json()['data']
    print(f'✅ Wallet Info:')
    print(f'   Current balance: {wallet["current_balance"]} đ')
    print(f'   Total deposit: {wallet["total_deposit"]} đ')
    print(f'   Daily limit: {wallet["daily_limit"]} đ')
    print(f'   Per transaction: {wallet["per_transaction_limit"]} đ')
else:
    print(f'❌ Failed: {resp.status_code}')
    print(resp.json())

# Test 2: Deposit money
print('\n=== TEST 2: DEPOSIT MONEY ===')
deposit_amount = 5000000
resp = requests.post(
    f'http://localhost:8000/api/agents/{agent_id}/deposit',
    headers={'Authorization': f'Bearer {token}'},
    json={
        'amount': deposit_amount,
        'payment_method': 'bank_transfer',
        'notes': 'Test deposit'
    }
)

if resp.status_code == 200:
    result = resp.json()
    data = result['data']
    print(f'✅ Deposit Success!')
    print(f'   Transaction code: {data["transaction_code"]}')
    print(f'   Amount: {data["amount"]} đ')
    print(f'   Previous balance: {data["previous_balance"]} đ')
    print(f'   New balance: {data["new_balance"]} đ')
else:
    print(f'❌ Deposit Failed: {resp.status_code}')
    error = resp.json()
    print(f'   Error: {error.get("detail", error)}')

# Test 3: Check wallet again
print('\n=== TEST 3: VERIFY BALANCE UPDATE ===')
resp = requests.get(
    f'http://localhost:8000/api/agents/{agent_id}/wallet',
    headers={'Authorization': f'Bearer {token}'}
)
if resp.status_code == 200:
    wallet = resp.json()['data']
    expected = deposit_amount
    actual = int(wallet['current_balance'])
    if actual == expected:
        print(f'✅ Balance Updated Correctly!')
        print(f'   Current balance: {wallet["current_balance"]} đ')
        print(f'   Total deposit: {wallet["total_deposit"]} đ')
    else:
        print(f'⚠️  Balance mismatch!')
        print(f'   Expected: {expected}, Got: {actual}')
else:
    print(f'❌ Failed: {resp.status_code}')

# Test 4: Get deposit history
print('\n=== TEST 4: DEPOSIT HISTORY ===')
resp = requests.get(
    f'http://localhost:8000/api/agents/{agent_id}/deposit-history',
    headers={'Authorization': f'Bearer {token}'}
)
if resp.status_code == 200:
    history = resp.json()
    if history['data']:
        print(f'✅ Deposit History:')
        for deposit in history['data']:
            print(f'   - {deposit["transaction_code"]}: {deposit["amount"]} đ ({deposit["status"]})')
    else:
        print('⚠️  No deposits in history')
else:
    print(f'❌ Failed: {resp.status_code}')

# Test 5: Multiple deposits
print('\n=== TEST 5: MULTIPLE DEPOSITS ===')
for i in range(3):
    resp = requests.post(
        f'http://localhost:8000/api/agents/{agent_id}/deposit',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'amount': 1000000,
            'payment_method': 'cash',
            'notes': f'Deposit {i+1}'
        }
    )
    if resp.status_code == 200:
        result = resp.json()['data']
        print(f'✅ Deposit {i+1}: {result["transaction_code"]} - {result["amount"]} đ')
    else:
        print(f'❌ Deposit {i+1} failed: {resp.status_code}')

# Final check
print('\n=== FINAL CHECK ===')
resp = requests.get(
    f'http://localhost:8000/api/agents/{agent_id}/wallet',
    headers={'Authorization': f'Bearer {token}'}
)
if resp.status_code == 200:
    wallet = resp.json()['data']
    expected_total = deposit_amount + (1000000 * 3)
    actual_total = int(wallet['current_balance'])
    print(f'Final balance: {wallet["current_balance"]} đ')
    print(f'Total deposits: {wallet["total_deposit"]} đ')
    if actual_total == expected_total:
        print(f'✅ ALL TESTS PASSED!')
    else:
        print(f'⚠️  Final balance mismatch')
else:
    print('❌ Final check failed')
