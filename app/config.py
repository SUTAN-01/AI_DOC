from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    openai_api_key: str = ''
    # OpenAI-compatible endpoints can be configured here (e.g. https://api.gptsapi.net/v1).
    openai_base_url: str = 'https://api.gptsapi.net/v1'
    openai_chat_model: str = 'gpt-4o-mini'
    openai_embed_model: str = 'text-embedding-3-small'

    jwt_secret: str = 'change-me-in-prod'
    jwt_expire_minutes: int = 60 * 24

    docs_dir: str = 'data/docs'
    chroma_dir: str = 'data/chroma'
    sqlite_path: str = 'data/app.db'

    rag_use_mcp: bool = False
    mcp_server_cmd: str = 'python -m app.mcp_server'


settings = Settings()

_BASE_DIR = Path(__file__).resolve().parents[1]


def _abs_path(p: str) -> str:
    pp = Path(p)
    if pp.is_absolute():
        return str(pp)
    return str((_BASE_DIR / pp).resolve())


# Make path settings stable regardless of the process working directory.
settings.docs_dir = _abs_path(settings.docs_dir)
settings.chroma_dir = _abs_path(settings.chroma_dir)
settings.sqlite_path = _abs_path(settings.sqlite_path)
