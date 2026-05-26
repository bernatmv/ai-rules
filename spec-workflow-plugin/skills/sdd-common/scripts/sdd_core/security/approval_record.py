"""Typed approval record — single source of truth for on-disk shape.

``ApprovalRecord`` and ``Verification`` are both frozen dataclasses
(matches the ``PipelineTodo`` / ``LedgerEntry`` / ``ReferenceAckEntry``
convention). Mutation goes through ``dataclasses.replace``; field
evolution stays observable in call-site diffs.

Parsing is robust: ``from_dict`` never raises on untrusted input.
Every failure mode yields an ``ApprovalRecord`` with
``schema_state="malformed"`` and a human-readable reason on the
embedded ``verification`` object, so read paths stay total.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Callable, Literal, Optional

# Single source of truth for accepted categories.
from sdd_core.category_registry import known_categories

__all__ = [
    "ApprovalRecord",
    "Verification",
    "VerificationState",
    "SchemaState",
    "register_approval_validator",
    "reset_approval_validators",
    "approval_validators",
]


_validators: list[Callable[["ApprovalRecord"], None]] = []


def register_approval_validator(
    fn: Callable[["ApprovalRecord"], None],
) -> None:
    """Add a post-parse validator. Raise ``ValueError`` to flag malformed."""
    _validators.append(fn)


def reset_approval_validators() -> None:
    _validators.clear()


def approval_validators() -> tuple[Callable[["ApprovalRecord"], None], ...]:
    return tuple(_validators)


SchemaState = Literal["current", "legacy", "malformed"]


class VerificationState(str, Enum):
    """Verification enum — 3.10-compatible (``class Foo(str, Enum)``)."""

    CURRENT = "current"
    DRIFTED = "drifted"
    PENDING_MIGRATION = "pending-migration"
    MALFORMED = "malformed"


@dataclass(frozen=True)
class Verification:
    state: VerificationState
    lastVerifiedAt: str
    lastHash: str
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "lastVerifiedAt": self.lastVerifiedAt,
            "lastHash": self.lastHash,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: "dict | None") -> "Verification | None":
        if not data:
            return None
        raw_state = data.get("state", "pending-migration")
        try:
            state = VerificationState(raw_state)
        except ValueError:
            state = VerificationState.MALFORMED
        return cls(
            state=state,
            lastVerifiedAt=str(data.get("lastVerifiedAt") or ""),
            lastHash=str(data.get("lastHash") or ""),
            reason=str(data.get("reason") or ""),
        )


_REQUIRED_IDENTITY = (
    "id", "title", "category", "categoryName", "status", "createdAt",
)
_MIGRATION_GATED = ("canonicalPath", "contentHash")


@dataclass(frozen=True)
class ApprovalRecord:
    id: str
    title: str
    category: str                 # validated via category_registry
    categoryName: str
    type: Literal["document", "action"]
    filePath: str
    canonicalPath: str
    contentHash: str
    verification: Verification
    authorizedBy: Optional[dict]   # reserved for signature payloads
    status: Literal["pending", "approved", "rejected", "needs_revision"]
    createdAt: str
    respondedAt: Optional[str] = None
    response: Optional[str] = None
    filePaths: tuple[str, ...] = field(default_factory=tuple)
    schema_state: SchemaState = "current"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["verification"] = self.verification.to_dict()
        data["filePaths"] = list(self.filePaths)
        data.pop("schema_state")
        return data

    def with_verification(self, v: Verification) -> "ApprovalRecord":
        """Convenience for the one write site in ``update-status.py``."""
        return replace(self, verification=v)

    @classmethod
    def _malformed(cls, reason: str) -> "ApprovalRecord":
        empty = Verification(
            state=VerificationState.MALFORMED,
            lastVerifiedAt="",
            lastHash="",
            reason=reason,
        )
        return cls(
            id="", title="", category="", categoryName="",
            type="document", filePath="", canonicalPath="",
            contentHash="", verification=empty, authorizedBy=None,
            status="pending", createdAt="",
            filePaths=(), schema_state="malformed",
        )

    @classmethod
    def from_dict(cls, data: dict) -> "ApprovalRecord":
        try:
            if not isinstance(data, dict):
                return cls._malformed("payload is not a JSON object")
            missing_core = [k for k in _REQUIRED_IDENTITY if not data.get(k)]
            if missing_core:
                return cls._malformed(
                    f"missing required fields: {', '.join(missing_core)}"
                )
            if data["category"] not in known_categories():
                return cls._malformed(
                    f"unknown category {data['category']!r}"
                )
            verification = Verification.from_dict(data.get("verification"))
            if (
                verification is not None
                and verification.state is VerificationState.MALFORMED
            ):
                return cls._malformed(
                    f"invalid verification.state "
                    f"{data.get('verification')!r}"
                )
            legacy = verification is None or any(
                k not in data for k in _MIGRATION_GATED
            )
            record = cls(
                id=str(data["id"]),
                title=str(data["title"]),
                category=str(data["category"]),
                categoryName=str(data["categoryName"]),
                type=str(data.get("type", "document")),  # type: ignore[arg-type]
                filePath=str(data.get("filePath") or ""),
                canonicalPath=str(data.get("canonicalPath") or ""),
                contentHash=str(data.get("contentHash") or ""),
                verification=verification or Verification(
                    state=VerificationState.PENDING_MIGRATION,
                    lastVerifiedAt="",
                    lastHash="",
                    reason="pending migration to canonical-path schema",
                ),
                authorizedBy=data.get("authorizedBy"),
                status=str(data.get("status", "pending")),  # type: ignore[arg-type]
                createdAt=str(data["createdAt"]),
                respondedAt=data.get("respondedAt"),
                response=data.get("response"),
                filePaths=tuple(data.get("filePaths") or ()),
                schema_state="legacy" if legacy else "current",
            )
            for validator in _validators:
                try:
                    validator(record)
                except ValueError as exc:
                    return cls._malformed(f"validator failed: {exc}")
            return record
        except (KeyError, TypeError, ValueError) as exc:
            return cls._malformed(f"parse error: {exc}")
