"""Tencent COS helpers used by the MCP server."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from qcloud_cos import CosConfig, CosS3Client
from qcloud_cos.cos_exception import CosClientError, CosServiceError

from ..config import (
    COS_BASE_URL,
    COS_BUCKET,
    COS_PATH_PREFIX,
    COS_REGION,
    COS_SECRET_ID,
    COS_SECRET_KEY,
)

logger = logging.getLogger(__name__)

_COS_CLIENT: CosS3Client | None = None


class CosConfigurationError(ValueError):
    """Raised when mandatory COS configuration is missing."""


def _ensure_configured() -> None:
    if not all([COS_SECRET_ID, COS_SECRET_KEY, COS_REGION, COS_BUCKET]):
        raise CosConfigurationError("COS 配置信息缺失，请检查环境变量。")


def get_cos_client() -> CosS3Client:
    """Create or reuse a COS client instance using environment configuration."""

    global _COS_CLIENT
    if _COS_CLIENT is None:
        _ensure_configured()
        config = CosConfig(
            Region=COS_REGION,
            SecretId=COS_SECRET_ID,
            SecretKey=COS_SECRET_KEY,
            Token=None,
            Scheme="https",
        )
        _COS_CLIENT = CosS3Client(config)
    return _COS_CLIENT


def _build_cos_base_url() -> str:
    if COS_BASE_URL:
        return COS_BASE_URL.rstrip("/")
    if not all([COS_BUCKET, COS_REGION]):
        raise CosConfigurationError("COS Bucket 或 Region 未配置。")
    return f"https://{COS_BUCKET}.cos.{COS_REGION}.myqcloud.com"


def upload_chart_image(image_bytes: bytes, suffix: str) -> str:
    """Upload chart image bytes to Tencent COS and return the public URL."""

    client = get_cos_client()
    if not COS_BUCKET:
        raise CosConfigurationError("COS Bucket 未配置。")

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
