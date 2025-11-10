from __future__ import annotations
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

def _find_env_file() -> Optional[str]:
    """
    Find backend/.env robustly:
    - FINTRID_ENV_PATH (explicit override) wins
    - CWD/.env or CWD/backend/.env
    - Paths relative to this file, so it works from site-packages too
    """
    override = os.getenv("FINTRID_ENV_PATH")
    if override and Path(override).is_file():
        return override

    cwd = Path.cwd()
    candidates = [
        cwd / ".env",
        cwd / "backend" / ".env",
    ]
    here = Path(__file__).resolve()
    candidates += [
        here.parent.parent.parent / ".env",        # .../backend/.env (dev layout)
        here.parent.parent.parent.parent / ".env", # project root .env (just in case)
    ]
    for p in candidates:
        if p.is_file():
            return str(p)
    return None  # fall back to pure environment variables

class Settings(BaseSettings):
    # ← Feel free to add more here (e.g., DATABASE_URL)
    landingai_api_key: Optional[str] = None
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()