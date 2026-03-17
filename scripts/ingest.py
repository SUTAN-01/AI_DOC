from __future__ import annotations

import os
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.rag_store import get_vectorstore


def _build_loader(docs_dir: str) -> DirectoryLoader:
    # Load txt/md as text; pdf via PyPDFLoader
    # DirectoryLoader can accept a loader_cls, but for multiple patterns we compose loaders.
    return DirectoryLoader(
        docs_dir,
        glob="**/*",
        show_progress=True,
        use_multithreading=True,
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        silent_errors=True,
    )


def _load_pdfs(docs_dir: str):
    pdfs = list(Path(docs_dir).rglob("*.pdf"))
    docs = []
    for p in pdfs:
        loader = PyPDFLoader(str(p))
        docs.extend(loader.load())
    return docs


def main() -> None:
    os.makedirs(settings.docs_dir, exist_ok=True)
    os.makedirs(settings.chroma_dir, exist_ok=True)
    print(f"docs_dir={settings.docs_dir}")
    print(f"chroma_dir={settings.chroma_dir}")

    loader = _build_loader(settings.docs_dir)
    docs = loader.load()
    docs.extend(_load_pdfs(settings.docs_dir))

    if not docs:
        print(f"No documents found under: {settings.docs_dir}")
        return

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    splits = splitter.split_documents(docs)

    vs = get_vectorstore()
    vs.add_documents(splits)
    # Chroma 0.4+ auto-persists; no need to call persist().

    print(f"Ingested {len(splits)} chunks into: {settings.chroma_dir}")


if __name__ == "__main__":
    main()

