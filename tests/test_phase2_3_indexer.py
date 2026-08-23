import pytest
import chromadb
from src.config import CHROMA_DB_DIR, EMBEDDING_MODEL_NAME


COLLECTION_NAME = "mutual_fund_facts"


def test_chromadb_collection_exists_and_count():
    """Verify ChromaDB collection exists with all 83 documents."""
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection(name=COLLECTION_NAME)
    count = collection.count()
    assert count == 83, f"Expected 83 documents, got {count}"


def test_chromadb_metadata_fields():
    """Verify each document in ChromaDB has all required metadata fields."""
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection(name=COLLECTION_NAME)

    results = collection.get(include=["metadatas", "documents"])
    required_keys = {"scheme_id", "scheme_name", "category", "url", "chunk_type", "attribute_key", "last_updated"}

    for i, meta in enumerate(results["metadatas"]):
        missing = required_keys - set(meta.keys())
        assert len(missing) == 0, f"Document {results['ids'][i]} missing metadata: {missing}"

    # Verify all URLs are Groww URLs
    for meta in results["metadatas"]:
        assert meta["url"].startswith("https://groww.in/mutual-funds")


def test_chromadb_scheme_id_filter():
    """Verify metadata-filtered retrieval returns only the requested scheme's chunks."""
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection(name=COLLECTION_NAME)

    # Filter by HDFC Small Cap Fund
    results = collection.get(
        where={"scheme_id": "hdfc-small-cap-fund"},
        include=["metadatas"]
    )
    assert len(results["ids"]) == 15  # 14 atomic + 1 composite profile
    for meta in results["metadatas"]:
        assert meta["scheme_id"] == "hdfc-small-cap-fund"


def test_chromadb_chunk_type_distribution():
    """Verify chunk type distribution matches expected counts."""
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection(name=COLLECTION_NAME)

    results = collection.get(include=["metadatas"])
    type_counts = {}
    for meta in results["metadatas"]:
        ct = meta["chunk_type"]
        type_counts[ct] = type_counts.get(ct, 0) + 1

    assert type_counts.get("atomic_fact", 0) == 70
    assert type_counts.get("composite_profile", 0) == 5
    assert type_counts.get("shared_fact", 0) >= 4
    assert type_counts.get("operational_guide", 0) >= 4


def test_cosine_similarity_query():
    """Verify semantic search returns relevant results for a factual query."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection(name=COLLECTION_NAME)

    # BGE asymmetric prefix for query time
    query_prefix = "Represent this sentence for searching relevant passages: "
    query = "What is the exit load for HDFC Small Cap Fund?"
    query_embedding = model.encode(
        [query_prefix + query],
        normalize_embeddings=True
    ).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=3,
        include=["documents", "metadatas", "distances"]
    )

    # Top result should be about HDFC Small Cap exit load
    top_doc = results["documents"][0][0]
    top_meta = results["metadatas"][0][0]
    assert "small cap" in top_doc.lower() or "small cap" in top_meta["scheme_name"].lower()
    assert results["distances"][0][0] < 0.5  # Cosine distance should be low
