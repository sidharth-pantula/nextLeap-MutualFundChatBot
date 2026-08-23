"""
Unit and Integration Tests for Phase 6: FastAPI Backend & Web Interface.

Validates:
1. GET /api/health endpoint status, models, and metadata.
2. GET /api/schemes list and attributes for all 5 HDFC schemes.
3. POST /api/chat with factual query (accurate grounding, valid source URL).
4. POST /api/chat with advisory query (deterministic refusal, SEBI citation).
5. POST /api/chat with PII input (interception, zero PII collection).
6. GET / static HTML interface serving.
"""

import pytest
from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)


def test_api_health():
    """Verify health endpoint returns status healthy, model metadata, and scheme count."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["schemes_count"] == 5
    assert "groq_model" in data
    assert "embedding_model" in data
    assert "Facts-only" in data["disclaimer"]


def test_api_schemes():
    """Verify schemes endpoint returns the 5 target HDFC schemes."""
    response = client.get("/api/schemes")
    assert response.status_code == 200
    schemes = response.json()
    assert len(schemes) == 5
    scheme_ids = [s["id"] for s in schemes]
    assert "hdfc-small-cap-fund" in scheme_ids
    assert "hdfc-mid-cap-fund" in scheme_ids
    assert "hdfc-nifty-50-index-fund" in scheme_ids
    assert "hdfc-nifty-next-50-index-fund" in scheme_ids
    assert "hdfc-multi-cap-fund" in scheme_ids


def test_api_chat_factual():
    """Verify factual query processing through full RAG pipeline."""
    payload = {"query": "What is the expense ratio of HDFC Small Cap Fund?"}
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_refusal"] is False
    assert data["intent"] == "FACTUAL"
    assert data["has_pii"] is False
    assert "0.75%" in data["answer"]
    assert "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth" in data["source_url"]
    assert "Last updated from sources:" in data["answer"]


def test_api_chat_advisory_refusal():
    """Verify subjective investment advice queries are refused politely."""
    payload = {"query": "Should I invest in HDFC Mid Cap Fund?"}
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_refusal"] is True
    assert "cannot provide investment advice" in data["answer"].lower()
    assert "Source:" in data["answer"]
    assert "Last updated from sources:" in data["answer"]


def test_api_chat_pii_interception():
    """Verify queries containing confidential PII are intercepted."""
    payload = {"query": "My PAN is ABCDE1234F, what is my account balance?"}
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_refusal"] is True
    assert data["has_pii"] is True
    assert "do not share" in data["answer"].lower() or "confidential" in data["answer"].lower()


def test_serve_index_html():
    """Verify the root endpoint serves the frontend HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Groww" in response.text
