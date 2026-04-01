#!/usr/bin/env python3
"""
Debug script to verify cache is working correctly.
Run this after making some queries in the frontend.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from cache import get_all_cached_items, collection, get_cache_stats

print("\n" + "="*60)
print("🔍 CACHE DEBUG REPORT")
print("="*60)

# Check total items in ChromaDB
total_count = collection.count()
print(f"\n📊 Collection Count: {total_count} items")

# Get stats
stats = get_cache_stats()
print(f"\n📈 Cache Statistics:")
print(f"   • Hits: {stats.get('hits', 0)}")
print(f"   • Misses: {stats.get('misses', 0)}")
print(f"   • Total Stored: {stats.get('total_stored', 0)}")

# Get all cached items
print(f"\n📋 Cached Items:")
items = get_all_cached_items()

if not items:
    print("   ❌ No items cached yet!")
else:
    print(f"   ✅ Found {len(items)} cached items:\n")
    for i, item in enumerate(items, 1):
        query = item.get("query", "N/A")[:60]
        timestamp = item.get("last_used_formatted", "N/A")
        resp_len = len(item.get("response", ""))
        print(f"   {i}. Query: '{query}...'")
        print(f"      Last used: {timestamp}")
        print(f"      Response length: {resp_len} chars\n")

print("="*60)
print("Run 'python debug_cache.py' again after making more queries\n")
