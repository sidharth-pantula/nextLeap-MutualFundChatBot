import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests
from bs4 import BeautifulSoup

from src.config import GROWW_SCHEMES, RAW_DATA_DIR

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class GrowwScraper:
    """Scrapes raw web pages and extracts factual attributes from official Groww scheme URLs."""

    def __init__(self):
        self.schemes_meta = GROWW_SCHEMES
        self.raw_dir = RAW_DATA_DIR
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.raw_extracted_file = self.raw_dir / "raw_extracted.json"

    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch raw HTML content from a Groww scheme URL."""
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code == 200:
                return response.text
            print(f"[ERROR] Failed to fetch {url} (Status: {response.status_code})")
            return None
        except Exception as e:
            print(f"[ERROR] Exception fetching {url}: {e}")
            return None

    def extract_raw_scheme_data(self, html: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses Next.js __NEXT_DATA__ payload (specifically mfServerSideData)
        and extracts key financial parameters.
        """
        soup = BeautifulSoup(html, "html.parser")
        scheme_id = meta["id"]
        scheme_url = meta["url"]
        scraped_at = datetime.now().strftime("%Y-%m-%d")

        mf_data: Dict[str, Any] = {}
        next_data_script = soup.find("script", id="__NEXT_DATA__")
        if next_data_script and next_data_script.string:
            try:
                payload = json.loads(next_data_script.string)
                page_props = payload.get("props", {}).get("pageProps", {})
                mf_data = page_props.get("mfServerSideData", {}) or page_props.get("mfData", {}) or {}
            except Exception as e:
                print(f"[WARN] Error parsing __NEXT_DATA__ for {scheme_id}: {e}")

        # 1. Expense Ratio
        expense_ratio = mf_data.get("expense_ratio")
        if expense_ratio is not None:
            expense_ratio_str = f"{expense_ratio}% (inclusive of GST)"
        else:
            er_match = re.search(r'Expense\s*Ratio\s*[:\n\r\t]*([0-9.]+\s*%)', html, re.I)
            expense_ratio_str = er_match.group(1) if er_match else "Available on Groww factsheet"

        # 2. Exit Load
        exit_load = mf_data.get("exit_load")
        if exit_load:
            exit_load_str = str(exit_load).strip()
        else:
            exit_load_str = "Nil / Refer to scheme details on Groww"

        # 3. Minimum SIP and Lumpsum
        min_sip = mf_data.get("min_sip_investment")
        min_sip_str = f"₹{int(min_sip)}" if min_sip is not None else "₹100"

        min_lumpsum = mf_data.get("min_lumpsum_investment") or mf_data.get("min_investment_amount")
        min_lumpsum_str = f"₹{int(min_lumpsum)}" if min_lumpsum is not None else "₹100"

        # 4. Fund Size / AUM & NAV
        fund_size = mf_data.get("fund_size") or mf_data.get("aum")
        fund_size_str = f"₹{fund_size:,.2f} Cr" if isinstance(fund_size, (int, float)) else "Available on Groww factsheet"

        nav = mf_data.get("nav")
        nav_str = f"₹{nav:.2f}" if isinstance(nav, (int, float)) else "Available on Groww factsheet"

        # 5. Benchmark & Riskometer
        benchmark = mf_data.get("benchmark_name") or f"Benchmark for {meta['category']}"
        risk = mf_data.get("risk_name") or mf_data.get("risk") or "Very High Risk"
        fund_manager = mf_data.get("fund_manager") or "HDFC Asset Management Team"

        # 6. Lock-in Period
        lock_in_obj = mf_data.get("lock_in")
        if isinstance(lock_in_obj, dict) and any(lock_in_obj.values()):
            lock_in_str = f"{lock_in_obj.get('years', 0)} years"
        else:
            lock_in_str = "No lock-in period"

        # 7. Stamp Duty & Tax Rules
        stamp_duty = mf_data.get("stamp_duty") or "0.005% (Applicable on mutual fund purchases since July 1, 2020)"
        tax_info = (
            "Returns are taxed at 20% for holding periods under 1 year (STCG). "
            "For holding periods over 1 year, gains exceeding ₹1.25 Lakh per financial year are taxed at 12.5% (LTCG)."
        )

        return {
            "id": scheme_id,
            "name": meta["name"],
            "official_scheme_name": mf_data.get("scheme_name", meta["name"]),
            "category": meta["category"],
            "url": scheme_url,
            "last_updated": scraped_at,
            "raw_attributes": {
                "expense_ratio": expense_ratio_str,
                "exit_load": exit_load_str,
                "min_sip_amount": min_sip_str,
                "min_lumpsum_amount": min_lumpsum_str,
                "fund_size_aum": fund_size_str,
                "current_nav": nav_str,
                "riskometer": str(risk),
                "benchmark_index": str(benchmark),
                "lock_in_period": lock_in_str,
                "fund_manager": str(fund_manager),
                "stamp_duty": stamp_duty,
                "taxation_rules": tax_info,
                "amc_name": "HDFC Mutual Fund (HDFC Asset Management Company Limited)",
                "plan_type": "Direct Plan - Growth Option",
            },
            "scheme_objective": (mf_data.get("objective") or mf_data.get("scheme_objective") or "").strip()
        }

    def run(self) -> List[Dict[str, Any]]:
        """Scrapes all 5 target schemes, caches raw HTML, and saves raw extracted JSON."""
        print("[INFO] Starting Phase 2.1 Web Scraping for 5 Groww mutual fund schemes...")
        extracted_data = []

        for meta in self.schemes_meta:
            scheme_id = meta["id"]
            url = meta["url"]
            raw_html_file = self.raw_dir / f"{scheme_id}.html"

            print(f"[INFO] Fetching {meta['name']} -> {url}")
            html = self.fetch_page(url)

            if html:
                # Save raw HTML cache
                with open(raw_html_file, "w", encoding="utf-8") as f:
                    f.write(html)
            elif raw_html_file.exists():
                print(f"[WARN] Using existing cache for {scheme_id}")
                html = raw_html_file.read_text(encoding="utf-8")
            else:
                raise RuntimeError(f"Could not fetch data or find cache for {scheme_id} at {url}")

            parsed_record = self.extract_raw_scheme_data(html, meta)
            extracted_data.append(parsed_record)
            time.sleep(0.5)

        # Save extracted raw JSON
        with open(self.raw_extracted_file, "w", encoding="utf-8") as f:
            json.dump(extracted_data, f, indent=2, ensure_ascii=False)

        print(f"[SUCCESS] Phase 2.1 Complete: Extracted 5 schemes and cached in {self.raw_dir}")
        return extracted_data


if __name__ == "__main__":
    scraper = GrowwScraper()
    scraper.run()
