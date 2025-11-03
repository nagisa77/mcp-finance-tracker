# 使用指南

## 快速启动

### 方式一：使用 Docker Compose（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/yourusername/mcp-finance-tracker.git
cd mcp-finance-tracker

# 2. 启动服务（会自动构建镜像和初始化数据库）
docker-compose up -d

# 3. 查看日志
docker-compose logs -f mcp_server

# 4. 停止服务
docker-compose down
```

### 方式二：本地开发

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动 MySQL（如果没有运行）
docker-compose up -d mysql

# 3. 配置环境变量（可选，默认会使用 Docker Compose 中的配置）
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=finance_user
export DB_PASSWORD=finance_password
export DB_NAME=finance_db

# 4. 运行服务
python mcp_server.py
```

## 数据库配置

默认配置：
- **主机**: `mysql`（Docker） 或 `localhost`（本地）
- **端口**: `3306`
- **数据库**: `finance_db`
- **用户名**: `finance_user`
- **密码**: `finance_password`

可以通过环境变量修改这些配置。

## MCP Tool 使用示例

### 1. 查询分类

```python
# 调用 get_categories tool
result = await get_categories()
print(result)
```

输出示例：
```
当前可用的分类列表：
1. 【餐饮】
   描述：日常用餐、外卖等餐饮消费
2. 【交通】
   描述：公交、地铁、打车、油费等交通相关费用
3. 【购物】
   描述：日常用品、服装、电子产品等购物消费
...
```

### 2. 记录账单

```python
# 记录支出
result = await record_bill(amount=100.50, category="餐饮", description="午餐")
print(result)

# 记录收入（使用负数）
result = await record_bill(amount=-5000.00, category="工资", description="本月工资")
print(result)
```

输出示例：
```
✓ 账单记录成功！
类型：支出
金额：¥100.50
分类：餐饮
描述：午餐
```

## 数据库管理

### 连接数据库

```bash
# Docker 环境
docker exec -it finance_mysql mysql -u finance_user -pfinance_password finance_db

# 本地环境
mysql -u finance_user -pfinance_password finance_db
```

### 查看账单记录

```sql
SELECT * FROM bills ORDER BY created_at DESC LIMIT 10;
```

### 查看分类列表

```sql
SELECT * FROM categories ORDER BY id;
```

### 统计数据

```sql
-- 按类型统计金额
SELECT type, SUM(amount) as total FROM bills GROUP BY type;

-- 按分类统计金额
SELECT c.name, SUM(b.amount) as total 
FROM bills b 
LEFT JOIN categories c ON b.category_id = c.id 
GROUP BY c.name 
ORDER BY total DESC;
```

## 故障排查

### 1. 数据库连接失败

```bash
# 检查 MySQL 容器是否运行
docker-compose ps

# 查看 MySQL 日志
docker-compose logs mysql

# 重启 MySQL 容器
docker-compose restart mysql
```

### 2. MCP 服务无法启动

```bash
# 查看服务日志
docker-compose logs mcp_server

# 检查依赖是否正确安装
docker-compose exec mcp_server pip list
```

### 3. 数据库表不存在

```bash
# 重新初始化数据库（会清空数据）
docker-compose down -v
docker-compose up -d
```

## 开发和测试

### 运行测试

```bash
# 进入容器
docker-compose exec mcp_server bash

# 在容器内运行 Python
python
```

```python
# 在 Python 交互环境中测试
from database import DatabaseManager

db = DatabaseManager()
db.connect()

# 测试查询分类
categories = db.get_categories()
print(categories)

# 测试添加账单
db.add_bill(100.0, 'expense', 1, '测试')
```

## 部署到生产环境

### 安全配置

1. **修改默认密码**：在 `docker-compose.yml` 中修改 MySQL 密码
2. **使用环境变量**：将敏感信息从环境变量读取
3. **添加 SSL**：为 MySQL 连接启用 SSL
4. **定期备份**：设置数据库自动备份

### 性能优化

1. **连接池**：配置 MySQL 连接池
2. **索引优化**：为常用查询字段添加索引
3. **缓存**：添加 Redis 缓存层
4. **负载均衡**：部署多个实例并使用负载均衡器

