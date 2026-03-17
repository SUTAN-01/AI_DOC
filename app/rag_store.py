from __future__ import annotations

import os
from typing import Iterable

from chromadb.config import Settings as ChromaClientSettings
from langchain_community.vectorstores import Chroma
from langchain_core.embeddings import Embeddings
from openai import OpenAI

from app.config import settings


class OpenAICompatEmbeddings(Embeddings):
    def __init__(self):
        if not settings.openai_api_key:
            raise RuntimeError('OPENAI_API_KEY is required')
        self._client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        self._model = settings.openai_embed_model

    def embed_documents(self, texts):
        if not texts:
            return []
        resp = self._client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in resp.data]

    def embed_query(self, text):
        resp = self._client.embeddings.create(model=self._model, input=[text])
        return resp.data[0].embedding


def get_embeddings():
    return OpenAICompatEmbeddings()


def _client_settings():
    return ChromaClientSettings(anonymized_telemetry=False)


def get_vectorstore():
    os.makedirs(settings.chroma_dir, exist_ok=True)
    try:
        return Chroma(persist_directory=settings.chroma_dir, embedding_function=get_embeddings(), collection_name='docs', client_settings=_client_settings())
    except KeyError as e:
        if e.args and e.args[0] == '_type':
            raise RuntimeError('Chroma persistence format mismatch. Delete data/chroma and re-run: python -m scripts.ingest') from e
        raise


def format_docs_for_prompt(docs: Iterable):
    parts = []
    for i, d in enumerate(docs, start=1):
        src = d.metadata.get('source', '')
        page = d.metadata.get('page', None)
        page_str = f' (page {page})' if page is not None else ''
        loc = f'{src}{page_str}'
        parts.append(f'[{i}] {loc}\\n{d.page_content}')
    return '\\n\\n'.join(parts)
