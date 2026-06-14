import os

ROOT_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(ROOT_DIR, "rag_crawl_data")
os.makedirs(DATA_DIR, exist_ok=True)

BASE_URL = "https://fgo.wiki"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
