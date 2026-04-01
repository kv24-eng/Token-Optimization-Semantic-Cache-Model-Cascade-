
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
        include=["documents", "metadatas", "distances", "ids"]
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

    print(f"[CACHE] similarity={similarity:.3f} confidence={confidence:.3f} threshold={threshold}")

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
        include=["ids", "distances", "metadatas"]
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

