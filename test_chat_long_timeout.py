import requests
import sys

try:
    resp = requests.post(
        'http://localhost:8000/chat',
        json={'query': 'What is Python?', 'budget_usd': None},
        timeout=120  # 2 minute timeout
    )
    print(f'Status: {resp.status_code}')
    if resp.status_code == 200:
        data = resp.json()
        print(f'Model used: {data["model_used"]}')
        print(f'Cache hit: {data["was_cached"]}')
        print(f'Response length: {len(data["response"])} chars')
        print(f'✓ Success: Chat endpoint is working!')
        sys.exit(0)
    else:
        print(f'Error: {resp.text}')
        sys.exit(1)
except requests.exceptions.Timeout:
    print('Request timed out after 120 seconds')
    sys.exit(1)
except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)
