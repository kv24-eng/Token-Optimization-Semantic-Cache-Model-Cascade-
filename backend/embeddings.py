from sentence_transformers import SentenceTransformer
import numpy as np

# ── Load Model Once at Startup ────────────────────────
# all-MiniLM-L6-v2 is small, fast, and great for semantic similarity
# Downloads automatically on first run (~90MB)

print("[EMBEDDINGS] Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")
print("[EMBEDDINGS] Model loaded successfully")


# ── Core Functions ────────────────────────────────────

def get_embedding(text: str) -> list[float]:
    """
    Convert a text string into a vector embedding.
    
    Example:
        "How do I reset my password?"
        → [0.23, -0.11, 0.87, ...]  (384 numbers)
    """
    text = text.strip().lower()  # normalize input
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()    # ChromaDB expects a plain list


def get_similarity(text1: str, text2: str) -> float:
    """
    Compute cosine similarity between two texts.
    Returns a score between 0.0 and 1.0.
    
    1.0 = identical meaning
    0.0 = completely unrelated
    """
    vec1 = np.array(get_embedding(text1))
    vec2 = np.array(get_embedding(text2))

    # Cosine similarity formula
    dot_product  = np.dot(vec1, vec2)
    magnitude    = np.linalg.norm(vec1) * np.linalg.norm(vec2)

    if magnitude == 0:
        return 0.0

    return round(float(dot_product / magnitude), 4)


def batch_embed(texts: list[str]) -> list[list[float]]:
    """
    Embed multiple texts at once — faster than one by one.
    Useful for loading existing queries into cache in bulk.
    """
    normalized = [t.strip().lower() for t in texts]
    embeddings = model.encode(normalized, convert_to_numpy=True)
    return embeddings.tolist()