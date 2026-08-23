"""
Streamlit Web UI for Groww Mutual Fund FAQ Assistant.

Provides interactive web application with:
- Persistent Compliance Disclaimer: 'Facts-only. No investment advice.'
- 5 HDFC Mutual Fund Scheme Selector & Quick Metrics Cards
- Interactive Factual Query Chips
- Compliance-First Chat Interface with verified source links & timestamp footers
"""

import streamlit as st
from src.config import (
    GROWW_SCHEMES,
    DISCLAIMER_TEXT,
    GROQ_MODEL,
    EMBEDDING_MODEL_NAME,
    SEBI_INVESTOR_URL,
    AMFI_INVESTOR_URL,
)
from src.core.guardrail import GuardrailEngine
from src.core.retriever import SemanticRetriever
from src.core.generator import RAGGenerator
from src.core.validator import ResponseValidator

# Page Configuration
st.set_page_config(
    page_title="Groww Mutual Fund FAQ Assistant",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling matching Groww Fintech Theme
st.markdown("""
<style>
    /* Global Styles */
    .stApp {
        background-color: #0B0F17;
        color: #F8FAFC;
    }
    
    /* Header Banner */
    .compliance-header-banner {
        background-color: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.3);
        border-radius: 8px;
        padding: 10px 16px;
        color: #F59E0B;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    /* Scheme Card in Sidebar */
    .scheme-sidebar-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 10px;
    }
    
    .scheme-sidebar-title {
        font-size: 0.88rem;
        font-weight: 600;
        color: #F8FAFC;
    }
    
    .scheme-sidebar-meta {
        font-size: 0.75rem;
        color: #00D09C;
        margin-top: 4px;
    }
    
    /* Verified Badge */
    .verified-badge {
        background-color: rgba(0, 208, 156, 0.12);
        color: #00D09C;
        border: 1px solid rgba(0, 208, 156, 0.3);
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 0.72rem;
        font-weight: 600;
        display: inline-block;
        margin-top: 6px;
    }
    
    /* Citation Link */
    .citation-link {
        color: #00D09C !important;
        font-size: 0.8rem;
        text-decoration: none;
        font-weight: 500;
    }
    .citation-link:hover {
        text-decoration: underline;
    }
</style>
""", unsafe_allow_html=True)


# Initialize Session State & Singletons
@st.cache_resource
def get_engine_instances():
    g = GuardrailEngine()
    r = SemanticRetriever()
    gen = RAGGenerator()
    val = ResponseValidator()
    return g, r, gen, val


guardrail, retriever, generator, validator = get_engine_instances()

if "messages" not in st.session_state:
    st.session_state.messages = []


# ==============================================================================
# SIDEBAR: COVERED SCHEMES DIRECTORY & FACTSHEET
# ==============================================================================

with st.sidebar:
    st.title("📊 Scheme Directory")
    st.caption("5 Supported HDFC Mutual Fund Schemes")
    
    for s in GROWW_SCHEMES:
        st.markdown(f"""
        <div class="scheme-sidebar-card">
            <div class="scheme-sidebar-title">{s['name']}</div>
            <div class="scheme-sidebar-meta">{s['category']} • Direct Growth</div>
            <div style="margin-top:6px;">
                <a href="{s['url']}" target="_blank" class="citation-link">View on Groww ↗</a>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    st.subheader("Investor Education")
    st.markdown(f"- [SEBI Investor Portal]({SEBI_INVESTOR_URL})")
    st.markdown(f"- [AMFI Knowledge Center]({AMFI_INVESTOR_URL})")
    
    st.markdown("---")
    st.caption(f"**Models:** {GROQ_MODEL} • {EMBEDDING_MODEL_NAME}")


# ==============================================================================
# MAIN PAGE: HEADER & CHAT
# ==============================================================================

st.title("Groww Mutual Fund FAQ Assistant")
st.markdown(
    f"""
    <div class="compliance-header-banner">
        ⚠️ <strong>{DISCLAIMER_TEXT}</strong> All answers are strictly grounded in official Groww scheme data.
    </div>
    """,
    unsafe_allow_html=True
)

# Interactive Question Chips
st.markdown("##### Popular Factual Questions:")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("What is the expense ratio of HDFC Small Cap?"):
        st.session_state.current_prompt = "What is the expense ratio of HDFC Small Cap Fund?"

with col2:
    if st.button("Exit load for HDFC Mid-Cap Opportunities?"):
        st.session_state.current_prompt = "What is the exit load for HDFC Mid-Cap Opportunities Fund?"

with col3:
    if st.button("How to download capital gains statement?"):
        st.session_state.current_prompt = "How can I download my mutual fund capital gains statement on Groww?"


# Display Message History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("source_url"):
            st.markdown(f"[Source Factsheet: {msg['source_url']}]({msg['source_url']})")


# Prompt Input Handler
prompt = st.chat_input("Ask a factual question about the 5 HDFC schemes...")
if hasattr(st.session_state, "current_prompt") and st.session_state.current_prompt:
    prompt = st.session_state.current_prompt
    st.session_state.current_prompt = None

if prompt:
    # Append User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Process via RAG Pipeline
    with st.chat_message("assistant"):
        with st.spinner("Retrieving verified facts..."):
            # 1. Guardrail
            g_res = guardrail.process_query(prompt)

            if not g_res.passed:
                refusal = g_res.refusal_response or guardrail.get_refusal_response(g_res.intent)
                val_res = validator.validate(refusal)
                st.markdown(val_res.formatted_output)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": val_res.formatted_output,
                    "source_url": val_res.citation_url
                })
            else:
                # 2. Retriever
                retrieved = retriever.retrieve(prompt, detected_scheme_ids=g_res.detected_scheme_ids, top_k=4)
                
                # 3. Generator
                raw_ans = generator.generate(prompt, retrieved)
                
                # 4. Validator
                fallback_url = retrieved[0]["chunk"].get("url") if retrieved else None
                val_res = validator.validate(raw_ans, fallback_url=fallback_url)
                
                st.markdown(val_res.formatted_output)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": val_res.formatted_output,
                    "source_url": val_res.citation_url
                })
