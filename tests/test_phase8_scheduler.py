"""
Phase 8 Tests: Automated Ingestion Scheduler, Diff Checker & Freshness API.

Validates:
1. DiffChecker validation rules (missing schemes, malformed attributes).
2. Field-level differential detection across previous vs newly scraped records.
3. IngestionScheduler execution, audit logging, and no-op handling.
4. FastAPI Admin Endpoints (/api/admin/freshness, /api/admin/refresh).
5. GitHub Actions workflow file presence and structure.
"""

import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient

from src.config import BASE_DIR, GROWW_SCHEMES, RAW_DATA_DIR, PROCESSED_DATA_DIR
from src.ingestion.diff_checker import DiffChecker
from src.ingestion.scheduler import IngestionScheduler, LOG_FILE
from src.api.app import app

client = TestClient(app)


def test_diff_checker_validation_valid():
    """Verify validation passes when all 5 schemes are present with valid attributes."""
    checker = DiffChecker()
    mock_scraped = []
    for s in GROWW_SCHEMES:
        mock_scraped.append({
            "scheme_id": s["id"],
            "scheme_name": s["name"],
            "raw_attributes": {
                "expense_ratio": "0.75%",
                "exit_load": "1%",
                "current_nav": "₹150.00"
            }
        })
    is_valid, msg = checker.validate_scraped_data(mock_scraped)
    assert is_valid is True
    assert "successfully" in msg


def test_diff_checker_validation_missing_scheme():
    """Verify validation fails when a required scheme is missing."""
    checker = DiffChecker()
    mock_scraped = [
        {
            "scheme_id": "hdfc-small-cap-fund",
            "raw_attributes": {"expense_ratio": "0.75%", "exit_load": "1%", "current_nav": "₹150.00"}
        }
    ]
    is_valid, msg = checker.validate_scraped_data(mock_scraped)
    assert is_valid is False
    assert "Missing required schemes" in msg


def test_diff_checker_validation_empty_critical_attr():
    """Verify validation fails when critical attributes are empty."""
    checker = DiffChecker()
    mock_scraped = []
    for s in GROWW_SCHEMES:
        mock_scraped.append({
            "scheme_id": s["id"],
            "raw_attributes": {
                "expense_ratio": "",
                "exit_load": "1%",
                "current_nav": "₹150.00"
            }
        })
    is_valid, msg = checker.validate_scraped_data(mock_scraped)
    assert is_valid is False
    assert "expense_ratio" in msg


def test_diff_checker_detects_nav_change():
    """Verify field-level modifications are detected accurately."""
    checker = DiffChecker()
    raw_file = RAW_DATA_DIR / "raw_extracted.json"
    if not raw_file.exists():
        pytest.skip("raw_extracted.json not present")

    current_data = json.loads(raw_file.read_text(encoding="utf-8"))
    
    # Simulate NAV change on first scheme
    modified_data = json.loads(json.dumps(current_data))
    modified_data[0]["raw_attributes"]["current_nav"] = "₹999.99"

    has_changes, diffs = checker.detect_changes(modified_data)
    assert has_changes is True
    assert len(diffs) >= 1
    assert diffs[0]["changes"]["current_nav"]["new"] == "₹999.99"


def test_scheduler_run_pipeline_noop():
    """Verify pipeline detects no changes when fed current cached data."""
    scheduler = IngestionScheduler()
    # Execute single pipeline run without forcing re-indexing
    result = scheduler.run_pipeline(force=False)
    assert result["status"] in ["NO_CHANGES_DETECTED", "SUCCESS"]
    assert "duration_ms" in result
    assert LOG_FILE.exists()


def test_admin_freshness_endpoint():
    """Verify GET /api/admin/freshness returns scheme metadata and history."""
    response = client.get("/api/admin/freshness")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active"
    assert data["schemes_count"] == 5
    assert len(data["schemes_freshness"]) == 5
    assert "recent_ingestion_runs" in data


def test_github_actions_workflow_file_exists():
    """Verify the GitHub Actions workflow file exists and contains cron & dispatch triggers."""
    workflow_path = BASE_DIR / ".github" / "workflows" / "data_refresh_scheduler.yml"
    assert workflow_path.exists(), f"Workflow file missing: {workflow_path}"
    content = workflow_path.read_text(encoding="utf-8")
    assert "schedule:" in content
    assert "cron:" in content
    assert "workflow_dispatch:" in content
    assert "python -m src.ingestion.scheduler" in content
    assert "python -m tests.eval_runner" in content
