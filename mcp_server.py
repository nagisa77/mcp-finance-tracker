"""记账 MCP 服务端."""
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from crud import (
    create_bill,
    ensure_default_categories,
    get_category_by_name,
    list_categories,
)
from database import init_database, session_scope
from schemas import BillCreate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP("记账服务", host="0.0.0.0", port=8000)


@mcp.tool()
async def get_categories() -> str:
    """获取当前所有分类及其描述."""
    try:
        with session_scope() as session:
            categories = list_categories(session)

        if not categories:
            return "当前没有分类，请先添加分类。"

        lines = ["📂 当前可用的分类列表："]
        for index, category in enumerate(categories, start=1):
            lines.append(f"{index}. 【{category.name}】")
            if category.description:
                lines.append(f"   描述：{category.description}")

        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        logger.exception("获取分类失败: %s", exc)
        return f"获取分类失败：{exc}"


@mcp.tool()
async def record_bill(
    amount: float,
    category: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    """记录一笔账单."""
    try:
        bill_data = BillCreate(amount=amount, category=category, description=description)
    except ValidationError as exc:
        logger.warning("账单数据校验失败: %s", exc)
        return "账单数据不合法，请检查输入金额。"

    try:
        with session_scope() as session:
            category_obj = None
            category_display = "未分类"

            if bill_data.category:
                category_obj = get_category_by_name(session, bill_data.category)
                if category_obj is not None:
                    category_display = category_obj.name
                else:
                    category_display = f"未知分类：{bill_data.category}"

            bill = create_bill(session, bill_data, category_obj)

        type_text = "支出" if bill.type == "expense" else "收入"
        lines = [
            "💾 账单记录成功！",
            f"类型：{type_text}",
            f"金额：¥{bill.amount:.2f}",
            f"分类：{category_display}",
        ]
        if bill.description:
            lines.append(f"描述：{bill.description}")

        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        logger.exception("记录账单失败: %s", exc)
        return f"记录账单失败：{exc}"


def main() -> None:
    """主函数."""
    try:
        init_database()
        with session_scope() as session:
            ensure_default_categories(session)

        logger.info("记账 MCP 服务启动成功")
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭服务…")
    except Exception as exc:  # noqa: BLE001
        logger.exception("服务运行出错: %s", exc)
        raise
    finally:
        logger.info("记账 MCP 服务已关闭")


if __name__ == "__main__":
    main()
