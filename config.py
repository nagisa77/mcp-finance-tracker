"""应用配置模块"""
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "finance_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "finance_password")
DB_NAME = os.getenv("DB_NAME", "finance_db")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4",
)

DEFAULT_CATEGORIES = [
    {"name": "餐饮", "description": "吃饭、饮品等相关花费"},
    {"name": "交通", "description": "交通出行的费用"},
    {"name": "购物", "description": "日常购物开销"},
    {"name": "收入", "description": "工资、奖金等收入"},
]
