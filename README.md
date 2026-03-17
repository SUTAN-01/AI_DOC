# RAG AI (LangChain + OpenAI + MCP + FastAPI)

本项目是一个最小可用的 **Python + LangChain** RAG 示例（支持 MCP + 多用户 Web）：

- 读取 `data/docs/` 下的本地文档，构建向量数据库（Chroma 持久化）
- 用户提问时，基于相关文档内容进行总结并生成回答（OpenAI API）
- 提供 **MCP Server**（Model Context Protocol）把“文档检索”以 MCP 工具暴露出去
- 提供 **FastAPI Web 服务**：多用户注册/登录（账号密码），每个用户的对话互不干扰（按用户隔离会话与消息）

## 1) 环境准备

1. 安装 Python 3.11+（推荐 3.11/3.12）
2. 在项目根目录创建虚拟环境并安装依赖：

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

3. 配置环境变量（推荐使用 `.env`）：

```bash
copy .env.example .env
```

编辑 `.env`，至少设置：

- `OPENAI_API_KEY=...`

## 2) 放入本地文档

把你的文档放到 `data/docs/`（支持 `txt/md/pdf`）。

## 3) 构建向量库（首次或文档更新后）

```bash
python -m scripts.ingest
```

默认向量库目录：`data/chroma/`

## 4) 启动 Web 服务（多用户登录 + 提问）

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

接口概览：

- `POST /auth/register` 注册
- `POST /auth/login` 登录（返回 JWT）
- `POST /chat/ask` 提问（Authorization: Bearer <token>）
- `GET /chat/conversations` 列出当前用户会话
- `GET /chat/conversations/{conversation_id}` 获取会话消息

## 5) 启动 MCP Server（可选但本项目已实现并可被外部 MCP 客户端调用）

```bash
python -m app.mcp_server
```

MCP 工具：

- `search_docs(query: str, k: int=4)` 返回相似文档片段
- `health()` 健康检查

FastAPI 的 `/chat/ask` 默认直接走本地向量库检索；若设置 `RAG_USE_MCP=1`，则会通过 MCP client 调用上述工具完成检索。

---

提示：

- SQLite 数据库默认在 `data/app.db`。
- 账号密码使用 bcrypt 哈希存储。
