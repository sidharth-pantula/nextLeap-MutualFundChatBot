"""
Input Guardrails & Query Sanitizer Module.

This module provides deterministic pre-processing for user queries:
1. PII Detection & Sanitization (PAN, Aadhaar, Folio, Account No, Phone, Email, OTP/PIN/Card).
2. Intent Classification (FACTUAL, ADVISORY, OUT_OF_CORPUS).
3. Scheme Entity Recognition.
4. Deterministic Compliance Refusal Generation adhering to the format contract (<= 3 sentences, 1 citation, date footer).
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from src.config import (
    GROWW_SCHEMES,
    SEBI_INVESTOR_URL,
    AMFI_INVESTOR_URL,
)

DEFAULT_LAST_UPDATED = "2026-08-23"

# ==============================================================================
# Regex Patterns for Personally Identifiable Information (PII)
# ==============================================================================

# Indian PAN Card: 5 uppercase letters, 4 digits, 1 uppercase letter
PAN_PATTERN = re.compile(r"\b[A-Za-z]{5}[0-9]{4}[A-Za-z]\b")

# Indian Aadhaar Number: 12 digits, often formatted as 4-4-4 (with space or hyphen) or solid 12 digits (starting 2-9)
AADHAAR_PATTERN = re.compile(r"\b[2-9]\d{3}[\s\-]?\d{4}[\s\-]?\d{4}\b")

# Folio / Bank Account Numbers:
# Captures explicitly labeled folio/account numbers or standalone long numbers associated with account/folio
FOLIO_OR_ACCOUNT_PATTERN = re.compile(
    r"\b(?:folio|account|acct|acc|a/c)\s*(?:no\.?|number|#)?\s*[:\-]?\s*([0-9A-Za-z\/\-]{6,20})\b",
    re.IGNORECASE
)
STANDALONE_FOLIO_PATTERN = re.compile(
    r"\b(?:folio\s+is\s+|folio\s+)([0-9A-Za-z]{5,20})\b",
    re.IGNORECASE
)

# Indian Phone / Mobile Numbers: 10 digits starting with 6, 7, 8, 9, optionally prefixed by +91 / 0
PHONE_PATTERN = re.compile(
    r"(?:(?:\+91[\-\s]?|0)?[6-9]\d{9}\b)|(?:\b(?:phone|mobile|call|contact|tel)\s*(?:no\.?|number|#)?\s*[:\-]?\s*(?:\+91[\-\s]?)?([0-9]{10,12})\b)",
    re.IGNORECASE
)

# Email Addresses
EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# OTP / Passwords / PINs / Card Numbers
SECURITY_CREDENTIALS_PATTERN = re.compile(
    r"\b(?:otp|password|pwd|cvv|pin|passcode)\s*(?:is|:|=|-)?\s*([0-9a-zA-Z]{4,8})\b",
    re.IGNORECASE
)
CREDIT_DEBIT_CARD_PATTERN = re.compile(
    r"\b(?:\d{4}[\s\-]?){3}\d{4}\b"
)


# ==============================================================================
# Advisory, Opinion, Comparison & Non-Factual Intent Keywords / Patterns
# ==============================================================================

ADVISORY_PATTERNS = [
    # Direct advice, recommendations & opinions
    r"\bshould\s+i\s+(?:invest|buy|sell|choose|pick|enter|exit|start|hold|put|opt)\b",
    r"\b(?:can|shall|would|could)\s+i\s+(?:invest|buy|put\s+money|start\s+sip)\b",
    r"\bis\s+it\s+(?:good|bad|safe|better|advisable|worth|profitable|right\s+time|recommended)\b",
    r"\bis\s+.*?\b(?:good|suitable|safe|profitable|worth\s+investing|the\s+best|recommended|good\s+to\s+buy|advisable)\b",
    r"\b(?:suggest|recommend|advise|give\s+me\s+advice|opinion\s+on)\b",
    r"\b(?:top|best)\s+(?:mutual\s+)?(?:fund|scheme)s?\b",
    r"\b(?:which|what)\s+(?:fund|scheme)\s+should\s+i\s+(?:buy|choose|pick|invest)\b",
    r"\b(?:what\s+is\s+the\s+best\s+mutual\s+fund|what\s+is\s+the\s+best\s+scheme)\b",
    r"\b(?:stock\s+picks|trading\s+calls|hot\s+funds|multibagger)\b",

    # Profile-based & goal-oriented suitability
    r"\bsuitable\s+for\s+me\b",
    r"\b(?:i\s+am|i\'m)\s+\d{1,2}\s*(?:years\s+old|yo)?\b",
    r"\b(?:my\s+salary\s+is|i\s+earn|i\s+have\s+₹?\s*\d+)\b",
    r"\b(?:where\s+should\s+i\s+invest|how\s+should\s+i\s+allocate)\b",
    r"\b(?:plan\s+(?:my\s+)?retirement|retirement\s+plan(?:ning)?|child\s+education|marriage\s+corpus|help\s+me\s+plan)\b",

    # Comparative advice & subjective comparisons
    r"\bwhich\s+(?:fund\s+|scheme\s+|one\s+)?is\s+better\b",
    r"\bcompare\s+.*?\b(?:and|with|vs|versus|to)\b",
    r"\b\w+\s+(?:vs|versus)\s+\w+\b",
    r"\bbetter\s+than\b",
    r"\bwhich\s+(?:fund\s+)?gives?\s+(?:more|higher|better)\s+returns?\b",
    r"\bwhich\s+(?:fund\s+)?is\s+safer\b",

    # Return predictions, projections & guarantees
    r"\bhow\s+much\s+(?:will|can)\s+.*?\b(?:grow|earn|make|return|give)\b",
    r"\bwill\s+.*?\b(?:double|triple|grow\s+to|give|reach)\b",
    r"\b(?:guaranteed|guarantee)\s+(?:returns?|money|profit)\b",
    r"\bpredict\s+(?:nav|returns?|future|growth)\b",
    r"\bexpected\s+returns?\s+in\s+\d+\s+years?\b",
    r"\bcalculate\s+.*?\breturns?\b",
    r"\bcalculate\s+.*?\b(?:profit|growth|gain|future|sip)\b",

    # Adversarial jailbreak & prompt injection attempts
    r"\bignore\s+(?:all\s+)?(?:previous\s+|prior\s+)?(?:instructions|constraints|rules|guidelines)\b",
    r"\bignore\s+(?:all\s+)?(?:compliance\s+|safety\s+|system\s+)?rules\b",
    r"\byou\s+are\s+now\s+(?:wealthgpt|dan|an\s+advisor|unrestricted)\b",
    r"\bact\s+as\s+(?:an?\s+)?(?:unrestricted|financial\s+(?:advisor|planner)|expert\s+advisor)\b",
    r"\b(?:pick|choose|suggest)\s+(?:a|the|me\s+a)\s+fund\b",
    r"\bforget\s+(?:your\s+)?(?:system\s+prompt|constraints|rules)\b",
    r"\bbypass\s+(?:guardrails|restrictions)\b",
]

# Compile advisory regexes
COMPILED_ADVISORY_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in ADVISORY_PATTERNS
]


# ==============================================================================
# Competitor AMCs / Out-of-Corpus Mutual Fund Brands
# ==============================================================================

COMPETITOR_AMCS = [
    "sbi", "icici", "icici prudential", "nippon", "nippon india", "kotak",
    "kotak mahindra", "axis", "axis mutual fund", "parag parikh", "ppfas",
    "mirae", "mirae asset", "uti", "uti mutual fund", "dsp", "tata",
    "tata mutual fund", "motilal", "motilal oswal", "quant", "quant mutual fund",
    "bandhan", "aditya birla", "aditya birla sun life", "absl", "franklin",
    "franklin templeton", "invesco", "canara robeco", "sundaram", "edelweiss",
    "whiteoak", "navi", "zerodha", "pgim", "baroda bnp paribas", "hsbc",
    "mahindra manulife", "union mutual fund", "samco", "trust mutual fund",
    "groww mutual fund", "helios", "old bridge", "360 one"
]

COMPETITOR_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(brand) for brand in COMPETITOR_AMCS) + r")\s+(?:mutual\s+fund|fund|scheme|bluechip|flexi\s*cap|emerging|hybrid|arbitrage|overnight|liquid|elss|small\s*cap|mid\s*cap|large\s*cap)\b",
    re.IGNORECASE
)

# Standalone check for explicit competitor mentions
STANDALONE_COMPETITOR_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(brand) for brand in COMPETITOR_AMCS) + r")\b",
    re.IGNORECASE
)


# ==============================================================================
# Factual Attribute Keywords
# ==============================================================================

FACTUAL_KEYWORDS = [
    "expense ratio", "ter", "total expense ratio",
    "exit load", "redemption load", "exit penalty",
    "min sip", "minimum sip", "sip amount", "sip minimum",
    "lumpsum", "min lumpsum", "minimum lumpsum", "lump sum",
    "nav", "net asset value", "current nav",
    "aum", "fund size", "asset size", "assets under management",
    "benchmark", "benchmark index", "index",
    "riskometer", "risk level", "risk grade",
    "fund manager", "managed by", "portfolio manager",
    "lock in", "lock-in", "lock in period", "elss",
    "tax", "taxation", "stcg", "ltcg", "capital gains tax", "tax rate",
    "stamp duty", "stamp charge",
    "amc", "amc name", "fund house", "hdfc amc",
    "direct plan", "regular plan", "growth option", "plan type",
    "statement", "account statement", "download statement", "capital gains",
    "capital gains statement", "capital gains report", "download report",
    "how to switch", "how to invest", "groww"
]


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass
class GuardrailResult:
    """Structured evaluation result produced by the GuardrailEngine."""
    passed: bool
    intent: str  # "FACTUAL", "ADVISORY", "OUT_OF_CORPUS", "PII_INTERCEPTED"
    has_pii: bool
    pii_types: List[str] = field(default_factory=list)
    sanitized_query: str = ""
    refusal_response: Optional[str] = None
    detected_scheme_ids: List[str] = field(default_factory=list)
    reason: Optional[str] = None


# ==============================================================================
# Guardrail Engine Implementation
# ==============================================================================

class GuardrailEngine:
    """
    Compliance and Safety Guardrail Engine.
    Handles PII detection, intent routing, scheme recognition, and refusal formatting.
    """

    def __init__(self, last_updated_date: str = DEFAULT_LAST_UPDATED):
        self.last_updated_date = last_updated_date
        self.schemes = GROWW_SCHEMES

    def sanitize_and_check_pii(self, text: str) -> Tuple[bool, str]:
        """
        Scans query for sensitive Personally Identifiable Information (PII).
        Returns a tuple of (detected: bool, sanitized_text: str).
        """
        if not text or not text.strip():
            return False, text

        sanitized = text
        detected_types: List[str] = []

        # 1. PAN detection
        if PAN_PATTERN.search(sanitized):
            sanitized = PAN_PATTERN.sub("[REDACTED_PAN]", sanitized)
            detected_types.append("PAN")

        # 2. Aadhaar detection
        if AADHAAR_PATTERN.search(sanitized):
            sanitized = AADHAAR_PATTERN.sub("[REDACTED_AADHAAR]", sanitized)
            detected_types.append("Aadhaar")

        # 3. Folio / Account Number detection
        if FOLIO_OR_ACCOUNT_PATTERN.search(sanitized):
            sanitized = FOLIO_OR_ACCOUNT_PATTERN.sub(r"account [REDACTED_ACCOUNT]", sanitized)
            detected_types.append("Folio/Account")
        elif STANDALONE_FOLIO_PATTERN.search(sanitized):
            sanitized = STANDALONE_FOLIO_PATTERN.sub(r"folio [REDACTED_FOLIO]", sanitized)
            detected_types.append("Folio/Account")

        # 4. Phone Number detection
        if PHONE_PATTERN.search(sanitized):
            sanitized = PHONE_PATTERN.sub("[REDACTED_PHONE]", sanitized)
            detected_types.append("Phone")

        # 5. Email detection
        if EMAIL_PATTERN.search(sanitized):
            sanitized = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", sanitized)
            detected_types.append("Email")

        # 6. Credentials (OTP, PIN, Card)
        if SECURITY_CREDENTIALS_PATTERN.search(sanitized):
            sanitized = SECURITY_CREDENTIALS_PATTERN.sub("[REDACTED_CREDENTIAL]", sanitized)
            detected_types.append("Credential")

        if CREDIT_DEBIT_CARD_PATTERN.search(sanitized):
            sanitized = CREDIT_DEBIT_CARD_PATTERN.sub("[REDACTED_CARD]", sanitized)
            detected_types.append("Card")

        has_pii = len(detected_types) > 0
        return has_pii, sanitized

    def detect_scheme(self, text: str) -> List[str]:
        """
        Identifies which of the 5 HDFC schemes are explicitly or implicitly referenced in the query.
        Returns a list of scheme IDs (e.g., ['hdfc-small-cap-fund']).
        """
        lowered = text.lower()
        matched_schemes: List[str] = []

        # Check in order of specificity (Nifty Next 50 before Nifty 50)
        # 1. HDFC Nifty Next 50
        if any(alias in lowered for alias in ["nifty next 50", "next 50", "junior nifty"]):
            matched_schemes.append("hdfc-nifty-next-50-index-fund")

        # 2. HDFC Nifty 50 (ensure not Next 50)
        elif any(alias in lowered for alias in ["nifty 50", "hdfc nifty", "nifty index"]):
            matched_schemes.append("hdfc-nifty-50-index-fund")

        # 3. HDFC Mid-Cap
        if any(alias in lowered for alias in ["mid cap", "midcap", "mid-cap"]):
            matched_schemes.append("hdfc-mid-cap-fund")

        # 4. HDFC Small Cap
        if any(alias in lowered for alias in ["small cap", "smallcap", "small-cap"]):
            matched_schemes.append("hdfc-small-cap-fund")

        # 5. HDFC Multi Cap
        if any(alias in lowered for alias in ["multi cap", "multicap", "multi-cap"]):
            matched_schemes.append("hdfc-multi-cap-fund")

        # Generic Index Fund (both Nifty 50 and Nifty Next 50)
        if "index fund" in lowered and not matched_schemes:
            matched_schemes = ["hdfc-nifty-50-index-fund", "hdfc-nifty-next-50-index-fund"]

        return matched_schemes

    def classify_intent(self, text: str) -> str:
        """
        Classifies user query intent into:
        - 'ADVISORY' (advice, opinions, comparisons, future predictions, jailbreaks)
        - 'OUT_OF_CORPUS' (unsupported AMCs, off-topic domains)
        - 'FACTUAL' (verifiable scheme attributes, processes, facts)
        """
        if not text or not text.strip():
            return "FACTUAL"

        lowered = text.lower()

        # 1. Check Advisory Patterns
        for pattern in COMPILED_ADVISORY_PATTERNS:
            if pattern.search(lowered):
                return "ADVISORY"

        # 2. Check for Competitor AMCs / Non-HDFC mutual funds
        # If query mentions a competitor AMC without mentioning HDFC
        is_hdfc_mentioned = "hdfc" in lowered
        if COMPETITOR_PATTERN.search(lowered) and not is_hdfc_mentioned:
            return "OUT_OF_CORPUS"

        for comp in COMPETITOR_AMCS:
            if comp in lowered and not is_hdfc_mentioned:
                # Check if it's asking about that competitor fund
                if any(w in lowered for w in ["fund", "scheme", "aum", "nav", "ratio", "load", "sip"]):
                    return "OUT_OF_CORPUS"

        # 3. Check for Completely Off-Topic Queries (Weather, Coding, Recipes, Politics, Crypto)
        off_topic_indicators = [
            "weather", "forecast", "temperature outside", "rain today",
            "recipe", "how to cook", "ingredients for",
            "write code", "python script", "javascript function", "debug this",
            "who is the president", "election", "prime minister",
            "bitcoin", "crypto", "ethereum", "btc", "dogecoin", "buy stock in reliance", "share price of tata motors"
        ]
        if any(ind in lowered for ind in off_topic_indicators) and not is_hdfc_mentioned:
            return "OUT_OF_CORPUS"

        # 4. Check for Greetings / Capability Inquiries
        if re.search(r"^\s*(?:hi|hello|hey|greetings|help|what\s+can\s+you\s+do|how\s+can\s+you\s+help)\b", lowered):
            if not any(k in lowered for k in ["expense", "nav", "exit load", "sip", "aum", "manager", "benchmark", "tax", "hdfc"]):
                return "GREETING"

        # Default to FACTUAL
        return "FACTUAL"

    def get_refusal_response(
        self,
        intent: str,
        detected_scheme_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> str:
        """
        Constructs a strictly compliant refusal response meeting all format contracts:
        - <= 3 sentences
        - Exactly 1 citation link (SEBI, AMFI, or Groww)
        - Mandatory footer: 'Last updated from sources: <date>'
        """
        # Determine source URL
        citation_url = SEBI_INVESTOR_URL

        if intent == "GREETING":
            citation_url = "https://groww.in/mutual-funds"
            body = (
                "Hello! I am the Groww Mutual Fund FAQ Assistant. "
                "I provide verified, facts-only answers for 5 designated HDFC Mutual Fund schemes including expense ratios, exit loads, NAV, minimum SIPs, and taxation rules."
            )

        elif intent == "PII_INTERCEPTED":
            # For PII, provide Groww scheme link or SEBI portal link
            if detected_scheme_id:
                scheme = next((s for s in self.schemes if s["id"] == detected_scheme_id), None)
                if scheme:
                    citation_url = scheme["url"]
                else:
                    citation_url = self.schemes[0]["url"]
            else:
                citation_url = self.schemes[0]["url"]

            body = (
                "For your privacy and security, please do not share sensitive personal information such as "
                "PAN, Aadhaar, account or folio numbers, OTPs, or contact details. "
                "I only provide objective, factual information about mutual fund schemes."
            )

        elif intent == "ADVISORY":
            if reason == "PREDICTION":
                if detected_scheme_id:
                    scheme = next((s for s in self.schemes if s["id"] == detected_scheme_id), None)
                    citation_url = scheme["url"] if scheme else self.schemes[0]["url"]
                else:
                    citation_url = self.schemes[0]["url"]

                body = (
                    "Mutual fund investments are subject to market risks and future returns cannot be guaranteed or predicted. "
                    "You can review historical NAV and factual scheme parameters directly on the official scheme factsheets on Groww."
                )
            elif reason == "COMPARISON":
                citation_url = AMFI_INVESTOR_URL
                body = (
                    "I am a facts-only assistant and strictly cannot compare fund quality or advise which scheme to choose. "
                    "You may ask for individual factual parameters such as the expense ratio, exit load, or benchmark index for each scheme."
                )
            else:
                citation_url = SEBI_INVESTOR_URL
                body = (
                    "I am a facts-only assistant and strictly cannot provide investment advice, fund suitability evaluations, or personal recommendations. "
                    "For objective investor education and regulatory guidelines, please consult the official SEBI investor portal."
                )

        elif intent == "OUT_OF_CORPUS":
            citation_url = AMFI_INVESTOR_URL
            body = (
                "This assistant is specifically configured to answer factual questions for 5 designated HDFC Mutual Fund schemes on Groww. "
                "Factual information for other mutual fund schemes can be explored on the Groww platform or AMFI website."
            )

        else:
            citation_url = SEBI_INVESTOR_URL
            body = (
                "I am a facts-only assistant and only provide verified, objective mutual fund information from official Groww pages. "
                "Please consult the SEBI investor portal for general regulatory and educational guidelines."
            )

        # Assemble format contract: Body -> Source: <URL> -> Last updated from sources: <date>
        return f"{body}\n\nSource: {citation_url}\nLast updated from sources: {self.last_updated_date}"

    def process_query(self, query: str) -> GuardrailResult:
        """
        Executes the end-to-end input guardrail pipeline:
        1. Checks for PII.
        2. Detects referenced scheme(s).
        3. Classifies query intent.
        4. Generates standard refusal if intercepted, or marks as passed for RAG retrieval.
        """
        # Step 1: PII Sanitization & Check
        has_pii, sanitized = self.sanitize_and_check_pii(query)
        detected_schemes = self.detect_scheme(query)
        primary_scheme = detected_schemes[0] if detected_schemes else None

        if has_pii:
            refusal = self.get_refusal_response(
                intent="PII_INTERCEPTED",
                detected_scheme_id=primary_scheme
            )
            return GuardrailResult(
                passed=False,
                intent="PII_INTERCEPTED",
                has_pii=True,
                sanitized_query=sanitized,
                refusal_response=refusal,
                detected_scheme_ids=detected_schemes,
                reason="Sensitive personal data detected in user query."
            )

        # Step 2: Intent Classification
        intent = self.classify_intent(query)

        if intent == "ADVISORY":
            # Sub-reasoning for fine-tuned refusal messaging
            lowered = query.lower()
            if any(w in lowered for w in ["will it double", "grow to", "how much will", "guaranteed", "predict", "calculate"]):
                reason = "PREDICTION"
            elif any(w in lowered for w in ["which is better", "compare", "vs", "versus", "better than"]):
                reason = "COMPARISON"
            else:
                reason = "ADVICE"

            refusal = self.get_refusal_response(
                intent="ADVISORY",
                detected_scheme_id=primary_scheme,
                reason=reason
            )
            return GuardrailResult(
                passed=False,
                intent="ADVISORY",
                has_pii=False,
                sanitized_query=sanitized,
                refusal_response=refusal,
                detected_scheme_ids=detected_schemes,
                reason=f"Advisory/subjective query detected ({reason})."
            )

        if intent == "OUT_OF_CORPUS":
            refusal = self.get_refusal_response(
                intent="OUT_OF_CORPUS",
                detected_scheme_id=primary_scheme
            )
            return GuardrailResult(
                passed=False,
                intent="OUT_OF_CORPUS",
                has_pii=False,
                sanitized_query=sanitized,
                refusal_response=refusal,
                detected_scheme_ids=detected_schemes,
                reason="Query refers to an unsupported AMC or out-of-scope domain."
            )

        if intent == "GREETING":
            refusal = self.get_refusal_response(intent="GREETING")
            return GuardrailResult(
                passed=False,
                intent="GREETING",
                has_pii=False,
                sanitized_query=sanitized,
                refusal_response=refusal,
                detected_scheme_ids=detected_schemes,
                reason="Greeting / capability inquiry."
            )

        # Step 3: Factual Query (Passed)
        return GuardrailResult(
            passed=True,
            intent="FACTUAL",
            has_pii=False,
            sanitized_query=sanitized,
            refusal_response=None,
            detected_scheme_ids=detected_schemes,
            reason="Objective factual query within approved corpus scope."
        )
