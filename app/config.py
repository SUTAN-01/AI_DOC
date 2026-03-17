from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"

    jwt_secret: str = "change-me-in-prod"
    jwt_expire_minutes: int = 60 * 24

    docs_dir: str = "data/docs"
    chroma_dir: str = "data/chroma"
    sqlite_path: str = "data/app.db"

    rag_use_mcp: bool = False
    mcp_server_cmd: str = "python -m app.mcp_server"


settings = Settings()
