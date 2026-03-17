from __future__ import annotations

from app.rag_store import get_vectorstore

try:
    from mcp.server.fastmcp import FastMCP
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "MCP SDK not available. Please install requirements.txt (mcp)."
    ) from e


mcp = FastMCP("rag-docs")


@mcp.tool()
def health() -> dict:
    return {"ok": True}


@mcp.tool()
def search_docs(query: str, k: int = 4) -> list[dict]:
    vs = get_vectorstore()
    docs = vs.similarity_search(query, k=k)
    out: list[dict] = []
    for d in docs:
        out.append(
            {
                "content": d.page_content,
                "metadata": d.metadata,
            }
        )
    return out


def main() -> None:
    # stdio transport by default in most MCP runtimes
    mcp.run()


if __name__ == "__main__":
    main()
