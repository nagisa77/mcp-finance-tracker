"""数据库配置模块"""
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'finance_user'),
    'password': os.getenv('DB_PASSWORD', 'finance_password'),
    'database': os.getenv('DB_NAME', 'finance_db'),
    'charset': 'utf8mb4'
}

