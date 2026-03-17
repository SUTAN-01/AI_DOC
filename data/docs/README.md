# 示例文档

把你的本地文档放到 `data/docs/`，例如：

- `产品说明.md`
- `技术方案.txt`
- `合同.pdf`

然后运行：

```bash
python -m scripts.ingest
```

接着启动服务并提问，模型将基于检索到的文档片段进行总结与回答。
