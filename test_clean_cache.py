#!/usr/bin/env python3
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'backend')
from dotenv import load_dotenv
load_dotenv()

# Clear cache first
import shutil
cache_dir = os.path.join(os.path.dirname(__file__), "chroma_db")
if os.path.exists(cache_dir):
    shutil.rmtree(cache_dir)
    print(f"[CLEANUP] Removed old cache: {cache_dir}")
print()

from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

print('=' * 80)
print('SEMANTIC CACHE TEST (Fresh Cache)')
print('=' * 80)
print()

# Test 1: First query
print('[Test 1] Query: "what is 2+2?"')
r1 = client.post('/chat', json={'query': 'what is 2+2?', 'budget_usd': None})
result1 = r1.json()
print(f'  Response 1:')
print(f'    - Was cached: {result1["was_cached"]}')
print(f'    - Model used: {result1["model_used"]}')
print(f'    - Cost: ${result1["cost_usd"]:.6f}')
print()

# Test 2: Identical query
print('[Test 2] Query: "what is 2+2?" (identical)')
r2 = client.post('/chat', json={'query': 'what is 2+2?', 'budget_usd': None})
result2 = r2.json()
print(f'  Response 2:')
print(f'    - Was cached: {result2["was_cached"]}')
print(f'    - Model used: {result2["model_used"]}')
print(f'    - Cost: ${result2["cost_usd"]:.6f}')
print()

# Test 3: Similar query
print('[Test 3] Query: "2+2?" (similar, shorter)')
r3 = client.post('/chat', json={'query': '2+2?', 'budget_usd': None})
result3 = r3.json()
print(f'  Response 3:')
print(f'    - Was cached: {result3["was_cached"]}')
print(f'    - Model used: {result3["model_used"]}')
if result3.get('similarity'):
    print(f'    - Similarity: {result3["similarity"]:.4f}')
print(f'    - Cost: ${result3["cost_usd"]:.6f}')
print()

# Test 4: Different query
print('[Test 4] Query: "Hello world" (dissimilar)')
r4 = client.post('/chat', json={'query': 'Hello world', 'budget_usd': None})
result4 = r4.json()
print(f'  Response 4:')
print(f'    - Was cached: {result4["was_cached"]}')
print(f'    - Model used: {result4["model_used"]}')
if result4.get('similarity'):
    print(f'    - Similarity: {result4["similarity"]:.4f}')
print(f'    - Cost: ${result4["cost_usd"]:.6f}')
print()

# Verification
print('=' * 80)
print('RESULTS:')
print('=' * 80)
passed = []
failed = []

if not result1['was_cached']:
    passed.append("Test 1: First query correctly NOT cached (called LLM)")
else:
    failed.append("Test 1: First query should NOT be cached")

if result2['was_cached'] and result2['cost_usd'] == 0:
    passed.append("Test 2: Identical query correctly cached (0 cost)")
else:
    failed.append(f"Test 2: Identical query should be cached (was_cached={result2['was_cached']}, cost={result2['cost_usd']})")

if result3['was_cached'] and result3.get('similarity', 0) >= 0.75:
    passed.append(f"Test 3: Similar query cached with similarity={result3.get('similarity'):.4f}")
else:
    failed.append(f"Test 3: Similar query not cached (similarity={result3.get('similarity', 'N/A')})")

if not result4['was_cached']:
    passed.append("Test 4: Dissimilar query correctly NOT cached (called new LLM)")
else:
    failed.append("Test 4: Dissimilar query should NOT be cached")

print()
for msg in passed:
    print(f"  [PASS] {msg}")
for msg in failed:
    print(f"  [FAIL] {msg}")

print()
if not failed:
    print('[SUCCESS] All semantic caching tests passed!')
else:
    print(f'[ERROR] {len(failed)} test(s) failed')
