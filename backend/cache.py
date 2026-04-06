
import os
import sys
import time
import hashlib
import chromadb
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))

from embeddings import get_embedding

load_dotenv()

MAX_CACHE_SIZE = 100
BASE_SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", 0.80))

print("[CACHE] Initializing ChromaDB...")

# Use absolute path to ensure cache persists regardless of working directory
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
CACHE_DIR = os.path.abspath(CACHE_DIR)  # Convert to absolute path
chroma_client = chromadb.PersistentClient(path=CACHE_DIR)

collection = chroma_client.get_or_create_collection(
    name="semantic_cache",
    metadata={"hnsw:space": "cosine"}
)

print(f"[CACHE] Using cache directory: {CACHE_DIR}")
print(f"[CACHE] ChromaDB collection ready")


cache_stats = {
    "hits": 0,
    "misses": 0,
    "total_stored": 0,
}


def get_dynamic_threshold(smart_score: float | None):
    if smart_score is None:
        return BASE_SIMILARITY_THRESHOLD

    if smart_score > 0.8:
        return 0.9
    elif smart_score > 0.5:
        return 0.8
    else:
        return 0.7

def compute_confidence(similarity, last_used, hit_count):
    now = time.time()

    # Recency score (decay over time)
    age = now - last_used if last_used else 1
    recency_score = 1 / (1 + age / 3600)  # decay per hour

    # Frequency score
    freq_score = min(1.0, hit_count / 10)

    confidence = (
        0.6 * similarity +
        0.2 * recency_score +
        0.2 * freq_score
    )

    return round(confidence, 4)


def check_cache(query: str, smart_score: float | None = None) -> dict | None:

    if collection.count() == 0:
        cache_stats["misses"] += 1
        return None

    query_embedding = get_embedding(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=1,
        include=["documents", "metadatas", "distances"]
    )

    distance = results["distances"][0][0]
    similarity = 1 - distance

    metadata = results["metadatas"][0][0]
    matched_query = results["documents"][0][0]
    matched_id = results["ids"][0][0]

    last_used = metadata.get("last_used", 0)
    hit_count = metadata.get("hit_count", 0)

    # Get threshold based on query complexity (smart_score)
    threshold = get_dynamic_threshold(smart_score)
    
    # Use similarity directly as the primary matching metric
    # (not the complex confidence score which penalizes new cache entries)
    print(f"[CACHE] Query: '{query[:50]}...' | Matched: '{matched_query[:50]}...'")
    print(f"[CACHE] Similarity: {similarity:.4f} | Threshold: {threshold:.4f}")

    if similarity >= threshold:

        # Update metadata - increment hit count and refresh last_used timestamp
        collection.update(
            ids=[matched_id],
            metadatas=[{
                "response": metadata["response"],
                "last_used": time.time(),
                "hit_count": hit_count + 1,
                "created_at": metadata.get("created_at", time.time())
            }]
        )

        cache_stats["hits"] += 1

        return {
            "response": metadata["response"],
            "similarity": round(similarity, 4),
            "matched_query": matched_query,
        }

    else:
        cache_stats["misses"] += 1
        return None


def find_similar_existing(query_embedding, threshold=0.9):
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=1,
        include=["distances", "metadatas"]
    )

    if not results["ids"] or not results["ids"][0]:
        return None

    similarity = 1 - results["distances"][0][0]

    if similarity >= threshold:
        return {
            "id": results["ids"][0][0],
            "metadata": results["metadatas"][0][0],
            "similarity": similarity
        }

    return None

def store_in_cache(query: str, response: str) -> None:

    query_embedding = get_embedding(query)
    doc_id = hashlib.md5(query.encode()).hexdigest()

    existing = find_similar_existing(query_embedding)

    if existing:
        print("[CACHE] Updating existing entry instead of inserting")

        metadata = existing["metadata"]

        collection.update(
            ids=[existing["id"]],
            metadatas=[{
                "response": response,
                "last_used": time.time(),
                "hit_count": metadata.get("hit_count", 0) + 1,
                "created_at": metadata.get("created_at", time.time())
            }]
        )
        return


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


    collection.upsert(
        ids=[doc_id],
        embeddings=[query_embedding],
        documents=[query],
        metadatas=[{
            "response": response,
            "last_used": time.time(),
            "created_at": time.time(),
            "hit_count": 1
        }]
    )

    cache_stats["total_stored"] += 1


def clear_cache() -> None:
    """Clear all cached items"""
    collection.delete(
        where={}  # ChromaDB syntax to match all
    )
    cache_stats["hits"] = 0
    cache_stats["misses"] = 0
    cache_stats["total_stored"] = 0
    print("[CACHE] Cache cleared")


def get_cache_stats() -> dict:
    """Get cache statistics"""
    total = cache_stats.get("hits", 0) + cache_stats.get("misses", 0)
    hit_rate = cache_stats["hits"] / total if total > 0 else 0
    
    return {
        "hits": cache_stats.get("hits", 0),
        "misses": cache_stats.get("misses", 0),
        "hit_rate_percent": round(hit_rate * 100, 2),
        "total_stored": cache_stats.get("total_stored", 0),
    }


def get_all_cached_items() -> list:
    """Get all items currently in the cache"""
    try:
        results = collection.get(include=["documents", "metadatas"])
        
        items = []
        for i, doc_id in enumerate(results["ids"]):
            metadata = results["metadatas"][i]
            query = results["documents"][i]
            
            # Format timestamp
            last_used = metadata.get("last_used", 0)
            last_used_formatted = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_used))
            
            items.append({
                "id": doc_id,
                "query": query,
                "response": metadata.get("response", ""),
                "last_used": last_used,
                "last_used_formatted": last_used_formatted,
                "hit_count": metadata.get("hit_count", 0),
                "created_at": metadata.get("created_at", 0),
            })
        
        return items
    except Exception as e:
        print(f"[CACHE] Error getting all items: {e}")
        return []


def cluster_similar_prompts(threshold: float = 0.85) -> dict:
    """Cluster similar prompts in the cache"""
    items = get_all_cached_items()
    
    if not items:
        return {"clusters": [], "total_items": 0}
    
    clusters = []
    used_indices = set()
    
    for i, item in enumerate(items):
        if i in used_indices:
            continue
        
        cluster = {"primary": item, "similar": []}
        used_indices.add(i)
        
        query_embedding = get_embedding(item["query"])
        
        for j, other_item in enumerate(items):
            if j <= i or j in used_indices:
                continue
            
            other_embedding = get_embedding(other_item["query"])
            
            # Compute similarity
            import numpy as np
            vec1 = np.array(query_embedding)
            vec2 = np.array(other_embedding)
            
            dot_product = np.dot(vec1, vec2)
            magnitude = np.linalg.norm(vec1) * np.linalg.norm(vec2)
            
            if magnitude > 0:
                similarity = float(dot_product / magnitude)
            else:
                similarity = 0.0
            
            if similarity >= threshold:
                cluster["similar"].append({
                    "item": other_item,
                    "similarity": round(similarity, 4)
                })
                used_indices.add(j)
        
        if cluster["similar"]:  # Only add clusters with similar items
            cluster["id"] = len(clusters)
            clusters.append(cluster)
    
    return {
        "clusters": clusters,
        "total_items": len(items),
        "clustered_items": len(used_indices),
    }


def get_cache_summary() -> dict:
    """Get cache summary with clustering information"""
    stats = get_cache_stats()
    clusters = cluster_similar_prompts()
    items = get_all_cached_items()
    
    return {
        "statistics": stats,
        "total_items": len(items),
        "clustering": clusters,
        "items": items,
    }

def store_in_cache(query: str, response: str) -> None:

    query_embedding = get_embedding(query)
    doc_id = hashlib.md5(query.encode()).hexdigest()

    existing = find_similar_existing(query_embedding)

    if existing:
        print("[CACHE] Updating existing entry instead of inserting")

        metadata = existing["metadata"]

        collection.update(
            ids=[existing["id"]],
            metadatas=[{
                "response": response,
                "last_used": time.time(),
                "hit_count": metadata.get("hit_count", 0) + 1,
                "created_at": metadata.get("created_at", time.time())
            }]
        )
        return


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


    collection.upsert(
        ids=[doc_id],
        embeddings=[query_embedding],
        documents=[query],
        metadatas=[{
            "response": response,
            "last_used": time.time(),
            "created_at": time.time(),
            "hit_count": 1
        }]
    )

    cache_stats["total_stored"] += 1

