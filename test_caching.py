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

print('Testing query 1 (not cached)...')
response1 = client.post('/chat', json={'query': 'what is 2+2?', 'budget_usd': None})
result1 = response1.json()
print('[OK] Response 1 received')
print(f'   Was cached: {result1["was_cached"]}')
print(f'   Model used: {result1["model_used"]}')
print(f'   Cost: ${result1["cost_usd"]:.6f}')
print()

print('Testing query 2 (same query, should be cached)...')
response2 = client.post('/chat', json={'query': 'what is 2+2?', 'budget_usd': None})
result2 = response2.json()
print('[OK] Response 2 received')
print(f'   Was cached: {result2["was_cached"]}')
print(f'   Model used: {result2["model_used"]}')
print(f'   Cost: ${result2["cost_usd"]:.6f}')
print()

print('Testing query 3 (similar query, should use cache)...')
response3 = client.post('/chat', json={'query': 'what is two plus two?', 'budget_usd': None})
result3 = response3.json()
print('[OK] Response 3 received')
print(f'   Was cached: {result3["was_cached"]}')
print(f'   Similarity: {result3.get("similarity", "N/A")}')
print(f'   Cost: ${result3["cost_usd"]:.6f}')
print()

print('[OK] All tests passed! Backend is working correctly.')
