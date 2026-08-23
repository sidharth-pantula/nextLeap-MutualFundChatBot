import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import numpy as np
import chromadb
from sentence_transformers import SentenceTransformer
from src.config import CHROMA_DB_DIR, PROCESSED_DATA_DIR, EMBEDDING_MODEL_NAME, GROWW_SCHEMES


def run_full_vectordb_audit():
    print("=" * 80)
    print("🔍 VECTOR DATABASE COMPREHENSIVE INTEGRITY & QUALITY AUDIT")
    print(f"📁 Path: {CHROMA_DB_DIR}")
    print("=" * 80)

    # 1. Connect to ChromaDB
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection(name="mutual_fund_facts")
    total_docs = collection.count()
    print(f"\n[CHECK 1] Document Count Verification:")
    print(f"   • Total records in ChromaDB: {total_docs}")
    
    index_file = PROCESSED_DATA_DIR / "index.json"
    raw_chunks = json.loads(index_file.read_text(encoding="utf-8"))
    print(f"   • Total records in index.json: {len(raw_chunks)}")
    assert total_docs == len(raw_chunks) == 83, f"Count mismatch! Chroma={total_docs}, JSON={len(raw_chunks)}"
    print("   ✅ PASS: Total count matches exactly (83 records).")

    # 2. Fetch all records from ChromaDB
    all_data = collection.get(include=["documents", "metadatas", "embeddings"])
    ids = all_data["ids"]
    docs = all_data["documents"]
    metas = all_data["metadatas"]
    embeddings = all_data["embeddings"]

    # 3. Verify Scheme Coverage
    print(f"\n[CHECK 2] Scheme Breakdown & Partitioning:")
    scheme_counts = {}
    type_counts = {}
    for meta in metas:
        sid = meta["scheme_id"]
        ctype = meta["chunk_type"]
        scheme_counts[sid] = scheme_counts.get(sid, 0) + 1
        type_counts[ctype] = type_counts.get(ctype, 0) + 1

    for s in GROWW_SCHEMES:
        cnt = scheme_counts.get(s["id"], 0)
        print(f"   • {s['name']} ({s['id']}): {cnt} chunks (14 atomic + 1 profile)")
        assert cnt == 15, f"Expected 15 chunks for {s['id']}, got {cnt}"

    shared_cnt = scheme_counts.get("all", 0)
    print(f"   • Cross-Cutting / Operational Guidance (all): {shared_cnt} chunks")
    assert shared_cnt == 8, f"Expected 8 shared/operational chunks, got {shared_cnt}"
    print("   ✅ PASS: All 5 schemes and shared categories have complete coverage.")

    # 4. Verify Chunk Type Breakdown
    print(f"\n[CHECK 3] Chunk Types Distribution:")
    for ct, cnt in type_counts.items():
        print(f"   • {ct:20s}: {cnt} chunks")
    assert type_counts["atomic_fact"] == 70
    assert type_counts["composite_profile"] == 5
    assert type_counts["shared_fact"] == 4
    assert type_counts["operational_guide"] == 4
    print("   ✅ PASS: Chunk distribution matches exact design specifications.")

    # 5. Verify Metadata Integrity
    print(f"\n[CHECK 4] Metadata & URL Integrity:")
    required_keys = {"scheme_id", "scheme_name", "category", "url", "chunk_type", "attribute_key", "last_updated"}
    for i, meta in enumerate(metas):
        for k in required_keys:
            assert k in meta and meta[k] is not None and str(meta[k]).strip() != "", f"Missing/empty metadata '{k}' in {ids[i]}"
        assert meta["url"].startswith("https://groww.in/mutual-funds"), f"Invalid citation URL: {meta['url']}"
    print("   ✅ PASS: 100% of metadata fields populated with zero nulls and verified Groww URLs.")

    # 6. Verify Embedding Vectors (384-dim, No NaN/Inf, L2 Normalized)
    print(f"\n[CHECK 5] Vector Embedding Mathematical Quality:")
    emb_matrix = np.array(embeddings, dtype=np.float32)
    assert emb_matrix.shape == (83, 384), f"Incorrect shape: {emb_matrix.shape}"
    assert not np.isnan(emb_matrix).any(), "Found NaN in embeddings!"
    assert not np.isinf(emb_matrix).any(), "Found Inf in embeddings!"
    
    norms = np.linalg.norm(emb_matrix, axis=1)
    norm_mean = np.mean(norms)
    norm_std = np.std(norms)
    print(f"   • Matrix Shape : {emb_matrix.shape}")
    print(f"   • Mean L2 Norm : {norm_mean:.6f} (Std: {norm_std:.6f})")
    assert np.allclose(norms, 1.0, atol=1e-3), "Vectors are not normalized to unit length!"
    print("   ✅ PASS: 83 vectors are 384-dimensional, finite, and strictly L2-normalized.")

    # 7. Semantic Retrieval Benchmark Test
    print(f"\n[CHECK 6] End-to-End Semantic Retrieval Benchmark (With & Without Scheme Filtering):")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    query_prefix = "Represent this sentence for searching relevant passages: "

    test_cases = [
        ("What is the expense ratio of HDFC Small Cap Fund?", "hdfc-small-cap-fund", "0.75%"),
        ("What is the exit load for HDFC Mid-Cap Opportunities Fund?", "hdfc-mid-cap-fund", "1%"),
        ("What benchmark index does HDFC Nifty 50 Index Fund track?", "hdfc-nifty-50-index-fund", "NIFTY 50"),
        ("What is the exit load for HDFC Nifty Next 50 Index Fund?", "hdfc-nifty-next-50-index-fund", "Nil"),
        ("Who is the fund manager of HDFC Multi Cap Fund?", "hdfc-multi-cap-fund", "Gopal Agrawal"),
        ("What is the minimum SIP amount across schemes?", None, "₹100"),
        ("What are the capital gains taxation rules for mutual funds?", None, "20%"),
        ("How can I download my capital gains statement on Groww?", None, "Reports"),
        ("What is the AUM of HDFC Mid-Cap Opportunities Fund?", "hdfc-mid-cap-fund", "Cr"),
        ("What is the current NAV of HDFC Nifty 50 Index Fund?", "hdfc-nifty-50-index-fund", "₹237")
    ]

    for idx, (q, target_scheme, expected_keyword) in enumerate(test_cases, 1):
        q_emb = model.encode([query_prefix + q], normalize_embeddings=True).tolist()
        
        # Test with scheme metadata filter if targeted, else global search
        where_clause = {"scheme_id": target_scheme} if target_scheme else None
        res = collection.query(
            query_embeddings=q_emb, 
            n_results=1, 
            where=where_clause,
            include=["documents", "metadatas", "distances"]
        )
        top_doc = res["documents"][0][0]
        top_meta = res["metadatas"][0][0]
        dist = res["distances"][0][0]

        has_keyword = expected_keyword.lower() in top_doc.lower()
        status = "✅ PASS" if has_keyword else "❌ FAIL"
        filter_str = f"[Filter: {target_scheme}]" if target_scheme else "[Global Search]"
        print(f"   [{idx:02d}] Query  : \"{q}\" {filter_str}")
        print(f"        Match  : [{top_meta['scheme_id']}] {top_doc[:95]}... (Dist: {dist:.4f}) -> {status}")
        assert has_keyword, f"Failed keyword test on query '{q}'. Got '{top_doc}'"

    print("\n" + "=" * 80)
    print("🏆 ALL AUDIT CHECKS PASSED: Vector Database is 100% healthy and production ready!")
    print("=" * 80)


if __name__ == "__main__":
    run_full_vectordb_audit()
