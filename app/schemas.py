from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None


class AskResponse(BaseModel):
    conversation_id: int
    answer: str
    sources: list[dict]


class ConversationItem(BaseModel):
    id: int
    title: str


class MessageItem(BaseModel):
    id: int
    role: str
    content: str
