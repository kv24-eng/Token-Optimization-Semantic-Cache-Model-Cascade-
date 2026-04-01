"""
streamlit_app.py — Frontend UI for Semantic Cache + Model Cascade
==================================================================

Interactive Streamlit interface to:
- Query the LLM with cache and cascade optimization
- Visualize routing decisions
- Monitor cache performance and cost metrics
- Test semantic cache similarity
"""

import streamlit as st
import requests
import json
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"

st.set_page_config(
    page_title="Semantic Cache + Model Cascade",
    page_icon="🚀",
    layout="wide",
)

st.title("🚀 Semantic Cache + Model Cascade")
st.markdown("Cost-optimized LLM responses with intelligent routing and caching")

# ── Sidebar Configuration ─────────────────────────────────────────────────

with st.sidebar:
    st.header("Configuration")
    
    budget_mode = st.radio(
        "Budget Mode",
        options=["No Limit", "Moderate", "Tight"],
        help="Controls which model tier to prefer"
    )
    
    budget_map = {
        "No Limit": None,
        "Moderate": 0.01,
        "Tight": 0.001,
    }
    budget_usd = budget_map[budget_mode]
    
    if budget_usd:
        st.info(f"💰 Budget cap: ${budget_usd}")
    
    st.divider()
    st.subheader("API Health")
    
    try:
        resp = requests.get(f"{API_BASE_URL}/", timeout=2)
        if resp.status_code == 200:
            st.success("✅ API is running")
        else:
            st.error("❌ API error")
    except:
        st.error("❌ Cannot reach API. Ensure FastAPI server is running on port 8000")


# ── Main Chat Interface ───────────────────────────────────────────────────

st.header("Chat Interface")

col1, col2 = st.columns([3, 1])

with col1:
    user_query = st.text_input(
        "Enter your question:",
        placeholder="e.g., Explain transformer architecture step by step",
        label_visibility="collapsed"
    )

with col2:
    submit_button = st.button("Send", type="primary", use_container_width=True)

if submit_button and user_query:
    with st.spinner("Processing..."):
        try:
            response = requests.post(
                f"{API_BASE_URL}/chat",
                json={"query": user_query, "budget_usd": budget_usd},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Display response
                st.success("✅ Response received")
                
                st.markdown("### Answer")
                st.write(result["response"])
                
                # Metrics display
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    cache_badge = "🎯" if result["was_cached"] else "🔄"
                    st.metric(
                        f"{cache_badge} Cache",
                        "HIT" if result["was_cached"] else "MISS"
                    )
                
                with col2:
                    st.metric("Model Tier", result["tier"].upper())
                
                with col3:
                    st.metric("Score", f"{result['smart_score']:.2f}")
                
                with col4:
                    st.metric("Cost", f"${result['cost_usd']:.6f}")
                
                st.divider()
                
                # Detailed metrics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Input Tokens", result["input_tokens"])
                
                with col2:
                    st.metric("Output Tokens", result["output_tokens"])
                
                with col3:
                    st.metric("Latency", f"{result['latency_ms']:.1f} ms")
                
                with col4:
                    if result.get("similarity"):
                        st.metric("Similarity", f"{result['similarity']:.2%}")
                
                # Cache hit details
                if result["was_cached"]:
                    st.info(f"📌 Matched query: *{result['matched_query']}*")
                else:
                    st.info(f"🤖 Using model: **{result['model_used']}**")
                
            else:
                st.error(f"Error: {response.status_code}")
                st.write(response.json())
                
        except requests.exceptions.Timeout:
            st.error("⏱️ Request timeout. API might be slow or unreachable.")
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to API. Make sure the server is running.")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")


# ── Routing Explanation ───────────────────────────────────────────────────

st.divider()
st.header("Routing Explanation")

explain_query = st.text_input(
    "Analyze how this query would be routed (dry-run):",
    placeholder="e.g., Translate hello to Spanish",
    key="explain_input"
)

if explain_query:
    try:
        params = {"query": explain_query}
        if budget_usd:
            params["budget_usd"] = budget_usd
        
        response = requests.get(
            f"{API_BASE_URL}/routing/explain",
            params=params,
            timeout=5
        )
        
        if response.status_code == 200:
            routing = response.json()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Selected Tier", routing["selected_tier"].upper())
            
            with col2:
                st.metric("Smart Score", f"{routing['smart_score']:.3f}")
            
            with col3:
                st.metric("Model", routing["selected_model"][-30:])  # last 30 chars
            
            # Sub-scores
            st.subheader("Component Scores")
            sub_cols = st.columns(4)
            
            for idx, (name, value) in enumerate(routing["sub_scores"].items()):
                with sub_cols[idx]:
                    st.metric(name.capitalize(), f"{value:.3f}")
            
            # Signals
            if routing["signals"]:
                st.subheader("Signals Detected")
                st.write(", ".join([f"`{s}`" for s in routing["signals"]]))
            
    except Exception as e:
        st.warning(f"Could not explain routing: {str(e)}")


# ── Metrics Dashboard ────────────────────────────────────────────────────

st.divider()
st.header("📊 Metrics Dashboard")

try:
    metrics_response = requests.get(f"{API_BASE_URL}/metrics", timeout=5)
    
    if metrics_response.status_code == 200:
        metrics = metrics_response.json()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Queries", metrics["total_queries"])
        
        with col2:
            hit_rate = metrics["cache_hit_rate"]
            st.metric("Cache Hit Rate", f"{hit_rate:.1%}")
        
        with col3:
            st.metric("Total Cost", f"${metrics['total_cost_usd']:.4f}")
        
        with col4:
            st.metric("Avg Latency", f"{metrics['avg_latency_ms']:.1f} ms")
        
        st.divider()
        
        # Tier distribution
        tier_data = metrics["tier_distribution"]
        if tier_data and any(tier_data.values()):
            st.subheader("Model Tier Distribution")
            st.bar_chart(tier_data)
        
        # Cache stats
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Cache Statistics")
            st.write(f"- Hits: {metrics['cache_hits']}")
            st.write(f"- Misses: {metrics['cache_misses']}")
            st.write(f"- Total Stored: {metrics['cache_total_stored']}")
        
        with col2:
            st.subheader("Token Usage")
            st.write(f"- Total Tokens: {metrics['total_tokens']}")
            st.write(f"- Errors: {metrics['errors']}")
        
except Exception as e:
    st.warning(f"Could not load metrics: {str(e)}")


# ── Cache Management ────────────────────────────────────────────────────

st.divider()
st.header("🗑️ Cache Management")

if st.button("Clear Cache", type="secondary"):
    try:
        response = requests.delete(f"{API_BASE_URL}/cache/clear", timeout=5)
        if response.status_code == 200:
            st.success("✅ Cache cleared successfully")
        else:
            st.error(f"Error: {response.status_code}")
    except Exception as e:
        st.error(f"Failed to clear cache: {str(e)}")

st.info("ℹ️ Clearing the cache will remove all cached responses but won't affect metrics history.")

# ── Footer ───────────────────────────────────────────────────────────────

st.divider()
st.markdown(
    """
    ---
    **Semantic Cache + Model Cascade** — Cost-optimized LLM inference
    - 🎯 Semantic caching with configurable similarity threshold
    - 🔀 Intelligent model routing based on query complexity
    - 💰 Cost optimization through smart tier selection
    - 📊 Real-time metrics and performance tracking
    """
)
