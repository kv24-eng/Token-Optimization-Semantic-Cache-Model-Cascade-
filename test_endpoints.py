import requests
import json

endpoints = [
    ('GET', '/cache/items'),
    ('GET', '/metrics'),
    ('GET', '/routing/explain', {'query': 'test'}),
    ('GET', '/cache/summary'),
    ('POST', '/chat', {'query': 'hello', 'budget_usd': None}),
]

for method, endpoint, *params in endpoints:
    try:
        url = f'http://localhost:8000{endpoint}'
        if method == 'GET':
            resp = requests.get(url, params=params[0] if params else None, timeout=5)
        else:
            resp = requests.post(url, json=params[0] if params else {}, timeout=5)
        
        print(f'{method} {endpoint}: {resp.status_code}')
        if resp.status_code >= 400:
            print(f'  Response: {resp.text[:200]}')
    except Exception as e:
        print(f'{method} {endpoint}: ERROR - {str(e)[:100]}')
