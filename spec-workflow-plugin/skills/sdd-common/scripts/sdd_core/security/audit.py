"""Pluggable audit-sink seam.

Today every audit-log writer composes :func:`reference_ledger.append`
or :func:`output.atomic_write_json` directly. Audit-driven prescriptions
("hash-chain entries", "sign with HSM key", "fan out to syslog") become
a one-class swap behind :class:`AuditSink`.

Default sink delegates to ``reference_ledger.append`` so every
existing audit-log entry continues to land in the canonical ledger.
"""
from __future__ import annotations

from typing import Final, Mapping, Protocol, runtime_checkable

from ._seam import Seam, dump_security_provenance

_AUDIT_LOG_FILENAME_FORMAT: Final[str] = "{channel}-audit.log"

__all__ = [
    "AuditSink",
    "PROTOCOL_VERSION",
    "audit_sink",
    "set_audit_sink",
    "reset_audit_sink",
    "build_audit_entry",
    "EVENT_TYPES",
    "EVENT_APPROVAL_STATUS_CHANGE",
    "EVENT_APPROVAL_ATTEMPT_REJECTED",
    "EVENT_FEATURE_BOOTSTRAPPED",
    "EVENT_FEATURE_BOOTSTRAP_REPLACED",
    "EVENT_FEATURE_BOOTSTRAP_REPLACED_COMMITTED",
    "EVENT_REVIEW_RETROACTIVE_COMPLETED",
]

PROTOCOL_VERSION = 1

# Canonical audit-event vocabulary. Adding a new type is one row;
# ``build_audit_entry`` rejects unregistered types so the registry is
# the single source of truth (closed for modification, open for
# extension).
EVENT_APPROVAL_STATUS_CHANGE = "approval-status-change"
EVENT_APPROVAL_ATTEMPT_REJECTED = "approval-attempt-rejected"
EVENT_FEATURE_BOOTSTRAPPED = "feature-bootstrapped"
EVENT_FEATURE_BOOTSTRAP_REPLACED = "feature-bootstrap-replaced"
EVENT_FEATURE_BOOTSTRAP_REPLACED_COMMITTED = "feature-bootstrap-replaced-committed"
EVENT_REVIEW_RETROACTIVE_COMPLETED = "review-retroactive-completed"

EVENT_TYPES: frozenset[str] = frozenset({
    EVENT_APPROVAL_STATUS_CHANGE,
    EVENT_APPROVAL_ATTEMPT_REJECTED,
    EVENT_FEATURE_BOOTSTRAPPED,
    EVENT_FEATURE_BOOTSTRAP_REPLACED,
    EVENT_FEATURE_BOOTSTRAP_REPLACED_COMMITTED,
    EVENT_REVIEW_RETROACTIVE_COMPLETED,
})


@runtime_checkable
class AuditSink(Protocol):
    """``entry`` is a read-only Mapping; sinks must not mutate it."""

    protocol_version: int

    def emit(self, *, channel: str, entry: Mapping[str, object]) -> None: ...

    def path(self, *, channel: str, project_path: str = "") -> "str | None": ...

    def format(self) -> str: ...


_RESERVED_LEDGER_FIELDS = frozenset(
    {"target_name", "category", "script", "type", "project_path"},
)


class _LedgerSink:
    """Default sink: writes the canonical ledger and mirrors to the flat-file audit log.

    ``entry`` must carry ``target_name`` and ``category``; missing fields raise ``ValueError``.
    """

    protocol_version = PROTOCOL_VERSION

    def emit(self, *, channel: str, entry: Mapping[str, object]) -> None:
        self._append_to_canonical_ledger(channel=channel, entry=entry)
        self._mirror_to_flat_file(channel=channel, entry=entry)

    def path(self, *, channel: str, project_path: str = "") -> "str | None":
        from sdd_core import paths as _paths

        try:
            workflow_root = _paths.find_workflow_root(project_path or ".")
        except FileNotFoundError:
            return None
        return str(
            workflow_root
            / _paths.WORKFLOW_DIR
            / _AUDIT_LOG_FILENAME_FORMAT.format(channel=channel)
        )

    def format(self) -> str:
        return "flat-jsonl"

    def _append_to_canonical_ledger(
        self, *, channel: str, entry: Mapping[str, object],
    ) -> None:
        from sdd_core.reference_ledger import append as _ledger_append

        target_name = str(entry.get("target_name") or "")
        if not target_name:
            raise ValueError(
                f"audit entry on channel {channel!r} missing required "
                "'target_name'; channel name is not a valid path component."
            )
        category = str(entry.get("category") or "")
        if not category:
            raise ValueError(
                f"audit entry on channel {channel!r} missing required "
                "'category'."
            )
        script = str(entry.get("script") or entry.get("type") or "audit")
        project_path = str(entry.get("project_path", ""))
        extra = {
            k: v for k, v in entry.items()
            if k not in _RESERVED_LEDGER_FIELDS
        }
        _ledger_append(
            category=category,
            target_name=target_name,
            script=script,
            project_path=project_path,
            extra=extra,
        )

    def _mirror_to_flat_file(
        self, *, channel: str, entry: Mapping[str, object],
    ) -> None:
        from sdd_core import output as _output

        project_path = str(entry.get("project_path") or "")
        target = self.path(channel=channel, project_path=project_path)
        if not target:
            return
        try:
            _output.append_jsonl(target, dict(entry))
        except OSError:
            pass


_seam: Seam[AuditSink] = Seam(
    name="AuditSink",
    protocol=AuditSink,
    default=_LedgerSink(),
    protocol_version=PROTOCOL_VERSION,
)

audit_sink = _seam.get


def set_audit_sink(sink: AuditSink) -> None:
    _seam.set(sink)


def reset_audit_sink() -> None:
    _seam.reset()


def build_audit_entry(
    *,
    type: str,
    actor: str,
    actor_kind: "object",
    timestamp: str,
    approval_id: "str | None" = None,
    harness_name: "str | None" = None,
    **extra: object,
) -> dict[str, object]:
    """Construct an approval-flow audit entry with provenance.

    Single emitter for every approval audit dict — adding a new field
    lands in one place. Embeds :func:`dump_security_provenance` under
    ``securityProvenance`` so downstream readers can attribute the
    entry to the seam impls in force at write time.

    ``actor_kind`` may be either an :class:`ActorKind` enum or already a
    string (the ``.value``); the builder normalises to a string.

    ``harness_name`` is resolved lazily from ``sdd_core.harness``
    when ``None`` is passed so callers do not need to know the
    adapter; tests pass an explicit value to avoid the side effect.
    """
    if type not in EVENT_TYPES:
        raise TypeError(
            f"unknown audit event type {type!r}; register it in EVENT_TYPES"
        )
    if hasattr(actor_kind, "value"):
        actor_kind_str = str(actor_kind.value)
    else:
        actor_kind_str = str(actor_kind)
    if harness_name is None:
        try:
            from sdd_core.harness import load_adapter
            harness_name = load_adapter().name
        except (ImportError, AttributeError):
            harness_name = "unknown"
    entry: dict[str, object] = {
        "timestamp": timestamp,
        "type": type,
        "actor": actor,
        "actor_kind": actor_kind_str,
        "harness_name": harness_name,
        "securityProvenance": dump_security_provenance(),
    }
    if approval_id is not None:
        entry["approvalId"] = approval_id
    entry.update(extra)
    return entry
