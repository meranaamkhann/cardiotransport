import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = 20260904
MODEL_VERSION = "1.0.0"


class Settings:
    def __init__(self):
        env = os.environ.get
        self.environment = env("CARDIOLENS_ENV", "development")
        self.database_url = env("DATABASE_URL", f"sqlite:///{ROOT / 'cardiolens.db'}")
        self.secret_key = env("SECRET_KEY", "")
        if not self.secret_key:
            if self.environment == "production":
                raise RuntimeError("SECRET_KEY must be set in production")
            self.secret_key = "development-only-secret-key-change-me"
        self.fernet_key = env("FERNET_KEY", "")
        self.token_minutes = int(env("ACCESS_TOKEN_MINUTES", "60"))
        self.data_dir = Path(env("CARDIOLENS_DATA", ROOT / "data" / "raw"))
        self.artifact_dir = Path(env("CARDIOLENS_ARTIFACTS", ROOT / "artifacts"))
        self.upload_dir = Path(env("CARDIOLENS_UPLOADS", ROOT / "uploads"))
        self.static_dir = Path(env("CARDIOLENS_STATIC", ROOT.parent / "frontend" / "dist"))
        self.cors_origins = [o for o in env("CORS_ORIGINS", "http://localhost:5173").split(",") if o]
        self.rate_limit_enabled = env("RATE_LIMIT_ENABLED", "1") == "1"
        self.trust_proxy = env("TRUST_PROXY", "0") == "1"
        self.max_upload_mb = int(env("MAX_UPLOAD_MB", "10"))
        self.log_level = env("LOG_LEVEL", "INFO")

    @property
    def is_sqlite(self):
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


_settings = get_settings()
DATA_DIR = _settings.data_dir
ARTIFACT_DIR = _settings.artifact_dir
STATIC_DIR = _settings.static_dir
