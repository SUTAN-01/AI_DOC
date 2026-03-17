from __future__ import annotations

import shlex
from dataclasses import dataclass

import anyio

from app.config import settings

try:
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
except Exception as e:  # pragma: no cover
    raise RuntimeError("MCP SDK not available. Please install requirements.txt (mcp).") from e


@dataclass(frozen=True)
class MCPDoc:
    content: str
    metadata: dict


async def _search_docs_async(query: str, k: int) -> list[MCPDoc]:
    # Spawn MCP server via stdio (per-call; simplest and robust for Windows)
    cmd = shlex.split(settings.mcp_server_cmd)
    async with stdio_client(cmd) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("search_docs", {"query": query, "k": k})
            items = result.content  # list of {content, metadata}
            docs: list[MCPDoc] = []
            for it in items:
                docs.append(MCPDoc(content=it.get("content", ""), metadata=it.get("metadata", {})))
            return docs


def search_docs(query: str, k: int = 4) -> list[MCPDoc]:
    return anyio.run(_search_docs_async, query, k)
