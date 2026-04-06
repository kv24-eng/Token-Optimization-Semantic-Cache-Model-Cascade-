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

print('=' * 60)
print('SEMANTIC CACHE SIMILARITY TEST')
print('=' * 60)
print()

# First query - store in cache
print('Query 1: "what is 2+2?"')
response1 = client.post('/chat', json={'query': 'what is 2+2?', 'budget_usd': None})
result1 = response1.json()
print(f'   Status: {response1.status_code}')
print(f'   Was cached: {result1["was_cached"]}')
print(f'   Model used: {result1["model_used"]}')
print(f'   Response: {result1["response"][:50]}...')
print()

# Second query - very similar phrasing
print('Query 2: "2+2?" (shorter version)')
response2 = client.post('/chat', json={'query': '2+2?', 'budget_usd': None})
result2 = response2.json()
print(f'   Status: {response2.status_code}')
print(f'   Was cached: {result2["was_cached"]}')
print(f'   Model used: {result2["model_used"]}')
if result2.get("similarity"):
    print(f'   Similarity: {result2["similarity"]}')
if result2.get("matched_query"):
    print(f'   Matched query: {result2["matched_query"]}')
print(f'   Response: {result2["response"][:50]}...')
print()

# Check what happened
print('=' * 60)
if result2['was_cached']:
    print('PASS: Query 2 was matched from cache (semantic similarity working)')
else:
    print('FAIL: Query 2 was NOT matched from cache (semantic similarity broken)')
    if result2.get('similarity'):
        sim = result2['similarity']
        print(f'  Computed similarity: {sim}')
        print(f'  Threshold: 0.75 (default)')
        if sim < 0.75:
            print(f'  Issue: Similarity too low ({sim:.3f} < 0.75)')
        else:
            print(f'  Issue: Similarity passed but still not cached???')
print('=' * 60)
