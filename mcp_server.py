"""记账 MCP 服务端"""
import asyncio
import logging
from fastmcp import FastMCP
from database import DatabaseManager
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建 MCP 服务器实例
mcp = FastMCP("记账服务")

# 初始化数据库管理器
db_manager = DatabaseManager()


class BillInput(BaseModel):
    """账单输入模型"""
    amount: float = Field(..., description="金额，正数表示支出，负数表示收入")
    category: Optional[str] = Field(None, description="分类名称")
    description: Optional[str] = Field(None, description="账单描述")


@mcp.tool()
async def get_categories() -> str:
    """获取当前所有分类及其描述
    
    这个工具会返回系统中所有的记账分类列表，包括分类的名称和描述，
    帮助用户了解可以使用的分类选项。
    
    Returns:
        str: 分类列表的格式化字符串
    """
    try:
        categories = db_manager.get_categories()
        if not categories:
            return "当前没有分类，请先添加分类。"
        
        result = "当前可用的分类列表：\n"
        for idx, cat in enumerate(categories, 1):
            result += f"{idx}. 【{cat['name']}】\n"
            if cat['description']:
                result += f"   描述：{cat['description']}\n"
        return result
    except Exception as e:
        logger.error(f"获取分类失败: {e}")
        return f"获取分类失败：{str(e)}"


@mcp.tool()
async def record_bill(amount: float, category: Optional[str] = None, 
                      description: Optional[str] = None) -> str:
    """记录一笔账单
    
    用于记录收入或支出的账单。金额为正数表示支出，负数表示收入。
    可以选择性地指定分类和描述信息。
    
    Args:
        amount: 金额（正数=支出，负数=收入）
        category: 分类名称（可选）
        description: 账单描述（可选）
        
    Returns:
        str: 操作结果信息
    """
    try:
        # 确定账单类型
        bill_type = 'expense' if amount >= 0 else 'income'
        abs_amount = abs(amount)
        
        # 处理分类
        category_id = None
        if category:
            cat_info = db_manager.get_category_by_name(category)
            if cat_info:
                category_id = cat_info['id']
                category_display = category
            else:
                # 分类不存在，但仍然记录账单
                category_display = f"未知分类: {category}"
        else:
            category_display = "未分类"
        
        # 添加账单
        db_manager.add_bill(abs_amount, bill_type, category_id, description)
        
        # 返回结果
        type_text = "支出" if bill_type == 'expense' else "收入"
        result = f"✓ 账单记录成功！\n"
        result += f"类型：{type_text}\n"
        result += f"金额：¥{abs_amount:.2f}\n"
        result += f"分类：{category_display}\n"
        if description:
            result += f"描述：{description}\n"
        
        return result
    except Exception as e:
        logger.error(f"记录账单失败: {e}")
        return f"记录账单失败：{str(e)}"


def main():
    """主函数"""
    try:
        db_manager.connect()
        logger.info("记账 MCP 服务启动成功")
        mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭服务...")
    except Exception as e:
        logger.error(f"服务运行出错: {e}", exc_info=True)
        raise
    finally:
        logger.info("记账 MCP 服务已关闭")


if __name__ == "__main__":
    main()

