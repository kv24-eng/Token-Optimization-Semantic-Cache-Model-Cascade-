
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
BASE_SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", 0.75))  # Lowered from 0.80

print("[CACHE] Initializing ChromaDB...")

chroma_client = chromadb.PersistentClient(path="./chroma_db")

collection = chroma_client.get_or_create_collection(
    name="semantic_cache",
    metadata={"hnsw:space": "cosine"}
)

print("[CACHE] ChromaDB ready")


def normalize_query(query: str) -> str:
    """Normalize query for better semantic matching"""
    # Remove extra whitespace
    query = ' '.join(query.split())
    # Convert to lowercase for consistency
    query = query.lower()
    # Remove trailing punctuation
    query = query.rstrip('?!.,;:')
    return query


cache_stats = {
    "hits": 0,
    "misses": 0,
    "total_stored": 0,
}


def get_dynamic_threshold(smart_score: float | None):
    """
    Dynamic threshold based on query complexity score
    - More complex/specific queries: lower threshold (more likely to hit)
    - Simpler/ambiguous queries: higher threshold (more selective)
    """
    if smart_score is None:
        return BASE_SIMILARITY_THRESHOLD  # 0.75

    if smart_score > 0.8:
        return 0.70  # Specific queries need lower threshold
    elif smart_score > 0.5:
        return 0.75  # Moderate queries 
    else:
        return 0.80  # Ambiguous queries need higher threshold

def compute_confidence(similarity, last_used, hit_count):
    now = time.time()

    # Recency score (decay over time) - minor factor
    age = now - last_used if last_used else 0
    recency_score = 1 / (1 + age / 7200)  # decay per 2 hours (slower decay)

    # Frequency score - minor factor  
    freq_score = min(1.0, (hit_count + 1) / 2)  # +1 to boost new entries

    # Confidence heavily weighted towards similarity (semantic matching is primary)
    confidence = (
        0.85 * similarity +    # 85% semantic similarity
        0.10 * recency_score + # 10% recency  
        0.05 * freq_score      # 5% frequency
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

    confidence = compute_confidence(similarity, last_used, hit_count)

    threshold = get_dynamic_threshold(smart_score)

    print(f"[CACHE] Query: '{query[:50]}' | Matched: '{matched_query[:50]}' | Similarity: {similarity:.3f} | Confidence: {confidence:.3f} | Threshold: {threshold:.3f} | Result: {'HIT' if confidence >= threshold else 'MISS'}")

    if confidence >= threshold:

        # update metadata
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
            "confidence": confidence,
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

        results = collection.get(include=["metadatas"])
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


def clear_cache() -> None:
    """Clear all cached items"""
    global cache_stats
    try:
        # Get all item IDs first
        all_items = collection.get()
        all_ids = all_items.get("ids", [])
        
        if all_ids:
            print(f"[CACHE] Clearing {len(all_ids)} items from cache")
            # Delete all items by ID
            collection.delete(ids=all_ids)
            print(f"[CACHE] Successfully cleared all cache items")
        else:
            print(f"[CACHE] Cache is already empty")
        
        # Reset stats
        cache_stats = {
            "hits": 0,
            "misses": 0,
            "total_stored": 0,
        }
    except Exception as e:
        print(f"[ERROR] clear_cache: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def get_cache_stats() -> dict:
    """Get current cache statistics including hit rate"""
    total_requests = cache_stats["hits"] + cache_stats["misses"]
    hit_rate = (cache_stats["hits"] / total_requests * 100) if total_requests > 0 else 0
    
    return {
        "hits": cache_stats["hits"],
        "misses": cache_stats["misses"],
        "hit_rate_percent": round(hit_rate, 2),
        "total_stored": cache_stats["total_stored"],
    }


def get_all_cached_items() -> list:
    """Get all items currently in the cache"""
    from datetime import datetime
    
    results = collection.get(include=["documents", "metadatas"])
    
    items = []
    for i, doc_id in enumerate(results["ids"]):
        metadata = results["metadatas"][i]
        last_used = metadata.get("last_used", 0)
        
        # Format timestamp
        if last_used > 0:
            last_used_formatted = datetime.fromtimestamp(last_used).strftime("%Y-%m-%d %H:%M:%S")
        else:
            last_used_formatted = "Never"
        
        items.append({
            "id": doc_id,
            "query": results["documents"][i],
            "response": metadata.get("response", ""),
            "hit_count": metadata.get("hit_count", 0),
            "last_used": last_used,
            "last_used_formatted": last_used_formatted,
            "created_at": metadata.get("created_at", 0),
        })
    
    return items


def cluster_similar_prompts(similarity_threshold: float = 0.85) -> dict:
    """Cluster similar prompts together"""
    try:
        results = collection.get(include=["documents", "embeddings", "metadatas"])
        
        if not results["ids"] or not results["embeddings"]:
            return {"clusters": []}
        
        clusters = {}
        cluster_id = 0
        visited = set()
        
        embeddings = results["embeddings"]
        
        for i, doc_id in enumerate(results["ids"]):
            if doc_id in visited:
                continue
            
            cluster = [i]
            visited.add(doc_id)
            
            # Find similar items
            for j in range(i + 1, len(results["ids"])):
                if results["ids"][j] in visited:
                    continue
                
                try:
                    # Simple cosine similarity calculation
                    import numpy as np
                    emb1 = np.array(embeddings[i])
                    emb2 = np.array(embeddings[j])
                    norm1 = np.linalg.norm(emb1)
                    norm2 = np.linalg.norm(emb2)
                    
                    if norm1 > 0 and norm2 > 0:
                        similarity = np.dot(emb1, emb2) / (norm1 * norm2)
                        
                        if similarity >= similarity_threshold:
                            cluster.append(j)
                            visited.add(results["ids"][j])
                except Exception as e:
                    print(f"[WARNING] Similarity calculation error: {e}")
                    continue
            
            metadata = results["metadatas"][i]
            last_used = metadata.get("last_used", 0)
            if last_used > 0:
                from datetime import datetime
                last_used_formatted = datetime.fromtimestamp(last_used).strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_used_formatted = "Never"
            
            clusters[cluster_id] = {
                "query": results["documents"][i],
                "id": results["ids"][i],
                "last_used_formatted": last_used_formatted,
                "similar_items": [
                    {
                        "id": results["ids"][idx],
                        "query": results["documents"][idx],
                        "response": results["metadatas"][idx].get("response", ""),
                        "last_used_formatted": (
                            "Never" if not results["metadatas"][idx].get("last_used") 
                            else datetime.fromtimestamp(results["metadatas"][idx]["last_used"]).strftime("%Y-%m-%d %H:%M:%S")
                        ),
                    }
                    for idx in cluster[1:]
                ],
            }
            cluster_id += 1
        
        return {"clusters": list(clusters.values())}
    except Exception as e:
        print(f"[ERROR] cluster_similar_prompts: {str(e)}")
        return {"clusters": []}


def get_cache_summary() -> dict:
    """Get cache summary with clustering information"""
    try:
        all_items = get_all_cached_items()
        total_items = len(all_items)
        
        # Get clusters
        clusters_data = cluster_similar_prompts()
        clusters_list = clusters_data.get("clusters", [])
        total_clusters = len(clusters_list)
        
        # Format clusters for frontend
        formatted_clusters = []
        for idx, cluster in enumerate(clusters_list):
            similar_items = cluster.get("similar_items", [])
            formatted_clusters.append({
                "cluster_id": idx,
                "primary_query": cluster["query"],
                "duplicate_count": len(similar_items),
                "avg_similarity": 0.85,  # placeholder
                "items": [
                    {
                        "id": cluster["id"],
                        "query": cluster["query"],
                        "last_used_formatted": cluster.get("last_used_formatted", "Never"),
                    }
                ] + [
                    {
                        "id": item["id"],
                        "query": item["query"],
                        "last_used_formatted": item.get("last_used_formatted", "Never"),
                    }
                    for item in similar_items
                ]
            })
        
        return {
            "total_items": total_items,
            "total_clusters": total_clusters,
            "clusters": formatted_clusters,
            "statistics": get_cache_stats(),
        }
    except Exception as e:
        print(f"[ERROR] get_cache_summary: {str(e)}")
        # Return safe empty response
        return {
            "total_items": 0,
            "total_clusters": 0,
            "clusters": [],
            "statistics": get_cache_stats(),
        }


def delete_cache_items(item_ids: list[str]) -> dict:
    """Delete specific cache items by ID"""
    try:
        print(f"[CACHE] Attempting to delete {len(item_ids)} items: {item_ids}")
        
        deleted_count = 0
        for item_id in item_ids:
            try:
                collection.delete(ids=[item_id])
                deleted_count += 1
                print(f"[CACHE] Deleted item: {item_id}")
            except Exception as e:
                print(f"[CACHE] Failed to delete {item_id}: {e}")
        
        # Update stats
        cache_stats["total_stored"] = max(0, cache_stats["total_stored"] - deleted_count)
        
        print(f"[CACHE] Successfully deleted {deleted_count} items. Total stored: {cache_stats['total_stored']}")
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"Deleted {deleted_count} items"
        }
    except Exception as e:
        print(f"[ERROR] delete_cache_items: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "deleted_count": 0
        }


def delete_cluster(cluster_id: int, keep_primary: bool = True) -> dict:
    """Delete all items in a cluster"""
    try:
        print(f"[CACHE] Deleting cluster {cluster_id}, keep_primary={keep_primary}")
        
        clusters = cluster_similar_prompts()["clusters"]
        
        if cluster_id < 0 or cluster_id >= len(clusters):
            return {
                "success": False,
                "error": f"Cluster {cluster_id} not found. Available clusters: {len(clusters)}",
                "deleted_count": 0
            }
        
        cluster = clusters[cluster_id]
        to_delete = []
        
        if not keep_primary:
            to_delete.append(cluster["id"])
            print(f"[CACHE] Including primary item: {cluster['id']}")
        
        for item in cluster.get("similar_items", []):
            to_delete.append(item["id"])
        
        print(f"[CACHE] Deleting {len(to_delete)} items: {to_delete}")
        
        # Delete items
        deleted_count = 0
        for item_id in to_delete:
            try:
                collection.delete(ids=[item_id])
                deleted_count += 1
                print(f"[CACHE] Deleted cluster item: {item_id}")
            except Exception as e:
                print(f"[CACHE] Failed to delete cluster item {item_id}: {e}")
        
        # Update stats
        cache_stats["total_stored"] = max(0, cache_stats["total_stored"] - deleted_count)
        
        print(f"[CACHE] Successfully deleted {deleted_count} items from cluster {cluster_id}")
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"Deleted {deleted_count} items from cluster {cluster_id}"
        }
    except Exception as e:
        print(f"[ERROR] delete_cluster: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "deleted_count": 0
        }

