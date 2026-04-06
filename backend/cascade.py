"""
cascade.py — Smart Model Cascade Router
========================================
Flow:
  1. Semantic Cache checked (in main.py / cache.py)
  2. On MISS → this module scores the query and routes
     directly to the best-fit model (no escalation).

Routing is based on a combined smart score using:
  - Complexity Score  : token length + structural signals
  - Keyword Score     : domain / intent keyword detection
  - Ambiguity Score   : question clarity & specificity
  - Cost Budget Score : optional per-request budget cap
"""

import re
import os
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from groq import Groq

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
# 1.  MODEL REGISTRY
# ══════════════════════════════════════════════════════════════════════════

class ModelTier(Enum):
    LIGHT  = "light"    # fast, cheap  — simple / factual queries
    MID    = "mid"      # balanced     — moderate reasoning
    HEAVY  = "heavy"    # powerful     — complex / multi-step


@dataclass
class ModelConfig:
    tier:             ModelTier
    model_id:         str
    max_tokens:       int
    cost_per_1k_in:   float   # USD per 1 000 input  tokens
    cost_per_1k_out:  float   # USD per 1 000 output tokens
    score_threshold:  float   # minimum smart_score to use this tier


# Registry — swap model_id values to point at any provider you like
MODEL_REGISTRY: dict[ModelTier, ModelConfig] = {
    ModelTier.LIGHT: ModelConfig(
        tier             = ModelTier.LIGHT,
        model_id         = "llama-3.1-8b-instant",
        max_tokens       = 1024,
        cost_per_1k_in   = 0.05,  # per 1M tokens
        cost_per_1k_out  = 0.08,
        score_threshold  = 0.0,   # catch-all lower bound
    ),
    ModelTier.MID: ModelConfig(
        tier             = ModelTier.MID,
        model_id         = "llama-3.3-70b-versatile",
        max_tokens       = 4096,
        cost_per_1k_in   = 0.59,  # per 1M tokens
        cost_per_1k_out  = 0.79,
        score_threshold  = 0.40,  # score ≥ 0.40 → use mid
    ),
    ModelTier.HEAVY: ModelConfig(
        tier             = ModelTier.HEAVY,
        model_id         = "openai/gpt-oss-120b",
        max_tokens       = 8192,
        cost_per_1k_in   = 0.15,  # per 1M tokens
        cost_per_1k_out  = 0.60,
        score_threshold  = 0.70,  # score ≥ 0.70 → use heavy
    ),
}


# ══════════════════════════════════════════════════════════════════════════
# 2.  SCORING ENGINE
# ══════════════════════════════════════════════════════════════════════════

# --- keyword sets --------------------------------------------------------

_HEAVY_KEYWORDS: set[str] = {
    # reasoning / analysis
    "analyze", "analyse", "evaluate", "critique", "compare",
    "contrast", "debate", "argue", "justify", "explain in depth",
    # code / technical
    "implement", "architecture", "design pattern", "algorithm",
    "optimize", "refactor", "debug complex",
    # research / writing
    "research", "essay", "report", "dissertation", "thesis",
    "literature review", "technical document",
    # math / logic
    "proof", "derive", "theorem", "equation", "calculus",
    "linear algebra", "statistics",
    # multi-step
    "step by step", "detailed", "comprehensive", "in-depth",
}

_LIGHT_KEYWORDS: set[str] = {
    # facts / lookup
    "what is", "who is", "when did", "where is", "define",
    "meaning of", "abbreviation", "capital of",
    # simple tasks
    "translate", "convert", "summarize briefly", "list",
    "give me a few", "quick", "short",
    # yes / no
    "is it", "does it", "can i", "should i",
}

# --- regex patterns -------------------------------------------------------

_CODE_BLOCK_RE   = re.compile(r"```[\s\S]*?```")
_MULTI_PART_RE   = re.compile(r"\b(and also|additionally|furthermore|moreover|part \d|step \d)\b", re.I)
_QUESTION_RE     = re.compile(r"\?")
_NUMERIC_RE      = re.compile(r"\b\d+\b")


class QueryScorer:
    """
    Produces a normalised smart_score in [0.0, 1.0].

    Sub-scores (each 0–1):
      - complexity  : token length / structural signals
      - keyword     : weighted keyword match
      - ambiguity   : how open-ended / vague the query is
      - budget      : cost-budget pressure (optional)

    Weights sum to 1.0.
    """

    WEIGHTS = {
        "complexity": 0.35,
        "keyword":    0.35,
        "ambiguity":  0.20,
        "budget":     0.10,
    }

    # token-length breakpoints (approx words)
    _LEN_LIGHT = 20
    _LEN_MID   = 80
    _LEN_HEAVY = 200

    def score(
        self,
        query:              str,
        budget_usd:         Optional[float] = None,
        conversation_turns: int             = 0,
    ) -> dict:
        """
        Returns a dict with:
          smart_score  : float [0, 1]
          sub_scores   : dict of component scores
          signals      : list[str] — human-readable explanation
        """
        tokens  = query.split()
        n_tok   = len(tokens)
        q_lower = query.lower()
        signals = []

        # ── 2a. Complexity score ──────────────────────────────────────────
        if n_tok <= self._LEN_LIGHT:
            c = 0.1
        elif n_tok <= self._LEN_MID:
            c = 0.1 + 0.4 * (n_tok - self._LEN_LIGHT) / (self._LEN_MID - self._LEN_LIGHT)
        elif n_tok <= self._LEN_HEAVY:
            c = 0.5 + 0.3 * (n_tok - self._LEN_MID) / (self._LEN_HEAVY - self._LEN_MID)
        else:
            c = 0.9

        # structural boosts
        code_blocks = len(_CODE_BLOCK_RE.findall(query))
        if code_blocks:
            c = min(1.0, c + 0.15 * code_blocks)
            signals.append(f"code_blocks={code_blocks}")

        multi_parts = len(_MULTI_PART_RE.findall(query))
        if multi_parts:
            c = min(1.0, c + 0.10 * multi_parts)
            signals.append(f"multi_part_signals={multi_parts}")

        if conversation_turns > 4:
            c = min(1.0, c + 0.05)
            signals.append(f"long_conversation={conversation_turns}_turns")

        complexity_score = round(c, 3)

        # ── 2b. Keyword score ─────────────────────────────────────────────
        heavy_hits = sum(1 for kw in _HEAVY_KEYWORDS if kw in q_lower)
        light_hits = sum(1 for kw in _LIGHT_KEYWORDS if kw in q_lower)

        if heavy_hits == 0 and light_hits == 0:
            k = 0.3   # neutral
        elif heavy_hits > light_hits:
            k = min(1.0, 0.5 + 0.15 * heavy_hits)
            signals.append(f"heavy_keywords={heavy_hits}")
        else:
            k = max(0.0, 0.3 - 0.10 * light_hits)
            signals.append(f"light_keywords={light_hits}")

        keyword_score = round(k, 3)

        # ── 2c. Ambiguity score ───────────────────────────────────────────
        # high ambiguity → harder for a small model → push score up
        questions      = len(_QUESTION_RE.findall(query))
        unique_ratio   = len(set(tokens)) / max(n_tok, 1)
        numeric_tokens = len(_NUMERIC_RE.findall(query))

        a = 0.3  # baseline
        if questions > 1:
            a += 0.10 * (questions - 1)
            signals.append(f"multi_question={questions}")
        if unique_ratio > 0.85:              # very diverse vocab → complex
            a += 0.15
            signals.append("high_vocab_diversity")
        if numeric_tokens > 3:              # lots of numbers → data-heavy
            a += 0.10
            signals.append(f"numeric_tokens={numeric_tokens}")
        # short, vague query — likely simple
        if n_tok < 8 and questions <= 1:
            a -= 0.10
            signals.append("short_vague_query")

        ambiguity_score = round(min(1.0, max(0.0, a)), 3)

        # ── 2d. Budget score ──────────────────────────────────────────────
        # budget_score near 0 → prefer cheaper model
        # budget_score near 1 → budget allows heavy model
        if budget_usd is None:
            b = 0.5   # no constraint
        elif budget_usd <= 0.001:
            b = 0.0
            signals.append("tight_budget")
        elif budget_usd <= 0.01:
            b = 0.3
            signals.append("moderate_budget")
        else:
            b = 1.0
            signals.append("open_budget")

        budget_score = round(b, 3)

        # ── 2e. Weighted combination ──────────────────────────────────────
        smart_score = round(
            self.WEIGHTS["complexity"] * complexity_score
            + self.WEIGHTS["keyword"]    * keyword_score
            + self.WEIGHTS["ambiguity"]  * ambiguity_score
            + self.WEIGHTS["budget"]     * budget_score,
            4,
        )

        return {
            "smart_score": smart_score,
            "sub_scores": {
                "complexity": complexity_score,
                "keyword":    keyword_score,
                "ambiguity":  ambiguity_score,
                "budget":     budget_score,
            },
            "signals": signals,
            "token_count": n_tok,
        }


# ══════════════════════════════════════════════════════════════════════════
# 3.  MODEL SELECTOR
# ══════════════════════════════════════════════════════════════════════════

class ModelSelector:
    """
    Maps a smart_score → ModelConfig.
    Tiers are evaluated from HEAVY → MID → LIGHT (highest threshold first).
    """

    def select(self, smart_score: float, budget_usd: Optional[float] = None) -> ModelConfig:
        # Hard budget override: if budget is very tight, cap at LIGHT
        if budget_usd is not None and budget_usd <= 0.001:
            logger.info("Budget cap → forcing LIGHT tier")
            return MODEL_REGISTRY[ModelTier.LIGHT]

        for tier in [ModelTier.HEAVY, ModelTier.MID]:
            cfg = MODEL_REGISTRY[tier]
            if smart_score >= cfg.score_threshold:
                return cfg

        return MODEL_REGISTRY[ModelTier.LIGHT]


# ══════════════════════════════════════════════════════════════════════════
# 4.  RESPONSE DATACLASS
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class CascadeResponse:
    answer:           str
    model_used:       str
    tier:             str
    smart_score:      float
    sub_scores:       dict
    signals:          list
    input_tokens:     int
    output_tokens:    int
    latency_ms:       float
    cost_usd:         float
    cache_hit:        bool  = False
    error:            Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════
# 5.  CASCADE ROUTER  (main entry-point)
# ══════════════════════════════════════════════════════════════════════════

class CascadeRouter:
    """
    Primary interface.  Called after a semantic-cache MISS.

    Usage:
        router = CascadeRouter()
        result = router.route(query="Explain transformer architecture in detail")
        print(result.answer)
        print(f"Used: {result.model_used}  |  Score: {result.smart_score}")
    """

    def __init__(self, api_key: Optional[str] = None):
        self.client   = Groq(api_key=api_key or os.getenv("GROQ_API_KEY"))
        self.scorer   = QueryScorer()
        self.selector = ModelSelector()

    # ------------------------------------------------------------------ #
    def route(
        self,
        query:              str,
        system_prompt:      str            = "You are a helpful assistant.",
        conversation_turns: int            = 0,
        budget_usd:         Optional[float] = None,
        stream:             bool           = False,
    ) -> CascadeResponse:
        """
        Score → Select model → Call API → Return CascadeResponse.
        """
        # 5a. Score
        score_result = self.scorer.score(
            query              = query,
            budget_usd         = budget_usd,
            conversation_turns = conversation_turns,
        )
        smart_score = score_result["smart_score"]

        # 5b. Select model
        model_cfg = self.selector.select(smart_score, budget_usd)

        logger.info(
            "CASCADE ROUTE | score=%.3f | tier=%s | model=%s | signals=%s",
            smart_score,
            model_cfg.tier.value,
            model_cfg.model_id,
            score_result["signals"],
        )

        # 5c. Call API
        t0 = time.perf_counter()
        try:
            response = self.client.chat.completions.create(
                model      = model_cfg.model_id,
                max_tokens = model_cfg.max_tokens,
                messages   = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
            )
            latency_ms   = (time.perf_counter() - t0) * 1000
            answer       = response.choices[0].message.content
            input_tokens  = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            error         = None

        except Exception as exc:
            latency_ms    = (time.perf_counter() - t0) * 1000
            answer        = f"[CascadeRouter error] {exc}"
            input_tokens  = 0
            output_tokens = 0
            error         = str(exc)
            logger.error("API call failed: %s", exc)

        # 5d. Estimate cost
        cost_usd = (
            input_tokens  / 1000 * model_cfg.cost_per_1k_in
            + output_tokens / 1000 * model_cfg.cost_per_1k_out
        )

        return CascadeResponse(
            answer        = answer,
            model_used    = model_cfg.model_id,
            tier          = model_cfg.tier.value,
            smart_score   = smart_score,
            sub_scores    = score_result["sub_scores"],
            signals       = score_result["signals"],
            input_tokens  = input_tokens,
            output_tokens = output_tokens,
            latency_ms    = round(latency_ms, 2),
            cost_usd      = round(cost_usd, 6),
            error         = error,
        )

    # ------------------------------------------------------------------ #
    def explain_routing(self, query: str, budget_usd: Optional[float] = None) -> dict:
        """
        Dry-run: returns the routing decision without calling the API.
        Useful for debugging / unit tests.
        """
        score_result = self.scorer.score(query, budget_usd)
        model_cfg    = self.selector.select(score_result["smart_score"], budget_usd)
        return {
            "selected_tier":  model_cfg.tier.value,
            "selected_model": model_cfg.model_id,
            **score_result,
            "thresholds": {
                t.value: MODEL_REGISTRY[t].score_threshold
                for t in ModelTier
            },
        }


# ══════════════════════════════════════════════════════════════════════════
# 6.  METRICS HELPER  (integrates with your metrics.py)
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class CascadeMetrics:
    total_requests:   int   = 0
    cache_hits:       int   = 0
    tier_counts:      dict  = field(default_factory=lambda: {"light": 0, "mid": 0, "heavy": 0})
    total_tokens_in:  int   = 0
    total_tokens_out: int   = 0
    total_cost_usd:   float = 0.0
    total_latency_ms: float = 0.0
    errors:           int   = 0

    def record(self, resp: CascadeResponse) -> None:
        self.total_requests   += 1
        self.total_tokens_in  += resp.input_tokens
        self.total_tokens_out += resp.output_tokens
        self.total_cost_usd   += resp.cost_usd
        self.total_latency_ms += resp.latency_ms
        if resp.cache_hit:
            self.cache_hits += 1
        else:
            self.tier_counts[resp.tier] = self.tier_counts.get(resp.tier, 0) + 1
        if resp.error:
            self.errors += 1

    @property
    def cache_hit_rate(self) -> float:
        return self.cache_hits / self.total_requests if self.total_requests else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.total_requests if self.total_requests else 0.0

    def summary(self) -> dict:
        return {
            "total_requests":  self.total_requests,
            "cache_hit_rate":  f"{self.cache_hit_rate:.1%}",
            "tier_distribution": self.tier_counts,
            "total_tokens":    self.total_tokens_in + self.total_tokens_out,
            "total_cost_usd":  round(self.total_cost_usd, 4),
            "avg_latency_ms":  round(self.avg_latency_ms, 1),
            "errors":          self.errors,
        }


# ══════════════════════════════════════════════════════════════════════════
# 7.  INTEGRATION HELPER  (drop-in for main.py)
# ══════════════════════════════════════════════════════════════════════════

def handle_cache_miss(
    query:          str,
    router:         CascadeRouter,
    metrics:        CascadeMetrics,
    budget_usd:     float = None,
    system_prompt:  str   = "You are a helpful assistant.",
) -> CascadeResponse:
    """
    Call this from main.py whenever cache.py returns a MISS.
    
    Handles:
      1. Score the query
      2. Route to best-fit model
      3. Call the LLM
      4. Record metrics
      5. Return response
    
    Returns a CascadeResponse with all fields populated.
    """
    try:
        # Use the router to score, select model, and call API
        resp = router.route(
            query          = query,
            system_prompt  = system_prompt,
            budget_usd     = budget_usd,
            stream         = False,
        )
        
        # Record in metrics
        metrics.record(resp)
        
        return resp
        
    except Exception as e:
        # Return error response on failure
        logger.error(f"Cache miss routing failed: {e}")
        return CascadeResponse(
            answer        = f"Error: {str(e)}",
            model_used    = "error",
            tier          = "error",
            smart_score   = 0.0,
            sub_scores    = {},
            signals       = [],
            input_tokens  = 0,
            output_tokens = 0,
            latency_ms    = 0.0,
            cost_usd      = 0.0,
            cache_hit     = False,
            error         = str(e),
        )


# ══════════════════════════════════════════════════════════════════════════
# 7.  INTEGRATION HELPER  (drop-in for main.py)
# ══════════════════════════════════════════════════════════════════════════

def handle_cache_miss(
    query:          str,
    router:         CascadeRouter,
    metrics:        CascadeMetrics,
    budget_usd:     Optional[float] = None,
    system_prompt:  str             = "You are a helpful assistant.",
) -> CascadeResponse:
    """
    Call this from main.py whenever cache.py returns a MISS.

    Example in main.py:
        from cache import SemanticCache
        from cascade import CascadeRouter, CascadeMetrics, handle_cache_miss

        cache  = SemanticCache()
        router = CascadeRouter()
        metrics = CascadeMetrics()

        cached = cache.get(query)
        if cached:
            return cached            # HIT
        else:
            resp = handle_cache_miss(query, router, metrics)
            cache.set(query, resp.answer)   # store for future hits
            return resp.answer
    """
    resp = router.route(
        query         = query,
        budget_usd    = budget_usd,
        system_prompt = system_prompt,
    )
    metrics.record(resp)
    return resp


# ══════════════════════════════════════════════════════════════════════════
# 8.  QUICK SMOKE-TEST
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    router = CascadeRouter()

    test_queries = [
        ("What is 2+2?",                                              None),
        ("Summarize the French Revolution briefly.",                  None),
        ("Design a distributed rate-limiter with Redis. Step by step, "
         "include architecture, code in Python, and tradeoffs.",      0.05),
        ("Translate 'hello' to Spanish.",                             0.001),
    ]

    print("\n" + "=" * 70)
    print("  CASCADE ROUTER — DRY-RUN ROUTING DECISIONS")
    print("=" * 70)

    for q, budget in test_queries:
        info = router.explain_routing(q, budget)
        print(f"\nQuery   : {q[:60]}{'…' if len(q) > 60 else ''}")
        print(f"Budget  : {'unlimited' if budget is None else f'${budget}'}")
        print(f"Score   : {info['smart_score']}  "
              f"(C={info['sub_scores']['complexity']}  "
              f"K={info['sub_scores']['keyword']}  "
              f"A={info['sub_scores']['ambiguity']}  "
              f"B={info['sub_scores']['budget']})")
        print(f"→ Tier  : {info['selected_tier'].upper()}  ({info['selected_model']})")
        print(f"Signals : {info['signals']}")

    print("\n" + "=" * 70)