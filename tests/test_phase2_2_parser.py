import json
import pytest
from pathlib import Path
from src.config import PROCESSED_DATA_DIR, GROWW_SCHEMES


def test_processed_files_exist():
    """Verify schemes.json and index.json exist in data/processed."""
    schemes_file = PROCESSED_DATA_DIR / "schemes.json"
    index_file = PROCESSED_DATA_DIR / "index.json"

    assert schemes_file.exists(), "data/processed/schemes.json is missing"
    assert index_file.exists(), "data/processed/index.json is missing"


def test_normalized_schemes_schema():
    """Verify normalized schemes data structure and attributes."""
    schemes_file = PROCESSED_DATA_DIR / "schemes.json"
    schemes = json.loads(schemes_file.read_text(encoding="utf-8"))

    assert len(schemes) == 5, f"Expected 5 schemes, found {len(schemes)}"

    for s in schemes:
        assert "id" in s
        assert "name" in s
        assert "category" in s
        assert "url" in s
        assert "last_updated" in s
        assert "attributes" in s

        attrs = s["attributes"]
        assert "%" in attrs["expense_ratio"]
        assert len(attrs["exit_load"]) > 0
        assert "₹" in attrs["min_sip_amount"]
        assert "₹" in attrs["min_lumpsum_amount"]
        assert len(attrs["benchmark_index"]) > 0
        assert len(attrs["riskometer"]) > 0
        assert len(attrs["fund_manager"]) > 0
        assert "HDFC" in attrs["amc_name"]
        assert "Direct Plan" in attrs["plan_type"]


def test_chunking_strategy_counts():
    """Verify total chunks count and breakdown by type."""
    index_file = PROCESSED_DATA_DIR / "index.json"
    chunks = json.loads(index_file.read_text(encoding="utf-8"))

    assert len(chunks) >= 80, f"Expected at least 80 chunks, got {len(chunks)}"

    atomic_chunks = [c for c in chunks if c["chunk_type"] == "atomic_fact"]
    composite_chunks = [c for c in chunks if c["chunk_type"] == "composite_profile"]
    shared_chunks = [c for c in chunks if c["chunk_type"] == "shared_fact"]
    op_chunks = [c for c in chunks if c["chunk_type"] == "operational_guide"]

    # 14 attributes * 5 schemes = 70 atomic facts
    assert len(atomic_chunks) == 70, f"Expected 70 atomic chunks, got {len(atomic_chunks)}"
    # 1 composite summary * 5 schemes = 5
    assert len(composite_chunks) == 5, f"Expected 5 composite profile chunks, got {len(composite_chunks)}"
    # Shared facts = 4
    assert len(shared_chunks) >= 4
    # Operational guides = 4
    assert len(op_chunks) >= 4


def test_chunk_metadata_and_content_integrity():
    """Verify all chunks contain required metadata fields and meaningful natural language content."""
    index_file = PROCESSED_DATA_DIR / "index.json"
    chunks = json.loads(index_file.read_text(encoding="utf-8"))

    for c in chunks:
        assert "chunk_id" in c and len(c["chunk_id"]) > 0
        assert "scheme_id" in c and len(c["scheme_id"]) > 0
        assert "scheme_name" in c and len(c["scheme_name"]) > 0
        assert "category" in c and len(c["category"]) > 0
        assert "url" in c and c["url"].startswith("https://groww.in/mutual-funds")
        assert "chunk_type" in c
        assert "attribute_key" in c
        assert "content" in c and len(c["content"]) > 10
        assert "last_updated" in c

        # Verify atomic chunks embed the scheme name directly in content for retrieval clarity
        if c["chunk_type"] == "atomic_fact":
            assert c["scheme_name"] in c["content"]
