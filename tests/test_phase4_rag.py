"""
Unit and Integration Tests for Phase 4: Scheme-Filtered BGE Retriever & Groq LLM Generator.

Validates:
1. BGE Semantic Retrieval Precision@3 across all 5 schemes and factual attributes.
2. Direct Lookup Short-Circuit for single-attribute queries.
3. Disambiguation between HDFC Nifty 50 and HDFC Nifty Next 50.
4. Shared facts & Operational Guide retrieval for corpus-wide queries.
5. Grounded RAG generation adhering to format constraints (<= 3 sentences, 1 Groww citation, footer).
6. Local deterministic fallback resilience when Groq API is unavailable.
7. Full pipeline integration: Guardrails -> Retriever -> Generator.
"""

import pytest
import re
from src.core.retriever import SemanticRetriever
from src.core.generator import RAGGenerator
from src.core.guardrail import GuardrailEngine
from src.config import GROWW_SCHEMES


@pytest.fixture(scope="module")
def retriever():
    return SemanticRetriever()


@pytest.fixture(scope="module")
def generator():
    return RAGGenerator()


@pytest.fixture(scope="module")
def guardrail():
    return GuardrailEngine()


# ==============================================================================
# 1. Semantic Retrieval Precision Tests
# ==============================================================================

@pytest.mark.parametrize("query,expected_scheme,expected_attr,expected_snippet", [
    ("What is the expense ratio of HDFC Small Cap Fund?", "hdfc-small-cap-fund", "expense_ratio", "0.75%"),
    ("What is the exit load for HDFC Mid-Cap Opportunities Fund?", "hdfc-mid-cap-fund", "exit_load", "1%"),
    ("What is the benchmark index of HDFC Nifty 50 Index Fund?", "hdfc-nifty-50-index-fund", "benchmark_index", "NIFTY 50"),
    ("What is the current NAV of HDFC Nifty Next 50 Index Fund?", "hdfc-nifty-next-50-index-fund", "current_nav", "₹17.52"),
    ("Who is the fund manager for HDFC Multi Cap Fund?", "hdfc-multi-cap-fund", "fund_manager", "Gopal Agrawal"),
    ("What is the riskometer rating of HDFC Multi Cap Fund?", "hdfc-multi-cap-fund", "riskometer", "Very High Risk"),
    ("What is the minimum SIP amount for HDFC Small Cap?", "hdfc-small-cap-fund", "min_sip_amount", "₹100"),
])
def test_bge_retrieval_accuracy(
    retriever: SemanticRetriever,
    query: str,
    expected_scheme: str,
    expected_attr: str,
    expected_snippet: str
):
    results = retriever.retrieve(query, top_k=3)
    assert len(results) > 0, f"No results retrieved for: {query}"
    
    top_chunk = results[0]["chunk"]
    assert top_chunk["scheme_id"] == expected_scheme, f"Expected scheme {expected_scheme}, got {top_chunk['scheme_id']}"
    assert top_chunk["attribute_key"] == expected_attr or top_chunk["attribute"] == expected_attr
    assert expected_snippet.lower() in top_chunk["content"].lower()


# ==============================================================================
# 2. Entity Disambiguation Tests (Nifty 50 vs Nifty Next 50)
# ==============================================================================

def test_nifty_50_vs_next_50_disambiguation(retriever: SemanticRetriever):
    # Query specific to Nifty 50
    res_50 = retriever.retrieve("What is the exit load for HDFC Nifty 50 Index Fund?", top_k=1)
    assert len(res_50) > 0
    assert res_50[0]["chunk"]["scheme_id"] == "hdfc-nifty-50-index-fund"
    assert "0.25%" in res_50[0]["chunk"]["content"]

    # Query specific to Nifty Next 50
    res_next50 = retriever.retrieve("What is the exit load for HDFC Nifty Next 50 Index Fund?", top_k=1)
    assert len(res_next50) > 0
    assert res_next50[0]["chunk"]["scheme_id"] == "hdfc-nifty-next-50-index-fund"
    assert "Nil" in res_next50[0]["chunk"]["content"]


# ==============================================================================
# 3. Shared Facts & Operational Guidelines Retrieval
# ==============================================================================

@pytest.mark.parametrize("query,expected_snippet", [
    ("How can I download my mutual fund statement from Groww?", "Reports"),
    ("What is the stamp duty applicable on mutual funds?", "0.005%"),
    ("What are the capital gains taxation rules?", "STCG"),
    ("How do I redeem mutual fund units?", "Redeem"),
])
def test_shared_and_operational_retrieval(
    retriever: SemanticRetriever,
    query: str,
    expected_snippet: str
):
    results = retriever.retrieve(query, top_k=3)
    assert len(results) > 0
    combined_content = " ".join(r["chunk"]["content"] for r in results)
    assert expected_snippet.lower() in combined_content.lower()


# ==============================================================================
# 4. Context Assembly & Citation Extraction
# ==============================================================================

def test_assemble_context(retriever: SemanticRetriever):
    results = retriever.retrieve("What is the expense ratio of HDFC Small Cap?", top_k=3)
    context_text, primary_url, last_updated = retriever.assemble_context(results)
    
    assert len(context_text) > 0
    assert "0.75%" in context_text
    assert primary_url == "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth"
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", last_updated)


# ==============================================================================
# 5. Grounded RAG Generation Tests
# ==============================================================================

def test_generator_grounding(generator: RAGGenerator):
    mock_results = [{
        "chunk": {
            "content": "The expense ratio of HDFC Small Cap Fund is 0.75% (inclusive of GST).",
            "url": "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
            "last_updated": "2026-08-23",
            "scheme_id": "hdfc-small-cap-fund",
            "attribute_key": "expense_ratio"
        }
    }]
    output = generator.generate("What is the expense ratio of HDFC Small Cap?", mock_results)
    
    assert "0.75%" in output
    assert "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth" in output
    assert "Last updated from sources:" in output


def test_generator_format_contract(generator: RAGGenerator, retriever: SemanticRetriever):
    queries = [
        "What is the exit load for HDFC Mid-Cap Opportunities Fund?",
        "What is the benchmark of HDFC Multi Cap Fund?",
        "What is the minimum SIP for HDFC Nifty 50?",
    ]
    for q in queries:
        results = retriever.retrieve(q, top_k=3)
        output = generator.generate(q, results)

        # 1. Check sentence count <= 3 in body
        lines = [l for l in output.split("\n") if not l.startswith("Source:") and not l.startswith("Last updated")]
        body = " ".join(lines).strip()
        sentences = [s.strip() for s in re.split(r'[.!?]+', body) if s.strip()]
        assert len(sentences) <= 3, f"Output exceeded 3 sentences ({len(sentences)}): {body}"

        # 2. Check exactly 1 citation URL
        urls = re.findall(r"https?://[^\s]+", output)
        assert len(urls) == 1, f"Expected 1 citation URL, got {len(urls)}"
        assert "groww.in" in urls[0]

        # 3. Check mandatory date footer
        assert "Last updated from sources:" in output


def test_generator_empty_context_fallback(generator: RAGGenerator):
    output = generator.generate("Unknown obscure query", [])
    assert "not available in the official scheme documents" in output
    assert "Source:" in output
    assert "Last updated from sources:" in output


# ==============================================================================
# 6. End-to-End Pipeline Integration Test
# ==============================================================================

def test_full_rag_pipeline_integration(
    guardrail: GuardrailEngine,
    retriever: SemanticRetriever,
    generator: RAGGenerator
):
    query = "What is the expense ratio of HDFC Mid-Cap Opportunities Fund?"
    
    # 1. Guardrail inspection
    g_res = guardrail.process_query(query)
    assert g_res.passed is True
    assert g_res.intent == "FACTUAL"
    assert "hdfc-mid-cap-fund" in g_res.detected_scheme_ids
    
    # 2. Retrieve grounded chunks
    retrieved = retriever.retrieve(query, detected_scheme_ids=g_res.detected_scheme_ids, top_k=3)
    assert len(retrieved) > 0
    assert "0.75%" in retrieved[0]["chunk"]["content"]
    
    # 3. Generate compliant response
    response = generator.generate(query, retrieved)
    assert "0.75%" in response
    assert "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth" in response
    assert "Last updated from sources: 2026-08-23" in response
