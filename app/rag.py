from __future__ import annotations

from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.rag_store import format_docs_for_prompt, get_vectorstore


SYSTEM_PROMPT_ZH = """你是一个基于本地文档回答问题的助手。
要求：
1) 只根据给定的“文档上下文”回答；不要编造。
2) 如果上下文不足以回答，请明确说明“文档中未找到相关信息”，并给出你需要哪些信息才能继续。
3) 输出中文，尽量简洁、结构化。"""


@dataclass(frozen=True)
class RAGResult:
    answer: str
    sources: list[dict]


class RAGService:
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        self._vs = get_vectorstore()
        self._llm = ChatOpenAI(model=settings.openai_chat_model, api_key=settings.openai_api_key, temperature=0)

    def retrieve(self, query: str, k: int = 4):
        return self._vs.similarity_search(query, k=k)

    def answer(self, *, question: str, docs) -> RAGResult:
        context = format_docs_for_prompt(docs)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT_ZH),
            HumanMessage(
                content=f"文档上下文：\n{context}\n\n用户问题：{question}\n\n请基于上下文回答，并给出要点总结。"
            ),
        ]
        resp = self._llm.invoke(messages)
        sources: list[dict] = []
        for d in docs:
            sources.append(
                {
                    "source": d.metadata.get("source", ""),
                    "page": d.metadata.get("page", None),
                    "snippet": (d.page_content[:200] + "...") if len(d.page_content) > 200 else d.page_content,
                }
            )
        return RAGResult(answer=str(resp.content), sources=sources)
