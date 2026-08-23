# Groww Mutual Fund FAQ Assistant (HDFC Mutual Funds)

A compliance-first, retrieval-augmented generation (RAG) assistant designed for factual, verifiable inquiries regarding **HDFC Mutual Fund schemes on Groww**.

> **Regulatory Compliance Philosophy:**  
> **"Facts-only. No investment advice."**  
> This assistant strictly adheres to SEBI and AMFI guidelines. It provides 100% grounded facts with verified Groww source URLs and timestamps, while intercepting sensitive PII, rejecting speculative return projections, and refusing subjective recommendations.

---

## 🎯 Target AMC & Supported Schemes

This assistant is indexed for **5 flagship Direct Growth schemes** from **HDFC Mutual Fund**:

| # | Scheme Name | Category | NAV (as of Aug 2026) | Expense Ratio | Exit Load | Official Groww URL |
|---|---|---|---|---|---|---|
| 1 | **HDFC Small Cap Fund** | Small Cap (Direct Growth) | ₹164.67 | 0.75% | 1% if redeemed within 1 year | [Groww Scheme Link](https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth) |
| 2 | **HDFC Mid-Cap Opportunities Fund** | Mid Cap (Direct Growth) | ₹197.87 | 0.75% | 1% if redeemed within 1 year | [Groww Scheme Link](https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth) |
| 3 | **HDFC Nifty 50 Index Fund** | Large Cap / Index | ₹25.68 | 0.29% | 0.25% if redeemed within 3 days | [Groww Scheme Link](https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth) |
| 4 | **HDFC Nifty Next 50 Index Fund** | Large Cap / Index | ₹17.52 | 0.36% | Nil | [Groww Scheme Link](https://groww.in/mutual-funds/hdfc-nifty-next-50-index-fund-direct-growth) |
| 5 | **HDFC Multi Cap Fund** | Multi Cap (Direct Growth) | ₹21.68 | 0.93% | 1% if redeemed within 1 year | [Groww Scheme Link](https://groww.in/mutual-funds/hdfc-multi-cap-fund-direct-growth) |

---

## 🏗️ Multi-Stage Pipeline Architecture

```
User Query
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│ Phase 3: Input Guardrails & Query Sanitizer              │
│ 1. PII Redaction & Interception (PAN, Aadhaar, Folio)    │
│ 2. Intent Classifier (FACTUAL / ADVISORY / OUT_OF_CORPUS)│
│ 3. Scheme Entity Resolution & Disambiguation             │
└──────────────────────────┬───────────────────────────────┘
                           │ Passed (FACTUAL)
                           ▼
┌──────────────────────────────────────────────────────────┐
│ Phase 4: Scheme-Filtered BGE Semantic Retriever          │
│ 1. Short-Circuit Attribute Direct Fact Lookup            │
│ 2. ChromaDB Dense Search (BAAI/bge-small-en-v1.5, 384-d) │
│ 3. Metadata Pre-Filtering by Detected Scheme IDs         │
└──────────────────────────┬───────────────────────────────┘
                           │ Grounded Context
                           ▼
┌──────────────────────────────────────────────────────────┐
│ Phase 4: Grounded LLM Generator (Groq Llama 3.3 70B)     │
│ 1. Temperature = 0.0 with strict system format prompt    │
│ 2. Deterministic local fallback for rate-limit resilience│
└──────────────────────────┬───────────────────────────────┘
                           │ Raw Response
                           ▼
┌──────────────────────────────────────────────────────────┐
│ Phase 5: Output Validation & Post-Processing             │
│ 1. Sentence Limiter (Strictly <= 3 sentences)            │
│ 2. Numbered list & Decimal/Currency protection           │
│ 3. Single Citation Whitelist & Mandatory Date Footer     │
│ 4. Advisory Trigger Word & Leakage Scrubbing             │
└──────────────────────────┬───────────────────────────────┘
                           │ Verified Compliant Output
                           ▼
               FastAPI Web UI & Streamlit App
```

---

## 🚀 Quickstart & Local Setup

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Groq API Key (optional for LLM generation; deterministic fallback runs 100% offline)

### 2. Installation
```powershell
# Clone or navigate to the repository directory
cd MutualFundFAQAssistant

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Create or update `.env` in the root directory:
```ini
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
CHROMA_PERSIST_DIR=data/chromadb
```

---

## 💻 Running the Applications

### Option A: Modern Desktop Web Application (FastAPI + Vanilla JS)
```powershell
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```
- **Desktop Web UI:** Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.
- **Interactive Swagger Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check:** [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

### Option B: Streamlit Web UI
```powershell
streamlit run ui/app.py
```

---

## 🔄 Automated Ingestion Scheduler & GitHub Actions (Phase 8)

The assistant features an automated data freshness system to synchronize scheme facts and NAV updates:

### 1. GitHub Actions Scheduled Workflow
- **Workflow File:** `.github/workflows/data_refresh_scheduler.yml`
- **Schedule:** Runs automatically at **23:00 IST (17:30 UTC)** Monday through Friday following AMFI NAV publications.
- **Manual Trigger:** Supports one-click on-demand triggering via `workflow_dispatch` in the GitHub Actions UI.
- **Auto-Sync:** Validates data, runs differential detection, re-indexes ChromaDB, tests golden benchmarks, and automatically commits updated factsheets.

### 2. Standalone CLI & Background Daemon
```powershell
# Execute single refresh run with diff detection
python -m src.ingestion.scheduler --run-once

# Force re-scrape and vector re-indexing
python -m src.ingestion.scheduler --run-once --force

# Run continuous background worker (e.g. every 12 hours)
python -m src.ingestion.scheduler --daemon --interval-hours 12
```

### 3. Admin Freshness & Refresh REST APIs
- `POST /api/admin/refresh` (Manual trigger endpoint)
- `GET /api/admin/freshness` (Inspect scheme freshness, NAV timestamps, and audit history)

---

## 🧪 Testing & Evaluation Benchmark

### 1. Run Complete Automated Test Suite (162 Tests)
```powershell
python -m pytest tests/ -v
```
**Results:** `162 passed (100% pass rate)` across all 8 phases (Setup, Scraper, Parser, Vector Indexer, Guardrails, Retriever, Generator, Validator, API, Golden Benchmark, and Ingestion Scheduler).

### 2. Run 30-Query Golden Benchmark Evaluation Runner
```powershell
python -m tests.eval_runner
```

### 📊 Benchmark Summary:
```text
=================================================================
                      EVALUATION REPORT
=================================================================
Total Test Cases:            30
Passed:                      30 (100.0%)
Failed:                      0 (0.0%)

Detailed Metrics:
- Factual Accuracy Rate:     100.0% (Target: 100%) [PASSED]
- Advisory Leakage Rate:       0.0% (Target:   0%) [PASSED]
- PII Leakage Rate:            0.0% (Target:   0%) [PASSED]
- Sentence Limit Compliance: 100.0% (Target: 100%) [PASSED]
- Citation Validity:         100.0% (Target: 100%) [PASSED]
- Timestamp Footer Rate:     100.0% (Target: 100%) [PASSED]
- Latency (p50):               118ms
- Latency (p95):               346ms (Target: <1.5s)[PASSED]
=================================================================
```

---

## 🛡️ Compliance & Safety Guardrails

1. **Strict Response Format Contract:**
   - **Body:** $\le 3$ discrete sentences.
   - **Source:** Exactly 1 whitelisted URL (`groww.in`, `investor.sebi.gov.in`, or `amfiindia.com`).
   - **Footer:** Mandatory timestamp (`Last updated from sources: YYYY-MM-DD`).
2. **Deterministic Interceptions:**
   - **PII:** Intercepts PAN, Aadhaar, Folio numbers, and phone numbers before any retrieval.
   - **Advisory:** Refuses investment recommendations, return predictions, scheme comparisons, and jailbreak prompts.
   - **Competitor AMC:** Clarifies that the scope is focused on the 5 designated HDFC schemes.

---

## 📜 Regulatory Disclaimers

> **Disclaimer:** Mutual fund investments are subject to market risks, read all scheme related documents carefully. Past performance is not an indicator of future returns. This assistant provides verified, factual data for educational purposes only and does not constitute financial, legal, or investment advice.
