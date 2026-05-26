"""Ledger markers / write-through for launch preconditions.

The post-change-review gate uses two complementary markers:

* ``post_change_review.acked`` — workspace-scoped, persists across
  gate cycles. Records that the user acknowledged the prompt at least
  once for this workspace; the marker is bound to the ledger's
  workspace key and survives process restarts trivially because the
  ledger itself is persistent.
* ``post_change_review.presented`` — gate-cycle-scoped, keyed by
  ``gate_uuid``. Records that the prompt was surfaced for the current
  cycle so a second resume inside the same cycle does not re-fire the
  presentation; a *new* gate cycle (different ``gate_uuid``) is
  detected by the absence of a matching marker and re-presents the
  prompt exactly once.

Bound-on-growth strategy. Both markers are workspace-scoped, keyed by
``gate_uuid``, and naturally evicted as gates advance: the append-only
ledger keeps one ``presented`` entry per distinct gate cycle, and
read helpers return the latest entry. Each cycle's presentation
fires exactly once, so storage grows linearly with the number of
distinct cycles a workspace runs — never per resume or per process
boundary. The ledger does NOT auto-compact; explicit eviction is not
wired (no ``clear_presented`` helper exists, by deliberate decision).
If a future workload pushes ``presented`` cardinality high enough to
matter, callers can add a ``clear_presented`` helper that overwrites
the entry on ack so the storage cost stays bounded by workspace count
rather than cycle count.
"""
from __future__ import annotations

from sdd_core import reference_ledger

from .policy import _read_warn_seen_script
from .types import (
    AnyPrecondition,
    ReferenceReadPrecondition,
    advisory_echoed_script_id,
    post_change_review_presented_script_id,
    post_change_review_script_id,
    _WARN_SEEN_SCRIPT,
)

__all__ = [
    "record_marker",
    "mark_warn_seen",
    "mark_read_warn_seen",
    "mark_post_change_review_acked",
    "mark_post_change_review_presented",
    "read_post_change_review_presented",
    "mark_advisory_echoed",
    "post_change_review_script_id",
    "post_change_review_presented_script_id",
    "advisory_echoed_script_id",
]


def record_marker(
    *,
    script: str,
    category: str,
    target_name: str,
    project_path: str = "",
    extras: "dict | None" = None,
) -> None:
    """Append a ledger marker with the given script key and optional extras."""
    reference_ledger.append(
        category=category,
        target_name=target_name,
        project_path=project_path,
        script=script,
        extra=extras,
    )


def mark_warn_seen(
    *, category: str, target_name: str, project_path: str = "",
) -> None:
    """Append the warn marker so the next call escalates to ``error``."""
    record_marker(script=_WARN_SEEN_SCRIPT, category=category, target_name=target_name, project_path=project_path)


def mark_read_warn_seen(
    *,
    pre: ReferenceReadPrecondition,
    category: str,
    target_name: str,
    project_path: str = "",
) -> None:
    """Record the per-reference warn marker so the next call escalates."""
    record_marker(script=_read_warn_seen_script(pre), category=category, target_name=target_name, project_path=project_path)


def mark_post_change_review_acked(
    *,
    category: str,
    target_name: str,
    gate_id: str,
    project_path: str = "",
    prompt_sha256: "str | None" = None,
) -> None:
    """Append the post-change-review acknowledgement ledger marker."""
    extra: "dict | None" = {"prompt_sha256": prompt_sha256} if prompt_sha256 else None
    record_marker(
        script=post_change_review_script_id(gate_id),
        category=category, target_name=target_name, project_path=project_path, extras=extra,
    )


def mark_post_change_review_presented(
    *,
    category: str,
    target_name: str,
    gate_id: str,
    project_path: str = "",
    prompt_sha256: "str | None" = None,
) -> None:
    """Record the per-gate-cycle ``presented`` marker.

    The marker is keyed by ``gate_uuid`` so a new gate cycle (different
    ``gate_id``) presents the prompt exactly once even when the
    workspace-scoped ack already exists from a prior cycle. The
    ledger's persistence guarantees the marker survives a process
    restart unchanged.
    """
    extra: dict = {"gate_uuid": gate_id or "default"}
    if prompt_sha256:
        extra["prompt_sha256"] = prompt_sha256
    record_marker(
        script=post_change_review_presented_script_id(gate_id),
        category=category, target_name=target_name,
        project_path=project_path, extras=extra,
    )


def read_post_change_review_presented(
    *,
    category: str,
    target_name: str,
    gate_id: str,
    project_path: str = "",
) -> "dict | None":
    """Return the latest ``presented`` marker for *gate_id* (or ``None``).

    Reads the workspace-scoped reference ledger and returns the entry's
    ``extra`` dict (carries ``gate_uuid`` / ``prompt_sha256``) when a
    marker exists for the requested gate cycle. Used by both the
    launch-precondition handler and the restart-survival regression
    test.
    """
    script_id = post_change_review_presented_script_id(gate_id)
    for entry in reference_ledger.read_entries(category, target_name, project_path):
        if entry.script == script_id:
            extra = getattr(entry, "extra", None)
            return extra if isinstance(extra, dict) else {}
    return None


def mark_advisory_echoed(
    *,
    advisory_name: str,
    category: str,
    target_name: str,
    project_path: str = "",
    echoed_sha256: "str | None" = None,
) -> None:
    """Append an ``advisory.echoed/<name>`` marker after verbatim echo."""
    extra: "dict | None" = {"echoed_sha256": echoed_sha256} if echoed_sha256 else None
    record_marker(
        script=advisory_echoed_script_id(advisory_name),
        category=category, target_name=target_name, project_path=project_path, extras=extra,
    )
