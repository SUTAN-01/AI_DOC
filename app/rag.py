from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from app.config import settings
from app.rag_store import format_docs_for_prompt, get_vectorstore


SYSTEM_PROMPT_ZH = (
    '\u4f60\u662f\u4e00\u4e2a\u57fa\u4e8e\u672c\u5730\u6587\u6863\u56de\u7b54\u95ee\u9898\u7684\u52a9\u624b\u3002\n'
    '\u8981\u6c42\uff1a\n'
    '1) \u53ea\u6839\u636e\u7ed9\u5b9a\u7684\u201c\u6587\u6863\u4e0a\u4e0b\u6587\u201d\u56de\u7b54\uff1b\u4e0d\u8981\u7f16\u9020\u3002\n'
    '2) \u5982\u679c\u4e0a\u4e0b\u6587\u4e0d\u8db3\u4ee5\u56de\u7b54\uff0c\u8bf7\u660e\u786e\u8bf4\u660e\u201c\u6587\u6863\u4e2d\u672a\u627e\u5230\u76f8\u5173\u4fe1\u606f\u201d\uff0c\u5e76\u8bf4\u660e\u8fd8\u9700\u8981\u54ea\u4e9b\u4fe1\u606f\u3002\n'
    '3) \u8f93\u51fa\u4e2d\u6587\uff0c\u5c3d\u91cf\u7b80\u6d01\u3001\u7ed3\u6784\u5316\u3002'
)


@dataclass(frozen=True)
class RAGResult:
    answer: str
    sources: list[dict]


class RAGService:
    def __init__(self):
        if not settings.openai_api_key:
            raise RuntimeError('OPENAI_API_KEY is required')
        self._vs = get_vectorstore()
        self._client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)

    def retrieve(self, query: str, k: int = 4):
        return self._vs.similarity_search(query, k=k)

    def answer(self, *, question: str, docs) -> RAGResult:
        context = format_docs_for_prompt(docs)
        user_content = (
            f'\u6587\u6863\u4e0a\u4e0b\u6587\uff1a\n{context}\n\n'
            f'\u7528\u6237\u95ee\u9898\uff1a{question}\n\n'
            f'\u8bf7\u57fa\u4e8e\u4e0a\u4e0b\u6587\u56de\u7b54\uff0c\u5e76\u7ed9\u51fa\u8981\u70b9\u603b\u7ed3\u3002'
        )
        resp = self._client.chat.completions.create(
            model=settings.openai_chat_model,
            temperature=0,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT_ZH},
                {'role': 'user', 'content': user_content},
            ],
        )
        answer = resp.choices[0].message.content or ''

        sources: list[dict] = []
        for d in docs:
            sources.append({
                'source': d.metadata.get('source', ''),
                'page': d.metadata.get('page', None),
                'snippet': (d.page_content[:200] + '...') if len(d.page_content) > 200 else d.page_content,
            })
        return RAGResult(answer=answer, sources=sources) 
