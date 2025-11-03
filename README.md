# mcp-finance-tracker

构建基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 的记账服务，使用 SQLite 作为默认存储，
同时提供 Docker 镜像便于部署。服务提供两个工具：

- `list_finance_categories`：查看当前分类及描述。
- `record_bill`：记录一笔账单，金额正数表示收入，负数表示支出。

## 本地运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m finance_tracker.server
```

首次启动会自动在 `data/finance.db` 中创建数据库并写入基础分类。

## Docker 运行

```bash
docker build -t mcp-finance-tracker .
docker run --rm -v $(pwd)/data:/app/data mcp-finance-tracker
```

挂载 `data` 目录可以持久化账单数据。
