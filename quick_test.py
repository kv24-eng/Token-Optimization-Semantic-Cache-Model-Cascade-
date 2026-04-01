#!/usr/bin/env python3
"""Quick test to verify semantic cache is working"""
import requests
import sys

API_BASE_URL = "http://localhost:8000"

print("Testing semantic cache...\n")

# Query 1
print("1. Sending: 'What is Python?'")
r1 = requests.post(f"{API_BASE_URL}/chat", 
    json={"query": "What is Python?", "budget_usd": None}, 
    timeout=120)
print(f"   Status: {r1.status_code}, Cache hit: {r1.json()['was_cached']}")

# Query 2 - semantic variant
print("\n2. Sending: 'what is python?' (lowercase)")
r2 = requests.post(f"{API_BASE_URL}/chat", 
    json={"query": "what is python?", "budget_usd": None}, 
    timeout=120)
data2 = r2.json()
print(f"   Status: {r2.status_code}, Cache hit: {data2['was_cached']}")
if data2['was_cached']:
    print(f"   ✓ Semantic cache HIT!")
    print(f"   Similarity: {data2.get('similarity')}")
    print(f"   Matched: '{data2.get('matched_query')}'")
else:
    print(f"   ✗ Should have hit cache")
