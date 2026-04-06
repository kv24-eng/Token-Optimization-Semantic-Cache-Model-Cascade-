#!/usr/bin/env python3
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'backend')
from dotenv import load_dotenv
load_dotenv()

# Check embeddings directly
from embeddings import get_embedding, get_similarity

print('=' * 70)
print('EMBEDDING SIMILARITY ANALYSIS')
print('=' * 70)
print()

query1 = "what is 2+2?"
query2 = "2+2?"

print(f'Query 1: "{query1}"')
print(f'Query 2: "{query2}"')
print()

# Get embeddings
emb1 = get_embedding(query1)
emb2 = get_embedding(query2)

print(f'Embedding 1 length: {len(emb1)} dimensions')
print(f'Embedding 2 length: {len(emb2)} dimensions')
print()

# Calculate similarity
similarity = get_similarity(query1, query2)
print(f'Cosine Similarity: {similarity:.4f}')
print(f'Threshold: 0.75 (default BASE_SIMILARITY_THRESHOLD)')
print(f'Will be cached: {similarity >= 0.75}')
print()

# Now test with cache
from main import app
from fastapi.testclient import TestClient

print('=' * 70)
print('CACHE PERSISTENCE TEST')
print('=' * 70)
print()

client = TestClient(app)

print('[Step 1] Querying: "what is 2+2?"')
r1 = client.post('/chat', json={'query': query1, 'budget_usd': None})
result1 = r1.json()
print(f'  Result: Cached={result1["was_cached"]}, Model={result1["model_used"]}')
print()

print('[Step 2] Querying: "2+2?" (should use cache)')
r2 = client.post('/chat', json={'query': query2, 'budget_usd': None})
result2 = r2.json()
print(f'  Result: Cached={result2["was_cached"]}, Model={result2["model_used"]}')
if result2.get('similarity'):
    print(f'  Similarity Score: {result2["similarity"]:.4f}')
print()

# Test edge case - very different query
print('[Step 3] Querying: "Hello there, how are you?" (should NOT use cache)')
r3 = client.post('/chat', json={'query': 'Hello there, how are you?', 'budget_usd': None})
result3 = r3.json()
print(f'  Result: Cached={result3["was_cached"]}, Model={result3["model_used"]}')
if result3.get('similarity'):
    print(f'  Similarity Score: {result3["similarity"]:.4f}')
print()

print('=' * 70)
if result2['was_cached'] and not result3['was_cached']:
    print('[OK] Semantic caching working correctly!')
elif result2['was_cached']:
    print('[WARNING] Both similar and dissimilar queries cached')
else:
    print('[ERROR] Similar queries NOT being cached')
print('=' * 70)
