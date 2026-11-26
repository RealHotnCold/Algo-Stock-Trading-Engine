import os
from dotenv import load_dotenv
load_dotenv()

def _b(k, d): return os.getenv(k, str(d)).strip().lower() in ("1", "true", "yes")

MT5_LOGIN = int(os.getenv("MT5_LOGIN") or 0) or None
MT5_PASSWORD = os.getenv("MT5_PASSWORD") or None
MT5_SERVER = os.getenv("MT5_SERVER") or None
MT5_PATH = os.getenv("MT5_PATH") or None
DEMO_ONLY = _b("DEMO_ONLY", True)
ALLOW_REAL_TRADING = _b("ALLOW_REAL_TRADING", False)
DB_URL = os.getenv("DB_URL", "sqlite:///./data/app.db")
