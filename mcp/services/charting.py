"""Chart rendering helpers for expense summaries."""
from __future__ import annotations

import logging
from io import BytesIO
from typing import Iterable

import matplotlib
import numpy as np
from matplotlib import font_manager, image as mpimg

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from ..config import OTHER_CATEGORY_COLOR, UNCATEGORIZED_CATEGORY_COLOR
from ..schemas import CategoryExpenseBreakdown, ChartImage
from .cos_storage import upload_chart_image

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


def _figure_to_png_bytes(fig) -> bytes:
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    buffer.seek(0)
    data = buffer.getvalue()
    buffer.close()
    plt.close(fig)
    return data


def _prepend_sans_family(family: str) -> None:
    current = plt.rcParams.get("font.sans-serif", [])
    if isinstance(current, (list, tuple)):
        new_list = [family, *[item for item in current if item != family]]
    elif current:
        new_list = [family, str(current)]
    else:
        new_list = [family]
    plt.rcParams["font.sans-serif"] = new_list


def _configure_matplotlib_font() -> None:
    """Ensure Matplotlib renders Chinese text with an available font."""

    plt.rcParams["axes.unicode_minus"] = False

    custom_font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
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


def _render_bar_chart(
    breakdown: Iterable[CategoryExpenseBreakdown],
    period_label: str,
) -> bytes:
    breakdown_list = list(breakdown)
    categories = [item.category_name for item in breakdown_list]
    amounts = [item.total_amount for item in breakdown_list]
    colors = [item.color or UNCATEGORIZED_CATEGORY_COLOR for item in breakdown_list]
    figure_width = max(6.0, 0.9 * len(categories))
    fig, ax = plt.subplots(figsize=(figure_width, 5))

    x_positions = range(len(categories))
    bars = ax.bar(x_positions, amounts, color=colors)
    ax.set_ylabel("金额 (元)")
    ax.set_title(f"各分类支出柱状图（{period_label}）")
    ax.grid(axis="y", linestyle="--", alpha=0.3)

    max_amount = max(amounts, default=0)
    if max_amount <= 0:
        ax.set_ylim(0, 1)
    else:
        ax.set_ylim(0, max_amount * 1.15)

    ax.bar_label(
        bars,
        labels=[f"{value:.2f}" for value in amounts],
        padding=3,
        fontsize=9,
    )
    ax.set_xticks(list(x_positions))
    ax.set_xticklabels(categories, rotation=45, ha="right")

    fig.tight_layout()
    return _figure_to_png_bytes(fig)


def _render_comparison_bar_chart(
    first_breakdown: Iterable[CategoryExpenseBreakdown],
    first_label: str,
    second_breakdown: Iterable[CategoryExpenseBreakdown],
    second_label: str,
) -> bytes | None:
    first_items = list(first_breakdown)
    second_items = list(second_breakdown)
    combined: dict[tuple[int | None, str], dict[str, object]] = {}

    def _ingest(items: list[CategoryExpenseBreakdown], key: str) -> None:
        for item in items:
            identifier = (item.category_id, item.category_name)
            entry = combined.setdefault(
                identifier,
                {
                    "category_name": item.category_name,
                    "color": item.color or UNCATEGORIZED_CATEGORY_COLOR,
                    "first": 0.0,
                    "second": 0.0,
                },
            )
            entry[key] = float(item.total_amount)

    _ingest(first_items, "first")
    _ingest(second_items, "second")

    if not combined:
        return None

    ordered_entries = sorted(
        combined.values(),
        key=lambda value: float(value.get("first", 0.0))
        + float(value.get("second", 0.0)),
        reverse=True,
    )

    categories = [entry["category_name"] for entry in ordered_entries]
    first_amounts = [float(entry.get("first", 0.0)) for entry in ordered_entries]
    second_amounts = [float(entry.get("second", 0.0)) for entry in ordered_entries]
    colors = [str(entry.get("color", UNCATEGORIZED_CATEGORY_COLOR)) for entry in ordered_entries]

    x_positions = np.arange(len(categories))
    bar_width = 0.38
    figure_width = max(6.0, 0.9 * len(categories))
    fig, ax = plt.subplots(figsize=(figure_width, 5))

    bars_first = ax.bar(
        x_positions - bar_width / 2,
        first_amounts,
        bar_width,
        label=first_label,
        color=colors,
        alpha=0.85,
    )
    bars_second = ax.bar(
        x_positions + bar_width / 2,
        second_amounts,
        bar_width,
        label=second_label,
        color=colors,
        alpha=0.55,
    )

    ax.set_ylabel("金额 (元)")
    ax.set_title(f"分类支出对比：{first_label} vs {second_label}")
    ax.set_xticks(list(x_positions))
    ax.set_xticklabels(categories, rotation=45, ha="right")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.3)

    max_amount = max(first_amounts + second_amounts, default=0)
    if max_amount <= 0:
        ax.set_ylim(0, 1)
    else:
        ax.set_ylim(0, max_amount * 1.2)

    ax.bar_label(
        bars_first,
        labels=[f"{value:.2f}" for value in first_amounts],
        padding=3,
        fontsize=9,
    )
    ax.bar_label(
        bars_second,
        labels=[f"{value:.2f}" for value in second_amounts],
        padding=3,
        fontsize=9,
    )

    fig.tight_layout()
    return _figure_to_png_bytes(fig)


def _render_pie_chart(
    breakdown: Iterable[CategoryExpenseBreakdown],
    period_label: str,
) -> bytes:
    breakdown_list = list(breakdown)
    categories = [item.category_name for item in breakdown_list]
    amounts = [item.total_amount for item in breakdown_list]
    colors = [item.color or UNCATEGORIZED_CATEGORY_COLOR for item in breakdown_list]
    total = sum(amounts)
    fig, ax = plt.subplots(figsize=(6, 6))

    if total <= 0:
        ax.axis("off")
        ax.text(0.5, 0.5, "暂无支出数据", ha="center", va="center", fontsize=14)
        fig.suptitle(f"各分类支出占比（{period_label}）")
        fig.tight_layout()
        return _figure_to_png_bytes(fig)

    grouped_categories: list[str] = []
    grouped_amounts: list[float] = []
    grouped_colors: list[str] = []
    other_amount = 0.0
    for name, amount, color in zip(categories, amounts, colors):
        if total > 0 and amount / total < 0.025:
            other_amount += amount
        else:
            grouped_categories.append(name)
            grouped_amounts.append(amount)
            grouped_colors.append(color)
    if other_amount > 0:
        grouped_categories.append("其他")
        grouped_amounts.append(other_amount)
        grouped_colors.append(OTHER_CATEGORY_COLOR)

    categories = grouped_categories
    amounts = grouped_amounts
    colors = grouped_colors

    def _format_pct(pct: float) -> str:
        return "" if pct < 1 else f"{pct:.1f}%"

    wedges, texts, autotexts = ax.pie(  # noqa: F841
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


def _merge_chart_images_horizontally(left: bytes, right: bytes) -> bytes:
    """Merge two PNG images into a single image placed side-by-side."""

    left_image = mpimg.imread(BytesIO(left), format="png")
    right_image = mpimg.imread(BytesIO(right), format="png")

    max_height = max(left_image.shape[0], right_image.shape[0])

    def _pad_to_height(image: np.ndarray) -> np.ndarray:
        if image.shape[0] == max_height:
            return image

        pad_total = max_height - image.shape[0]
        pad_top = pad_total // 2
        pad_bottom = pad_total - pad_top
        pad_width = ((pad_top, pad_bottom), (0, 0))
        if image.ndim == 3:
            pad_width += ((0, 0),)
        return np.pad(image, pad_width, mode="constant", constant_values=1.0)

    left_padded = _pad_to_height(left_image)
    right_padded = _pad_to_height(right_image)

    merged = np.concatenate((left_padded, right_padded), axis=1)

    buffer = BytesIO()
    plt.imsave(buffer, merged, format="png")
    buffer.seek(0)
    data = buffer.getvalue()
    buffer.close()
    return data


def generate_expense_summary_charts(
    breakdown: list[CategoryExpenseBreakdown],
    period_label: str,
) -> list[ChartImage]:
    """Generate bar and pie charts for the expense summary."""

    if not breakdown:
        return []

    bar_chart_bytes = _render_bar_chart(breakdown, period_label)
    pie_chart_bytes = _render_pie_chart(breakdown, period_label)

    combined_bytes = _merge_chart_images_horizontally(bar_chart_bytes, pie_chart_bytes)
    combined_url = upload_chart_image(combined_bytes, "combined")

    return [
        ChartImage(
            title=f"各分类支出概览（{period_label}）",
            image_url=combined_url,
            mime_type="image/png",
        )
    ]


def generate_expense_comparison_chart(
    first_breakdown: list[CategoryExpenseBreakdown],
    first_label: str,
    second_breakdown: list[CategoryExpenseBreakdown],
    second_label: str,
) -> list[ChartImage]:
    """Generate comparison bar chart for two expense breakdowns."""

    chart_bytes = _render_comparison_bar_chart(
        first_breakdown,
        first_label,
        second_breakdown,
        second_label,
    )

    if not chart_bytes:
        return []

    chart_url = upload_chart_image(chart_bytes, "comparison")
    return [
        ChartImage(
            title=f"分类支出对比（{first_label} vs {second_label}）",
            image_url=chart_url,
            mime_type="image/png",
        )
    ]
