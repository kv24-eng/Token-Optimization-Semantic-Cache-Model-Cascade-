"""
metrics.py — Metrics tracking and reporting
============================================

Provides functionality to track cascade routing performance,
cache statistics, cost optimization, and request latency.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import json


@dataclass
class RequestMetrics:
    """Individual request metrics"""
    timestamp:     datetime
    query:         str
    model_used:    str
    tier:          str
    smart_score:   float
    input_tokens:  int
    output_tokens: int
    latency_ms:    float
    cost_usd:      float
    was_cached:    bool
    error:         Optional[str] = None


@dataclass
class AggregatedMetrics:
    """Aggregated metrics across all requests"""
    total_requests:    int = 0
    cache_hits:        int = 0
    cache_hit_rate:    float = 0.0
    total_cost_usd:    float = 0.0
    total_tokens:      int = 0
    avg_latency_ms:    float = 0.0
    tier_distribution: dict = field(default_factory=lambda: {"light": 0, "mid": 0, "heavy": 0, "cache": 0})
    errors:            int = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": f"{self.cache_hit_rate:.1%}",
            "total_cost_usd": round(self.total_cost_usd, 4),
            "total_tokens": self.total_tokens,
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "tier_distribution": self.tier_distribution,
            "errors": self.errors,
        }


class MetricsTracker:
    """Track and aggregate metrics across requests"""
    
    def __init__(self):
        self.requests: list[RequestMetrics] = []
        self.aggregated = AggregatedMetrics()
    
    def record_request(self, **kwargs) -> None:
        """Record a single request"""
        kwargs["timestamp"] = datetime.now()
        metric = RequestMetrics(**kwargs)
        self.requests.append(metric)
        self._update_aggregated(metric)
    
    def _update_aggregated(self, metric: RequestMetrics) -> None:
        """Update aggregated metrics"""
        self.aggregated.total_requests += 1
        
        if metric.was_cached:
            self.aggregated.cache_hits += 1
        
        self.aggregated.total_cost_usd += metric.cost_usd
        self.aggregated.total_tokens += metric.input_tokens + metric.output_tokens
        
        # Update latency average
        if self.aggregated.total_requests > 1:
            prev_avg = self.aggregated.avg_latency_ms
            self.aggregated.avg_latency_ms = (
                (prev_avg * (self.aggregated.total_requests - 1) + metric.latency_ms)
                / self.aggregated.total_requests
            )
        else:
            self.aggregated.avg_latency_ms = metric.latency_ms
        
        # Update cache hit rate
        if self.aggregated.total_requests > 0:
            self.aggregated.cache_hit_rate = (
                self.aggregated.cache_hits / self.aggregated.total_requests
            )
        
        # Update tier distribution
        tier_key = metric.tier.lower()
        if tier_key in self.aggregated.tier_distribution:
            self.aggregated.tier_distribution[tier_key] += 1
        
        if metric.error:
            self.aggregated.errors += 1
    
    def get_summary(self) -> dict:
        """Get current metrics summary"""
        return self.aggregated.to_dict()
    
    def get_recent_requests(self, limit: int = 10) -> list[dict]:
        """Get recent requests"""
        recent = self.requests[-limit:] if self.requests else []
        return [
            {
                "timestamp": r.timestamp.isoformat(),
                "query": r.query[:100],  # truncate for display
                "model": r.model_used,
                "tier": r.tier,
                "cost_usd": round(r.cost_usd, 6),
                "latency_ms": r.latency_ms,
                "was_cached": r.was_cached,
                "error": r.error,
            }
            for r in recent
        ]
    
    def reset(self) -> None:
        """Reset all metrics"""
        self.requests = []
        self.aggregated = AggregatedMetrics()
    
    def export_to_json(self, filepath: str) -> None:
        """Export metrics to JSON file"""
        data = {
            "summary": self.get_summary(),
            "recent_requests": self.get_recent_requests(100),
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[METRICS] Exported to {filepath}")


# Global metrics tracker instance
metrics_tracker = MetricsTracker()
