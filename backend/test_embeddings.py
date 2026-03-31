from embeddings import get_embedding, get_similarity

# Test 1 — Get embedding shape
vec = get_embedding("Hello world")
print(f"Embedding dimensions: {len(vec)}")  # Should print 384

# Test 2 — Similar sentences should score high
score1 = get_similarity(
    "How do I reset my password?",
    "I forgot my password, what should I do?"
)
print(f"Similar sentences: {score1}")  # Should be > 0.85

# Test 3 — Unrelated sentences should score low
score2 = get_similarity(
    "How do I reset my password?",
    "What is the capital of France?"
)
print(f"Unrelated sentences: {score2}")