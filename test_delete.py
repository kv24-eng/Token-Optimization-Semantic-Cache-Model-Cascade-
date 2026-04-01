#!/usr/bin/env python3
"""Test cache deletion functionality"""
import requests
import sys

API_BASE_URL = "http://localhost:8000"

print("=" * 70)
print("CACHE DELETION TEST")
print("=" * 70)

# First, check current cache status
print("\n[STEP 1] Checking current cache status...")
resp = requests.get(f"{API_BASE_URL}/cache/items", timeout=15)
if resp.status_code == 200:
    data = resp.json()
    print(f"Current cache items: {data['total_items']}")
    items = data.get('items', [])
    for idx, item in enumerate(items, 1):
        print(f"  {idx}. ID: {item['id'][:8]}... Query: {item['query'][:50]}...")
else:
    print(f"Error: {resp.status_code}")
    sys.exit(1)

if data['total_items'] == 0:
    print("\n⚠️ Cache is empty. Add some queries first!")
    sys.exit(1)

# Delete first item
if items:
    print(f"\n[STEP 2] Attempting to delete first item: {items[0]['id']}")
    delete_resp = requests.post(
        f"{API_BASE_URL}/cache/delete",
        json={"item_ids": [items[0]['id']]},
        timeout=15
    )
    
    if delete_resp.status_code == 200:
        result = delete_resp.json()
        print(f"Response: {result}")
        
        if result.get("success"):
            print(f"✓ Deleted {result['deleted_count']} item(s)")
            
            # Verify deletion
            print("\n[STEP 3] Verifying deletion...")
            resp2 = requests.get(f"{API_BASE_URL}/cache/items", timeout=15)
            data2 = resp2.json()
            print(f"Remaining cache items: {data2['total_items']}")
            if data2['total_items'] < data['total_items']:
                print("✓ Cache deletion working!")
            else:
                print("✗ Item was not deleted")
        else:
            print(f"✗ Delete failed: {result.get('error')}")
    else:
        print(f"Error: {delete_resp.status_code}")
        print(f"Response: {delete_resp.text[:300]}")

print("\n" + "=" * 70)
