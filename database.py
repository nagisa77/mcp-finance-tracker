"""数据库操作模块"""
import pymysql
from config import DB_CONFIG
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        self.connection = None
    
    def connect(self):
        """建立数据库连接"""
        try:
            self.connection = pymysql.connect(**DB_CONFIG)
            logger.info("数据库连接成功")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise
    
    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            logger.info("数据库连接已关闭")
    
    def get_categories(self) -> List[Dict[str, str]]:
        """获取所有分类"""
        if not self.connection:
            self.connect()
        
        try:
            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("SELECT id, name, description FROM categories ORDER BY id")
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"获取分类失败: {e}")
            raise
    
    def add_bill(self, amount: float, bill_type: str, category_id: Optional[int], 
                 description: Optional[str]) -> bool:
        """添加账单"""
        if not self.connection:
            self.connect()
        
        try:
            with self.connection.cursor() as cursor:
                sql = """
                    INSERT INTO bills (amount, type, category_id, description)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(sql, (amount, bill_type, category_id, description))
                self.connection.commit()
                logger.info(f"账单添加成功: {amount} {bill_type}")
                return True
        except Exception as e:
            logger.error(f"添加账单失败: {e}")
            self.connection.rollback()
            raise
    
    def get_category_by_name(self, name: str) -> Optional[Dict[str, str]]:
        """根据名称获取分类"""
        if not self.connection:
            self.connect()
        
        try:
            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("SELECT id, name, description FROM categories WHERE name = %s", (name,))
                return cursor.fetchone()
        except Exception as e:
            logger.error(f"获取分类失败: {e}")
            raise

