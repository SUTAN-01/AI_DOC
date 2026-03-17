from __future__ import annotations

import os
import shutil
import threading
import time
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List

from fastapi import UploadFile
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.rag_store import get_vectorstore


ALLOWED_SUFFIXES = {'.txt', '.md', '.pdf'}


@dataclass
class BuildStatus:
    state: str = 'idle'  # idle, running, ok, error
    message: str = ''
    started_at: float = 0.0
    finished_at: float = 0.0
    files: int = 0
    chunks: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)


_build_lock = threading.Lock()
_status = BuildStatus()


def get_status() -> BuildStatus:
    return _status


def _set_status(**kwargs) -> None:
    for k, v in kwargs.items():
        setattr(_status, k, v)


def list_doc_files() -> List[Dict]:
    root = Path(settings.docs_dir)
    if not root.exists():
        return []
    out: List[Dict] = []
    for p in root.rglob('*'):
        if not p.is_file():
            continue
        if p.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        st = p.stat()
        out.append({
            'name': str(p.relative_to(root)).replace('\\', '/'),
            'size': st.st_size,
            'mtime': int(st.st_mtime),
        })
    out.sort(key=lambda x: x['mtime'], reverse=True)
    return out


def save_upload(file: UploadFile) -> str:
    os.makedirs(settings.docs_dir, exist_ok=True)
    filename = Path(file.filename or 'upload').name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError(f'Unsupported file type: {suffix}')

    target = Path(settings.docs_dir) / filename
    if target.exists():
        stem = target.stem
        ts = time.strftime('%Y%m%d_%H%M%S')
        target = target.with_name(f'{stem}_{ts}{suffix}')

    max_bytes = 25 * 1024 * 1024
    written = 0
    with target.open('wb') as f:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                try:
                    target.unlink(missing_ok=True)
                except Exception:
                    pass
                raise ValueError('File too large (max 25MB)')
            f.write(chunk)

    return str(target)


def _load_text_docs(docs_dir: str, glob: str):
    loader = DirectoryLoader(
        docs_dir,
        glob=glob,
        show_progress=False,
        use_multithreading=True,
        loader_cls=TextLoader,
        loader_kwargs={'encoding': 'utf-8'},
        silent_errors=True,
    )
    return loader.load()


def _load_pdfs(docs_dir: str):
    pdfs = list(Path(docs_dir).rglob('*.pdf'))
    docs = []
    for p in pdfs:
        docs.extend(PyPDFLoader(str(p)).load())
    return docs


def _reset_chroma_dir() -> None:
    p = Path(settings.chroma_dir)
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)
    p.mkdir(parents=True, exist_ok=True)


def build_vector_db() -> BuildStatus:
    if not _build_lock.acquire(blocking=False):
        raise RuntimeError('Build already running')
    try:
        _set_status(
            state='running',
            message=f'Building vector database... (docs_dir={settings.docs_dir}, chroma_dir={settings.chroma_dir})',
            started_at=time.time(),
            finished_at=0.0,
            files=0,
            chunks=0,
        )
        if not settings.openai_api_key:
            raise RuntimeError('OPENAI_API_KEY is required')
        os.makedirs(settings.docs_dir, exist_ok=True)
        _reset_chroma_dir()

        docs = []
        docs.extend(_load_text_docs(settings.docs_dir, '**/*.txt'))
        docs.extend(_load_text_docs(settings.docs_dir, '**/*.md'))
        docs.extend(_load_pdfs(settings.docs_dir))

        files = len(list_doc_files())
        if not docs:
            _set_status(state='error', message='No documents found under data/docs.', finished_at=time.time(), files=files, chunks=0)
            return _status

        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
        splits = splitter.split_documents(docs)
        vs = get_vectorstore()
        vs.add_documents(splits)
        # Chroma 0.4+ auto-persists; no need to call persist().

        _set_status(
            state='ok',
            message=f'Build complete. Files={files}, Chunks={len(splits)}. (chroma_dir={settings.chroma_dir})',
            finished_at=time.time(),
            files=files,
            chunks=len(splits),
        )
        return _status
    except Exception as e:
        traceback.print_exc()
        _set_status(state='error', message=f'Build failed: {e}', finished_at=time.time())
        return _status
    finally:
        _build_lock.release()

