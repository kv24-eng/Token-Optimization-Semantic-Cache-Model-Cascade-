from cache import check_cache, store_in_cache, get_cache_stats

# Store a query
store_in_cache(
    "How do I reset my password?",
    "You can reset your password by clicking Forgot Password on the login page."
)

# Test exact same query
result = check_cache("How do I reset my password?")
print(f"Exact match: {result}")

# Test semantically similar query
result = check_cache("I forgot my password, what do I do?")
print(f"Similar match: {result}")

# Test unrelated query
result = check_cache("i am stuck , what do i do?")
print(f"Unrelated: {result}")

# Stats
print(get_cache_stats())
