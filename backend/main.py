from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import time

load_dotenv()

app = FastAPI(
    title="Semantic Cache + Model Cascade",
    description="Cost-optimized LLM response system",
    version="1.0.0"
)

# Allow Streamlit to talk to FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Temporary in-memory metrics ──────────────────────
metrics = {
    "total_queries": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "small_model_uses": 0,
    "large_model_uses": 0,
    "total_cost_usd": 0.0,
    "total_latency_ms": 0.0,
}


# ── Routes ────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "running", "message": "Semantic Cache + Cascade API is live"}


@app.post("/chat")
def chat(query: str):
    start = time.time()

    # Placeholder — will be replaced with real logic
    response = f"(placeholder) You asked: {query}"
    model_used = "small"
    was_cached = False
    confidence = 0.91
    cost = 0.0003

    latency_ms = round((time.time() - start) * 1000, 2)

    # Update metrics
    metrics["total_queries"] += 1
    metrics["total_latency_ms"] += latency_ms
    metrics["total_cost_usd"] += cost
    if was_cached:
        metrics["cache_hits"] += 1
    else:
        metrics["cache_misses"] += 1
    if model_used == "small":
        metrics["small_model_uses"] += 1
    else:
        metrics["large_model_uses"] += 1

    return {
        "response": response,
        "was_cached": was_cached,
        "model_used": model_used,
        "confidence_score": confidence,
        "latency_ms": latency_ms,
        "cost_usd": cost,
    }


@app.get("/metrics")
def get_metrics():
    total = metrics["total_queries"]
    avg_latency = (
        round(metrics["total_latency_ms"] / total, 2) if total > 0 else 0
    )
    cache_hit_rate = (
        round((metrics["cache_hits"] / total) * 100, 1) if total > 0 else 0
    )

    return {
        **metrics,
        "avg_latency_ms": avg_latency,
        "cache_hit_rate_percent": cache_hit_rate,
    }


@app.delete("/cache/clear")
def clear_cache():
    # Placeholder — will call cache.py clear function later
    return {"message": "Cache cleared successfully"}