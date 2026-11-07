import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("CARDIOLENS_DATA", ROOT / "data" / "raw"))
ARTIFACT_DIR = Path(os.environ.get("CARDIOLENS_ARTIFACTS", ROOT / "artifacts"))
STATIC_DIR = Path(os.environ.get("CARDIOLENS_STATIC", ROOT.parent / "frontend" / "dist"))
SEED = 20260904
MODEL_VERSION = "1.0.0"
import secrets

DATABASE_URL = os.environ.get("CARDIOLENS_DB", f"sqlite:///{ROOT / 'cardiolens.db'}")
SECRET_KEY = os.environ.get("CARDIOLENS_SECRET") or secrets.token_urlsafe(48)
TOKEN_MINUTES = int(os.environ.get("CARDIOLENS_TOKEN_MINUTES", "60"))
