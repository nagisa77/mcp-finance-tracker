"""Chart rendering helpers for expense summaries."""
from __future__ import annotations

import logging
import os
from io import BytesIO
from typing import Iterable

import matplotlib
from matplotlib import font_manager

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

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
    categories = [item.category_name for item in breakdown]
    amounts = [item.total_amount for item in breakdown]
    figure_width = max(6.0, 0.9 * len(categories))
    fig, ax = plt.subplots(figsize=(figure_width, 5))

    x_positions = range(len(categories))
    bars = ax.bar(x_positions, amounts, color="#4C72B0")
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


def _render_pie_chart(
    breakdown: Iterable[CategoryExpenseBreakdown],
    period_label: str,
) -> bytes:
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

    grouped_categories: list[str] = []
    grouped_amounts: list[float] = []
    other_amount = 0.0
    for name, amount in zip(categories, amounts):
        if total > 0 and amount / total < 0.025:
            other_amount += amount
        else:
            grouped_categories.append(name)
            grouped_amounts.append(amount)
    if other_amount > 0:
        grouped_categories.append("Other")
        grouped_amounts.append(other_amount)

    categories = grouped_categories
    amounts = grouped_amounts

    cmap = plt.get_cmap("tab20")
    colors = [cmap(i % cmap.N) for i in range(len(categories))]

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


def generate_expense_summary_charts(
    breakdown: list[CategoryExpenseBreakdown],
    period_label: str,
) -> list[ChartImage]:
    """Generate bar and pie charts for the expense summary."""

    if not breakdown:
        return []

    bar_chart_bytes = _render_bar_chart(breakdown, period_label)
    pie_chart_bytes = _render_pie_chart(breakdown, period_label)

    bar_chart_url = upload_chart_image(bar_chart_bytes, "bar")
    pie_chart_url = upload_chart_image(pie_chart_bytes, "pie")

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
