import json
from pathlib import Path

DATA_DIR = Path("data")
RAW_FILE = DATA_DIR / "raw" / "raw_extracted.json"
SCHEMES_DIR = DATA_DIR / "schemes"
SCHEMES_DIR.mkdir(parents=True, exist_ok=True)
SUMMARY_MD = DATA_DIR / "scraped_schemes_summary.md"

if not RAW_FILE.exists():
    raise FileNotFoundError(f"{RAW_FILE} does not exist.")

schemes = json.loads(RAW_FILE.read_text(encoding="utf-8"))

# 1. Generate master summary markdown
summary_lines = [
    "# Scraped Mutual Fund Schemes - Master Summary Report",
    "",
    "> **Data Source:** Official Groww scheme pages (`https://groww.in/mutual-funds/`)",
    "> **AMC:** HDFC Mutual Fund (HDFC Asset Management Company Limited)",
    f"> **Total Schemes Scraped:** {len(schemes)}",
    "",
    "---",
    "",
    "## 1. Comparative Overview Table",
    "",
    "| Scheme Name | Category | Expense Ratio | Exit Load | Min SIP | Benchmark Index | Riskometer | AUM (Fund Size) |",
    "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
]

for s in schemes:
    attrs = s["raw_attributes"]
    summary_lines.append(
        f"| **[{s['name']}](#{s['id']})** | {s['category']} | `{attrs['expense_ratio']}` | {attrs['exit_load']} | {attrs['min_sip_amount']} | {attrs['benchmark_index']} | {attrs['riskometer']} | {attrs['fund_size_aum']} |"
    )

summary_lines.extend([
    "",
    "---",
    "",
    "## 2. Detailed Scheme Breakdown",
    ""
])

for idx, s in enumerate(schemes, 1):
    attrs = s["raw_attributes"]
    scheme_md_path = f"data/schemes/{s['id']}.md"
    
    # Add to master summary
    summary_lines.extend([
        f"### <a id=\"{s['id']}\"></a>{idx}. {s['name']}",
        f"- **Official Title on Groww:** {s['official_scheme_name']}",
        f"- **Category:** {s['category']}",
        f"- **Groww Reference URL:** [{s['url']}]({s['url']})",
        f"- **Last Updated / Scraped:** {s['last_updated']}",
        "",
        "#### Key Financial Attributes:",
        f"- **Expense Ratio:** {attrs['expense_ratio']}",
        f"- **Exit Load:** {attrs['exit_load']}",
        f"- **Minimum SIP Amount:** {attrs['min_sip_amount']}",
        f"- **Minimum Lumpsum Amount:** {attrs['min_lumpsum_amount']}",
        f"- **Fund Size (AUM):** {attrs['fund_size_aum']}",
        f"- **Current NAV:** {attrs['current_nav']}",
        f"- **Benchmark Index:** {attrs['benchmark_index']}",
        f"- **Riskometer Rating:** {attrs['riskometer']}",
        f"- **Fund Manager:** {attrs['fund_manager']}",
        f"- **Lock-in Period:** {attrs['lock_in_period']}",
        f"- **Stamp Duty:** {attrs['stamp_duty']}",
        f"- **Taxation Rules:** {attrs['taxation_rules']}",
        f"- **Dedicated Scheme Doc:** [{s['id']}.md]({scheme_md_path})",
        "",
        "---",
        ""
    ])

    # 2. Write individual scheme Markdown document
    individual_lines = [
        f"# {s['name']}",
        "",
        f"- **Official Scheme Name:** {s['official_scheme_name']}",
        f"- **Fund Category:** {s['category']}",
        f"- **Groww URL:** [{s['url']}]({s['url']})",
        f"- **Scraped Date:** {s['last_updated']}",
        "",
        "## Key Statistics & Facts",
        "",
        "| Attribute | Extracted Value |",
        "| :--- | :--- |",
        f"| **Expense Ratio** | {attrs['expense_ratio']} |",
        f"| **Exit Load** | {attrs['exit_load']} |",
        f"| **Minimum SIP** | {attrs['min_sip_amount']} |",
        f"| **Minimum Lumpsum** | {attrs['min_lumpsum_amount']} |",
        f"| **Fund Size (AUM)** | {attrs['fund_size_aum']} |",
        f"| **Current NAV** | {attrs['current_nav']} |",
        f"| **Benchmark Index** | {attrs['benchmark_index']} |",
        f"| **Riskometer** | {attrs['riskometer']} |",
        f"| **Fund Manager** | {attrs['fund_manager']} |",
        f"| **Lock-in Period** | {attrs['lock_in_period']} |",
        f"| **Stamp Duty** | {attrs['stamp_duty']} |",
        f"| **Plan & Option** | {attrs['plan_type']} |",
        f"| **AMC Name** | {attrs['amc_name']} |",
        "",
        "## Taxation Policy",
        f"> {attrs['taxation_rules']}",
        "",
        "## Account Statements & Capital Gains Reports Download Guide",
        "- **Via Groww:** Navigate to `Profile` -> `Reports` -> `Mutual Fund P&L / Capital Gains Statement`.",
        "- **Via HDFC AMC Investor Portal:** Visit the HDFC Mutual Fund online investor desk and generate your Statement of Account (SOA) by entering your Folio Number and PAN.",
        "",
        "---",
        f"*Source: {s['url']} | Last updated: {s['last_updated']}*"
    ]

    (SCHEMES_DIR / f"{s['id']}.md").write_text("\n".join(individual_lines), encoding="utf-8")

SUMMARY_MD.write_text("\n".join(summary_lines), encoding="utf-8")
print(f"[SUCCESS] Generated summary at {SUMMARY_MD} and individual files in {SCHEMES_DIR}")
