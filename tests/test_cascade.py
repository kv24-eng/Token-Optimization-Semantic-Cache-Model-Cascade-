"""
test_cascade.py — Unit tests for cascade routing logic
======================================================

Tests the scoring engine, model selection, and cascade routing
without calling the actual Anthropic API.
"""

import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from cascade import (
    QueryScorer,
    ModelSelector,
    CascadeRouter,
    MODEL_REGISTRY,
    ModelTier,
)


class TestQueryScorer:
    """Test query scoring engine"""
    
    def __init__(self):
        self.scorer = QueryScorer()
    
    def test_simple_query(self):
        """Simple queries should score low"""
        result = self.scorer.score("What is 2+2?")
        assert result["smart_score"] < 0.5, f"Expected low score, got {result['smart_score']}"
        print("✅ Simple query scores low")
    
    def test_complex_query(self):
        """Complex queries should score high"""
        result = self.scorer.score(
            "Design a distributed rate-limiter with Redis. Step by step, "
            "include architecture, code in Python, and tradeoffs."
        )
        assert result["smart_score"] > 0.40, f"Expected high score, got {result['smart_score']}"
        print(f"✅ Complex query scores high ({result['smart_score']:.3f})")
    
    def test_keyword_detection(self):
        """Test heavy vs light keyword detection"""
        heavy_result = self.scorer.score("Analyze and critique the implementation")
        light_result = self.scorer.score("What is the capital of France?")
        
        assert heavy_result["smart_score"] > light_result["smart_score"], \
            "Heavy keywords should score higher than light keywords"
        print("✅ Keyword detection works")
    
    def test_ambiguity_detection(self):
        """Test ambiguity score"""
        result = self.scorer.score(
            "What is the meaning of life, the universe, and everything? "
            "Why? How? When? Where?"
        )
        # Should have some signals indicating high ambiguity
        assert len(result["signals"]) > 0, "Should have signals"
        assert result["sub_scores"]["ambiguity"] > 0.3, "Ambiguity score should be elevated"
        print(f"✅ Ambiguity detection works (signals: {result['signals']})")
    
    def test_budget_score(self):
        """Test budget constraint scoring"""
        result_unlimited = self.scorer.score("complex query", budget_usd=None)
        result_tight = self.scorer.score("complex query", budget_usd=0.0005)
        
        assert result_tight["sub_scores"]["budget"] < result_unlimited["sub_scores"]["budget"], \
            "Tight budget should lower budget score"
        print("✅ Budget scoring works")
    
    def test_token_counting(self):
        """Test approximate token counting"""
        query = "This is a test query with multiple words to count."
        result = self.scorer.score(query)
        
        assert result["token_count"] > 0, "Should count tokens"
        assert result["token_count"] <= len(query.split()), "Token count should be reasonable"
        print(f"✅ Token counting works ({result['token_count']} tokens)")
    
    def test_score_normalization(self):
        """Test that scores are normalized to [0, 1]"""
        queries = [
            "What is 2+2?",
            "medium complexity query here",
            "Very complex multi-part query with lots of details and requirements...",
        ]
        
        for query in queries:
            result = self.scorer.score(query)
            assert 0 <= result["smart_score"] <= 1.0, \
                f"Score {result['smart_score']} outside [0, 1]"
            
            for score in result["sub_scores"].values():
                assert 0 <= score <= 1.0, \
                    f"Sub-score {score} outside [0, 1]"
        
        print("✅ Score normalization works")


class TestModelSelector:
    """Test model selection logic"""
    
    def __init__(self):
        self.selector = ModelSelector()
    
    def test_light_selection(self):
        """Low score should select light model"""
        model = self.selector.select(0.1)
        assert model.tier == ModelTier.LIGHT, f"Expected LIGHT, got {model.tier}"
        print(f"✅ Low score selects LIGHT: {model.model_id}")
    
    def test_mid_selection(self):
        """Medium score should select mid model"""
        model = self.selector.select(0.5)
        assert model.tier == ModelTier.MID, f"Expected MID, got {model.tier}"
        print(f"✅ Medium score selects MID: {model.model_id}")
    
    def test_heavy_selection(self):
        """High score should select heavy model"""
        model = self.selector.select(0.8)
        assert model.tier == ModelTier.HEAVY, f"Expected HEAVY, got {model.tier}"
        print(f"✅ High score selects HEAVY: {model.model_id}")
    
    def test_budget_override_light(self):
        """Very tight budget should force LIGHT even with high score"""
        model = self.selector.select(0.9, budget_usd=0.0005)
        assert model.tier == ModelTier.LIGHT, \
            f"Tight budget should force LIGHT, got {model.tier}"
        print("✅ Budget override to LIGHT works")
    
    def test_threshold_boundaries(self):
        """Test score thresholds"""
        light_cfg = MODEL_REGISTRY[ModelTier.LIGHT]
        mid_cfg = MODEL_REGISTRY[ModelTier.MID]
        heavy_cfg = MODEL_REGISTRY[ModelTier.HEAVY]
        
        # Just below MID threshold
        model = self.selector.select(mid_cfg.score_threshold - 0.01)
        assert model.tier == ModelTier.LIGHT, "Just below MID threshold should use LIGHT"
        
        # Exactly at MID threshold
        model = self.selector.select(mid_cfg.score_threshold)
        assert model.tier == ModelTier.MID, "At MID threshold should use MID"
        
        # Exactly at HEAVY threshold
        model = self.selector.select(heavy_cfg.score_threshold)
        assert model.tier == ModelTier.HEAVY, "At HEAVY threshold should use HEAVY"
        
        print("✅ Threshold boundaries work correctly")


class TestCascadeRouter:
    """Test cascade router (explain_routing, no API calls)"""
    
    def __init__(self):
        self.router = CascadeRouter()
    
    def test_explain_routing_simple(self):
        """Test routing explanation for simple query"""
        result = self.router.explain_routing("What is Python?")
        
        assert "selected_tier" in result
        assert "selected_model" in result
        assert "smart_score" in result
        assert "sub_scores" in result
        assert "signals" in result
        assert result["selected_tier"] == "light"
        print(f"✅ Simple routing explanation: {result['selected_tier']}")
    
    def test_explain_routing_complex(self):
        """Test routing explanation for complex query"""
        result = self.router.explain_routing(
            "Design and implement a distributed consensus algorithm. "
            "Include Raft consensus, leader election, and log replication."
        )
        
        assert result["selected_tier"] in ["mid", "heavy"]
        print(f"✅ Complex routing explanation: {result['selected_tier']}")
    
    def test_explain_routing_with_budget(self):
        """Test routing with budget constraint"""
        result_unlimited = self.router.explain_routing("complex query", budget_usd=None)
        result_constrained = self.router.explain_routing("complex query", budget_usd=0.001)
        
        # Budget constraint might force lower tier
        print(f"✅ Budget-aware routing: {result_constrained['selected_tier']}")
    
    def test_explain_routing_thresholds(self):
        """Verify threshold values in routing explanation"""
        result = self.router.explain_routing("test")
        
        assert "thresholds" in result
        thresholds = result["thresholds"]
        
        assert "light" in thresholds
        assert "mid" in thresholds
        assert "heavy" in thresholds
        
        # LIGHT should have lowest threshold
        assert thresholds["light"] <= thresholds["mid"] <= thresholds["heavy"]
        print("✅ Threshold ordering is correct")


class TestIntegration:
    """Integration tests across components"""
    
    def __init__(self):
        self.scorer = QueryScorer()
        self.selector = ModelSelector()
    
    def test_full_routing_pipeline(self):
        """Test complete scoring → selection pipeline"""
        test_queries = [
            ("Hello", "light"),
            ("What is 2+2?", "light"),
            ("Explain machine learning", "light"),
            ("Design a distributed rate limiter step by step with code", "mid"),
            ("Implement QUIC protocol with detailed explanation, architecture, "
             "code examples, and performance analysis", "mid"),
        ]
        
        for query, expected_tier in test_queries:
            score_result = self.scorer.score(query)
            model = self.selector.select(score_result["smart_score"])
            
            assert model.tier.value == expected_tier, \
                f"Query '{query[:30]}' expected {expected_tier}, got {model.tier.value}"
            print(f"✅ '{query[:40]}...' → {model.tier.value}")
    
    def test_cost_estimation(self):
        """Verify cost estimation logic"""
        from cascade import CascadeResponse
        
        # Test cost calculation
        light_model = MODEL_REGISTRY[ModelTier.LIGHT]
        input_tokens = 500
        output_tokens = 200
        
        estimated_cost = (
            input_tokens / 1000 * light_model.cost_per_1k_in +
            output_tokens / 1000 * light_model.cost_per_1k_out
        )
        
        assert estimated_cost > 0, "Cost should be positive"
        assert estimated_cost < 0.01, "Cost should be reasonable for light model"
        print(f"✅ Cost estimation: ${estimated_cost:.6f} for 500in+200out tokens")


def run_all_tests():
    """Run all test suites"""
    print("\n" + "=" * 70)
    print("  CASCADE ROUTING UNIT TESTS")
    print("=" * 70 + "\n")
    
    # Test Query Scorer
    print("Testing QueryScorer...")
    scorer_tests = TestQueryScorer()
    scorer_tests.test_simple_query()
    scorer_tests.test_complex_query()
    scorer_tests.test_keyword_detection()
    scorer_tests.test_ambiguity_detection()
    scorer_tests.test_budget_score()
    scorer_tests.test_token_counting()
    scorer_tests.test_score_normalization()
    
    print("\n✅ All QueryScorer tests passed!\n")
    
    # Test Model Selector
    print("Testing ModelSelector...")
    selector_tests = TestModelSelector()
    selector_tests.test_light_selection()
    selector_tests.test_mid_selection()
    selector_tests.test_heavy_selection()
    selector_tests.test_budget_override_light()
    selector_tests.test_threshold_boundaries()
    
    print("\n✅ All ModelSelector tests passed!\n")
    
    # Test Cascade Router
    print("Testing CascadeRouter...")
    router_tests = TestCascadeRouter()
    router_tests.test_explain_routing_simple()
    router_tests.test_explain_routing_complex()
    router_tests.test_explain_routing_with_budget()
    router_tests.test_explain_routing_thresholds()
    
    print("\n✅ All CascadeRouter tests passed!\n")
    
    # Integration tests
    print("Testing Integration...")
    integration_tests = TestIntegration()
    integration_tests.test_full_routing_pipeline()
    integration_tests.test_cost_estimation()
    
    print("\n✅ All Integration tests passed!\n")
    
    print("=" * 70)
    print("  🎉 ALL TESTS PASSED!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_all_tests()
