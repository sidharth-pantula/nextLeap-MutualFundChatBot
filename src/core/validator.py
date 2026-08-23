"""
Output Validation & Post-Processing Module.

Enforces strict compliance and response formatting contracts:
1. Sentence Count Enforcement (strictly <= 3 sentences).
2. Single Valid Source Citation (whitelisted Groww / SEBI / AMFI URLs).
3. Mandatory Timestamp Footer ('Last updated from sources: <date>').
4. Advisory Trigger Word / Recommendation Leakage Detection & Neutralization.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from src.config import (
    GROWW_SCHEMES,
    SEBI_INVESTOR_URL,
    AMFI_INVESTOR_URL,
    MAX_SENTENCE_LIMIT,
)

DEFAULT_LAST_UPDATED = "2026-08-23"

# Whitelist of approved citation domains and URLs
APPROVED_URLS = [s["url"] for s in GROWW_SCHEMES] + [
    "https://groww.in/mutual-funds",
    SEBI_INVESTOR_URL,
    AMFI_INVESTOR_URL,
    "https://www.amfiindia.com/",
]

# Prohibited advisory & opinion trigger phrases that must never appear in final output
PROHIBITED_ADVISORY_PATTERNS = [
    r"\b(?:i|we)\s+(?:recommend|advise|suggest|urge)\b",
    r"\byou\s+(?:should|must|ought\s+to)\s+(?:invest|buy|choose|pick|allocate)\b",
    r"\b(?:best\s+choice|best\s+fund\s+to\s+choose|best\s+option\s+for\s+you)\b",
    r"\b(?:guaranteed\s+returns?|guaranteed\s+profit|assured\s+growth)\b",
    r"\b(?:top\s+stock\s+picks?|trading\s+calls?|hot\s+picks?)\b",
    r"\b(?:buy\s+this\s+fund|sell\s+this\s+fund|enter\s+this\s+fund)\b",
    r"\b(?:in\s+my\s+opinion|my\s+advice\s+is)\b",
]

COMPILED_PROHIBITED_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in PROHIBITED_ADVISORY_PATTERNS
]


@dataclass
class ValidationResult:
    """Structured report produced by ResponseValidator."""
    valid: bool
    formatted_output: str
    sentence_count: int
    citation_url: str
    last_updated: str
    had_advisory_leakage: bool = False
    was_truncated: bool = False


class ResponseValidator:
    """
    Validates, sanitizes, and formats all LLM-generated and fallback responses
    to ensure 100% compliance with format contracts and regulatory constraints.
    """

    def __init__(
        self,
        default_last_updated: str = DEFAULT_LAST_UPDATED,
        max_sentences: int = MAX_SENTENCE_LIMIT
    ):
        self.default_last_updated = default_last_updated
        self.max_sentences = max_sentences
        self.approved_urls = APPROVED_URLS

    def split_sentences(self, text: str) -> List[str]:
        """
        Splits text into discrete sentences while protecting decimals (e.g. 0.75%),
        currency amounts (e.g. ₹105,142.69 Cr), abbreviations (e.g. i.e., e.g., vs.),
        and numbered lists.
        """
        if not text or not text.strip():
            return []

        cleaned = text.strip()
        
        # Protect common abbreviations and decimal points before splitting
        # Replace decimal dot in numbers (e.g. 0.75 or 142.69) with a placeholder
        decimal_placeholder = "<DEC_DOT>"
        cleaned = re.sub(r'(\d+)\.(\d+)', r'\1' + decimal_placeholder + r'\2', cleaned)
        
        # Protect abbreviations like e.g., i.e., vs., no., No.
        cleaned = re.sub(r'\b(e\.g\.|i\.e\.|vs\.|no\.|No\.|Rs\.|approx\.)', lambda m: m.group(0).replace('.', '<ABBR_DOT>'), cleaned, flags=re.IGNORECASE)

        # Protect numbered list markers (e.g. 1. 2. 3.)
        cleaned = re.sub(r'(^|\s)(\d+)\.', r'\1\2<NUM_DOT>', cleaned)

        # Split on sentence terminators (. ! ?) followed by whitespace or end of string
        raw_chunks = re.split(r'[.!?]+(?:\s+|$)', cleaned)

        sentences = []
        for s in raw_chunks:
            # Restore decimal dots, abbreviations, and numbered list dots
            restored = s.replace(decimal_placeholder, '.').replace('<ABBR_DOT>', '.').replace('<NUM_DOT>', '.').strip()
            if restored:
                # Append terminating period if missing
                if not restored.endswith(('.', '!', '?')):
                    restored += '.'
                sentences.append(restored)

        return sentences

    def check_and_scrub_advisory_leakage(self, text: str) -> Tuple[bool, str]:
        """
        Scans for prohibited advisory phrases. Scrubs/replaces any detected leakage.
        """
        leakage_detected = False
        scrubbed = text

        for pattern in COMPILED_PROHIBITED_PATTERNS:
            if pattern.search(scrubbed):
                leakage_detected = True
                scrubbed = pattern.sub("", scrubbed)

        # Clean up any awkward double spaces or broken punctuation
        scrubbed = re.sub(r'\s{2,}', ' ', scrubbed).strip()
        scrubbed = re.sub(r'\s+([.,!?])', r'\1', scrubbed)

        return leakage_detected, scrubbed

    def is_valid_url(self, url: str) -> bool:
        """Verifies if the URL belongs to approved Groww, SEBI, or AMFI sources."""
        if not url:
            return False
        
        # Check against approved list or known domain prefixes
        valid_domains = [
            "groww.in/mutual-funds",
            "investor.sebi.gov.in",
            "amfiindia.com",
            "www.amfiindia.com"
        ]
        return any(d in url for d in valid_domains)

    def extract_citation_and_footer(
        self,
        raw_text: str,
        fallback_url: Optional[str] = None,
        fallback_date: Optional[str] = None
    ) -> Tuple[str, str, str]:
        """
        Extracts body text, citation URL, and last updated date from raw output.
        """
        citation_url = fallback_url or GROWW_SCHEMES[0]["url"]
        last_updated = fallback_date or self.default_last_updated

        # 1. Search for Source: URL pattern
        source_match = re.search(r"Source:\s*(https?://[^\s\n]+)", raw_text, re.IGNORECASE)
        if source_match:
            found_url = source_match.group(1).strip()
            if self.is_valid_url(found_url):
                citation_url = found_url

        # 2. Search for Last updated from sources: YYYY-MM-DD pattern
        date_match = re.search(r"Last updated from sources:\s*(\d{4}-\d{2}-\d{2})", raw_text, re.IGNORECASE)
        if date_match:
            last_updated = date_match.group(1).strip()

        # 3. Extract pure body text by stripping Source and Last updated lines
        lines = raw_text.split("\n")
        body_lines = []
        for line in lines:
            trimmed = line.strip()
            if trimmed.lower().startswith("source:") or trimmed.lower().startswith("last updated from sources:"):
                continue
            if trimmed:
                body_lines.append(trimmed)

        body_text = " ".join(body_lines).strip()
        # Remove any inline markdown links from body text to prevent multiple links
        body_text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'\1', body_text)
        # Remove raw http/https links in the body text
        body_text = re.sub(r'https?://[^\s]+', '', body_text).strip()

        return body_text, citation_url, last_updated

    def validate_and_format(
        self,
        raw_output: str,
        fallback_url: Optional[str] = None,
        fallback_date: Optional[str] = None
    ) -> str:
        """
        Transforms and standardizes any raw response into a strictly compliant format:
        - Body: <= 3 sentences (trimmed if longer), with zero advisory leakage.
        - Source: Exactly 1 valid URL.
        - Footer: 'Last updated from sources: <date>'.
        """
        result = self.validate(raw_output, fallback_url, fallback_date)
        return result.formatted_output

    def validate(
        self,
        raw_output: str,
        fallback_url: Optional[str] = None,
        fallback_date: Optional[str] = None
    ) -> ValidationResult:
        """
        Performs full validation and returns a structured ValidationResult.
        """
        if not raw_output or not raw_output.strip():
            empty_url = fallback_url or GROWW_SCHEMES[0]["url"]
            empty_date = fallback_date or self.default_last_updated
            msg = "This information is not available in the official scheme documents on Groww."
            formatted = f"{msg}\n\nSource: {empty_url}\nLast updated from sources: {empty_date}"
            return ValidationResult(
                valid=True,
                formatted_output=formatted,
                sentence_count=1,
                citation_url=empty_url,
                last_updated=empty_date
            )

        # Step 1: Extract body, citation URL, and date
        body_text, citation_url, last_updated = self.extract_citation_and_footer(
            raw_output, fallback_url, fallback_date
        )

        # Step 2: Scrub advisory trigger words
        had_leakage, scrubbed_body = self.check_and_scrub_advisory_leakage(body_text)

        # Step 3: Split and enforce sentence limit (<= 3 sentences)
        sentences = self.split_sentences(scrubbed_body)
        was_truncated = len(sentences) > self.max_sentences

        if was_truncated:
            sentences = sentences[:self.max_sentences]

        final_body = " ".join(sentences).strip()
        if not final_body:
            final_body = "This information is not available in the official scheme documents on Groww."

        # Step 4: Assemble standardized compliance format
        formatted = f"{final_body}\n\nSource: {citation_url}\nLast updated from sources: {last_updated}"

        return ValidationResult(
            valid=True,
            formatted_output=formatted,
            sentence_count=len(sentences),
            citation_url=citation_url,
            last_updated=last_updated,
            had_advisory_leakage=had_leakage,
            was_truncated=was_truncated
        )
