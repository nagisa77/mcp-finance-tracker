"""记账 MCP 服务端."""
import logging
import os
import uuid
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO
from typing import Annotated, Literal

import matplotlib
from matplotlib import font_manager
from qcloud_cos import CosConfig, CosS3Client
from qcloud_cos.cos_exception import CosClientError, CosServiceError
from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field as PydanticField, ValidationError
from sqlalchemy.orm import Session

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .crud import (
    create_bill,
    ensure_default_categories,
    get_categories_by_ids,
    get_category_by_id,
    get_category_filtered_expenses,
    get_expense_summary_by_category,
    get_total_expense,
    get_total_expense_for_categories,
    list_categories,
)
from .database import init_database, session_scope
from .models import Category
from .schemas import (
    BillBatchRecordResult,
    BillCreate,
    BillRead,
    BillRecordResult,
    BillExpenseDetail,
    CategoryListResult,
    CategoryRead,
    CategoryExpenseBreakdown,
    CategoryExpenseDetailResult,
    ChartImage,
    ExpenseSummaryResult,
)
from .config import (
    COS_BASE_URL,
    COS_BUCKET,
    COS_PATH_PREFIX,
    COS_REGION,
    COS_SECRET_ID,
    COS_SECRET_KEY,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

_PREFERRED_FONT_FAMILIES = [
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "Source Han Sans CN",
    "Microsoft YaHei",
    "PingFang SC",
    "SimHei",
    "WenQuanYi Micro Hei",
]


def _configure_matplotlib_font() -> None:
    """Ensure Matplotlib renders Chinese text with an available font."""

    plt.rcParams["axes.unicode_minus"] = False

    def _prepend_sans_family(family: str) -> None:
        current = plt.rcParams.get("font.sans-serif", [])
        if isinstance(current, (list, tuple)):
            new_list = [family, *[item for item in current if item != family]]
        elif current:
            new_list = [family, str(current)]
        else:
            new_list = [family]
        plt.rcParams["font.sans-serif"] = new_list
    custom_font_path = os.getenv("MCP_CHART_FONT_PATH")
    if custom_font_path:
        try:
            font_manager.fontManager.addfont(custom_font_path)
            font_prop = font_manager.FontProperties(fname=custom_font_path)
            family_name = font_prop.get_name()
            plt.rcParams["font.family"] = family_name
            _prepend_sans_family(family_name)
            logger.info("已加载自定义图表字体: %s", family_name)
            return
        except (FileNotFoundError, OSError) as exc:  # noqa: TRY003
            logger.warning("加载自定义字体失败: %s", exc)

    available_families = {font.name for font in font_manager.fontManager.ttflist}
    for family in _PREFERRED_FONT_FAMILIES:
        if family in available_families:
            plt.rcParams["font.family"] = family
            _prepend_sans_family(family)
            logger.info("使用字体 %s 渲染图表", family)
            return

    logger.warning("未找到中文字体，图表中文字可能无法正常显示。")


_configure_matplotlib_font()

CURRENT_DATE_TEXT = date.today().isoformat()

mcp = FastMCP("记账服务", host="0.0.0.0", port=8000)

_cos_client: CosS3Client | None = None


def _figure_to_png_bytes(fig) -> bytes:
    """Serialize a Matplotlib figure to PNG bytes."""

    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    buffer.seek(0)
    data = buffer.getvalue()
    buffer.close()
    plt.close(fig)
    return data


def _get_cos_client() -> CosS3Client:
    """Create or reuse a COS client instance using environment configuration."""

    global _cos_client
    if _cos_client is None:
        if not all([COS_SECRET_ID, COS_SECRET_KEY, COS_REGION, COS_BUCKET]):
            raise ValueError("COS 配置信息缺失，请检查环境变量。")

        config = CosConfig(
            Region=COS_REGION,
            SecretId=COS_SECRET_ID,
            SecretKey=COS_SECRET_KEY,
            Token=None,
            Scheme="https",
        )
        _cos_client = CosS3Client(config)
    return _cos_client


def _build_cos_base_url() -> str:
    if COS_BASE_URL:
        return COS_BASE_URL.rstrip("/")
    if not all([COS_BUCKET, COS_REGION]):
        raise ValueError("COS Bucket 或 Region 未配置。")
    return f"https://{COS_BUCKET}.cos.{COS_REGION}.myqcloud.com"


def _upload_chart_image(image_bytes: bytes, suffix: str) -> str:
    """Upload chart image bytes to Tencent COS and return the public URL."""

    client = _get_cos_client()
    if not COS_BUCKET:
        raise ValueError("COS Bucket 未配置。")

    date_prefix = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    unique_key = uuid.uuid4().hex
    sanitized_prefix = COS_PATH_PREFIX.strip("/") if COS_PATH_PREFIX else ""
    key_parts = [part for part in (sanitized_prefix, date_prefix) if part]
    key_parts.append(f"expense-summary-{suffix}-{unique_key}.png")
    object_key = "/".join(key_parts)

    try:
        client.put_object(
            Bucket=COS_BUCKET,
            Body=image_bytes,
            Key=object_key,
            ContentType="image/png",
        )
    except (CosClientError, CosServiceError) as exc:
        logger.exception("上传图表到 COS 失败: %s", exc)
        raise ValueError("上传图表失败，请稍后再试。") from exc

    base_url = _build_cos_base_url()
    return f"{base_url}/{object_key}"


def _render_bar_chart(
    breakdown: list[CategoryExpenseBreakdown],
    period_label: str,
) -> bytes:
    """Create a horizontal bar chart for category expenses."""

    categories = [item.category_name for item in breakdown]
    amounts = [item.total_amount for item in breakdown]
    figure_height = max(3.5, 1.0 + 0.6 * len(categories))
    fig, ax = plt.subplots(figsize=(8, figure_height))

    reversed_amounts = amounts[::-1]
    bars = ax.barh(categories[::-1], reversed_amounts, color="#4C72B0")
    ax.set_xlabel("金额 (元)")
    ax.set_title(f"各分类支出柱状图（{period_label}）")
    ax.grid(axis="x", linestyle="--", alpha=0.3)

    max_amount = max(amounts, default=0)
    if max_amount <= 0:
        ax.set_xlim(0, 1)
    else:
        ax.set_xlim(0, max_amount * 1.15)

    ax.invert_yaxis()
    ax.bar_label(bars, labels=[f"{value:.2f}" for value in reversed_amounts], padding=4, fontsize=9)

    fig.tight_layout()
    return _figure_to_png_bytes(fig)


def _render_pie_chart(
    breakdown: list[CategoryExpenseBreakdown],
    period_label: str,
) -> bytes:
    """Create a pie chart for category expenses."""

    categories = [item.category_name for item in breakdown]
    amounts = [item.total_amount for item in breakdown]
    total = sum(amounts)
    fig, ax = plt.subplots(figsize=(6, 6))

    if total <= 0:
        ax.axis("off")
        ax.text(0.5, 0.5, "暂无支出数据", ha="center", va="center", fontsize=14)
        fig.suptitle(f"各分类支出占比（{period_label}）")
        fig.tight_layout()
        return _figure_to_png_bytes(fig)

    cmap = plt.get_cmap("tab20")
    colors = [cmap(i % cmap.N) for i in range(len(categories))]

    def _format_pct(pct: float) -> str:
        return "" if pct < 1 else f"{pct:.1f}%"

    _wedges, texts, autotexts = ax.pie(
        amounts,
        labels=categories,
        autopct=_format_pct,
        startangle=90,
        colors=colors,
        wedgeprops={"linewidth": 1, "edgecolor": "white"},
    )
    for text in texts + list(autotexts):
        text.set_fontsize(9)

    ax.axis("equal")
    ax.set_title(f"各分类支出占比（{period_label}）")
    fig.tight_layout()
    return _figure_to_png_bytes(fig)


def _build_chart_period_label(
    start: datetime,
    end: datetime,
    resolved_label: str,
) -> str:
    """Create a concise label describing the chart period."""

    start_text = start.strftime("%Y-%m-%d")
    end_inclusive = end - timedelta(seconds=1)
    end_text = end_inclusive.strftime("%Y-%m-%d")

    if end_inclusive.date() <= start.date():
        range_text = start_text
    else:
        range_text = f"{start_text} 至 {end_text}"

    resolved_label = resolved_label.strip()
    if resolved_label and resolved_label not in range_text:
        return f"{resolved_label}：{range_text}"
    return range_text


def _generate_expense_summary_charts(
    breakdown: list[CategoryExpenseBreakdown],
    period_label: str,
) -> list[ChartImage]:
    """Generate bar and pie charts for the expense summary."""

    if not breakdown:
        return []

    bar_chart_bytes = _render_bar_chart(breakdown, period_label)
    pie_chart_bytes = _render_pie_chart(breakdown, period_label)

    bar_chart_url = _upload_chart_image(bar_chart_bytes, "bar")
    pie_chart_url = _upload_chart_image(pie_chart_bytes, "pie")

    return [
        ChartImage(
            title=f"各分类支出柱状图（{period_label}）",
            image_url=bar_chart_url,
            mime_type="image/png",
        ),
        ChartImage(
            title=f"各分类支出占比（{period_label}）",
            image_url=pie_chart_url,
            mime_type="image/png",
        ),
    ]


def _resolve_category(
    session: Session, category_id: int | None
) -> tuple[Category | None, str]:
    """根据 ID 解析分类并返回显示文本."""

    category_obj: Category | None = None
    category_display = "未分类"
    if category_id is not None:
        category_obj = get_category_by_id(session, category_id)
        if category_obj is not None:
            category_display = category_obj.name
        else:
            category_display = f"未知分类：{category_id}"
    return category_obj, category_display


def _parse_period(
    period: Literal["day", "week", "month", "year"],
    reference: str,
) -> tuple[datetime, datetime, str]:
    """将周期与参考值转换为起止时间范围."""

    ref = reference.strip()
    if not ref:
        raise ValueError("请提供用于确定时间范围的参考值。")

    if period == "day":
        try:
            target_date = datetime.strptime(ref, "%Y-%m-%d").date()
        except ValueError as exc:  # noqa: TRY003
            raise ValueError("日期格式错误，应为 YYYY-MM-DD。") from exc
        start = datetime.combine(target_date, time.min)
        end = start + timedelta(days=1)
        label = target_date.strftime("%Y-%m-%d")
    elif period == "week":
        try:
            year_part, week_part = ref.split("-W", maxsplit=1)
            target_year = int(year_part)
            target_week = int(week_part)
            target_date = date.fromisocalendar(target_year, target_week, 1)
        except ValueError as exc:  # noqa: TRY003
            raise ValueError("周格式错误，应为 YYYY-Www，例如 2024-W09。") from exc
        start = datetime.combine(target_date, time.min)
        end = start + timedelta(days=7)
        label = f"{target_year:04d}-W{target_week:02d}"
    elif period == "month":
        try:
            target_date = datetime.strptime(ref, "%Y-%m").date().replace(day=1)
        except ValueError as exc:  # noqa: TRY003
            raise ValueError("月份格式错误，应为 YYYY-MM。") from exc
        start = datetime.combine(target_date, time.min)
        # 通过先跳到本月 28 日再加 4 天确保跨月
        next_month_base = target_date.replace(day=28) + timedelta(days=4)
        next_month = next_month_base.replace(day=1)
        end = datetime.combine(next_month, time.min)
        label = target_date.strftime("%Y-%m")
    elif period == "year":
        try:
            target_year = int(ref)
        except ValueError as exc:  # noqa: TRY003
            raise ValueError("年份格式错误，应为 YYYY。") from exc
        start_date = date(target_year, 1, 1)
        start = datetime.combine(start_date, time.min)
        end = datetime.combine(date(target_year + 1, 1, 1), time.min)
        label = f"{target_year:04d}"
    else:  # pragma: no cover - 由类型系统保证
        raise ValueError("不支持的统计粒度。")

    return start, end, label


def _unique_category_ids(category_ids: list[int]) -> list[int]:
    """保持顺序地去重分类 ID 列表."""

    seen: dict[int, None] = {}
    for cid in category_ids:
        if cid not in seen:
            seen[cid] = None
    return list(seen.keys())


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
    _ = ctx
    try:
        bill_data = BillCreate(
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
            category_obj, category_display = _resolve_category(
                session, bill_data.category_id
            )
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
                        {
                            "amount": 2000,
                            "type": "income",
                            "category_id": 5,
                            "description": "10月发薪",
                        },
                    ]
                }
            },
        ),
    ],
    ctx: Context | None = None,
) -> BillBatchRecordResult:
    """批量记录账单."""

    _ = ctx
    try:
        bill_inputs: list[BillCreate] = []
        for index, payload in enumerate(bills, start=1):
            try:
                bill_inputs.append(BillCreate.model_validate(payload))
            except ValidationError as exc:
                logger.warning("第 %s 条账单数据校验失败: %s", index, exc)
                raise ValueError(
                    f"第 {index} 条账单数据不合法，请检查金额与字段格式。"
                ) from exc
    except TypeError as exc:
        logger.warning("账单批量数据类型错误: %s", exc)
        raise ValueError("账单列表格式不正确，请提供 JSON 数组。") from exc

    try:
        with session_scope() as session:
            records: list[BillRecordResult] = []
            for bill_data in bill_inputs:
                category_obj, category_display = _resolve_category(
                    session, bill_data.category_id
                )
                bill = create_bill(session, bill_data, category_obj)
                bill_model = BillRead.model_validate(bill)
                records.append(
                    BillRecordResult(
                        message="💾 账单记录成功！",
                        category_display=category_display,
                        bill=bill_model,
                    )
        )
        return BillBatchRecordResult(
            message=f"成功记录 {len(records)} 笔账单。",
            records=records,
        )
    except ValidationError as exc:
        logger.exception("批量账单数据解析失败: %s", exc)
        raise ValueError("账单数据格式不正确，请稍后重试。") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("批量记录账单失败: %s", exc)
        raise ValueError(f"批量记录账单失败：{exc}") from exc


@mcp.tool(
    name="get_expense_summary",
    description=(
        "获取指定周期内的消费小结（包含总开销及各分类支出排行）。"
        f"当前日期：{CURRENT_DATE_TEXT}"
    ),
    structured_output=True,
)
async def get_expense_summary(
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
    """按分类汇总指定时间范围内的消费数据."""

    _ = ctx
    try:
        start, end, label = _parse_period(period, reference)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    try:
        with session_scope() as session:
            total_expense = get_total_expense(session, start, end)
            breakdown_raw = get_expense_summary_by_category(session, start, end)

        breakdown_models = [
            CategoryExpenseBreakdown(**item) for item in breakdown_raw
        ]

        period_label = _build_chart_period_label(start, end, label)
        charts = _generate_expense_summary_charts(breakdown_models, period_label)

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
        logger.exception("获取消费小结失败: %s", exc)
        raise ValueError(f"获取消费小结失败：{exc}") from exc


@mcp.tool(
    name="get_category_expense_detail",
    description=(
        "获取指定分类在某个周期内的消费明细（含总开销与金额排名前 20 的账单）。"
        f"当前日期：{CURRENT_DATE_TEXT}"
    ),
    structured_output=True,
)
async def get_category_expense_detail(
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
    """查询指定分类在某个时间范围内的消费明细."""

    _ = ctx
    try:
        start, end, label = _parse_period(period, reference)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    normalized_ids = _unique_category_ids(category_ids)

    try:
        with session_scope() as session:
            categories = get_categories_by_ids(session, normalized_ids)
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
                session, start, end, normalized_ids
            )
            bills = get_category_filtered_expenses(
                session, start, end, normalized_ids
            )

            bill_details = [
                BillExpenseDetail(
                    bill_id=bill.id,
                    amount=bill.amount,
                    description=bill.description,
                    created_at=bill.created_at,
                    category_name=
                    bill.category.name if bill.category is not None else "未分类",
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
        logger.exception("获取分类消费明细失败: %s", exc)
        raise ValueError(f"获取分类消费明细失败：{exc}") from exc


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
