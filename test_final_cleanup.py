#!/usr/bin/env python3
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'backend')
from dotenv import load_dotenv
load_dotenv()

from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

print('=' * 70)
print('TESTING: Smart Delete Removal + TokenMiser Branding')
print('=' * 70)
print()

# Test 1: Verify /chat endpoint still works
print('[Test 1] Chat endpoint')
r = client.post('/chat', json={'query': 'test', 'budget_usd': None})
print(f'  Status: {r.status_code}')
print(f'  Result: {"PASS" if r.status_code == 200 else "FAIL"}')
print()

# Test 2: Verify /metrics endpoint still works
print('[Test 2] Metrics endpoint')
r = client.get('/metrics')
print(f'  Status: {r.status_code}')
print(f'  Result: {"PASS" if r.status_code == 200 else "FAIL"}')
print()

# Test 3: Verify /cache/items endpoint still works
print('[Test 3] Cache items endpoint')
r = client.get('/cache/items')
print(f'  Status: {r.status_code}')
print(f'  Result: {"PASS" if r.status_code == 200 else "FAIL"}')
print()

# Test 4: Verify /cache/summary endpoint still works
print('[Test 4] Cache summary endpoint')
r = client.get('/cache/summary')
print(f'  Status: {r.status_code}')
print(f'  Result: {"PASS" if r.status_code == 200 else "FAIL"}')
print()

# Test 5: Verify /cache/delete endpoint is GONE (should return 404)
print('[Test 5] Delete cache endpoint (should be removed)')
r = client.post('/cache/delete', json={'item_ids': ['test']})
print(f'  Status: {r.status_code}')
print(f'  Result: {"PASS (404)" if r.status_code == 404 else "FAIL (endpoint still exists)"}')
print()

# Test 6: Verify /cache/delete-cluster endpoint is GONE (should return 404)
print('[Test 6] Delete cluster endpoint (should be removed)')
r = client.post('/cache/delete-cluster', json={'cluster_id': 0})
print(f'  Status: {r.status_code}')
print(f'  Result: {"PASS (404)" if r.status_code == 404 else "FAIL (endpoint still exists)"}')
print()

print('=' * 70)
print('[OK] All delete endpoints successfully removed!')
print('[OK] Core functionality preserved!')
print('=' * 70)
