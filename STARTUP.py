#!/usr/bin/env python3
"""
Quick startup guide for the Token Optimization System with Semantic Cache
"""

import time
import subprocess
import sys
import platform

print("\n" + "="*70)
print(" 🚀 STARTUP GUIDE - Token Optimization & Semantic Cache System")
print("="*70 + "\n")

print("📋 STEPS TO RUN:\n")

if platform.system() == "Windows":
    print("1️⃣  START BACKEND (First terminal):")
    print("    cd backend")
    print("    python -m uvicorn main:app --host 0.0.0.0 --port 8000\n")
    
    print("2️⃣  START FRONTEND (Second terminal):")
    print("    streamlit run frontend/streamlit_app.py\n")
    
    print("3️⃣  OR RUN BOTH TOGETHER (One terminal):")
    print("    powershell -ExecutionPolicy ByPass -File run_all.ps1\n")
else:
    print("1️⃣  START BACKEND (First terminal):")
    print("    cd backend")
    print("    python -m uvicorn main:app --host 0.0.0.0 --port 8000\n")
    
    print("2️⃣  START FRONTEND (Second terminal):")
    print("    streamlit run frontend/streamlit_app.py\n")

print("🌐 ACCESS POINTS:\n")
print("   • Frontend:     http://localhost:8501")
print("   • API:          http://localhost:8000")
print("   • API Docs:     http://localhost:8000/docs\n")

print("⏱️  TIMING NOTES:\n")
print("   • Backend startup: ~5 seconds")
print("   • First API call: ~8 seconds (embedding model loads on first use)")
print("   • Subsequent calls: <2 seconds")
print("   • API timeouts: 15-30 seconds (should be sufficient)\n")

print("🧪 TEST QUERIES:\n")
print("   • 'What is artificial intelligence?'")
print("   • 'Tell me about AI'  (should match first query from cache)")
print("   • 'How does machine learning work?'\n")

print("📊 EXPECTED BEHAVIOR:\n")
print("   1. First query: Calls Groq API (3-8 seconds), model: llama-3.1-8b")
print("   2. Similar query: Returns from cache instantly (cache HIT)")
print("   3. Complex query: Routes to llama-3.3-70b (MID tier)")
print("   4. Cache tab shows all cached queries\n")

print("❌ TROUBLESHOOTING:\n")
print("   • Timeout errors: Backend still initializing (wait 10 seconds)")
print("   • 'Module not found' errors: Check .venv is activated")
print("   • Cache empty: Make queries first, then refresh cache tab")
print("   • API not responding: Check port 8000 not in use\n")

print("🔍 DEBUG COMMANDS:\n")
print("   python debug_cache.py     # Show all cached items")
print("   python test_api.py        # Test API with sample queries\n")

print("="*70 + "\n")
