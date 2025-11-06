"""User related helpers for the MCP server."""
from __future__ import annotations

from mcp.server.fastmcp import Context

TELEGRAM_USER_ID_HEADER = "x-telegram-user-id"


def require_user_id(ctx: Context | None) -> str:
    """Extract the Telegram user id from the request context."""

    if ctx is None:
        raise ValueError("缺少请求上下文，无法识别用户。")

    try:
        request_context = ctx.request_context
    except ValueError as exc:  # noqa: TRY003
        raise ValueError("当前请求上下文不可用，无法识别用户。") from exc

    request = getattr(request_context, "request", None)
    if request is None:
        raise ValueError("无法获取请求信息，缺少用户标识。")

    header_value = request.headers.get(TELEGRAM_USER_ID_HEADER)
    if not header_value:
        raise ValueError("请求缺少 Telegram 用户标识。")

    user_id = header_value.strip()
    if not user_id:
        raise ValueError("请求缺少有效的 Telegram 用户标识。")

    return user_id
