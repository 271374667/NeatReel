from __future__ import annotations

import json
from typing import Any

from loguru import logger

from src.core.paths import PROJECT_ROOT


SETTINGS_FILE = PROJECT_ROOT / "settings.json"
VIDEO_INFO_DETECT_SHORT_EDGE_KEY = "videoInfoDetectShortEdge"
DEFAULT_VIDEO_INFO_DETECT_SHORT_EDGE = 360


def load_settings() -> dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return {}

    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read settings from {}: {}", SETTINGS_FILE, exc)
        return {}

    return data if isinstance(data, dict) else {}


def read_int_setting(
    key: str,
    default: int,
    *,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    settings = load_settings()
    raw_value = settings.get(key, default)

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return int(default)

    if min_value is not None:
        value = max(int(min_value), value)
    if max_value is not None:
        value = min(int(max_value), value)
    return value


def get_video_info_detect_short_edge() -> int:
    return read_int_setting(
        VIDEO_INFO_DETECT_SHORT_EDGE_KEY,
        DEFAULT_VIDEO_INFO_DETECT_SHORT_EDGE,
        min_value=120,
    )
