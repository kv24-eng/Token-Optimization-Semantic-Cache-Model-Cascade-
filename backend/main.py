from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import time

from cache import check_cache, store_in_cache, clear_cache as cache_clear, get_cache_stats
from cascade import CascadeRouter, CascadeMetrics, handle_cache_miss

load_dotenv()

# ── App Setup ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Semantic Cache + Model Cascade",
    description="Cost-optimized LLM response system",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Singletons (created once at startup) ─────────────────────────────────

router  = CascadeRouter()        # smart model router
metrics = CascadeMetrics()       # tracks all requests


# ── Request / Response Schemas ────────────────────────────────────────────

class ChatRequest(BaseModel):
    query:      str
    budget_usd: float | None = None   # optional per-request cost cap


class ChatResponse(BaseModel):
    response:         str
    was_cached:       bool
    model_used:       str
    tier:             str
    smart_score:      float
    similarity:       float | None     # only present on cache HIT
    matched_query:    str  | None      # only present on cache HIT
    input_tokens:     int
    output_tokens:    int
    latency_ms:       float
    cost_usd:         float


# ── Routes ────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "running", "message": "Semantic Cache + Cascade API is live"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Main pipeline:
      1. Check semantic cache
         HIT  → return cached answer immediately (free, fast)
         MISS → route to best-fit model via CascadeRouter
      2. Store new answer in cache for future hits
      3. Update metrics
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    start = time.perf_counter()

    # ── Step 1: Semantic Cache lookup ─────────────────────────────────────
    cached = check_cache(req.query)

    if cached:
        # ── CACHE HIT ─────────────────────────────────────────────────────
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        # Build a lightweight CascadeResponse-compatible object for metrics
        from cascade import CascadeResponse
        hit_resp = CascadeResponse(
            answer        = cached["response"],
            model_used    = "cache",
            tier          = "cache",
            smart_score   = 0.0,
            sub_scores    = {},
            signals       = [],
            input_tokens  = 0,
            output_tokens = 0,
            latency_ms    = latency_ms,
            cost_usd      = 0.0,
            cache_hit     = True,
        )
        metrics.record(hit_resp)

        return ChatResponse(
            response      = cached["response"],
            was_cached    = True,
            model_used    = "cache",
            tier          = "cache",
            smart_score   = 0.0,
            similarity    = cached.get("similarity"),
            matched_query = cached.get("matched_query"),
            input_tokens  = 0,
            output_tokens = 0,
            latency_ms    = latency_ms,
            cost_usd      = 0.0,
        )

    # ── Step 2: Cache MISS → CascadeRouter ───────────────────────────────
    resp = handle_cache_miss(
        query      = req.query,
        router     = router,
        metrics    = metrics,
        budget_usd = req.budget_usd,
    )

    if resp.error:
        raise HTTPException(status_code=502, detail=resp.error)

    # ── Step 3: Store answer in cache for future hits ─────────────────────
    store_in_cache(req.query, resp.answer)

    return ChatResponse(
        response      = resp.answer,
        was_cached    = False,
        model_used    = resp.model_used,
        tier          = resp.tier,
        smart_score   = resp.smart_score,
        similarity    = None,
        matched_query = None,
        input_tokens  = resp.input_tokens,
        output_tokens = resp.output_tokens,
        latency_ms    = resp.latency_ms,
        cost_usd      = resp.cost_usd,
    )


@app.get("/metrics")
def get_metrics():
    """
    Combined metrics: cascade routing stats + cache hit/miss stats.
    """
    cascade_summary = metrics.summary()
    cache_summary   = get_cache_stats()

    total = cascade_summary["total_requests"]

    return {
        # ── Request overview
        "total_queries":        total,
        "avg_latency_ms":       cascade_summary["avg_latency_ms"],
        "errors":               cascade_summary["errors"],

        # ── Cache stats
        "cache_hits":           cache_summary["hits"],
        "cache_misses":         cache_summary["misses"],
        "cache_hit_rate":       cache_summary["hit_rate_percent"],
        "cache_total_stored":   cache_summary["total_stored"],

        # ── Cascade / model routing stats
        "tier_distribution":    cascade_summary["tier_distribution"],

        # ── Token & cost stats
        "total_tokens":         cascade_summary["total_tokens"],
        "total_cost_usd":       cascade_summary["total_cost_usd"],
    }


@app.get("/routing/explain")
def explain_routing(query: str, budget_usd: float | None = None):
    """
    Dry-run: shows which model would be selected for a given query
    without actually calling the LLM. Great for debugging & demos.
    """
    return router.explain_routing(query, budget_usd)


@app.delete("/cache/clear")
def clear_cache_endpoint():
    cache_clear()
    return {"message": "Cache cleared successfully"}