"""
Groq LLM Generator & Grounded RAG Generation Module.

Invokes the Groq API (llama-3.3-70b-versatile / llama-3.1-8b-instant) with strict
prompt grounding, facts-only constraints, maximum 3-sentence limit, single Groww citation,
and mandatory timestamp footer. Provides deterministic local fallback when API is unreachable.
"""

import os
import re
from typing import Any, Dict, List, Optional
import groq

from src.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_TEMPERATURE,
    GROWW_SCHEMES,
)

DEFAULT_LAST_UPDATED = "2026-08-23"

# ==============================================================================
# Strict System Prompt
# ==============================================================================

SYSTEM_PROMPT = """You are the Mutual Fund FAQ Assistant for Groww.
Your sole responsibility is to answer factual, verifiable questions strictly using the facts in the CONTEXT provided below for 5 HDFC Mutual Fund schemes.

STRICT CONSTRAINTS:
1. GROUNDING: Answer ONLY from the CONTEXT. If the context lacks the answer, say "This information is not available in the official scheme documents on Groww."
2. NO FINANCIAL ADVICE: Never recommend, rate, compare fund quality, or advise on investment.
3. SENTENCE LIMIT: Your entire answer MUST NOT exceed 3 sentences.
4. CITATION: Append EXACTLY ONE citation link (the Groww scheme URL from CONTEXT). Format: "Source: <URL>"
5. FOOTER: Always append on a new line: "Last updated from sources: <date>"
"""


class RAGGenerator:
    """
    Grounded RAG Response Generator using Groq API with deterministic local fallback.
    """

    def __init__(
        self,
        api_key: str = GROQ_API_KEY,
        model: str = GROQ_MODEL,
        temperature: float = GROQ_TEMPERATURE
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model
        self.temperature = temperature
        self.client: Optional[groq.Groq] = None

        if self.api_key and self.api_key.strip():
            try:
                self.client = groq.Groq(api_key=self.api_key)
            except Exception:
                self.client = None

    def _extract_chunk_data(
        self,
        retrieved_chunks: List[Any]
    ) -> List[Dict[str, Any]]:
        """Normalizes list of retrieved chunk results into standard dictionary format."""
        normalized = []
        for item in retrieved_chunks:
            if isinstance(item, dict):
                if "chunk" in item and isinstance(item["chunk"], dict):
                    normalized.append(item["chunk"])
                else:
                    normalized.append(item)
        return normalized

    def _split_into_sentences(self, text: str) -> List[str]:
        """Splits text into sentences, preserving decimals, abbreviations, and numbered lists."""
        if not text:
            return []
        cleaned = text.strip()
        # Protect numbered list markers (e.g. 1. 2. 3.)
        cleaned = re.sub(r'(^|\s)(\d+)\.', r'\1\2<NUM_DOT>', cleaned)
        raw_sentences = re.split(r'(?<=[.!?])\s+', cleaned)
        return [s.replace('<NUM_DOT>', '.').strip() for s in raw_sentences if s.strip()]

    def _generate_deterministic_fallback(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        primary_url: str,
        last_updated: str
    ) -> str:
        """
        Synthesizes a grounded, compliant answer directly from retrieved chunks without external API call.
        Guarantees <= 3 sentences, 1 citation URL, and date footer.
        """
        if not chunks:
            return (
                "This information is not available in the official scheme documents on Groww.\n\n"
                f"Source: {primary_url}\n"
                f"Last updated from sources: {last_updated}"
            )

        # Prefer atomic_fact or shared_fact over composite_profile
        chosen_chunk = chunks[0]
        for c in chunks:
            if c.get("chunk_type") in ("atomic_fact", "shared_fact", "operational_guide"):
                chosen_chunk = c
                break

        content = chosen_chunk.get("content", "").strip()
        sentences = self._split_into_sentences(content)

        # Limit to max 2 sentences for clear, concise response
        if len(sentences) > 2:
            body = " ".join(sentences[:2])
        else:
            body = " ".join(sentences)

        if not body.endswith((".", "!", "?")):
            body += "."

        return f"{body}\n\nSource: {primary_url}\nLast updated from sources: {last_updated}"

    def generate(
        self,
        query: str,
        retrieved_chunks: List[Any],
        primary_url: Optional[str] = None,
        last_updated: Optional[str] = None
    ) -> str:
        """
        Generates a grounded answer for the user query using retrieved chunks.
        Applies Groq LLM when available; gracefully falls back to deterministic synthesis otherwise.
        """
        chunks = self._extract_chunk_data(retrieved_chunks)

        # Resolve primary URL and last updated date
        if not primary_url:
            for c in chunks:
                url = c.get("url", "")
                if url and "groww.in/mutual-funds/" in url and url != "https://groww.in/mutual-funds":
                    primary_url = url
                    break
            if not primary_url:
                primary_url = chunks[0].get("url", GROWW_SCHEMES[0]["url"]) if chunks else GROWW_SCHEMES[0]["url"]

        if not last_updated:
            last_updated = chunks[0].get("last_updated", DEFAULT_LAST_UPDATED) if chunks else DEFAULT_LAST_UPDATED

        if not chunks:
            return self._generate_deterministic_fallback(query, [], primary_url, last_updated)

        # Build context text
        context_snippets = []
        for i, c in enumerate(chunks, start=1):
            content = c.get("content", "")
            context_snippets.append(f"[{i}] {content}")
        context_text = "\n".join(context_snippets)

        # If Groq client is configured, attempt generation
        if self.client:
            user_prompt = f"""CONTEXT:
{context_text}

SOURCE URL: {primary_url}
LAST UPDATED: {last_updated}

QUESTION: {query}

Please provide a factual answer conforming strictly to the system constraints."""

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=250,
                    top_p=1.0
                )
                raw_text = response.choices[0].message.content.strip()

                # Ensure single Source URL is present
                if f"Source: {primary_url}" not in raw_text:
                    raw_text = re.sub(r"Source:.*", "", raw_text).strip()
                    raw_text += f"\n\nSource: {primary_url}"

                # Ensure Last updated footer is present
                if "Last updated from sources:" not in raw_text:
                    raw_text += f"\nLast updated from sources: {last_updated}"

                return raw_text
            except (groq.RateLimitError, groq.APIStatusError, groq.APIConnectionError, groq.APITimeoutError) as e:
                # Seamless fallback on rate limits (30 RPM / 15K TPM) or network issues
                return self._generate_deterministic_fallback(query, chunks, primary_url, last_updated)
            except Exception:
                # Catch-all fallback
                return self._generate_deterministic_fallback(query, chunks, primary_url, last_updated)

        # Fallback if no Groq client/API key is present
        return self._generate_deterministic_fallback(query, chunks, primary_url, last_updated)
