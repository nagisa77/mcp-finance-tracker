"""记账 MCP 服务端."""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Annotated, Literal

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field as PydanticField, ValidationError

from .config import COS_BASE_URL
from .crud import (
    create_bill,
    ensure_default_assets,
    ensure_default_categories,
    get_asset_by_id,
    get_asset_by_name,
    get_categories_by_ids,
    get_category_by_name,
    get_category_filtered_expenses,
    get_expense_summary_by_category,
    get_expense_timeline,
    get_total_expense,
    get_total_expense_for_categories,
    list_categories,
)
from .models import BillType, Category, CategoryType
from .database import init_database, session_scope
from .schemas import (
    BillBatchRecordResult,
    BillCreate,
    BillExpenseDetail,
    BillRead,
    BillRecordResult,
    CategoryExpenseBreakdown,
    CategoryExpenseDetailResult,
    CategoryListResult,
    CategoryRead,
    ChartImage,
    InvestmentRecordCreate,
    ExpenseComparisonResult,
    ExpenseComparisonSnapshot,
    ExpenseSummaryResult,
    ExpenseTimelineBucket,
    ExpenseTimelineResult,
    ExpenseTimelineSnapshot,
)
from .services import (
    generate_expense_comparison_chart,
    generate_expense_summary_charts,
    generate_expense_timeline_chart,
    parse_period,
    require_user_id,
    resolve_category,
    unique_category_ids,
    validate_granularity,
)
from .services.cos_storage import CosConfigurationError

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

    user_id = require_user_id(ctx)
    try:
        with session_scope() as session:
            ensure_default_categories(session, user_id)
            categories = list_categories(session, user_id)

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
            description="账单金额，必须为正数。",
        ),
    ],
    type: Annotated[
        Literal["income", "expense"],
        PydanticField(description="账单类型，可选值为 income 或 expense。"),
    ],
    category_id: Annotated[
        int | None,
        PydanticField(description="分类 ID，可选。"),
    ] = None,
    description: Annotated[
        str | None,
        PydanticField(default=None, description="账单描述，可选。"),
    ] = None,
    ctx: Context | None = None,
) -> BillRecordResult:
    """记录一笔账单."""

    user_id = require_user_id(ctx)
    try:
        bill_payload = BillCreate(
            amount=amount,
            type=type,
            category_id=category_id,
            description=description,
        )
    except ValidationError as exc:
        logger.warning("账单数据校验失败: %s", exc)
        raise ValueError("账单数据不合法，请检查输入金额。") from exc

    try:
        with session_scope() as session:
            ensure_default_categories(session, user_id)
            ensure_default_assets(session)
            cny_asset = get_asset_by_name(session, "CNY")
            if cny_asset is None:
                raise ValueError("未找到默认人民币资产，请先初始化资产列表。")
            category_obj, category_display = resolve_category(
                session, bill_payload.category_id, user_id
            )
            bill_data = bill_payload.model_copy(
                update={
                    "source_asset_id": cny_asset.id,
                    "target_asset_id": cny_asset.id,
                    "target_amount": bill_payload.amount,
                }
            )
            bill = create_bill(session, bill_data, category_obj, user_id)
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


@mcp.tool(
    name="record_multiple_bills",
    description="批量记录多笔账单，支持一次传入多条记录。",
    structured_output=True,
)
async def record_multiple_bills(
    bills: Annotated[
        list[BillCreate],
        PydanticField(
            description="待记录的账单列表。",
            min_length=1,
            json_schema_extra={
                "items": {
                    "examples": [
                        {
                            "amount": 18.5,
                            "type": "expense",
                            "category_id": 1,
                            "description": "午餐",
                        },
                    ]
                }
            },
        ),
    ],
    ctx: Context | None = None,
) -> BillBatchRecordResult:
    """批量记录多笔账单."""

    user_id = require_user_id(ctx)

    try:
        with session_scope() as session:
            ensure_default_categories(session, user_id)
            ensure_default_assets(session)
            cny_asset = get_asset_by_name(session, "CNY")
            if cny_asset is None:
                raise ValueError("未找到默认人民币资产，请先初始化资产列表。")
            bill_models: list[BillRecordResult] = []
            failed_records: list[str] = []

            for index, bill in enumerate(bills, start=1):
                try:
                    category_obj, category_display = resolve_category(
                        session, bill.category_id, user_id
                    )
                    enriched_bill = bill.model_copy(
                        update={
                            "source_asset_id": cny_asset.id,
                            "target_asset_id": cny_asset.id,
                            "target_amount": bill.amount,
                        }
                    )
                    created_bill = create_bill(
                        session,
                        enriched_bill,
                        category_obj,
                        user_id,
                    )
                    bill_models.append(
                        BillRecordResult(
                            message="💾 账单记录成功！",
                            category_display=category_display,
                            bill=BillRead.model_validate(created_bill),
                        )
                    )
                except ValidationError as exc:
                    logger.warning("第 %s 条账单校验失败: %s", index, exc)
                    failed_records.append(
                        f"第 {index} 条账单校验失败，请检查金额是否为数字。"
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.exception("第 %s 条账单记录失败: %s", index, exc)
                    failed_records.append(f"第 {index} 条账单记录失败：{exc}")

        success_count = len(bill_models)
        failure_count = len(failed_records)

        status_lines = [
            f"✅ 成功记录 {success_count} 条账单。",
            f"⚠️ 有 {failure_count} 条账单记录失败。" if failure_count else "",
        ]
        if failed_records:
            status_lines.extend(failed_records)
        status_message = "\n".join(filter(None, status_lines))

        return BillBatchRecordResult(message=status_message, records=bill_models)
    except Exception as exc:  # noqa: BLE001
        logger.exception("批量记录账单失败: %s", exc)
        raise ValueError(f"批量记录账单失败：{exc}") from exc


@mcp.tool(
    name="record_investment_transaction",
    description=(
        "记录一笔资产的投资或获利行为，支持指定源/目标资产及变动数量。"
    ),
    structured_output=True,
)
async def record_investment_transaction(
    mode: Annotated[
        Literal["invest", "profit"],
        PydanticField(description="操作类型：invest 表示投资，profit 表示获利。"),
    ],
    source_asset_id: Annotated[
        int,
        PydanticField(ge=1, description="源资产 ID。"),
    ],
    target_asset_id: Annotated[
        int,
        PydanticField(ge=1, description="目标资产 ID。"),
    ],
    target_amount: Annotated[
        float,
        PydanticField(gt=0, description="目标资产增加的数量。"),
    ],
    description: Annotated[
        str | None,
        PydanticField(default=None, description="该笔记录的备注，可选。"),
    ] = None,
    ctx: Context | None = None,
) -> BillRecordResult:
    """记录一笔投资或获利账单."""

    user_id = require_user_id(ctx)

    try:
        payload = InvestmentRecordCreate(
            mode=mode,
            source_asset_id=source_asset_id,
            target_asset_id=target_asset_id,
            target_amount=target_amount,
            description=description,
        )
    except ValidationError as exc:
        logger.warning("投资/获利数据校验失败: %s", exc)
        raise ValueError("投资或获利数据不合法，请检查输入参数。") from exc

    try:
        with session_scope() as session:
            ensure_default_categories(session, user_id)
            ensure_default_assets(session)
            source_asset = get_asset_by_id(session, payload.source_asset_id)
            if source_asset is None:
                raise ValueError(f"未找到源资产：{payload.source_asset_id}")
            target_asset = get_asset_by_id(session, payload.target_asset_id)
            if target_asset is None:
                raise ValueError(f"未找到目标资产：{payload.target_asset_id}")

            category_obj = get_category_by_name(
                session,
                "投资",
                user_id,
                category_type=CategoryType.INVESTMENT,
            )
            if category_obj is None:
                # Fallback: 创建一个新的投资分类
                category_obj = Category(
                    user_id=user_id,
                    name="投资",
                    description="资产买卖与转换相关的记录",
                    color="#9ADCFF",
                    type=CategoryType.INVESTMENT,
                )
                session.add(category_obj)
                session.flush()

            bill_data = BillCreate(
                amount=payload.target_amount,
                type=BillType.INVESTMENT,
                category_id=category_obj.id,
                description=payload.description,
                source_asset_id=payload.source_asset_id,
                target_asset_id=payload.target_asset_id,
                target_amount=payload.target_amount,
            )
            bill = create_bill(session, bill_data, category_obj, user_id)
            bill_model = BillRead.model_validate(bill)

        action_display = "投资" if payload.mode == "invest" else "获利"
        message = "📈 投资记录成功！" if payload.mode == "invest" else "🎉 获利记录成功！"
        return BillRecordResult(
            message=message,
            category_display=f"{action_display} - {category_obj.name}",
            bill=bill_model,
        )
    except ValidationError as exc:
        logger.exception("投资/获利账单解析失败: %s", exc)
        raise ValueError("投资或获利账单数据格式不正确，请稍后重试。") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("记录投资/获利失败: %s", exc)
        raise ValueError(f"记录投资/获利失败：{exc}") from exc


@mcp.tool(
    name="get_finance_summary",
    description=(
        "获取指定类型账单在给定周期内的统计信息（总金额、分类占比与图表等）。"
    ),
    structured_output=True,
)
async def get_finance_summary(
    type: Annotated[
        Literal["expense", "income"],
        PydanticField(description="账单类型，可选值为 expense 或 income。"),
    ],
    period: Annotated[
        Literal["day", "week", "month", "year"],
        PydanticField(
            description="统计粒度，可选值为 day、week、month、year。",
        ),
    ],
    reference: Annotated[
        str,
        PydanticField(
            description=(
                "用于确定时间范围的参考值。day 传 YYYY-MM-DD，"
                "week 传 YYYY-Www，month 传 YYYY-MM，year 传 YYYY。"
            )
        ),
    ],
    ctx: Context | None = None,
) -> ExpenseSummaryResult:
    """查询指定时间范围内的账单统计信息."""

    user_id = require_user_id(ctx)
    bill_type = BillType(type)

    try:
        start, end, label = parse_period(period, reference)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    try:
        with session_scope() as session:
            ensure_default_categories(session, user_id)
            total_expense = get_total_expense(
                session, start, end, user_id, bill_type=bill_type
            )
            breakdown = get_expense_summary_by_category(
                session, start, end, user_id, bill_type=bill_type
            )
            breakdown_models = [
                CategoryExpenseBreakdown.model_validate(category_breakdown)
                for category_breakdown in breakdown
            ]

        charts = []
        if COS_BASE_URL:
            try:
                charts = generate_expense_summary_charts(breakdown_models, label)
            except (ValueError, CosConfigurationError) as exc:
                logger.warning("生成账单图表失败: %s", exc)

        return ExpenseSummaryResult(
            period=period,
            reference=reference,
            resolved_label=label,
            start=start,
            end=end,
            total_expense=total_expense,
            category_breakdown=breakdown_models,
            charts=charts,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("获取账单小结失败: %s", exc)
        raise ValueError(f"获取账单小结失败：{exc}") from exc


@mcp.tool(
    name="compare_finance_periods",
    description=(
        "对比两个时间周期内的账单情况，支持选择收入或支出，并按日、周、月、年进行对比。"
    ),
    structured_output=True,
)
async def compare_finance_periods(
    type: Annotated[
        Literal["expense", "income"],
        PydanticField(description="账单类型，可选值为 expense 或 income。"),
    ],
    period: Annotated[
        Literal["day", "week", "month", "year"],
        PydanticField(description="统计粒度，可选值为 day、week、month、year。"),
    ],
    first_reference: Annotated[
        str,
        PydanticField(
            description=(
                "第一个周期的参考值。day 传 YYYY-MM-DD，week 传 YYYY-Www，"
                "month 传 YYYY-MM，year 传 YYYY。"
            )
        ),
    ],
    second_reference: Annotated[
        str,
        PydanticField(
            description=(
                "第二个周期的参考值。day 传 YYYY-MM-DD，week 传 YYYY-Www，"
                "month 传 YYYY-MM，year 传 YYYY。"
            )
        ),
    ],
    category_ids: Annotated[
        list[int] | None,
        PydanticField(
            default=None,
            description="需要对比的分类 ID 列表，可传入一个或多个分类，不传则统计全部分类。",
        ),
    ] = None,
    ctx: Context | None = None,
) -> ExpenseComparisonResult:
    """Compare bill summaries between two time periods."""

    user_id = require_user_id(ctx)
    bill_type = BillType(type)

    normalized_category_ids: list[int] | None = None
    if category_ids is not None:
        normalized_category_ids = unique_category_ids(category_ids)

    try:
        first_start, first_end, first_label = parse_period(period, first_reference)
        second_start, second_end, second_label = parse_period(period, second_reference)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    try:
        with session_scope() as session:
            ensure_default_categories(session, user_id)

            first_total = get_total_expense(
                session,
                first_start,
                first_end,
                user_id,
                normalized_category_ids,
                bill_type=bill_type,
            )
            first_breakdown_raw = get_expense_summary_by_category(
                session,
                first_start,
                first_end,
                user_id,
                normalized_category_ids,
                bill_type=bill_type,
            )

            second_total = get_total_expense(
                session,
                second_start,
                second_end,
                user_id,
                normalized_category_ids,
                bill_type=bill_type,
            )
            second_breakdown_raw = get_expense_summary_by_category(
                session,
                second_start,
                second_end,
                user_id,
                normalized_category_ids,
                bill_type=bill_type,
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("获取账单对比数据失败: %s", exc)
        raise ValueError(f"获取账单对比数据失败：{exc}") from exc

    try:
        first_breakdown = [
            CategoryExpenseBreakdown.model_validate(item)
            for item in first_breakdown_raw
        ]
        second_breakdown = [
            CategoryExpenseBreakdown.model_validate(item)
            for item in second_breakdown_raw
        ]
    except ValidationError as exc:
        logger.exception("账单对比数据解析失败: %s", exc)
        raise ValueError("账单对比数据格式不正确，请稍后重试。") from exc

    try:
        first_snapshot = ExpenseComparisonSnapshot(
            reference=first_reference,
            resolved_label=first_label,
            start=first_start,
            end=first_end,
            total_expense=first_total,
            category_breakdown=first_breakdown,
        )
        second_snapshot = ExpenseComparisonSnapshot(
            reference=second_reference,
            resolved_label=second_label,
            start=second_start,
            end=second_end,
            total_expense=second_total,
            category_breakdown=second_breakdown,
        )
    except ValidationError as exc:
        logger.exception("账单对比快照构建失败: %s", exc)
        raise ValueError("账单对比数据格式不正确，请稍后重试。") from exc

    charts: list[ChartImage] = []
    if COS_BASE_URL:
        try:
            charts = generate_expense_comparison_chart(
                first_breakdown,
                first_label,
                second_breakdown,
                second_label,
            )
        except (ValueError, CosConfigurationError) as exc:
            logger.warning("生成账单对比图表失败: %s", exc)

    return ExpenseComparisonResult(
        period=period,
        first=first_snapshot,
        second=second_snapshot,
        charts=charts,
    )


@mcp.tool(
    name="get_finance_timeline",
    description=(
        "获取指定周期内的账单时间序列。"
        "支持按分类筛选、可指定统计颗粒度（支持 month、week、day），"
        "可对两个不同周期的账单趋势进行对比。"
        "颗粒度表示时间分桶的单位，可选择“月”、“周”或“天”。"
        "也支持传入一个或多个分类 ID，统计指定分类的变化。"
    ),
    structured_output=True,
)
async def get_finance_timeline(
    type: Annotated[
        Literal["expense", "income"],
        PydanticField(description="账单类型，可选值为 expense 或 income。"),
    ],
    period: Annotated[
        Literal["year", "month", "week"],
        PydanticField(description="统计周期，可选值为 year、month、week。"),
    ],
    reference: Annotated[
        str,
        PydanticField(
            description=(
                "用于确定时间范围的参考值。year 传 YYYY，month 传 YYYY-MM，"
                "week 传 YYYY-Www。"
            )
        ),
    ],
    granularity: Annotated[
        Literal["month", "week", "day"],
        PydanticField(description="统计颗粒度，可选值为 month、week、day，决定数据按哪种粒度分组展示，可用于趋势分析。"),
    ],
    category_ids: Annotated[
        list[int] | None,
        PydanticField(
            default=None,
            description="需要统计的分类 ID 列表，留空则统计全部数据。可用于按多个分类细分趋势。",
        ),
    ] = None,
    comparison_reference: Annotated[
        str | None,
        PydanticField(
            default=None,
            description=(
                "可选的对比周期参考值，填写后可对比两个不同周期的账单趋势，如对比相邻两月、两周等。"
            ),
        ),
    ] = None,
    ctx: Context | None = None,
) -> ExpenseTimelineResult:
    """获取指定周期（可选分类）的账单时间序列数据，支持指定颗粒度（日、周、月）与对比周期分析。"""

    user_id = require_user_id(ctx)
    bill_type = BillType(type)

    category_id_list = unique_category_ids(category_ids or [])

    comparison_reference_normalized = (
        comparison_reference.strip() if comparison_reference else None
    )

    try:
        validate_granularity(period, granularity)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    try:
        start, end, label = parse_period(period, reference)
        comparison_start: datetime | None = None
        comparison_end: datetime | None = None
        comparison_label: str | None = None
        if comparison_reference_normalized:
            comparison_start, comparison_end, comparison_label = parse_period(
                period, comparison_reference_normalized
            )
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    try:
        with session_scope() as session:
            ensure_default_categories(session, user_id)

            selected_categories: list[CategoryRead] = []
            if category_id_list:
                categories = get_categories_by_ids(session, category_id_list, user_id)
                existing_ids = {category.id for category in categories}
                missing_ids = [
                    str(category_id)
                    for category_id in category_id_list
                    if category_id not in existing_ids
                ]
                if missing_ids:
                    raise ValueError(
                        "未找到以下分类 ID：" + ", ".join(missing_ids)
                    )
                selected_categories = [
                    CategoryRead.model_validate(category)
                    for category in categories
                ]

            timeline_rows = get_expense_timeline(
                session,
                start,
                end,
                user_id,
                granularity,
                category_id_list,
                bill_type=bill_type,
            )
            timeline_buckets = [
                ExpenseTimelineBucket.model_validate(bucket)
                for bucket in timeline_rows
            ]
            total_expense = sum(float(bucket.total_expense) for bucket in timeline_buckets)

            primary_snapshot = ExpenseTimelineSnapshot(
                period=period,
                reference=reference,
                resolved_label=label,
                start=start,
                end=end,
                granularity=granularity,
                category_ids=category_id_list,
                selected_categories=selected_categories,
                total_expense=total_expense,
                buckets=timeline_buckets,
            )

            comparison_snapshot: ExpenseTimelineSnapshot | None = None
            comparison_buckets: list[ExpenseTimelineBucket] = []
            if comparison_reference_normalized and comparison_start and comparison_end:
                comparison_rows = get_expense_timeline(
                    session,
                    comparison_start,
                    comparison_end,
                    user_id,
                    granularity,
                    category_id_list,
                    bill_type=bill_type,
                )
                comparison_buckets = [
                    ExpenseTimelineBucket.model_validate(bucket)
                    for bucket in comparison_rows
                ]
                comparison_total = sum(
                    float(bucket.total_expense) for bucket in comparison_buckets
                )
                comparison_snapshot = ExpenseTimelineSnapshot(
                    period=period,
                    reference=comparison_reference_normalized,
                    resolved_label=comparison_label or comparison_reference_normalized,
                    start=comparison_start,
                    end=comparison_end,
                    granularity=granularity,
                    category_ids=category_id_list,
                    selected_categories=selected_categories,
                    total_expense=comparison_total,
                    buckets=comparison_buckets,
                )
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("获取账单时间序列失败: %s", exc)
        raise ValueError(f"获取账单时间序列失败：{exc}") from exc

    charts: list[ChartImage] = []
    if COS_BASE_URL:
        try:
            charts = generate_expense_timeline_chart(
                primary_snapshot.buckets,
                granularity,
                primary_snapshot.resolved_label,
                comparison_snapshot.buckets if comparison_snapshot else None,
                comparison_snapshot.resolved_label if comparison_snapshot else None,
            )
        except (ValueError, CosConfigurationError) as exc:
            logger.warning("生成账单趋势图失败: %s", exc)

    return ExpenseTimelineResult(
        period=period,
        granularity=granularity,
        primary=primary_snapshot,
        comparison=comparison_snapshot,
        charts=charts,
    )


@mcp.tool(
    name="get_category_finance_detail",
    description=(
        "获取指定分类在某个周期内的账单明细（含总金额与金额排名前 20 的账单）。"
    ),
    structured_output=True,
)
async def get_category_finance_detail(
    type: Annotated[
        Literal["expense", "income"],
        PydanticField(description="账单类型，可选值为 expense 或 income。"),
    ],
    period: Annotated[
        Literal["day", "week", "month", "year"],
        PydanticField(
            description="统计粒度，可选值为 day、week、month、year。",
        ),
    ],
    reference: Annotated[
        str,
        PydanticField(
            description=(
                "用于确定时间范围的参考值。day 传 YYYY-MM-DD，"
                "week 传 YYYY-Www，month 传 YYYY-MM，year 传 YYYY。"
            )
        ),
    ],
    category_ids: Annotated[
        list[int],
        PydanticField(
            min_length=1,
            description="需要统计的分类 ID 列表。",
            json_schema_extra={"example": [1, 2, 3]},
        ),
    ],
    ctx: Context | None = None,
) -> CategoryExpenseDetailResult:
    """查询指定分类在某个时间范围内的账单明细."""

    user_id = require_user_id(ctx)
    bill_type = BillType(type)
    try:
        start, end, label = parse_period(period, reference)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    normalized_ids = unique_category_ids(category_ids)

    try:
        with session_scope() as session:
            ensure_default_categories(session, user_id)
            categories = get_categories_by_ids(session, normalized_ids, user_id)
            found_ids = {category.id for category in categories}
            missing = [cid for cid in normalized_ids if cid not in found_ids]
            if missing:
                raise ValueError(
                    "以下分类 ID 不存在，请检查后重试：" + ", ".join(map(str, missing))
                )

            category_models = [
                CategoryRead.model_validate(category) for category in categories
            ]
            total_expense = get_total_expense_for_categories(
                session, start, end, normalized_ids, user_id, bill_type=bill_type
            )
            bills = get_category_filtered_expenses(
                session, start, end, normalized_ids, user_id, bill_type=bill_type
            )

            bill_details = [
                BillExpenseDetail(
                    bill_id=bill.id,
                    amount=bill.amount,
                    description=bill.description,
                    created_at=bill.created_at,
                    category_name=bill.category.name if bill.category is not None else "未分类",
                )
                for bill in bills
            ]

        return CategoryExpenseDetailResult(
            period=period,
            reference=reference,
            resolved_label=label,
            start=start,
            end=end,
            category_ids=normalized_ids,
            selected_categories=category_models,
            total_expense=total_expense,
            top_bills=bill_details,
        )
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("获取分类账单明细失败: %s", exc)
        raise ValueError(f"获取分类账单明细失败：{exc}") from exc


def main() -> None:
    """主函数."""

    try:
        init_database()

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
