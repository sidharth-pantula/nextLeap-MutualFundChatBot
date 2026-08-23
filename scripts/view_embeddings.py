import sys
import argparse
from pathlib import Path
import numpy as np

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Force UTF-8 on Windows terminal if possible
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import chromadb
from src.config import CHROMA_DB_DIR


def view_embeddings(scheme_filter: str = None, limit: int = 5, show_full_vector: bool = False, query: str = None):
    """
    Inspects chunks and their corresponding dense vector embeddings stored in ChromaDB.
    Can also execute a semantic similarity query to inspect real-time retrieval embeddings.
    """
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection(name="mutual_fund_facts")

    total_docs = collection.count()
    print("=" * 80)
    print("CHROMADB EMBEDDING INSPECTOR")
    print(f"Database Path : {CHROMA_DB_DIR}")
    print(f"Collection    : mutual_fund_facts")
    print(f"Total Chunks  : {total_docs}")
    print("=" * 80)

    if query:
        from sentence_transformers import SentenceTransformer
        from src.config import EMBEDDING_MODEL_NAME

        print(f"\n[QUERY MODE] Searching top {limit} matches for: \"{query}\"")
        model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        query_prefix = "Represent this sentence for searching relevant passages: "
        query_emb = model.encode([query_prefix + query], normalize_embeddings=True).tolist()

        where_filter = {"scheme_id": scheme_filter} if scheme_filter else None
        results = collection.query(
            query_embeddings=query_emb,
            n_results=limit,
            where=where_filter,
            include=["documents", "metadatas", "embeddings", "distances"]
        )

        ids = results["ids"][0]
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        embeddings = results["embeddings"][0]
        distances = results["distances"][0]

        print(f"Found {len(ids)} matching chunk(s):\n")
        for i, (chunk_id, doc, meta, emb, dist) in enumerate(zip(ids, docs, metas, embeddings, distances), 1):
            similarity_pct = (1.0 - dist) * 100
            print(f"[{i}/{len(ids)}] Chunk ID: {chunk_id} | Similarity: {similarity_pct:.2f}% (Cosine Distance: {dist:.4f})")
            print(f"   * Scheme Name   : {meta.get('scheme_name')} ({meta.get('scheme_id')})")
            print(f"   * Chunk Type    : {meta.get('chunk_type')} | Attribute: {meta.get('attribute_key')}")
            print(f"   * Content Text  : \"{doc}\"")
            print(f"   * Vector Dims   : {len(emb)} (384-dimensional BGE embedding)")
            preview_vals = [f"{v:+.4f}" for v in emb[:8]]
            print(f"   * Vector Snapshot (First 8 dims): [{', '.join(preview_vals)}, ...]")
            if show_full_vector:
                print(f"   * Full Vector:\n{emb}")
            print("-" * 80)
        return

    where_filter = {"scheme_id": scheme_filter} if scheme_filter else None
    
    # Retrieve documents, metadata, and actual embeddings
    results = collection.get(
        where=where_filter,
        limit=limit,
        include=["documents", "metadatas", "embeddings"]
    )

    ids = results["ids"]
    docs = results["documents"]
    metas = results["metadatas"]
    embeddings = results["embeddings"]

    if not ids:
        print(f"No chunks found for scheme filter: '{scheme_filter}'")
        return

    print(f"\nShowing {len(ids)} chunk(s) (Filtered by scheme: {scheme_filter or 'ALL'}):\n")

    for i, (chunk_id, doc, meta, emb) in enumerate(zip(ids, docs, metas, embeddings), 1):
        emb_arr = np.array(emb, dtype=np.float32)
        norm = np.linalg.norm(emb_arr)

        print(f"[{i}/{len(ids)}] Chunk ID: {chunk_id}")
        print(f"   * Scheme Name   : {meta.get('scheme_name')} ({meta.get('scheme_id')})")
        print(f"   * Chunk Type    : {meta.get('chunk_type')} | Attribute: {meta.get('attribute_key')}")
        print(f"   * Content Text  : \"{doc}\"")
        print(f"   * Vector Dims   : {len(emb)} (384-dimensional BGE embedding)")
        print(f"   * L2 Norm       : {norm:.4f} (Cosine Normalized = 1.0)")
        
        # Display vector snapshot
        preview_vals = [f"{v:+.4f}" for v in emb[:8]]
        print(f"   * Vector Snapshot (First 8 dims): [{', '.join(preview_vals)}, ...]")
        
        if show_full_vector:
            print(f"   * Full Vector:\n{emb}")
        
        print("-" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="View chunk embeddings stored in ChromaDB.")
    parser.add_argument("--scheme", type=str, default=None, help="Filter by scheme_id (e.g. hdfc-mid-cap-fund, hdfc-small-cap-fund, all)")
    parser.add_argument("--limit", type=int, default=5, help="Number of chunks to display (default: 5)")
    parser.add_argument("--query", type=str, default=None, help="Semantic search query to retrieve and view top matching chunk embeddings")
    parser.add_argument("--full", action="store_true", help="Display full 384-dimensional vector floats")
    
    args = parser.parse_args()
    view_embeddings(scheme_filter=args.scheme, limit=args.limit, show_full_vector=args.full, query=args.query)
