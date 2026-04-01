import os
import sys
import time
import hashlib
import chromadb
from dotenv import load_dotenv

# Add backend to path for relative imports
sys.path.insert(0, os.path.dirname(__file__))

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

    print(f"[CACHE] Query: '{query[:50]}...'")
    print(f"[CACHE] Best match similarity: {similarity:.3f} (threshold: {SIMILARITY_THRESHOLD})")

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
        print(f"[CACHE] ✅ HIT matched: '{matched_query}'")

        return {
            "response": cached_response,
            "was_cached": True,
            "similarity": similarity,
            "matched_query": matched_query,
        }

    else:
        cache_stats["misses"] += 1
        print(f"[CACHE] ❌ MISS - similarity {similarity:.3f} below threshold {SIMILARITY_THRESHOLD}")
        return None


def store_in_cache(query: str, response: str) -> None:

    query_embedding = get_embedding(query)

    doc_id = hashlib.md5(query.encode()).hexdigest()

    current_count = collection.count()
    print(f"[CACHE] Storing: Query='{query[:50]}...' ID={doc_id} Current count={current_count}")

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
        print(f"[CACHE] Removed {len(ids_to_delete)} LRU entries to make space")

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
    print(f"[CACHE] ✅ Stored query: '{query[:50]}...' Response length: {len(response)} chars")


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


def get_all_cached_items() -> list:
    """Get all items currently in the cache"""
    
    try:
        count = collection.count()
        
        if count == 0:
            return []
        
        # Optimized retrieval without excessive logging
        results = collection.get(include=["documents", "metadatas"])
        
        items = []
        for idx, doc_id in enumerate(results["ids"]):
            query = results["documents"][idx] if idx < len(results["documents"]) else ""
            metadata = results["metadatas"][idx] if idx < len(results["metadatas"]) else {}
            
            item = {
                "id": doc_id,
                "query": query,
                "response": metadata.get("response", ""),
                "last_used": metadata.get("last_used", 0),
                "last_used_formatted": time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.localtime(metadata.get("last_used", 0))
                ) if metadata.get("last_used") else "Never",
            }
            items.append(item)
        
        # Sort by last_used descending
        items.sort(key=lambda x: x["last_used"], reverse=True)
        return items
        
    except Exception as e:
        print(f"[CACHE] Error retrieving cached items: {e}")
        return []


def cluster_similar_prompts(similarity_threshold: float = 0.75) -> dict:
    """
    Group similar prompts into clusters based on semantic similarity.
    Returns clusters with frequency and metadata.
    """
    
    items = get_all_cached_items()
    if not items:
        return {"clusters": [], "total_items": 0, "total_clusters": 0}
    
    clusters = []
    used_indices = set()
    
    for i, item1 in enumerate(items):
        if i in used_indices:
            continue
        
        # Start a new cluster with this item
        cluster = {
            "cluster_id": len(clusters),
            "primary_query": item1["query"],
            "items": [item1],
            "size": 1,
            "avg_similarity": 1.0,
        }
        used_indices.add(i)
        
        # Find similar items
        similarities = []
        embedding1 = get_embedding(item1["query"])
        
        for j, item2 in enumerate(items):
            if j <= i or j in used_indices:
                continue
            
            try:
                embedding2 = get_embedding(item2["query"])
                # Cosine similarity
                dot_prod = sum(a*b for a, b in zip(embedding1, embedding2))
                norm1 = sum(a**2 for a in embedding1) ** 0.5
                norm2 = sum(b**2 for b in embedding2) ** 0.5
                similarity = dot_prod / (norm1 * norm2) if norm1 * norm2 > 0 else 0
                
                if similarity >= similarity_threshold:
                    cluster["items"].append(item2)
                    similarities.append(similarity)
                    used_indices.add(j)
            except:
                continue
        
        cluster["size"] = len(cluster["items"])
        cluster["avg_similarity"] = sum(similarities) / len(similarities) if similarities else 1.0
        clusters.append(cluster)
    
    return {
        "clusters": clusters,
        "total_items": len(items),
        "total_clusters": len(clusters)
    }


def delete_cache_items(item_ids: list) -> dict:
    """Delete specific cache items by ID"""
    
    try:
        collection.delete(ids=item_ids)
        print(f"[CACHE] Deleted {len(item_ids)} items")
        return {
            "success": True,
            "deleted_count": len(item_ids),
            "remaining": collection.count()
        }
    except Exception as e:
        print(f"[CACHE] Error deleting items: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def delete_cluster(cluster_id: int, keep_primary: bool = True) -> dict:
    """
    Delete all items in a cluster, optionally keeping the primary query.
    
    Args:
        cluster_id: ID of the cluster to delete
        keep_primary: If True, keep the primary query and delete only similar ones
    """
    
    clusters = cluster_similar_prompts()["clusters"]
    
    if cluster_id >= len(clusters):
        return {"success": False, "error": "Cluster not found"}
    
    cluster = clusters[cluster_id]
    items_to_delete = cluster["items"]
    
    if keep_primary:
        # Keep the first (primary) item, delete the rest
        items_to_delete = cluster["items"][1:]
    
    item_ids = [item["id"] for item in items_to_delete]
    return delete_cache_items(item_ids)


def get_cache_summary() -> dict:
    """Get detailed cache statistics and cluster information"""
    
    clustering_result = cluster_similar_prompts()
    
    return {
        "total_items": clustering_result["total_items"],
        "total_clusters": clustering_result["total_clusters"],
        "clusters": [
            {
                "cluster_id": c["cluster_id"],
                "primary_query": c["primary_query"],
                "duplicate_count": c["size"] - 1,  # Non-primary items
                "avg_similarity": round(c["avg_similarity"], 3),
                "items": [
                    {
                        "id": item["id"],
                        "query": item["query"],
                        "last_used_formatted": item["last_used_formatted"]
                    }
                    for item in c["items"]
                ]
            }
            for c in clustering_result["clusters"]
        ]
    }
