"""
Scheme-Filtered BGE Semantic Retriever Module.

Provides high-precision retrieval over indexed ChromaDB vector store using:
1. Deterministic scheme metadata pre-filtering (from Guardrail / entity extraction).
2. Attribute-Key direct lookup short-circuit for precise single-fact queries.
3. BGE asymmetric dense retrieval with instruction prefix.
4. Chunk-type rank adjustment (demoting composite profiles for specific attribute queries,
   boosting canonical shared facts for corpus-wide queries).
5. Disambiguation handling for ambiguous entities (e.g. Nifty 50 vs Nifty Next 50).
"""

from typing import Any, Dict, List, Optional, Tuple
import chromadb
from sentence_transformers import SentenceTransformer

from src.config import (
    CHROMA_DB_DIR,
    EMBEDDING_MODEL_NAME,
    GROWW_SCHEMES,
)
from src.core.guardrail import GuardrailEngine

DEFAULT_LAST_UPDATED = "2026-08-23"
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
COLLECTION_NAME = "mutual_fund_facts"

# ==============================================================================
# Attribute Keywords Mapping for Direct Lookup & Rank Adjustment
# ==============================================================================

ATTRIBUTE_KEYWORDS = {
    "expense_ratio": ["expense ratio", "expense", "ter", "total expense ratio"],
    "exit_load": ["exit load", "exit penalty", "redemption fee", "redemption load"],
    "min_sip_amount": ["min sip", "minimum sip", "sip amount", "sip minimum", "start sip"],
    "min_lumpsum_amount": ["min lumpsum", "minimum lumpsum", "lumpsum", "lump sum", "one-time", "one time"],
    "fund_size_aum": ["aum", "fund size", "asset size", "assets under management"],
    "current_nav": ["nav", "net asset value", "current nav", "latest nav", "nav price"],
    "riskometer": ["riskometer", "risk level", "risk grade", "risk category", "how risky"],
    "benchmark_index": ["benchmark", "benchmark index", "tracked index", "tracks which index"],
    "lock_in_period": ["lock in", "lock-in", "lock in period", "lockin", "holding period", "elss"],
    "fund_manager": ["fund manager", "managed by", "portfolio manager", "who manages", "manager"],
    "stamp_duty": ["stamp duty", "stamp charge"],
    "taxation_rules": ["tax", "taxation", "stcg", "ltcg", "capital gains tax", "tax rate", "short term capital gains", "long term capital gains"],
    "amc_name": ["amc", "amc name", "fund house", "asset management company"],
    "plan_type": ["plan type", "direct plan", "regular plan", "growth option"]
}

BROAD_QUERY_KEYWORDS = [
    "tell me about", "overview", "describe", "all details", "summary",
    "profile", "about the fund", "scheme details", "what is "
]


class SemanticRetriever:
    """
    Two-Pass Hybrid Semantic Retriever for Mutual Fund FAQ Knowledge Base.
    """

    def __init__(
        self,
        chroma_dir=CHROMA_DB_DIR,
        model_name: str = EMBEDDING_MODEL_NAME,
        collection_name: str = COLLECTION_NAME
    ):
        self.chroma_dir = chroma_dir
        self.model_name = model_name
        self.collection_name = collection_name
        
        # Lazy loaded model and ChromaDB client
        self._model: Optional[SentenceTransformer] = None
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection = None
        self.guardrail = GuardrailEngine()

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load SentenceTransformer model."""
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def collection(self):
        """Lazy load ChromaDB collection."""
        if self._collection is None:
            self._client = chromadb.PersistentClient(path=str(self.chroma_dir))
            self._collection = self._client.get_collection(name=self.collection_name)
        return self._collection

    def detect_attribute(self, query: str) -> Optional[str]:
        """Identifies target factual attribute from query text based on keyword matching."""
        lowered = query.lower()
        for attr_key, keywords in ATTRIBUTE_KEYWORDS.items():
            for kw in keywords:
                if kw in lowered:
                    return attr_key
        return None

    def is_broad_query(self, query: str) -> bool:
        """Determines if query is asking for a general overview rather than a single attribute."""
        lowered = query.lower()
        return any(kw in lowered for kw in BROAD_QUERY_KEYWORDS)

    def retrieve(
        self,
        query: str,
        detected_scheme_ids: Optional[List[str]] = None,
        top_k: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top relevant chunks from ChromaDB using:
        1. Direct attribute short-circuit if single scheme and attribute match.
        2. BGE dense vector search with scheme metadata pre-filtering.
        3. Deterministic chunk-type rank adjustment.
        """
        if not query or not query.strip():
            return []

        # Resolve scheme IDs from guardrail if not provided
        if detected_scheme_ids is None:
            detected_scheme_ids = self.guardrail.detect_scheme(query)

        detected_attr = self.detect_attribute(query)
        is_broad = self.is_broad_query(query)
        results: List[Dict[str, Any]] = []

        # ======================================================================
        # 1. Short-Circuit Direct Lookup (for single-scheme + single-attribute)
        # ======================================================================
        if len(detected_scheme_ids) == 1 and detected_attr and not is_broad:
            scheme_id = detected_scheme_ids[0]
            target_chunk_id = f"{scheme_id}_{detected_attr}"
            try:
                direct_res = self.collection.get(
                    ids=[target_chunk_id],
                    include=["documents", "metadatas"]
                )
                if direct_res["ids"] and len(direct_res["ids"]) > 0:
                    meta = direct_res["metadatas"][0]
                    doc = direct_res["documents"][0]
                    results.append({
                        "chunk": {
                            "chunk_id": target_chunk_id,
                            "content": doc,
                            "scheme_id": meta.get("scheme_id", scheme_id),
                            "scheme_name": meta.get("scheme_name", ""),
                            "category": meta.get("category", ""),
                            "url": meta.get("url", ""),
                            "chunk_type": meta.get("chunk_type", "atomic_fact"),
                            "attribute_key": meta.get("attribute_key", detected_attr),
                            "attribute": meta.get("attribute_key", detected_attr),
                            "last_updated": meta.get("last_updated", DEFAULT_LAST_UPDATED),
                        },
                        "distance": 0.0
                    })
                    
                    # If we only need 1 specific atomic fact, direct lookup is sufficient
                    if top_k == 1:
                        return results
            except Exception:
                pass

        # ======================================================================
        # 2. BGE Dense Vector Retrieval with Metadata Pre-Filtering
        # ======================================================================
        query_embedding = self.model.encode(
            [BGE_QUERY_PREFIX + query],
            normalize_embeddings=True
        ).tolist()

        # Build metadata where filter
        where_filter = None
        if len(detected_scheme_ids) == 1:
            where_filter = {"scheme_id": detected_scheme_ids[0]}
        elif len(detected_scheme_ids) > 1:
            where_filter = {"scheme_id": {"$in": detected_scheme_ids}}

        # Fetch candidates (request up to 10 for re-ranking)
        candidate_count = max(top_k * 2, 8)
        
        try:
            vector_res = self.collection.query(
                query_embeddings=query_embedding,
                n_results=candidate_count,
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )
        except Exception:
            # Fallback without where filter if filter fails
            vector_res = self.collection.query(
                query_embeddings=query_embedding,
                n_results=candidate_count,
                include=["documents", "metadatas", "distances"]
            )

        vector_docs = vector_res["documents"][0] if vector_res["documents"] else []
        vector_metas = vector_res["metadatas"][0] if vector_res["metadatas"] else []
        vector_dists = vector_res["distances"][0] if vector_res["distances"] else []
        vector_ids = vector_res["ids"][0] if vector_res["ids"] else []

        # ======================================================================
        # 3. Post-Retrieval Rank Adjustment & Assembly
        # ======================================================================
        existing_ids = set(r["chunk"]["chunk_id"] for r in results)
        candidates: List[Dict[str, Any]] = []

        for doc_id, doc, meta, dist in zip(vector_ids, vector_docs, vector_metas, vector_dists):
            if doc_id in existing_ids:
                continue

            chunk_dict = {
                "chunk_id": doc_id,
                "content": doc,
                "scheme_id": meta.get("scheme_id", ""),
                "scheme_name": meta.get("scheme_name", ""),
                "category": meta.get("category", ""),
                "url": meta.get("url", ""),
                "chunk_type": meta.get("chunk_type", "atomic_fact"),
                "attribute_key": meta.get("attribute_key", ""),
                "attribute": meta.get("attribute_key", ""),
                "last_updated": meta.get("last_updated", DEFAULT_LAST_UPDATED),
            }
            
            # Distance adjustments for precise ranking
            adjusted_dist = dist

            # If not a broad query, penalize composite_profile chunks so atomic facts rank higher
            if not is_broad and chunk_dict["chunk_type"] == "composite_profile":
                adjusted_dist += 0.20

            # If exact attribute keyword matches chunk's attribute_key, reward it
            if detected_attr and chunk_dict["attribute_key"] == detected_attr:
                adjusted_dist -= 0.10

            # For corpus-wide queries (no scheme detected), boost shared facts
            if not detected_scheme_ids and chunk_dict["scheme_id"] == "all":
                adjusted_dist -= 0.15

            candidates.append({
                "chunk": chunk_dict,
                "distance": dist,
                "adjusted_dist": adjusted_dist
            })

        # Sort candidates by adjusted distance
        candidates.sort(key=lambda x: x["adjusted_dist"])

        # Append top candidates to results
        for c in candidates:
            if len(results) >= top_k:
                break
            results.append({
                "chunk": c["chunk"],
                "distance": c["distance"]
            })

        return results

    def assemble_context(
        self,
        retrieved_results: List[Dict[str, Any]]
    ) -> Tuple[str, str, str]:
        """
        Assembles retrieved chunks into structured context text along with
        the primary Groww citation URL and last updated date.
        """
        if not retrieved_results:
            return (
                "No factual context available in the knowledge base.",
                GROWW_SCHEMES[0]["url"],
                DEFAULT_LAST_UPDATED
            )

        context_lines = []
        primary_url = None
        last_updated = DEFAULT_LAST_UPDATED

        for i, item in enumerate(retrieved_results, start=1):
            chunk = item["chunk"]
            content = chunk["content"]
            scheme_name = chunk.get("scheme_name", "")
            attr = chunk.get("attribute_key", "")
            context_lines.append(f"[{i}] {content}")

            # Pick the first scheme-specific Groww URL as primary citation
            if primary_url is None:
                url = chunk.get("url", "")
                if url and "groww.in/mutual-funds/" in url and url != "https://groww.in/mutual-funds":
                    primary_url = url

            if chunk.get("last_updated"):
                last_updated = chunk["last_updated"]

        # Default URL if no specific scheme URL was found
        if not primary_url:
            primary_url = retrieved_results[0]["chunk"].get("url", GROWW_SCHEMES[0]["url"])

        context_text = "\n".join(context_lines)
        return context_text, primary_url, last_updated
