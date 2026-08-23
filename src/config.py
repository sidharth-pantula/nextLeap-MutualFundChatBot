import os
from pathlib import Path
from dotenv import load_dotenv

# Project Root Directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)

# Data Directories
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
CHROMA_DB_DIR = DATA_DIR / "chromadb"

# Ensure directories exist
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)

# The 5 Target Groww Mutual Fund Schemes (Strict Corpus Definition)
GROWW_SCHEMES = [
    {
        "id": "hdfc-mid-cap-fund",
        "name": "HDFC Mid-Cap Opportunities Fund",
        "category": "Mid Cap Fund",
        "url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        "search_aliases": ["hdfc mid cap", "hdfc midcap", "mid cap", "midcap opportunities"]
    },
    {
        "id": "hdfc-small-cap-fund",
        "name": "HDFC Small Cap Fund",
        "category": "Small Cap Fund",
        "url": "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
        "search_aliases": ["hdfc small cap", "hdfc smallcap", "small cap", "smallcap"]
    },
    {
        "id": "hdfc-nifty-50-index-fund",
        "name": "HDFC Nifty 50 Index Fund",
        "category": "Index Fund (Large Cap)",
        "url": "https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth",
        "search_aliases": ["hdfc nifty 50", "nifty 50 index", "nifty 50", "hdfc nifty index"]
    },
    {
        "id": "hdfc-nifty-next-50-index-fund",
        "name": "HDFC Nifty Next 50 Index Fund",
        "category": "Index Fund (Next 50)",
        "url": "https://groww.in/mutual-funds/hdfc-nifty-next-50-index-fund-direct-growth",
        "search_aliases": ["hdfc nifty next 50", "nifty next 50", "next 50", "junior nifty"]
    },
    {
        "id": "hdfc-multi-cap-fund",
        "name": "HDFC Multi Cap Fund",
        "category": "Multi Cap Fund",
        "url": "https://groww.in/mutual-funds/hdfc-multi-cap-fund-direct-growth",
        "search_aliases": ["hdfc multi cap", "hdfc multicap", "multi cap", "multicap"]
    }
]

# Educational & Regulatory Refusal Links
SEBI_INVESTOR_URL = "https://investor.sebi.gov.in/"
AMFI_INVESTOR_URL = "https://www.amfiindia.com/investor-corner/knowledge-center/what-are-mutual-funds.html"

# Compliance & Format Contracts
DISCLAIMER_TEXT = "Facts-only. No investment advice."
MAX_SENTENCE_LIMIT = 3

# Groq LLM Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TEMPERATURE = 0.0

# BGE Embedding Model Configuration
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"

# Server Host & Port
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", 8000))
