import json
import pytest
from pathlib import Path
from src.config import GROWW_SCHEMES, RAW_DATA_DIR


def test_raw_html_cache_files_exist():
    """Verify that all 5 Groww scheme HTML cache files exist and have non-trivial size."""
    for scheme in GROWW_SCHEMES:
        raw_file = RAW_DATA_DIR / f"{scheme['id']}.html"
        assert raw_file.exists(), f"Raw HTML file missing for {scheme['id']}"
        assert raw_file.stat().st_size > 10000, f"HTML file too small for {scheme['id']}"


def test_raw_extracted_json_schema():
    """Verify extracted raw data file exists and contains all required scheme attributes."""
    extracted_file = RAW_DATA_DIR / "raw_extracted.json"
    assert extracted_file.exists(), "raw_extracted.json is missing"

    data = json.loads(extracted_file.read_text(encoding="utf-8"))
    assert len(data) == 5, f"Expected 5 schemes, found {len(data)}"

    required_attrs = [
        "expense_ratio",
        "exit_load",
        "min_sip_amount",
        "min_lumpsum_amount",
        "riskometer",
        "benchmark_index",
        "lock_in_period",
        "fund_manager",
        "amc_name",
        "plan_type"
    ]

    for item in data:
        assert "id" in item
        assert "name" in item
        assert "url" in item
        assert item["url"].startswith("https://groww.in/mutual-funds/")
        assert "raw_attributes" in item

        attrs = item["raw_attributes"]
        for req in required_attrs:
            assert req in attrs, f"Missing attribute {req} in {item['id']}"
            assert attrs[req] is not None and str(attrs[req]).strip() != "", f"Empty attribute {req} in {item['id']}"

        # Verify expense ratio format
        assert "%" in attrs["expense_ratio"]
        # Verify min SIP format
        assert "₹" in attrs["min_sip_amount"]


def test_specific_extracted_values():
    """Verify extracted values match the official Groww statistics for each scheme."""
    extracted_file = RAW_DATA_DIR / "raw_extracted.json"
    data = json.loads(extracted_file.read_text(encoding="utf-8"))
    scheme_dict = {item["id"]: item["raw_attributes"] for item in data}

    # HDFC Mid-Cap Opportunities Fund
    mid_cap = scheme_dict["hdfc-mid-cap-fund"]
    assert "0.75%" in mid_cap["expense_ratio"]
    assert "1%" in mid_cap["exit_load"]
    assert "150" in mid_cap["benchmark_index"]

    # HDFC Small Cap Fund
    small_cap = scheme_dict["hdfc-small-cap-fund"]
    assert "0.75%" in small_cap["expense_ratio"]
    assert "1%" in small_cap["exit_load"]
    assert "250" in small_cap["benchmark_index"]

    # HDFC Nifty 50 Index Fund
    nifty_50 = scheme_dict["hdfc-nifty-50-index-fund"]
    assert "0.29%" in nifty_50["expense_ratio"]
    assert "0.25%" in nifty_50["exit_load"]
    assert "NIFTY 50" in nifty_50["benchmark_index"]

    # HDFC Nifty Next 50 Index Fund
    next_50 = scheme_dict["hdfc-nifty-next-50-index-fund"]
    assert "0.36%" in next_50["expense_ratio"]
    assert "Nil" in next_50["exit_load"]

    # HDFC Multi Cap Fund
    multi_cap = scheme_dict["hdfc-multi-cap-fund"]
    assert "0.93%" in multi_cap["expense_ratio"]
    assert "1%" in multi_cap["exit_load"]
