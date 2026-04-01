#!/usr/bin/env python3
"""Test cache clear functionality"""
import requests
import sys

API_BASE_URL = "http://localhost:8000"

print("=" * 70)
print("CACHE CLEAR TEST")
print("=" * 70)

# Check initial cache status
print("\n[STEP 1] Checking initial cache status...")
resp = requests.get(f"{API_BASE_URL}/cache/items", timeout=15)
if resp.status_code == 200:
    data = resp.json()
    print(f"Current cache items: {data['total_items']}")
else:
    print(f"Error: {resp.status_code}")
    sys.exit(1)

# Clear cache
print("\n[STEP 2] Clearing cache...")
clear_resp = requests.delete(f"{API_BASE_URL}/cache/clear", timeout=15)

if clear_resp.status_code == 200:
    result = clear_resp.json()
    print(f"Response: {result}")
    print("✓ Cache clear request successful")
    
    # Verify cache is empty
    print("\n[STEP 3] Verifying cache is empty...")
    resp2 = requests.get(f"{API_BASE_URL}/cache/items", timeout=15)
    if resp2.status_code == 200:
        data2 = resp2.json()
        print(f"Cache items after clear: {data2['total_items']}")
        
        if data2['total_items'] == 0:
            print("✓ Cache cleared successfully!")
        else:
            print(f"✗ Cache not empty - still has {data2['total_items']} items")
            sys.exit(1)
    else:
        print(f"Error checking cache: {resp2.status_code}")
        sys.exit(1)
else:
    print(f"✗ Error: {clear_resp.status_code}")
    print(f"Response: {clear_resp.text}")
    sys.exit(1)

print("\n" + "=" * 70)
print("✓ CACHE CLEAR TEST PASSED!")
print("=" * 70)
