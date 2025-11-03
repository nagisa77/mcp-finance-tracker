"""记账 MCP 服务端."""
import logging
from typing import Annotated

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field as PydanticField, ValidationError

from crud import (
    create_bill,
    ensure_default_categories,
    get_category_by_name,
    list_categories,
)
from database import init_database, session_scope
from schemas import (
    BillCreate,
    BillRead,
    BillRecordResult,
    CategoryListResult,
    CategoryRead,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP("记账服务", host="0.0.0.0", port=8000)


@mcp.tool(
    name="get_categories",
    description="获取当前所有分类及其描述。",
    structured_output=True,
)
async def get_categories(ctx: Context | None = None) -> CategoryListResult:
    """获取当前所有分类及其描述."""
    _ = ctx
    try:
        with session_scope() as session:
            categories = list_categories(session)

        category_models = [
            CategoryRead.model_validate(category) for category in categories
        ]
        return CategoryListResult(total=len(category_models), categories=category_models)
    except ValidationError as exc:
        logger.exception("分类数据解析失败: %s", exc)
        raise ValueError("分类数据格式不正确，请稍后重试。") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("获取分类失败: %s", exc)
        raise ValueError(f"获取分类失败：{exc}") from exc


@mcp.tool(
    name="record_bill",
    description="记录一笔账单，包括金额、分类与描述。",
    structured_output=True,
)
async def record_bill(
    amount: Annotated[
        float,
        PydanticField(
            description="账单金额，正数为支出，负数为收入。",
        ),
    ],
    category: Annotated[
        str | None,
        PydanticField(default=None, description="分类名称，可选。"),
    ] = None,
    description: Annotated[
        str | None,
        PydanticField(default=None, description="账单描述，可选。"),
    ] = None,
    ctx: Context | None = None,
) -> BillRecordResult:
    """记录一笔账单."""
    _ = ctx
    try:
        bill_data = BillCreate(amount=amount, category=category, description=description)
    except ValidationError as exc:
        logger.warning("账单数据校验失败: %s", exc)
        raise ValueError("账单数据不合法，请检查输入金额。") from exc

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
            bill_model = BillRead.model_validate(bill)
        return BillRecordResult(
            message="💾 账单记录成功！",
            category_display=category_display,
            bill=bill_model,
        )
    except ValidationError as exc:
        logger.exception("账单数据解析失败: %s", exc)
        raise ValueError("账单数据格式不正确，请稍后重试。") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("记录账单失败: %s", exc)
        raise ValueError(f"记录账单失败：{exc}") from exc


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
