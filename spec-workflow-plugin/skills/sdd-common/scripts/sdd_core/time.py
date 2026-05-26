"""Centralized timestamp formatting for all SDD scripts."""
from __future__ import annotations

from datetime import datetime, timezone

__all__ = ["ts_now", "ts_short", "ts_compact", "ts_from_epoch"]


def ts_now() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def ts_compact(source: str | None = None) -> str:
    """Collapse an ISO 8601 stamp to a filename-safe form.

    Strips the ``:``, ``-`` and ``.`` separators so archives sort
    lexicographically alongside other timestamped artifacts. When
    *source* is ``None`` the current time is used.
    """
    stamp = source if source is not None else ts_now()
    return stamp.translate(str.maketrans("", "", ":-."))


def ts_short() -> str:
    """Return current UTC timestamp in compact format for filenames."""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def ts_from_epoch(epoch_seconds: float) -> str:
    """Convert epoch seconds to ISO 8601 UTC timestamp."""
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )
