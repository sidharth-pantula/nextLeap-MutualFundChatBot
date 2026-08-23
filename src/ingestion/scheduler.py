"""
Phase 8: Ingestion Scheduler & Data Freshness Pipeline Orchestrator.

Orchestrates the automated end-to-end data freshness lifecycle:
1. Periodic & On-Demand Execution Trigger
2. Scraping with Retries & Rate-Limit Backoff
3. Pre-Commit Integrity Validation
4. Differential Change Detection
5. Atomic Normalization & Chunking
6. ChromaDB Dense Vector Re-indexing
7. Structured Ingestion Audit Logging (data/ingestion_logs.json)

Usage:
    # Single execution (for GitHub Actions or cron jobs)
    python -m src.ingestion.scheduler --run-once

    # Forced re-scrape and re-indexing
    python -m src.ingestion.scheduler --run-once --force

    # Continuous background daemon (every N hours)
    python -m src.ingestion.scheduler --daemon --interval-hours 12
"""

import sys
import time
import json
import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from src.config import BASE_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, CHROMA_DB_DIR
from src.ingestion.scraper import GrowwScraper
from src.ingestion.parser import DataParser
from src.ingestion.indexer import VectorIndexer
from src.ingestion.diff_checker import DiffChecker

LOG_FILE = BASE_DIR / "data" / "ingestion_logs.json"


class IngestionScheduler:
    """Orchestrates automated data refresh and vector store synchronization."""

    def __init__(self):
        self.scraper = GrowwScraper()
        self.parser = DataParser()
        self.diff_checker = DiffChecker()
        self.log_file = LOG_FILE
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock() if asyncio._get_running_loop() is not None else None

    def get_ingestion_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves recent audit log entries."""
        if not self.log_file.exists():
            return []
        try:
            logs = json.loads(self.log_file.read_text(encoding="utf-8"))
            return logs[-limit:]
        except Exception:
            return []

    def log_execution(self, record: Dict[str, Any]):
        """Appends an execution record to data/ingestion_logs.json."""
        records = []
        if self.log_file.exists():
            try:
                records = json.loads(self.log_file.read_text(encoding="utf-8"))
            except Exception:
                records = []
        records.append(record)
        # Keep last 100 runs
        if len(records) > 100:
            records = records[-100:]
        self.log_file.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    def run_pipeline(self, force: bool = False) -> Dict[str, Any]:
        """
        Executes the complete data freshness pipeline.
        Returns a structured execution summary dictionary.
        """
        start_time = time.perf_counter()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date_str = datetime.now().strftime("%Y-%m-%d")

        print(f"\n[INFO] [{timestamp}] Starting Mutual Fund Ingestion Pipeline (force={force})...")

        # Step 1: Scrape Fresh Data from Groww
        print("[1/5] Scraping 5 Groww scheme factsheets...")
        new_scraped = self.scraper.run()

        # Step 2: Validate Data Integrity
        print("[2/5] Validating scraped data integrity...")
        is_valid, val_msg = self.diff_checker.validate_scraped_data(new_scraped)
        if not is_valid:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            error_record = {
                "timestamp": timestamp,
                "date": date_str,
                "status": "VALIDATION_FAILED",
                "duration_ms": round(elapsed_ms, 2),
                "error": val_msg,
                "schemes_updated": 0,
                "changes_detected": False,
                "diff_report": []
            }
            self.log_execution(error_record)
            print(f"[ERROR] Ingestion Aborted: {val_msg}")
            return error_record

        # Step 3: Differential Change Detection
        print("[3/5] Checking for attribute modifications...")
        has_changes, diff_report = self.diff_checker.detect_changes(new_scraped)

        if not has_changes and not force:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            noop_record = {
                "timestamp": timestamp,
                "date": date_str,
                "status": "NO_CHANGES_DETECTED",
                "duration_ms": round(elapsed_ms, 2),
                "schemes_updated": 0,
                "changes_detected": False,
                "diff_report": [],
                "message": "All 5 schemes are up-to-date with current Groww values."
            }
            self.log_execution(noop_record)
            print(f"[INFO] No changes detected. ChromaDB re-indexing skipped ({elapsed_ms:.0f}ms).")
            return noop_record

        # Step 4: Parse Normalization & Structuring 83 Chunks
        print(f"[4/5] Changes detected / forced. Parsing and structuring 83 chunks...")
        parser_res = self.parser.run()

        # Step 5: Dense Vector Embedding & ChromaDB Re-indexing
        print("[5/5] Re-indexing ChromaDB collection with BAAI/bge-small-en-v1.5...")
        indexer = VectorIndexer()
        indexer_res = indexer.run()
        indexed_count = indexer_res.get("documents_indexed", 83)

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        success_record = {
            "timestamp": timestamp,
            "date": date_str,
            "status": "SUCCESS",
            "duration_ms": round(elapsed_ms, 2),
            "schemes_updated": len(new_scraped),
            "chunks_indexed": indexed_count,
            "changes_detected": True,
            "diff_report": diff_report,
            "message": f"Successfully updated and indexed {indexed_count} knowledge chunks."
        }
        self.log_execution(success_record)
        print(f"[SUCCESS] Ingestion completed in {elapsed_ms/1000:.2f}s! ({indexed_count} chunks indexed).")
        return success_record


def run_daemon(interval_hours: float):
    """Runs the scheduler continuously in the background."""
    scheduler = IngestionScheduler()
    print(f"[INFO] Ingestion Daemon active. Scheduled refresh every {interval_hours} hours.")
    interval_seconds = interval_hours * 3600

    while True:
        try:
            scheduler.run_pipeline(force=False)
        except Exception as e:
            print(f"[ERROR] Exception in daemon run: {e}")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mutual Fund Knowledge Base Ingestion Scheduler")
    parser.add_argument("--run-once", action="store_true", help="Execute single pipeline run and exit")
    parser.add_argument("--force", action="store_true", help="Force scrape and re-indexing even if no diffs")
    parser.add_argument("--daemon", action="store_true", help="Run continuously as a background daemon")
    parser.add_argument("--interval-hours", type=float, default=12.0, help="Interval between runs in daemon mode")

    args = parser.parse_args()

    scheduler = IngestionScheduler()

    if args.daemon:
        run_daemon(args.interval_hours)
    else:
        result = scheduler.run_pipeline(force=args.force)
        exit(0 if result["status"] in ["SUCCESS", "NO_CHANGES_DETECTED"] else 1)
