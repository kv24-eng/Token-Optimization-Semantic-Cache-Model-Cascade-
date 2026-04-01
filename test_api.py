#!/usr/bin/env python3
"""
Test script to verify the API and cache are working.
Run this with the backend running (python backend/main.py)
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_api_health():
    """Test if API is running"""
    try:
        resp = requests.get(f"{BASE_URL}/")
        print(f"✅ API is running: {resp.json()}")
        return True
    except:
        print("❌ API is NOT running. Start it with: python backend/main.py")
        return False

def test_chat_query(query: str, budget_usd: float = 0.1):
    """Make a test query"""
    print(f"\n📝 Query: {query}")
    
    resp = requests.post(
        f"{BASE_URL}/chat",
        json={
            "query": query,
            "budget_usd": budget_usd
        }
    )
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"   Model: {data['model_used']} ({data['tier']})")
        print(f"   Was cached: {data['was_cached']}")
        print(f"   Response: {data['response'][:100]}...")
        print(f"   Latency: {data['latency_ms']}ms")
        print(f"   Cost: ${data['cost_usd']:.6f}")
        return True
    else:
        print(f"   ❌ Error: {resp.status_code}")
        print(f"   {resp.text}")
        return False

def test_cache_view():
    """View cached items"""
    print(f"\n🗂️ Getting cached items...")
    
    resp = requests.get(f"{BASE_URL}/cache/items")
    
    if resp.status_code == 200:
        data = resp.json()
        total = data.get("total_items", 0)
        print(f"   ✅ Found {total} items in cache")
        
        items = data.get("items", [])
        for item in items[:3]:  # Show first 3
            query = item.get("query", "N/A")[:50]
            print(f"      • {query}...")
        return True
    else:
        print(f"   ❌ Error: {resp.status_code}")
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 API & CACHE TEST")
    print("="*60)
    
    if not test_api_health():
        exit(1)
    
    # Make 2 queries
    print("\n" + "-"*60)
    print("📤 Sending queries...")
    print("-"*60)
    
    test_chat_query("What is artificial intelligence?", budget_usd=0.5)
    time.sleep(1)
    
    # Second query - should be different or cache hit
    test_chat_query("Tell me about AI", budget_usd=0.5)
    time.sleep(1)
    
    # Check cache
    print("\n" + "-"*60)
    test_cache_view()
    
    print("\n" + "="*60)
    print("✅ Test complete! Check cache in Streamlit frontend.")
    print("="*60 + "\n")
