"""
Unit and Integration Tests for Phase 5: Output Validation & Post-Processing.

Validates:
1. Strict sentence limit enforcement (<= 3 sentences) without breaking decimals/currencies.
2. Single valid citation link integrity against the approved whitelist.
3. Mandatory date footer formatting ('Last updated from sources: <date>').
4. Advisory trigger words / recommendation leakage detection and scrubbing.
5. Structured ValidationResult contract.
6. Full End-to-End pipeline: Guardrail -> Retriever -> Generator -> Validator.
"""

import pytest
import re
from src.core.validator import ResponseValidator, ValidationResult
from src.core.guardrail import GuardrailEngine
from src.core.retriever import SemanticRetriever
from src.core.generator import RAGGenerator
from src.config import GROWW_SCHEMES, SEBI_INVESTOR_URL, AMFI_INVESTOR_URL


@pytest.fixture
def validator():
    return ResponseValidator()


# ==============================================================================
# 1. Sentence Count Enforcement Tests
# ==============================================================================

def test_sentence_count_enforcement(validator: ResponseValidator):
    verbose_text = (
        "Sentence one is here. Sentence two gives details. "
        "Sentence three provides context. Sentence four is too long and must be trimmed. "
        "Sentence five should never appear."
    )
    url = "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
    res = validator.validate_and_format(verbose_text, fallback_url=url)
    
    # Extract body before Source
    body = res.split("Source:")[0].strip()
    sentences = validator.split_sentences(body)
    assert len(sentences) <= 3, f"Expected <= 3 sentences, got {len(sentences)}"
    assert "Sentence four" not in body
    assert "Sentence five" not in body
    assert "Sentence one is here." in body


def test_sentence_splitting_protects_decimals_and_currencies(validator: ResponseValidator):
    complex_text = (
        "The expense ratio of HDFC Small Cap Fund is 0.75% (inclusive of GST). "
        "The fund has an AUM of ₹41,679.00 Cr and current NAV of ₹161.46. "
        "STCG is taxed at 20% and LTCG exceeding ₹1.25 Lakh is taxed at 12.5%."
    )
    sentences = validator.split_sentences(complex_text)
    assert len(sentences) == 3, f"Expected exactly 3 sentences, got {len(sentences)}: {sentences}"
    assert "0.75%" in sentences[0]
    assert "₹41,679.00 Cr" in sentences[1]
    assert "12.5%" in sentences[2]


# ==============================================================================
# 2. Citation Whitelist & Single URL Verification Tests
# ==============================================================================

def test_single_citation_and_footer(validator: ResponseValidator):
    res = validator.validate_and_format(
        "The exit load is 1% for 1 year.",
        fallback_url="https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth"
    )
    assert "Source: https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth" in res
    assert "Last updated from sources:" in res

    # Verify exactly 1 URL
    urls = re.findall(r"https?://[^\s]+", res)
    assert len(urls) == 1


def test_strips_extraneous_inline_links(validator: ResponseValidator):
    text_with_multiple_links = (
        "You can check the fund at [Groww Page](https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth) "
        "or visit https://groww.in/random for more info.\n\n"
        "Source: https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth\n"
        "Last updated from sources: 2026-08-23"
    )
    res = validator.validate_and_format(text_with_multiple_links)
    
    # Body should have no raw links or markdown links
    body = res.split("Source:")[0]
    assert "http://" not in body and "https://" not in body
    assert "[Groww Page]" not in body

    # Exactly 1 URL at the bottom
    urls = re.findall(r"https?://[^\s]+", res)
    assert len(urls) == 1
    assert urls[0] == "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"


# ==============================================================================
# 3. Advisory Trigger Word & Leakage Scrubbing Tests
# ==============================================================================

@pytest.mark.parametrize("raw_input,prohibited_word", [
    ("I recommend investing in HDFC Small Cap. The expense ratio is 0.75%.", "I recommend"),
    ("You should buy this fund immediately. The exit load is 1%.", "You should buy"),
    ("This is the best choice for high returns. Minimum SIP is ₹100.", "best choice"),
    ("We advise choosing Direct growth option. Stamp duty is 0.005%.", "We advise"),
])
def test_advisory_leakage_scrubbing(validator: ResponseValidator, raw_input: str, prohibited_word: str):
    res = validator.validate_and_format(raw_input, fallback_url=GROWW_SCHEMES[0]["url"])
    assert prohibited_word.lower() not in res.lower()
    
    # Body must remain coherent and formatted
    assert "Source:" in res
    assert "Last updated from sources:" in res


# ==============================================================================
# 4. Structured ValidationResult Contract Tests
# ==============================================================================

def test_structured_validation_result(validator: ResponseValidator):
    raw = (
        "I recommend HDFC Small Cap. Sentence one. Sentence two. Sentence three. Sentence four.\n\n"
        "Source: https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth\n"
        "Last updated from sources: 2026-08-23"
    )
    result = validator.validate(raw)
    assert isinstance(result, ValidationResult)
    assert result.valid is True
    assert result.had_advisory_leakage is True
    assert result.was_truncated is True
    assert result.sentence_count <= 3
    assert result.citation_url == "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth"
    assert result.last_updated == "2026-08-23"


# ==============================================================================
# 5. Full End-to-End Pipeline Integration Test
# ==============================================================================

def test_full_pipeline_with_validation():
    guardrail = GuardrailEngine()
    retriever = SemanticRetriever()
    generator = RAGGenerator()
    validator = ResponseValidator()

    query = "What is the exit load of HDFC Small Cap Fund?"
    
    # Step 1: Guardrail
    g_res = guardrail.process_query(query)
    assert g_res.passed is True
    
    # Step 2: Retriever
    retrieved = retriever.retrieve(query, detected_scheme_ids=g_res.detected_scheme_ids, top_k=3)
    assert len(retrieved) > 0
    
    # Step 3: Generator
    raw_response = generator.generate(query, retrieved)
    assert len(raw_response) > 0
    
    # Step 4: Validator
    final_output = validator.validate_and_format(raw_response)
    
    # Final compliance checks
    assert "1%" in final_output
    assert "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth" in final_output
    assert "Last updated from sources:" in final_output
    
    # Sentence count strictly <= 3
    body = final_output.split("Source:")[0].strip()
    sentences = validator.split_sentences(body)
    assert len(sentences) <= 3
    
    # Exactly 1 URL
    urls = re.findall(r"https?://[^\s]+", final_output)
    assert len(urls) == 1
