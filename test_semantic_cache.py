import requests
import time
import sys

API_BASE_URL = "http://localhost:8000"

print("=" * 70)
print("SEMANTIC CACHE TEST")
print("=" * 70)

# Test 1: First query (should miss cache, call API)
print("\n[TEST 1] First query - should MISS cache and call API")
query1 = "What is Python?"
resp1 = requests.post(f"{API_BASE_URL}/chat", json={"query": query1, "budget_usd": None}, timeout=120)
if resp1.status_code == 200:
    data1 = resp1.json()
    print(f"Query: {query1}")
    print(f"Cache hit: {data1['was_cached']}")
    print(f"Model used: {data1['model_used']}")
    print(f"Response length: {len(data1['response'])} chars")
    assert not data1['was_cached'], "First query should miss cache"
    print("✓ Test 1 passed\n")
else:
    print(f"Error: {resp1.text}\n")
    sys.exit(1)

# Small delay
time.sleep(1)

# Test 2: Semantically similar query (should hit cache)
print("[TEST 2] Semantically similar query - should HIT cache")
query2 = "What is python?"  # lowercase, same meaning
resp2 = requests.post(f"{API_BASE_URL}/chat", json={"query": query2, "budget_usd": None}, timeout=120)
if resp2.status_code == 200:
    data2 = resp2.json()
    print(f"Query: {query2}")
    print(f"Cache hit: {data2['was_cached']}")
    print(f"Matched query: {data2.get('matched_query', 'N/A')}")
    print(f"Similarity: {data2.get('similarity', 'N/A')}")
    
    if data2['was_cached']:
        print("✓ Test 2 passed - Semantic cache working!\n")
    else:
        print("✗ Test 2 FAILED - Should have hit cache\n")
        sys.exit(1)
else:
    print(f"Error: {resp2.text}\n")
    sys.exit(1)

# Test 3: Another semantic variant
print("[TEST 3] Another semantic variant - should HIT cache")
query3 = "python - what is it?"  # Different phrasing, same meaning
resp3 = requests.post(f"{API_BASE_URL}/chat", json={"query": query3, "budget_usd": None}, timeout=120)
if resp3.status_code == 200:
    data3 = resp3.json()
    print(f"Query: {query3}")
    print(f"Cache hit: {data3['was_cached']}")
    print(f"Matched query: {data3.get('matched_query', 'N/A')}")
    print(f"Similarity: {data3.get('similarity', 'N/A')}")
    
    if data3['was_cached']:
        print("✓ Test 3 passed - Semantic cache working!\n")
    else:
        print("✗ Test 3 FAILED - Should have hit cache\n")
        sys.exit(1)
else:
    print(f"Error: {resp3.text}\n")
    sys.exit(1)

# Test 4: Different query (should miss cache)
print("[TEST 4] Different query - should MISS cache and call API")
query4 = "Explain machine learning concepts"  # Completely different
resp4 = requests.post(f"{API_BASE_URL}/chat", json={"query": query4, "budget_usd": None}, timeout=120)
if resp4.status_code == 200:
    data4 = resp4.json()
    print(f"Query: {query4}")
    print(f"Cache hit: {data4['was_cached']}")
    print(f"Model used: {data4['model_used']}")
    
    if not data4['was_cached']:
        print("✓ Test 4 passed - Correctly missed for different query\n")
    else:
        print("✗ Test 4 FAILED - Should have missed cache\n")
        sys.exit(1)
else:
    print(f"Error: {resp4.text}\n")
    sys.exit(1)

print("=" * 70)
print("✓ ALL SEMANTIC CACHE TESTS PASSED!")
print("=" * 70)
