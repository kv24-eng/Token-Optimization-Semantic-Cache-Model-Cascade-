import os
import time
import hashlib
import chromadb
from dotenv import load_dotenv
from embeddings import get_embedding

load_dotenv()

MAX_CACHE_SIZE = 100
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", 0.80))

print("[CACHE] Initializing ChromaDB...")

chroma_client = chromadb.PersistentClient(path="./chroma_db")

collection = chroma_client.get_or_create_collection(
    name="semantic_cache",
    metadata={"hnsw:space": "cosine"}
)

print("[CACHE] ChromaDB ready")


cache_stats = {
    "hits": 0,
    "misses": 0,
    "total_stored": 0,
}


def check_cache(query: str) -> dict | None:

    if collection.count() == 0:
        cache_stats["misses"] += 1
        print("[CACHE] Cache is empty → miss")
        return None

    query_embedding = get_embedding(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=1,
        include=["documents", "metadatas", "distances"]
    )

    distance = results["distances"][0][0]
    similarity = round(1 - distance, 4)

    print(f"[CACHE] Best match similarity: {similarity}")

    if similarity >= SIMILARITY_THRESHOLD:

        cached_response = results["metadatas"][0][0]["response"]
        matched_query = results["documents"][0][0]
        matched_id = results["ids"][0][0]

        collection.update(
            ids=[matched_id],
            metadatas=[{
                "response": cached_response,
                "last_used": time.time()
            }]
        )

        cache_stats["hits"] += 1
        print(f"[CACHE] HIT matched: '{matched_query}'")

        return {
            "response": cached_response,
            "was_cached": True,
            "similarity": similarity,
            "matched_query": matched_query,
        }

    else:
        cache_stats["misses"] += 1
        print(f"[CACHE] MISS similarity {similarity} below threshold {SIMILARITY_THRESHOLD}")
        return None


def store_in_cache(query: str, response: str) -> None:

    query_embedding = get_embedding(query)

    doc_id = hashlib.md5(query.encode()).hexdigest()

    current_count = collection.count()

    if current_count >= MAX_CACHE_SIZE:

        results = collection.get(include=["metadatas", "ids"])
        ids = results["ids"]
        metadatas = results["metadatas"]

        sorted_items = sorted(
            zip(ids, metadatas),
            key=lambda x: x[1].get("last_used", 0)
        )

        num_to_delete = current_count - MAX_CACHE_SIZE + 1
        ids_to_delete = [item[0] for item in sorted_items[:num_to_delete]]

        collection.delete(ids=ids_to_delete)
        print(f"[CACHE] Removed {len(ids_to_delete)} LRU entries")

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
    print(f"[CACHE] Stored query: '{query}'")


def clear_cache() -> None:

    global collection

    chroma_client.delete_collection("semantic_cache")

    collection = chroma_client.get_or_create_collection(
        name="semantic_cache",
        metadata={"hnsw:space": "cosine"}
    )

    cache_stats["hits"] = 0
    cache_stats["misses"] = 0
    cache_stats["total_stored"] = 0

    print("[CACHE] Cache cleared")


def get_cache_stats() -> dict:

    total = cache_stats["hits"] + cache_stats["misses"]

    hit_rate = (
        round((cache_stats["hits"] / total) * 100, 1)
        if total > 0 else 0
    )

    return {
        **cache_stats,
        "hit_rate_percent": hit_rate,
        "total_queries": total,
    }
