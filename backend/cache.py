import os
import chromadb
from embeddings import get_embedding
from dotenv import load_dotenv
import time

load_dotenv()
MAX_CACHE_SIZE = 100
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", 0.80))

# ── Initialize ChromaDB ───────────────────────────────
# Stores data locally in a folder called chroma_db/
print("[CACHE] Initializing ChromaDB...")
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(
    name="semantic_cache",
    metadata={"hnsw:space": "cosine"}  # use cosine similarity
)
print("[CACHE] ChromaDB ready")


# ── In-memory stats ───────────────────────────────────
cache_stats = {
    "hits": 0,
    "misses": 0,
    "total_stored": 0,
}


# ── Core Functions ────────────────────────────────────

def check_cache(query: str) -> dict | None:
    """
    Check if a semantically similar query exists in cache.

    Returns cached response dict if found, None if not.
    """

    # Need at least 1 item in cache to query
    if collection.count() == 0:
        cache_stats["misses"] += 1
        print(f"[CACHE] Cache is empty → miss")
        return None

    # Embed the incoming query
    query_embedding = get_embedding(query)

    # Search ChromaDB for the most similar stored query
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=1,
        include=["documents", "metadatas", "distances"]
    )

    # ChromaDB cosine distance → convert to similarity
    # distance = 1 - similarity, so similarity = 1 - distance
    distance   = results["distances"][0][0]
    similarity = round(1 - distance, 4)

    print(f"[CACHE] Best match similarity: {similarity}")

   if similarity >= SIMILARITY_THRESHOLD:
    cached_response = results["metadatas"][0][0]["response"]
    matched_query   = results["documents"][0][0]
    matched_id      = results["ids"][0][0]

    # Update LRU timestamp
    collection.update(
        ids=[matched_id],
        metadatas=[{
            "response": cached_response,
            "last_used": time.time()
        }]
    )

    cache_stats["hits"] += 1
    print(f"[CACHE] HIT ✅ matched: '{matched_query}'")

    return {
        "response":       cached_response,
        "was_cached":     True,
        "similarity":     similarity,
        "matched_query":  matched_query,
    }
    cache_stats["misses"] += 1
    print(f"[CACHE] MISS ❌ similarity {similarity} below threshold {SIMILARITY_THRESHOLD}")
    return None


    def store_in_cache(query: str, response: str) -> None:
    query_embedding = get_embedding(query)
    doc_id = str(abs(hash(query)))

    # Enforce max cache size using LRU
    current_count = collection.count()

    if current_count >= MAX_CACHE_SIZE:
        results = collection.get(include=["metadatas", "ids"])
        ids = results["ids"]
        metadatas = results["metadatas"]

        # Sort by last_used (oldest first)
        sorted_items = sorted(
            zip(ids, metadatas),
            key=lambda x: x[1].get("last_used", 0)
        )

        num_to_delete = current_count - MAX_CACHE_SIZE + 1
        ids_to_delete = [item[0] for item in sorted_items[:num_to_delete]]

        collection.delete(ids=ids_to_delete)
        print(f"[CACHE] Removed {len(ids_to_delete)} LRU entries")

    # Insert new entry with timestamp
    collection.upsert(
        ids=[doc_id],
        embeddings=[query_embedding],
        documents=[query],
        metadatas=[{
            "response": response,
            "last_used": time.time()
        }]
    )

    cache_stats["total_stored"] += 1
    print(f"[CACHE] Stored query in cache: '{query}'")


def clear_cache() -> None:
    """
    Wipe all stored queries from the cache.
    """
    global collection

    chroma_client.delete_collection("semantic_cache")
    collection = chroma_client.get_or_create_collection(
        name="semantic_cache",
        metadata={"hnsw:space": "cosine"}
    )

    cache_stats["hits"]          = 0
    cache_stats["misses"]        = 0
    cache_stats["total_stored"]  = 0

    print("[CACHE] Cache cleared ✅")


def get_cache_stats() -> dict:
    """
    Return current cache performance stats.
    """
    total = cache_stats["hits"] + cache_stats["misses"]
    hit_rate = (
        round((cache_stats["hits"] / total) * 100, 1) if total > 0 else 0
    )

    return {
        **cache_stats,
        "hit_rate_percent": hit_rate,
        "total_queries":    total,
    }
