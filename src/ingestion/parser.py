import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from src.config import RAW_DATA_DIR, PROCESSED_DATA_DIR, GROWW_SCHEMES


class SchemeAttributes(BaseModel):
    expense_ratio: str
    exit_load: str
    min_sip_amount: str
    min_lumpsum_amount: str
    fund_size_aum: str
    current_nav: str
    riskometer: str
    benchmark_index: str
    lock_in_period: str
    fund_manager: str
    stamp_duty: str
    taxation_rules: str
    amc_name: str
    plan_type: str


class NormalizedScheme(BaseModel):
    id: str
    name: str
    official_scheme_name: str
    category: str
    url: str
    last_updated: str
    attributes: SchemeAttributes


class KnowledgeChunk(BaseModel):
    chunk_id: str
    scheme_id: str  # specific scheme_id or "all"
    scheme_name: str
    category: str
    url: str
    chunk_type: str  # "atomic_fact", "composite_profile", "shared_fact", "operational_guide"
    attribute_key: str
    content: str
    last_updated: str


class DataParser:
    """Normalizes raw scraped Groww data and builds granular factual knowledge chunks."""

    def __init__(self):
        self.raw_file = RAW_DATA_DIR / "raw_extracted.json"
        self.processed_dir = PROCESSED_DATA_DIR
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.schemes_output_file = self.processed_dir / "schemes.json"
        self.chunks_output_file = self.processed_dir / "index.json"

    def load_raw_data(self) -> List[Dict[str, Any]]:
        if not self.raw_file.exists():
            raise FileNotFoundError(f"Raw data file not found: {self.raw_file}. Please run scraper first.")
        return json.loads(self.raw_file.read_text(encoding="utf-8"))

    def normalize_schemes(self, raw_data: List[Dict[str, Any]]) -> List[NormalizedScheme]:
        normalized = []
        for item in raw_data:
            raw_attrs = item["raw_attributes"]
            attrs = SchemeAttributes(
                expense_ratio=raw_attrs.get("expense_ratio", "N/A"),
                exit_load=raw_attrs.get("exit_load", "N/A"),
                min_sip_amount=raw_attrs.get("min_sip_amount", "₹100"),
                min_lumpsum_amount=raw_attrs.get("min_lumpsum_amount", "₹100"),
                fund_size_aum=raw_attrs.get("fund_size_aum", "N/A"),
                current_nav=raw_attrs.get("current_nav", "N/A"),
                riskometer=raw_attrs.get("riskometer", "Very High Risk"),
                benchmark_index=raw_attrs.get("benchmark_index", "N/A"),
                lock_in_period=raw_attrs.get("lock_in_period", "No lock-in period"),
                fund_manager=raw_attrs.get("fund_manager", "N/A"),
                stamp_duty=raw_attrs.get("stamp_duty", "0.005%"),
                taxation_rules=raw_attrs.get("taxation_rules", "N/A"),
                amc_name=raw_attrs.get("amc_name", "HDFC Mutual Fund"),
                plan_type=raw_attrs.get("plan_type", "Direct Plan - Growth Option")
            )
            scheme = NormalizedScheme(
                id=item["id"],
                name=item["name"],
                official_scheme_name=item.get("official_scheme_name", item["name"]),
                category=item["category"],
                url=item["url"],
                last_updated=item.get("last_updated", datetime.now().strftime("%Y-%m-%d")),
                attributes=attrs
            )
            normalized.append(scheme)
        return normalized

    def build_atomic_sentence(self, scheme_name: str, key: str, value: str) -> str:
        """Constructs high-clarity natural language sentences embedding scheme entity names."""
        clean_val = value.strip().rstrip(".")
        if key == "exit_load":
            if clean_val.lower().startswith("exit load of "):
                exit_detail = clean_val[13:]
                return f"The exit load for {scheme_name} is {exit_detail}."
            return f"The exit load for {scheme_name} is {clean_val}."
        
        templates = {
            "expense_ratio": f"The expense ratio of {scheme_name} is {clean_val}.",
            "min_sip_amount": f"The minimum SIP (Systematic Investment Plan) investment for {scheme_name} is {clean_val}.",
            "min_lumpsum_amount": f"The minimum lumpsum (one-time) investment amount for {scheme_name} is {clean_val}.",
            "fund_size_aum": f"The fund size (AUM - Assets Under Management) of {scheme_name} is {clean_val}.",
            "current_nav": f"The Net Asset Value (NAV) of {scheme_name} is {clean_val}.",
            "riskometer": f"The riskometer rating for {scheme_name} is {clean_val}.",
            "benchmark_index": f"The benchmark index tracked by {scheme_name} is {clean_val}.",
            "lock_in_period": f"The lock-in period for {scheme_name} is {clean_val}.",
            "fund_manager": f"The fund manager managing {scheme_name} is {clean_val}.",
            "stamp_duty": f"The stamp duty applicable on {scheme_name} is {clean_val}.",
            "taxation_rules": f"The capital gains taxation rules applicable to {scheme_name} are: {clean_val}.",
            "amc_name": f"The Asset Management Company (AMC) managing {scheme_name} is {clean_val}.",
            "plan_type": f"The investment plan and option for {scheme_name} is {clean_val}."
        }
        return templates.get(key, f"For {scheme_name}, the {key.replace('_', ' ')} is {clean_val}.")

    def generate_chunks(self, schemes: List[NormalizedScheme]) -> List[KnowledgeChunk]:
        chunks: List[KnowledgeChunk] = []

        # 1. Atomic Fact Chunks (14 per scheme = 70 chunks)
        for s in schemes:
            attrs_dict = s.attributes.model_dump()
            for key, val in attrs_dict.items():
                content = self.build_atomic_sentence(s.name, key, val)
                chunk_id = f"{s.id}_{key}"
                chunks.append(
                    KnowledgeChunk(
                        chunk_id=chunk_id,
                        scheme_id=s.id,
                        scheme_name=s.name,
                        category=s.category,
                        url=s.url,
                        chunk_type="atomic_fact",
                        attribute_key=key,
                        content=content,
                        last_updated=s.last_updated
                    )
                )

        # 2. Composite Multi-Attribute Profile Chunks (1 per scheme = 5 chunks)
        for s in schemes:
            attrs = s.attributes
            profile_text = (
                f"{s.name} ({s.official_scheme_name}) is a {s.category} offered by {attrs.amc_name}. "
                f"It operates as a {attrs.plan_type} with an Expense Ratio of {attrs.expense_ratio} and Exit Load of {attrs.exit_load}. "
                f"The minimum SIP amount is {attrs.min_sip_amount} and minimum lumpsum is {attrs.min_lumpsum_amount}. "
                f"It benchmarks against {attrs.benchmark_index}, has an AUM of {attrs.fund_size_aum}, NAV of {attrs.current_nav}, "
                f"carries a riskometer level of {attrs.riskometer}, has {attrs.lock_in_period}, and is managed by {attrs.fund_manager}."
            )
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"{s.id}_profile_summary",
                    scheme_id=s.id,
                    scheme_name=s.name,
                    category=s.category,
                    url=s.url,
                    chunk_type="composite_profile",
                    attribute_key="full_profile",
                    content=profile_text,
                    last_updated=s.last_updated
                )
            )

        # 3. Shared Cross-Cutting Knowledge Chunks (scheme_id = "all")
        ref_url = "https://groww.in/mutual-funds"
        today = datetime.now().strftime("%Y-%m-%d")

        shared_facts = [
            (
                "shared_taxation",
                "taxation_rules",
                "For all equity-oriented HDFC mutual fund schemes on Groww, Short-Term Capital Gains (STCG) on units held for 12 months or less are taxed at 20%. "
                "Long-Term Capital Gains (LTCG) on units held for more than 12 months are taxed at 12.5% on gains exceeding ₹1.25 Lakh per financial year."
            ),
            (
                "shared_stamp_duty",
                "stamp_duty",
                "A stamp duty of 0.005% is uniformly applicable on all fresh mutual fund purchases, lumpsum investments, and SIP installments across all schemes since July 1, 2020."
            ),
            (
                "shared_sip_minimum",
                "min_investment",
                "The minimum SIP (Systematic Investment Plan) amount and minimum lumpsum investment across all 5 HDFC mutual fund direct growth schemes is ₹100."
            ),
            (
                "shared_plan_type",
                "plan_structure",
                "All 5 HDFC schemes in this assistant are Direct Plan - Growth Options, where expense ratios are lower compared to regular plans and returns are reinvested."
            )
        ]

        for chunk_id, attr_key, content in shared_facts:
            chunks.append(
                KnowledgeChunk(
                    chunk_id=chunk_id,
                    scheme_id="all",
                    scheme_name="All HDFC Mutual Fund Schemes",
                    category="Mutual Funds General Policy",
                    url=ref_url,
                    chunk_type="shared_fact",
                    attribute_key=attr_key,
                    content=content,
                    last_updated=today
                )
            )

        # 4. Operational / Process Guidance Chunks (Hand-authored accurate procedures)
        operational_guides = [
            (
                "op_download_groww_statement",
                "account_statement_groww",
                "To download your Mutual Fund Account Statement or Capital Gains Report via Groww: "
                "1. Open the Groww app or website and click on your profile icon. "
                "2. Go to 'Reports' section. "
                "3. Select 'Mutual Fund P&L / Capital Gains' report or 'Holding Statement', pick your financial year, and click 'Download PDF' or 'Send to Email'."
            ),
            (
                "op_download_amc_statement",
                "account_statement_amc",
                "To download your official Statement of Account (SOA) directly from HDFC Mutual Fund: "
                "1. Visit the HDFC Mutual Fund official investor portal (hdfcfund.com). "
                "2. Click on 'Investor Desk' -> 'Account Statement'. "
                "3. Enter your Folio Number or PAN along with registered email/phone to receive your password-protected Consolidated Account Statement (CAS)."
            ),
            (
                "op_redemption_process",
                "redemption_process",
                "To redeem your mutual fund units: "
                "On Groww, go to 'Investments' -> select your fund -> click 'Redeem' -> choose the amount or units to withdraw. "
                "Redemption proceeds will be credited directly to your verified primary bank account within T+2 to T+3 business days (subject to applicable exit load and STCG/LTCG taxes)."
            ),
            (
                "op_switch_plan_guidance",
                "switch_plan_guidance",
                "Switching from a Regular Plan to a Direct Plan or between different mutual fund schemes is treated as a redemption followed by a fresh purchase. "
                "Consequently, standard exit load and capital gains taxation (STCG or LTCG) will apply on the switched units based on holding duration."
            )
        ]

        for chunk_id, attr_key, content in operational_guides:
            chunks.append(
                KnowledgeChunk(
                    chunk_id=chunk_id,
                    scheme_id="all",
                    scheme_name="Mutual Fund Operations Guide",
                    category="Operational Guidelines",
                    url=ref_url,
                    chunk_type="operational_guide",
                    attribute_key=attr_key,
                    content=content,
                    last_updated=today
                )
            )

        return chunks

    def run(self) -> Dict[str, Any]:
        print("[INFO] Starting Phase 2.2 Data Normalization & Chunking...")
        raw_data = self.load_raw_data()
        normalized_schemes = self.normalize_schemes(raw_data)

        # 1. Save normalized schemes
        schemes_json_data = [s.model_dump() for s in normalized_schemes]
        with open(self.schemes_output_file, "w", encoding="utf-8") as f:
            json.dump(schemes_json_data, f, indent=2, ensure_ascii=False)
        print(f"[SUCCESS] Normalized 5 schemes saved to {self.schemes_output_file}")

        # 2. Generate and save knowledge chunks
        chunks = self.generate_chunks(normalized_schemes)
        chunks_json_data = [c.model_dump() for c in chunks]
        with open(self.chunks_output_file, "w", encoding="utf-8") as f:
            json.dump(chunks_json_data, f, indent=2, ensure_ascii=False)
        print(f"[SUCCESS] Generated {len(chunks)} knowledge chunks saved to {self.chunks_output_file}")

        return {
            "schemes_count": len(normalized_schemes),
            "chunks_count": len(chunks),
            "schemes_file": str(self.schemes_output_file),
            "chunks_file": str(self.chunks_output_file)
        }


if __name__ == "__main__":
    parser = DataParser()
    result = parser.run()
    print(f"Result: {result}")
