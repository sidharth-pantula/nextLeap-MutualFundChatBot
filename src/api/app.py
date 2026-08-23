"""
FastAPI Backend Gateway for Mutual Fund FAQ Assistant.

Exposes REST APIs:
- POST /api/chat: Full RAG pipeline (Guardrails -> Retriever -> Generator -> Validator)
- GET /api/schemes: List of 5 supported HDFC schemes and factual attributes
- GET /api/health: Health check, model status, and vector DB stats
- Serves static HTML/CSS/JS frontend on /
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.config import (
    BASE_DIR,
    PROCESSED_DATA_DIR,
    CHROMA_DB_DIR,
    GROWW_SCHEMES,
    GROQ_MODEL,
    EMBEDDING_MODEL_NAME,
    DISCLAIMER_TEXT,
    SEBI_INVESTOR_URL,
    AMFI_INVESTOR_URL,
)
from src.core.guardrail import GuardrailEngine
from src.core.retriever import SemanticRetriever
from src.core.generator import RAGGenerator
from src.core.validator import ResponseValidator

# Initialize FastAPI application
app = FastAPI(
    title="Groww Mutual Fund FAQ Assistant API",
    description="Compliance-first, facts-only RAG assistant API for 5 HDFC Mutual Fund schemes",
    version="1.0.0"
)

# Enable CORS for frontend flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core Engine Singletons
guardrail = GuardrailEngine()
retriever = SemanticRetriever()
generator = RAGGenerator()
validator = ResponseValidator()

# Static Files Directory
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# Pydantic Schemas
# ==============================================================================

class ChatRequest(BaseModel):
    query: str = Field(..., description="User question about mutual funds")
    scheme_id: Optional[str] = Field(None, description="Optional targeted scheme ID")


class ChatResponse(BaseModel):
    answer: str
    source_url: str
    last_updated: str
    is_refusal: bool
    intent: str
    has_pii: bool
    detected_scheme_ids: List[str]
    sentence_count: int
    raw_response: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    groq_model: str
    embedding_model: str
    schemes_count: int
    documents_indexed: int
    disclaimer: str
    version: str


# ==============================================================================
# API Endpoints
# ==============================================================================

@app.get("/api/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Returns system status, model configurations, and indexed document counts."""
    doc_count = 83
    try:
        if retriever.collection:
            doc_count = retriever.collection.count()
    except Exception:
        pass

    return HealthResponse(
        status="healthy",
        groq_model=GROQ_MODEL,
        embedding_model=EMBEDDING_MODEL_NAME,
        schemes_count=len(GROWW_SCHEMES),
        documents_indexed=doc_count,
        disclaimer=DISCLAIMER_TEXT,
        version="1.0.0"
    )


@app.get("/api/schemes")
def get_schemes() -> List[Dict[str, Any]]:
    """Returns the 5 supported HDFC Mutual Fund schemes with factual attributes."""
    schemes_path = PROCESSED_DATA_DIR / "schemes.json"
    if schemes_path.exists():
        try:
            return json.loads(schemes_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return GROWW_SCHEMES


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """
    Executes the full compliance-first RAG pipeline:
    1. Guardrail Inspection (PII check & Advisory Intent Classification)
    2. Semantic Retrieval with Scheme Metadata Pre-Filtering
    3. Grounded Generation via Groq LLM (with deterministic fallback)
    4. Output Validation & Formatting Enforcement
    """
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # Step 1: Input Guardrails & PII Sanitization
    g_res = guardrail.process_query(query)

    # If PII, Advisory, Out-of-Corpus, or Greeting intercepted, return formatted response
    if not g_res.passed:
        refusal_text = g_res.refusal_response or guardrail.get_refusal_response(g_res.intent)
        val_res = validator.validate(refusal_text)
        return ChatResponse(
            answer=val_res.formatted_output,
            source_url=val_res.citation_url,
            last_updated=val_res.last_updated,
            is_refusal=(g_res.intent != "GREETING"),
            intent=g_res.intent,
            has_pii=g_res.has_pii,
            detected_scheme_ids=g_res.detected_scheme_ids,
            sentence_count=val_res.sentence_count,
            raw_response=refusal_text
        )

    # Step 2: Semantic Retrieval
    target_schemes = [request.scheme_id] if request.scheme_id else g_res.detected_scheme_ids
    retrieved_chunks = retriever.retrieve(
        query=query,
        detected_scheme_ids=target_schemes,
        top_k=4
    )

    # Step 3: Grounded LLM Generation
    raw_answer = generator.generate(
        query=query,
        retrieved_chunks=retrieved_chunks
    )

    # Step 4: Output Validation & Post-Processing
    fallback_url = None
    if retrieved_chunks:
        fallback_url = retrieved_chunks[0]["chunk"].get("url")

    val_res = validator.validate(raw_answer, fallback_url=fallback_url)

    return ChatResponse(
        answer=val_res.formatted_output,
        source_url=val_res.citation_url,
        last_updated=val_res.last_updated,
        is_refusal=False,
        intent="FACTUAL",
        has_pii=False,
        detected_scheme_ids=g_res.detected_scheme_ids,
        sentence_count=val_res.sentence_count,
        raw_response=raw_answer
    )


# ==============================================================================
# Phase 8: Admin Ingestion & Freshness Monitoring Endpoints
# ==============================================================================

class RefreshRequest(BaseModel):
    force: bool = Field(default=False, description="Force re-scrape and vector re-indexing even if no diffs")


@app.post("/api/admin/refresh")
def trigger_refresh(request: RefreshRequest = RefreshRequest()):
    """
    Manually triggers the ingestion pipeline to refresh Groww mutual fund data.
    """
    from src.ingestion.scheduler import IngestionScheduler
    scheduler = IngestionScheduler()
    result = scheduler.run_pipeline(force=request.force)
    return result


@app.get("/api/admin/freshness")
def get_freshness_status():
    """
    Returns data freshness metadata, per-scheme timestamps, and recent audit logs.
    """
    from src.ingestion.scheduler import IngestionScheduler
    scheduler = IngestionScheduler()
    history = scheduler.get_ingestion_history(limit=5)
    
    schemes_file = PROCESSED_DATA_DIR / "schemes.json"
    schemes_data = []
    if schemes_file.exists():
        try:
            schemes_data = json.loads(schemes_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "status": "active",
        "schemes_count": len(GROWW_SCHEMES),
        "schemes_freshness": [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "last_updated": s.get("last_updated"),
                "current_nav": s.get("attributes", {}).get("current_nav")
            }
            for s in schemes_data
        ],
        "recent_ingestion_runs": history
    }


# ==============================================================================
# Static Web App Mount
# ==============================================================================

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index():
    """Serves the main desktop web application interface."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {
        "message": "Groww Mutual Fund FAQ Assistant API",
        "docs": "/docs",
        "health": "/api/health",
        "schemes": "/api/schemes"
    }
