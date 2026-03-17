from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api_deps import get_current_user, get_db
from app.config import settings
from app.db import Conversation, Message, User, init_db
from app.mcp_client import search_docs as mcp_search_docs
from app.rag import RAGService
from app.rag_store import get_vectorstore
from app.schemas import AskRequest, AskResponse, ConversationItem, LoginRequest, MessageItem, RegisterRequest, TokenResponse
from app.security import create_access_token, hash_password, verify_password


app = FastAPI(title='RAG AI')
templates = Jinja2Templates(directory='web/templates')
if os.path.isdir('web/static'):
    app.mount('/static', StaticFiles(directory='web/static'), name='static')


@app.on_event('startup')
def _startup():
    os.makedirs('data', exist_ok=True)
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

def _ensure_vectorstore_ready():
    try:
        vs = get_vectorstore()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    try:
        _ = vs._collection.count()
    except Exception:
        pass

@app.post('/chat/ask', response_model=AskResponse)
def ask(payload: AskRequest, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_vectorstore_ready()

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

    result = rag.answer(question=payload.question, docs=docs)

    db.add(Message(conversation_id=conv.id, role='assistant', content=result.answer))
    db.commit()

    return AskResponse(conversation_id=conv.id, answer=result.answer, sources=result.sources)
