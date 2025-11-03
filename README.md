# mcp-finance-tracker

一个基于 MCP (Model Context Protocol) 的记账服务，使用 Python 和 MySQL 实现，支持通过 Docker 容器化部署。

## 功能特性

- ✅ 基于 **FastMCP** 框架实现 MCP 服务端
- ✅ 使用 **MySQL** 作为数据存储
- ✅ 支持 **Docker** 和 **docker-compose** 一键部署
- ✅ 自动初始化数据库表结构和默认分类
- ✅ 提供两个核心 MCP Tool：
  1. `get_categories` - 查询所有分类及其描述
  2. `record_bill` - 记录账单（支持收入和支出）

## 数据库设计

### 分类表 (categories)
- `id`: 主键
- `name`: 分类名称（唯一）
- `description`: 分类描述

### 账单表 (bills)
- `id`: 主键
- `amount`: 金额
- `type`: 类型（income/expense）
- `category_id`: 分类ID（外键）
- `description`: 描述

## 快速开始

### 前置要求

- Docker 和 Docker Compose
- Python 3.11+（本地开发时）

### 使用 Docker Compose 部署（推荐）

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/mcp-finance-tracker.git
cd mcp-finance-tracker
```

2. 启动服务：
```bash
docker-compose up -d
```

3. 查看日志：
```bash
docker-compose logs -f mcp_server
```

### 本地开发

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 配置环境变量：
```bash
cp .env.example .env
# 编辑 .env 文件配置数据库连接信息
```

3. 启动 MySQL（如果本地没有）：
```bash
docker-compose up -d mysql
```

4. 运行服务：
```bash
python mcp_server.py
```

## 使用 MCP Tool

### 1. 查询分类

调用 `get_categories` 工具获取所有可用分类：

```python
await get_categories()
```

返回结果：
```
当前可用的分类列表：
1. 【餐饮】
   描述：日常用餐、外卖等餐饮消费
2. 【交通】
   描述：公交、地铁、打车、油费等交通相关费用
...
```

### 2. 记录账单

调用 `record_bill` 工具记录账单：

```python
# 记录支出
await record_bill(amount=100.50, category="餐饮", description="午餐")

# 记录收入
await record_bill(amount=-5000.00, category="工资", description="本月工资")
```

- `amount`: 金额（正数表示支出，负数表示收入）
- `category`: 分类名称（可选）
- `description`: 账单描述（可选）

## 项目结构

```
mcp-finance-tracker/
├── mcp_server.py          # MCP 服务端主程序
├── crud.py                # 数据库 CRUD 操作
├── schemas.py             # Pydantic 数据模型
├── models.py              # SQLAlchemy 数据模型
├── database.py            # 数据库会话管理模块
├── config.py              # 配置文件
├── requirements.txt       # Python 依赖
├── Dockerfile             # Docker 镜像定义
├── docker-compose.yml     # Docker Compose 配置
├── .env.example           # 环境变量示例
├── .gitignore            # Git 忽略文件
└── README.md             # 项目说明
```

系统启动时会自动创建数据库表并填充默认分类（餐饮、交通、购物、收入），无需手动执行 SQL 脚本。

## 配置说明

环境变量配置（通过 `.env` 文件或 docker-compose 环境变量）：

- `DB_HOST`: 数据库主机地址
- `DB_PORT`: 数据库端口
- `DB_USER`: 数据库用户名
- `DB_PASSWORD`: 数据库密码
- `DB_NAME`: 数据库名称

## 技术栈

- **MCP**: 官方 MCP 框架 (mcp>=1.19.0)
- **SQLAlchemy**: ORM 与表结构管理
- **Pydantic**: 数据验证
- **PyMySQL**: MySQL 数据库驱动
- **Docker**: 容器化部署

## 许可证

MIT License 
