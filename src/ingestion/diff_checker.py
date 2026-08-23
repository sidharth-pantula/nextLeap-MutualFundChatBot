"""
Phase 8: Differential Change Detector & Pre-Commit Ingestion Validator.

Provides:
- Integrity and completeness verification before committing scraped records.
- Field-level diff calculation between previous and freshly scraped scheme data.
- Payload hashing to prevent unnecessary re-embedding and vector re-indexing.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime

from src.config import RAW_DATA_DIR, PROCESSED_DATA_DIR, GROWW_SCHEMES


class DiffChecker:
    """Detects attribute changes and verifies data integrity before database commits."""

    CRITICAL_ATTRIBUTES = [
        "current_nav",
        "fund_size_aum",
        "expense_ratio",
        "exit_load",
        "benchmark_index",
        "fund_manager"
    ]

    def __init__(self):
        self.raw_extracted_file = RAW_DATA_DIR / "raw_extracted.json"
        self.processed_schemes_file = PROCESSED_DATA_DIR / "schemes.json"

    def compute_payload_hash(self, data: Any) -> str:
        """Computes a deterministic SHA256 hash of JSON-serializable data."""
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def validate_scraped_data(self, new_scraped: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Validates that freshly scraped data contains all 5 required schemes
        and has non-empty critical attributes.
        """
        if not new_scraped or not isinstance(new_scraped, list):
            return False, "Scraped data is empty or not a list."

        expected_ids = {s["id"] for s in GROWW_SCHEMES}
        scraped_ids = {item.get("id") or item.get("scheme_id") for item in new_scraped if (item.get("id") or item.get("scheme_id"))}

        missing_ids = expected_ids - scraped_ids
        if missing_ids:
            return False, f"Missing required schemes in scraped payload: {missing_ids}"

        for item in new_scraped:
            scheme_id = item.get("id") or item.get("scheme_id", "unknown")
            attrs = item.get("raw_attributes", {})

            if not attrs:
                return False, f"Scheme {scheme_id} has empty raw_attributes."

            # Check critical fields are non-empty
            for crit in ["expense_ratio", "exit_load", "current_nav"]:
                val = attrs.get(crit, "").strip()
                if not val or val.lower() in ["not available", "none", "null"]:
                    return False, f"Critical attribute '{crit}' for scheme {scheme_id} is empty or invalid ('{val}')."

        return True, "All 5 schemes validated successfully."

    def detect_changes(
        self,
        new_scraped: List[Dict[str, Any]]
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Compares new scraped data with previously stored `raw_extracted.json`.
        Returns:
            - has_changes: bool
            - diff_report: List of detected field-level modifications.
        """
        diff_report: List[Dict[str, Any]] = []

        if not self.raw_extracted_file.exists():
            # First run: all schemes are new
            for item in new_scraped:
                scheme_id = item.get("id") or item.get("scheme_id")
                scheme_name = item.get("name") or item.get("scheme_name")
                diff_report.append({
                    "scheme_id": scheme_id,
                    "scheme_name": scheme_name,
                    "change_type": "INITIAL_INGESTION",
                    "details": "Initial baseline data creation."
                })
            return True, diff_report

        try:
            previous_data = json.loads(self.raw_extracted_file.read_text(encoding="utf-8"))
        except Exception:
            return True, [{"change_type": "CORRUPTED_CACHE_REBUILD", "details": "Rebuilding corrupted cache."}]

        prev_by_id = {(item.get("id") or item.get("scheme_id")): item for item in previous_data}

        for new_item in new_scraped:
            scheme_id = new_item.get("id") or new_item.get("scheme_id")
            scheme_name = new_item.get("name") or new_item.get("scheme_name")
            prev_item = prev_by_id.get(scheme_id)

            if not prev_item:
                diff_report.append({
                    "scheme_id": scheme_id,
                    "scheme_name": scheme_name,
                    "change_type": "NEW_SCHEME_ADDED",
                    "details": "Newly discovered scheme."
                })
                continue

            new_attrs = new_item.get("raw_attributes", {})
            prev_attrs = prev_item.get("raw_attributes", {})

            scheme_diffs = {}
            for attr_key in self.CRITICAL_ATTRIBUTES:
                new_val = new_attrs.get(attr_key, "").strip()
                prev_val = prev_attrs.get(attr_key, "").strip()
                if new_val != prev_val:
                    scheme_diffs[attr_key] = {
                        "old": prev_val,
                        "new": new_val
                    }

            if scheme_diffs:
                diff_report.append({
                    "scheme_id": scheme_id,
                    "scheme_name": scheme_name,
                    "change_type": "ATTRIBUTES_UPDATED",
                    "changes": scheme_diffs
                })

        has_changes = len(diff_report) > 0
        return has_changes, diff_report
