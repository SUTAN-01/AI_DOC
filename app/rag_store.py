from __future__ import annotations

import os
from typing import Iterable

from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

from app.config import settings


def get_embeddings() -> OpenAIEmbeddings:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required")
    return OpenAIEmbeddings(model=settings.openai_embed_model, api_key=settings.openai_api_key)


def get_vectorstore() -> Chroma:
    os.makedirs(settings.chroma_dir, exist_ok=True)
    return Chroma(
        persist_directory=settings.chroma_dir,
        embedding_function=get_embeddings(),
        collection_name="docs",
    )


def format_docs_for_prompt(docs: Iterable) -> str:
    parts: list[str] = []
    for i, d in enumerate(docs, start=1):
        src = d.metadata.get("source", "")
        page = d.metadata.get("page", None)
        loc = f"{src}" + (f" (page {page})" if page is not None else "")
        parts.append(f"[{i}] {loc}\n{d.page_content}")
    return "\n\n".join(parts)
