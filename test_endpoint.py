#!/usr/bin/env python3
import sys
sys.path.insert(0, 'backend')
import os
from dotenv import load_dotenv
load_dotenv()

from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# Test the /chat endpoint
print('Testing /chat endpoint...')
try:
    response = client.post('/chat', json={'query': 'what is 2+2?', 'budget_usd': None})
    print(f'Status code: {response.status_code}')
    print(f'Response length: {len(response.text)}')
    print(f'Content-Type: {response.headers.get("content-type")}')
    
    if response.status_code == 200:
        try:
            result = response.json()
            print(f'✅ SUCCESS - Response is valid JSON')
            print(f'Response keys: {list(result.keys())}')
            print(f'Model used: {result.get("model_used")}')
            print(f'Was cached: {result.get("was_cached")}')
            print(f'Answer: {result.get("response", "N/A")[:80]}...')
        except Exception as e:
            print(f'❌ JSON parsing error: {e}')
            print(f'Response text: {response.text[:500]}')
    else:
        print(f'❌ Error response code: {response.status_code}')
        print(f'Response text: {response.text[:500]}')
except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()
