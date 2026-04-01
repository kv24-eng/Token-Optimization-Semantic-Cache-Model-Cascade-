#!/usr/bin/env python3
"""
Test script to verify smart cache deletion features.
Run this with the backend running.
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def pretty_print(title, data):
    """Pretty print JSON data"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    print(json.dumps(data, indent=2))

print("\n🧪 SMART CACHE DELETION TEST\n")

# 1. Get cache summary
print("📊 Step 1: Get cache summary with clusters...")
try:
    response = requests.get(f"{BASE_URL}/cache/summary", timeout=15)
    if response.status_code == 200:
        summary = response.json()
        pretty_print("Cache Summary", {
            "total_items": summary["total_items"],
            "total_clusters": summary["total_clusters"],
            "clusters_count": len(summary["clusters"])
        })
        
        if summary["total_clusters"] > 0:
            print("\n📋 Clusters found:")
            for cluster in summary["clusters"][:2]:  # Show first 2
                print(f"   • Cluster {cluster['cluster_id']}: '{cluster['primary_query'][:50]}...'")
                print(f"     - Duplicates: {cluster['duplicate_count']}")
                print(f"     - Avg Similarity: {cluster['avg_similarity']}")
    else:
        print(f"❌ Error: {response.status_code}")
except Exception as e:
    print(f"❌ Failed: {e}")

# 2. List all items
print("\n" + "="*60)
print("📋 Step 2: Get all cached items...")
try:
    response = requests.get(f"{BASE_URL}/cache/items", timeout=15)
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Total items: {data['total_items']}")
        if data['items']:
            print("\n   First 3 items:")
            for item in data['items'][:3]:
                print(f"   • ID: {item['id']}")
                print(f"     Query: {item['query'][:60]}...")
    else:
        print(f"❌ Error: {response.status_code}")
except Exception as e:
    print(f"❌ Failed: {e}")

# 3. Try deleting specific items (if any exist)
print("\n" + "="*60)
print("🗑️  Step 3: Test delete specific items...")
try:
    response = requests.get(f"{BASE_URL}/cache/items", timeout=15)
    items = response.json()["items"]
    
    if len(items) > 1:
        # Delete first item
        item_to_delete = items[0]
        print(f"\nDeleting item: {item_to_delete['query'][:50]}...")
        
        del_response = requests.post(
            f"{BASE_URL}/cache/delete",
            json={"item_ids": [item_to_delete["id"]]},
            timeout=15
        )
        
        if del_response.status_code == 200:
            result = del_response.json()
            pretty_print("Delete Result", result)
        else:
            print(f"❌ Delete failed: {del_response.status_code}")
    else:
        print("ℹ️  Not enough items to test deletion")
except Exception as e:
    print(f"❌ Failed: {e}")

# 4. Test cluster deletion
print("\n" + "="*60)
print("🗑️  Step 4: Test delete cluster (keep primary)...")
try:
    response = requests.get(f"{BASE_URL}/cache/summary", timeout=15)
    summary = response.json()
    
    if summary["total_clusters"] > 0 and summary["clusters"][0]["duplicate_count"] > 0:
        cluster = summary["clusters"][0]
        print(f"\nDeleting duplicates in cluster {cluster['cluster_id']}")
        print(f"Primary: {cluster['primary_query'][:50]}...")
        print(f"Duplicates to remove: {cluster['duplicate_count']}")
        
        cluster_response = requests.post(
            f"{BASE_URL}/cache/delete-cluster",
            json={
                "cluster_id": cluster["cluster_id"],
                "keep_primary": True,
                "reason": "Test deletion"
            },
            timeout=15
        )
        
        if cluster_response.status_code == 200:
            result = cluster_response.json()
            pretty_print("Cluster Delete Result", result)
        else:
            print(f"❌ Cluster delete failed: {cluster_response.status_code}")
    else:
        print("ℹ️  No clusters with duplicates found")
except Exception as e:
    print(f"❌ Failed: {e}")

print("\n" + "="*60)
print("✅ Smart cache deletion test complete!")
print("="*60 + "\n")
