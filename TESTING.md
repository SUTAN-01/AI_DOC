# 手动测试（Windows / curl）

## 1) 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 2) 注册

```bash
curl -X POST http://127.0.0.1:8000/auth/register ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"alice\",\"password\":\"alice123456\"}"
```

## 3) 登录获取 Token

```bash
curl -X POST http://127.0.0.1:8000/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"alice\",\"password\":\"alice123456\"}"
```

返回示例（取出 `access_token`）：

```json
{"access_token":"...","token_type":"bearer"}
```

## 4) 提问（RAG）

把 `<TOKEN>` 替换成上一步的 `access_token`：

```bash
curl -X POST http://127.0.0.1:8000/chat/ask ^
  -H "Content-Type: application/json" ^
  -H "Authorization: Bearer <TOKEN>" ^
  -d "{\"question\":\"请总结 data/docs 下文档的主要内容\"}"
```

## 5) 多用户隔离验证

再注册/登录一个用户 `bob`，用 bob 的 token 调用 `/chat/conversations`，看不到 alice 的会话。

```bash
curl -X GET http://127.0.0.1:8000/chat/conversations ^
  -H "Authorization: Bearer <BOB_TOKEN>"
```
