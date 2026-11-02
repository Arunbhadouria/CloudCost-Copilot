"""Configuration settings for CloudCost Copilot backend."""
import os
from pathlib import Path
from pydantic import BaseModel


def _load_env_file(dotenv_path: Path) -> None:
    """Simple .env reader without extra dependencies."""
    if not dotenv_path.is_file():
        return
    with open(dotenv_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            if k not in os.environ:
                os.environ[k] = v


BASE_DIR = Path(__file__).resolve().parent.parent.parent
_load_env_file(BASE_DIR / ".env")


class Settings(BaseModel):
    """Application settings loaded from environment."""
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./cloudcost.db")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    LLM_MODE: str = os.getenv("LLM_MODE", "mock")  # 'mock' or 'live'
    DEFAULT_SEED: int = int(os.getenv("DEFAULT_SEED", "1"))

    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    REFERENCE_DIR: Path = BASE_DIR / "data" / "reference"
    RAW_DIR: Path = BASE_DIR / "data" / "raw"


settings = Settings()
