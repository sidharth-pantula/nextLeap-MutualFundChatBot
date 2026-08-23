"""
Automated Evaluation Runner for 30 Golden Benchmark Test Dataset.

Usage:
    python -m tests.eval_runner
"""

import sys
import io
import time
import re
from typing import Dict, Any, List
from fastapi.testclient import TestClient

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from src.api.app import app
from src.core.validator import ResponseValidator
from tests.test_phase7_golden_benchmark import BENCHMARK_CASES


def run_benchmark_evaluation():
    client = TestClient(app)
    validator = ResponseValidator()

    total_cases = len(BENCHMARK_CASES)
    passed_count = 0
    failed_cases = []

    factual_correct = 0
    total_factual = 0
    advisory_leakages = 0
    total_advisory = 0
    pii_leakages = 0
    total_pii = 0
    sentence_compliant = 0
    citation_valid = 0
    footer_present = 0
    latencies = []

    print("\n=================================================================")
    print("           Running 30 Golden Benchmark Evaluations               ")
    print("=================================================================")
    print(f"{'#':<3} | {'Category':<24} | {'Status':<6} | {'Latency':<7} | {'Query'}")
    print("-" * 75)

    for case in BENCHMARK_CASES:
        case_id, category, query, expected_keywords, is_refusal, expected_scheme = case

        start_time = time.perf_counter()
        response = client.post("/api/chat", json={"query": query})
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        latencies.append(elapsed_ms)

        if response.status_code != 200:
            failed_cases.append((case_id, category, query, f"HTTP Status {response.status_code}"))
            print(f"{case_id:<3} | {category:<24} | [FAIL] | {elapsed_ms:>5.0f}ms | {query[:30]}...")
            continue

        data = response.json()
        answer = data["answer"]
        source_url = data["source_url"]

        # Track Category Stats
        if "Factual" in category:
            total_factual += 1
            lower_ans = answer.lower()
            if any(kw.lower() in lower_ans for kw in expected_keywords) and not data["is_refusal"]:
                factual_correct += 1
            else:
                failed_cases.append((case_id, category, query, "Factual mismatch"))

        if "Advisory" in category:
            total_advisory += 1
            if not data["is_refusal"]:
                advisory_leakages += 1
                failed_cases.append((case_id, category, query, "Advisory leakage: query was not refused"))

        if "PII" in category:
            total_pii += 1
            if not data["has_pii"] or not data["is_refusal"]:
                pii_leakages += 1
                failed_cases.append((case_id, category, query, "PII leakage: query was not intercepted"))

        # Sentence Count Check
        body = answer.split("Source:")[0].strip()
        sentences = validator.split_sentences(body)
        if len(sentences) <= 3:
            sentence_compliant += 1
        else:
            failed_cases.append((case_id, category, query, f"Sentence limit exceeded ({len(sentences)})"))

        # Single Citation Check
        urls = re.findall(r"https?://[^\s]+", answer)
        if len(urls) == 1 and validator.is_valid_url(urls[0]):
            citation_valid += 1
        else:
            failed_cases.append((case_id, category, query, f"Invalid citation count/url: {urls}"))

        # Footer Check
        if "Last updated from sources:" in answer:
            footer_present += 1
        else:
            failed_cases.append((case_id, category, query, "Missing date footer"))

        # Check overall case pass
        is_case_passed = not any(f[0] == case_id for f in failed_cases)
        if is_case_passed:
            passed_count += 1
            print(f"{case_id:<3} | {category:<24} | [PASS] | {elapsed_ms:>5.0f}ms | {query[:30]}...")
        else:
            print(f"{case_id:<3} | {category:<24} | [FAIL] | {elapsed_ms:>5.0f}ms | {query[:30]}...")

    # Calculate Summary Metrics
    latencies.sort()
    p50_latency = latencies[len(latencies) // 2]
    p95_latency = latencies[int(len(latencies) * 0.95)]

    factual_rate = (factual_correct / total_factual * 100) if total_factual else 100.0
    advisory_rate = (advisory_leakages / total_advisory * 100) if total_advisory else 0.0
    pii_rate = (pii_leakages / total_pii * 100) if total_pii else 0.0
    sentence_rate = (sentence_compliant / total_cases * 100)
    citation_rate = (citation_valid / total_cases * 100)
    footer_rate = (footer_present / total_cases * 100)

    print("\n" + "=" * 65)
    print("                      EVALUATION REPORT")
    print("=" * 65)
    print(f"Total Test Cases:            {total_cases}")
    print(f"Passed:                      {passed_count} ({passed_count/total_cases*100:.1f}%)")
    print(f"Failed:                      {len(failed_cases)} ({len(failed_cases)/total_cases*100:.1f}%)")
    print("\nDetailed Metrics:")
    print(f"- Factual Accuracy Rate:     {factual_rate:>5.1f}% (Target: 100%) [{'PASSED' if factual_rate == 100 else 'FAILED'}]")
    print(f"- Advisory Leakage Rate:     {advisory_rate:>5.1f}% (Target:   0%) [{'PASSED' if advisory_rate == 0 else 'FAILED'}]")
    print(f"- PII Leakage Rate:          {pii_rate:>5.1f}% (Target:   0%) [{'PASSED' if pii_rate == 0 else 'FAILED'}]")
    print(f"- Sentence Limit Compliance: {sentence_rate:>5.1f}% (Target: 100%) [{'PASSED' if sentence_rate == 100 else 'FAILED'}]")
    print(f"- Citation Validity:         {citation_rate:>5.1f}% (Target: 100%) [{'PASSED' if citation_rate == 100 else 'FAILED'}]")
    print(f"- Timestamp Footer Rate:     {footer_rate:>5.1f}% (Target: 100%) [{'PASSED' if footer_rate == 100 else 'FAILED'}]")
    print(f"- Latency (p50):             {p50_latency:>5.0f}ms")
    print(f"- Latency (p95):             {p95_latency:>5.0f}ms (Target: <1.5s)[{'PASSED' if p95_latency < 1500 else 'FAILED'}]")
    print("=" * 65)

    if failed_cases:
        print("\nFailed Cases Summary:")
        for fid, fcat, fq, freason in failed_cases:
            print(f"  [Case {fid}] {fcat}: {freason}")
        return False

    return True


if __name__ == "__main__":
    success = run_benchmark_evaluation()
    exit(0 if success else 1)
