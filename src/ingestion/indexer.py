import json
from pathlib import Path
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
import chromadb

from src.config import EMBEDDING_MODEL_NAME, CHROMA_DB_DIR, PROCESSED_DATA_DIR


COLLECTION_NAME = "mutual_fund_facts"


class VectorIndexer:
    """
    Phase 2.3: Embeds all knowledge chunks using BAAI/bge-small-en-v1.5
    and indexes them into a persistent ChromaDB collection with rich metadata.

    Embedding Strategy:
    - Documents are embedded WITHOUT the BGE query-instruction prefix (raw content only).
    - At query time (Phase 4 retriever), queries are embedded WITH the prefix:
      "Represent this sentence for searching relevant passages: "
    - ChromaDB collection uses cosine distance (best for BGE normalized embeddings).
    """

    def __init__(self):
        self.chunks_file = PROCESSED_DATA_DIR / "index.json"
        self.chroma_dir = CHROMA_DB_DIR
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = EMBEDDING_MODEL_NAME
        self.model = None
        self.client = None
        self.collection = None

    def load_chunks(self) -> List[Dict[str, Any]]:
        """Load all knowledge chunks from data/processed/index.json."""
        if not self.chunks_file.exists():
            raise FileNotFoundError(
                f"Chunks file not found: {self.chunks_file}. Run parser (Phase 2.2) first."
            )
        chunks = json.loads(self.chunks_file.read_text(encoding="utf-8"))
        print(f"[INFO] Loaded {len(chunks)} chunks from {self.chunks_file}")
        return chunks

    def initialize_embedding_model(self):
        """Load the BAAI/bge-small-en-v1.5 model via sentence-transformers."""
        print(f"[INFO] Loading embedding model: {self.model_name} ...")
        self.model = SentenceTransformer(self.model_name)
        embedding_dim = self.model.get_embedding_dimension()
        print(f"[INFO] Model loaded. Embedding dimensions: {embedding_dim}")
        return embedding_dim

    def initialize_chromadb(self):
        """Create or connect to persistent ChromaDB collection with cosine distance."""
        print(f"[INFO] Initializing persistent ChromaDB at {self.chroma_dir} ...")
        self.client = chromadb.PersistentClient(path=str(self.chroma_dir))

        # Delete existing collection if present (for clean re-indexing)
        existing_collections = [c.name for c in self.client.list_collections()]
        if COLLECTION_NAME in existing_collections:
            self.client.delete_collection(name=COLLECTION_NAME)
            print(f"[INFO] Deleted existing collection '{COLLECTION_NAME}' for clean re-index.")

        self.collection = self.client.create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
        print(f"[INFO] Created ChromaDB collection '{COLLECTION_NAME}' with cosine distance.")

    def compute_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Batch-encode document texts using BGE model.
        NOTE: Documents are embedded WITHOUT the query-instruction prefix.
        The prefix is only applied at query time (Phase 4 retriever).
        """
        print(f"[INFO] Computing embeddings for {len(texts)} chunks ...")
        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=True,
            batch_size=32
        )
        return embeddings.tolist()

    def index_chunks(self, chunks: List[Dict[str, Any]], embeddings: List[List[float]]):
        """Upsert all chunks with embeddings and metadata into ChromaDB."""
        ids = []
        documents = []
        metadatas = []

        for chunk in chunks:
            ids.append(chunk["chunk_id"])
            documents.append(chunk["content"])
            metadatas.append({
                "scheme_id": chunk["scheme_id"],
                "scheme_name": chunk["scheme_name"],
                "category": chunk["category"],
                "url": chunk["url"],
                "chunk_type": chunk["chunk_type"],
                "attribute_key": chunk["attribute_key"],
                "last_updated": chunk["last_updated"]
            })

        # ChromaDB upsert with pre-computed embeddings
        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )
        print(f"[SUCCESS] Indexed {len(ids)} documents into ChromaDB collection '{COLLECTION_NAME}'.")

    def verify_index(self):
        """Run basic integrity checks on the indexed collection."""
        count = self.collection.count()
        print(f"[VERIFY] Collection document count: {count}")

        # Verify a sample query retrieves relevant results
        sample_query = "What is the expense ratio of HDFC Mid Cap Fund?"
        query_prefix = "Represent this sentence for searching relevant passages: "
        query_embedding = self.model.encode(
            [query_prefix + sample_query],
            normalize_embeddings=True
        ).tolist()

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=3,
            include=["documents", "metadatas", "distances"]
        )

        print(f"[VERIFY] Sample query: '{sample_query}'")
        for i, (doc, meta, dist) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        )):
            print(f"  [{i+1}] (dist={dist:.4f}) [{meta['chunk_type']}] {doc[:120]}")

        return count

    def run(self) -> Dict[str, Any]:
        """Execute the full Phase 2.3 indexing pipeline."""
        print("=" * 60)
        print("Phase 2.3: BGE Dense Embedding & Vector Store Indexing")
        print("=" * 60)

        # 1. Load chunks
        chunks = self.load_chunks()

        # 2. Initialize BGE model
        embedding_dim = self.initialize_embedding_model()

        # 3. Initialize ChromaDB
        self.initialize_chromadb()

        # 4. Compute embeddings (documents only, no query prefix)
        texts = [chunk["content"] for chunk in chunks]
        embeddings = self.compute_embeddings(texts)

        # 5. Index into ChromaDB
        self.index_chunks(chunks, embeddings)

        # 6. Verify
        doc_count = self.verify_index()

        print("=" * 60)
        print(f"[SUCCESS] Phase 2.3 Complete.")
        print(f"  Model: {self.model_name}")
        print(f"  Embedding Dimensions: {embedding_dim}")
        print(f"  Documents Indexed: {doc_count}")
        print(f"  ChromaDB Path: {self.chroma_dir}")
        print("=" * 60)

        return {
            "model": self.model_name,
            "embedding_dim": embedding_dim,
            "documents_indexed": doc_count,
            "chromadb_path": str(self.chroma_dir)
        }


if __name__ == "__main__":
    indexer = VectorIndexer()
    indexer.run()
