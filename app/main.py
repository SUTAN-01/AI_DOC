from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api_deps import get_current_user, get_db
from app.config import settings
from app.db import Conversation, Message, User, init_db
from app.docs_routes import router as docs_router
from app.mcp_client import search_docs as mcp_search_docs
from app.rag import RAGService
from app.rag_store import get_vectorstore
from app.schemas import AskRequest, AskResponse, ConversationItem, LoginRequest, MessageItem, RegisterRequest, TokenResponse
from app.security import create_access_token, hash_password, verify_password


_BASE_DIR = Path(__file__).resolve().parents[1]

app = FastAPI(title='RAG AI')
app.include_router(docs_router)

templates = Jinja2Templates(directory=str(_BASE_DIR / 'web' / 'templates'))
static_dir = _BASE_DIR / 'web' / 'static'
if static_dir.is_dir():
    app.mount('/static', StaticFiles(directory=str(static_dir)), name='static')


@app.on_event('startup')
def _startup():
    init_db()
    os.makedirs(settings.chroma_dir, exist_ok=True)


@app.get('/health')
def health():
    return {'ok': True}


@app.get('/', include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})


@app.get('/login', include_in_schema=False)
def login_page(request: Request):
    return templates.TemplateResponse('login.html', {'request': request})


@app.get('/register', include_in_schema=False)
def register_page(request: Request):
    return templates.TemplateResponse('register.html', {'request': request})


@app.get('/chat', include_in_schema=False)
def chat_page(request: Request):
    return templates.TemplateResponse('chat.html', {'request': request})


@app.get('/ui', include_in_schema=False)
def ui_redirect():
    return RedirectResponse(url='/chat')


@app.post('/auth/register')
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail='Username already exists')
    user = User(username=payload.username, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    return {'ok': True}


@app.post('/auth/login', response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail='Invalid credentials')
    token = create_access_token(subject=user.username)
    return TokenResponse(access_token=token)


@app.get('/chat/conversations', response_model=list[ConversationItem])
def list_conversations(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Conversation).where(Conversation.user_id == current.id).order_by(Conversation.id.desc())).scalars()
    return [ConversationItem(id=c.id, title=c.title) for c in rows]


@app.get('/chat/conversations/{conversation_id}', response_model=list[MessageItem])
def get_conversation_messages(conversation_id: int, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = db.execute(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == current.id)).scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail='Conversation not found')
    msgs = db.execute(select(Message).where(Message.conversation_id == conv.id).order_by(Message.id.asc())).scalars()
    return [MessageItem(id=m.id, role=m.role, content=m.content) for m in msgs]


def _vectorstore_count(vs) -> int | None:
    try:
        return int(vs._collection.count())
    except Exception:
        return None


def _ensure_vectorstore_ready() -> int | None:
    try:
        vs = get_vectorstore()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return _vectorstore_count(vs)


@app.post('/chat/ask', response_model=AskResponse)
def ask(payload: AskRequest, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.conversation_id is None:
        conv = Conversation(user_id=current.id, title=payload.question[:50])
        db.add(conv)
        db.commit()
        db.refresh(conv)
    else:
        conv = db.execute(select(Conversation).where(Conversation.id == payload.conversation_id, Conversation.user_id == current.id)).scalar_one_or_none()
        if conv is None:
            raise HTTPException(status_code=404, detail='Conversation not found')

    db.add(Message(conversation_id=conv.id, role='user', content=payload.question))
    db.commit()

    count = _ensure_vectorstore_ready()
    if count == 0:
        answer = (
            '\u5411\u91cf\u5e93\u4e3a\u7a7a\uff08\u8fd8\u6ca1\u6709\u6784\u5efa/\u6784\u5efa\u5931\u8d25\uff09\uff0c\u56e0\u6b64\u65e0\u6cd5\u4ece\u6587\u6863\u4e2d\u68c0\u7d22\u5230\u4e0a\u4e0b\u6587\u3002\n'
            '\u8bf7\u5148\u5728\u9875\u9762\u91cc\u4e0a\u4f20\u6587\u6863\u540e\u70b9\u51fb\u201c\u6784\u5efa\u5411\u91cf\u5e93\u201d\uff0c\u6216\u8fd0\u884c\uff1apython -m scripts.ingest\u3002\n'
            '\u6784\u5efa\u6210\u529f\u540e\uff0c\u76ee\u5f55 data/chroma \u4e0b\u5e94\u8be5\u51fa\u73b0 chroma.sqlite3 \u7b49\u6587\u4ef6\u3002'
        )
        db.add(Message(conversation_id=conv.id, role='assistant', content=answer))
        db.commit()
        return AskResponse(conversation_id=conv.id, answer=answer, sources=[])

    rag = RAGService()
    if settings.rag_use_mcp:
        mcp_docs = mcp_search_docs(payload.question, k=4)

        class _Doc:
            def __init__(self, content, metadata):
                self.page_content = content
                self.metadata = metadata

        docs = [_Doc(d.content, d.metadata) for d in mcp_docs]
    else:
        docs = rag.retrieve(payload.question, k=4)

    if not docs:
        answer = (
            '\u672c\u6b21\u68c0\u7d22\u6ca1\u6709\u8fd4\u56de\u4efb\u4f55\u6587\u6863\u7247\u6bb5\uff0c\u6240\u4ee5\u65e0\u6cd5\u57fa\u4e8e\u6587\u6863\u56de\u7b54\u3002\n'
            '\u4f60\u53ef\u4ee5\u5c1d\u8bd5\uff1a\u6362\u5173\u952e\u8bcd/\u66f4\u5177\u4f53\u7684\u95ee\u9898\uff1b\u6216\u786e\u8ba4\u5df2\u6784\u5efa\u5411\u91cf\u5e93\u4e14 data/chroma \u76ee\u5f55\u975e\u7a7a\u3002'
        )
        db.add(Message(conversation_id=conv.id, role='assistant', content=answer))
        db.commit()
        return AskResponse(conversation_id=conv.id, answer=answer, sources=[])

    result = rag.answer(question=payload.question, docs=docs)

    db.add(Message(conversation_id=conv.id, role='assistant', content=result.answer))
    db.commit()

    return AskResponse(conversation_id=conv.id, answer=result.answer, sources=result.sources)
