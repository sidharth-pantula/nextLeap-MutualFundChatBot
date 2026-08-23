import pytest
from pathlib import Path


def test_config_completeness():
    """Verify all configuration constants and 5 Groww schemes are loaded."""
    from src.config import (
        GROWW_SCHEMES,
        DISCLAIMER_TEXT,
        SEBI_INVESTOR_URL,
        AMFI_INVESTOR_URL,
        MAX_SENTENCE_LIMIT,
        GROQ_MODEL,
        GROQ_TEMPERATURE,
        EMBEDDING_MODEL_NAME,
        DATA_DIR,
        RAW_DATA_DIR,
        PROCESSED_DATA_DIR,
        CHROMA_DB_DIR
    )

    assert len(GROWW_SCHEMES) == 5
    assert DISCLAIMER_TEXT == "Facts-only. No investment advice."
    assert MAX_SENTENCE_LIMIT == 3
    assert GROQ_MODEL == "llama-3.3-70b-versatile"
    assert GROQ_TEMPERATURE == 0.0
    assert EMBEDDING_MODEL_NAME == "BAAI/bge-small-en-v1.5"

    assert SEBI_INVESTOR_URL == "https://investor.sebi.gov.in/"
    assert AMFI_INVESTOR_URL.startswith("https://www.amfiindia.com/")

    # Check directory existence
    assert DATA_DIR.exists()
    assert RAW_DATA_DIR.exists()
    assert PROCESSED_DATA_DIR.exists()
    assert CHROMA_DB_DIR.exists()

    # Check Groww URLs format
    for scheme in GROWW_SCHEMES:
        assert "id" in scheme
        assert "name" in scheme
        assert "category" in scheme
        assert "url" in scheme
        assert scheme["url"].startswith("https://groww.in/mutual-funds/")
        assert len(scheme["search_aliases"]) > 0


def test_package_structure():
    """Verify package subdirectories exist and contain __init__.py."""
    base = Path(__file__).resolve().parent.parent
    assert (base / "src" / "__init__.py").exists()
    assert (base / "src" / "ingestion" / "__init__.py").exists()
    assert (base / "src" / "core" / "__init__.py").exists()
    assert (base / "src" / "api" / "__init__.py").exists()
    assert (base / "tests" / "__init__.py").exists()
    assert (base / "requirements.txt").exists()
