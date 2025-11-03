# mcp-finance-tracker

Builds a universal accounting interface and abstraction layer, leveraging MySQL as the underlying data store to standardize accounting logic. 构建通用的记账接口与封装层，以 MySQL 作为底层数据存储，实现标准化的记账逻辑。

## 项目简介

该项目实现了一个基于 [Model Context Protocol (MCP)](https://spec.modelcontextprotocol.io/) 的记账工具服务。服务使用 Python 编写，通过 MySQL 存储分类信息和账单记录，并提供 Docker 化部署方式，方便本地或生产环境运行。

### 功能特性

- **分类管理**：存储账单分类及描述。
- **账单记录**：记录收入或支出金额、所属分类以及描述信息。
- **MCP 工具**：提供 `list_category_tool` 与 `record_transaction_tool` 两个工具，分别用于查询分类信息和记录账单。
- **数据库自动初始化**：服务启动时自动创建数据库及所需数据表。

## 快速开始

### 环境要求

- Docker 与 Docker Compose

### 启动服务

```bash
docker-compose up --build
```

Compose 会启动两个服务：

- `mysql`：MySQL 8.0 数据库服务，预设数据库名称 `finance_tracker`。
- `app`：Python 实现的 MCP 服务，依赖 `mysql` 服务，并在启动时自动执行数据库初始化逻辑。

### 环境变量

可以通过以下环境变量调整数据库连接配置：

- `DB_HOST`（默认：`mysql`）
- `DB_PORT`（默认：`3306`）
- `DB_USER`（默认：`finance`）
- `DB_PASSWORD`（默认：`financepass`）
- `DB_NAME`（默认：`finance_tracker`）

### MCP 工具说明

服务启动后，可在 MCP 兼容客户端中注册 `finance_tracker` 服务对应的工具。

#### `list_category_tool`

- **作用**：返回当前所有分类及描述。
- **返回值**：列表，每项包含 `id`、`name`、`description`。

#### `record_transaction_tool`

- **作用**：记录一笔账单。
- **参数**：
  - `amount` *(字符串)*：金额，正数表示收入，负数表示支出。
  - `category_name` *(字符串)*：账单分类名称。
  - `description` *(可选字符串)*：账单描述。
  - `create_category_if_missing` *(布尔，可选)*：若分类不存在则自动创建，默认 `False`。
- **返回值**：账单详情，包括所属分类信息。

### 数据库结构

- `categories`：存储分类名称与描述。
- `transactions`：存储账单金额、分类、描述及创建时间。

## 开发与调试

如果希望在本地直接运行 MCP 服务，可先安装依赖：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DB_HOST=127.0.0.1
export DB_USER=finance
export DB_PASSWORD=financepass
export DB_NAME=finance_tracker
python -m finance_tracker
```

确保本地 MySQL 实例已启动且对应数据库、用户配置正确。
