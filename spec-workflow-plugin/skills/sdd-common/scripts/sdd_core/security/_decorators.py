"""Composable decorators for the security primitives.

:func:`with_audit` wraps any registered primitive and routes every
public method call through :func:`audit_sink().emit` so operators
opting into structured-trace observability gain a per-call audit
record without per-callsite edits.

Implementation note: the wrapper is a delegating proxy (no class
synthesis, no ``__dict__`` copy) so slotted primitives
(``SecurityConfig``) and context-manager primitives (``LockedStore``)
both compose cleanly. ``isinstance(wrapped, OriginalProtocol)`` keeps
returning True because every Protocol in :mod:`sdd_core.security` is
``runtime_checkable`` and inspects attribute presence, which the proxy
forwards through ``__getattr__``.
"""
from __future__ import annotations

import functools
from typing import Any, TypeVar

from . import audit

__all__ = ["with_audit"]

_T = TypeVar("_T")


class _AuditProxy:
    """Delegating proxy — every public method routes through the audit sink.

    Data attributes (``algo``, ``protocol_version``, dataclass fields)
    pass through unchanged and emit no event — auditors only care about
    side-effecting calls. Underscore-prefixed attributes pass through
    raw so private internals stay reachable.
    """

    __slots__ = ("_target", "_channel")

    def __init__(self, target: Any, channel: str) -> None:
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_channel", channel)

    def __getattr__(self, name: str) -> Any:
        target = object.__getattribute__(self, "_target")
        attr = getattr(target, name)
        if not callable(attr) or name.startswith("_"):
            return attr
        channel = object.__getattribute__(self, "_channel")
        cls_name = type(target).__name__

        @functools.wraps(attr)
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            try:
                result = attr(*args, **kwargs)
            except Exception as exc:
                audit.audit_sink().emit(
                    channel=channel,
                    entry={
                        "primitive": cls_name,
                        "method": name,
                        "ok": False,
                        "error": type(exc).__name__,
                    },
                )
                raise
            audit.audit_sink().emit(
                channel=channel,
                entry={
                    "primitive": cls_name,
                    "method": name,
                    "ok": True,
                },
            )
            return result

        return _wrapped

    def __enter__(self) -> Any:
        # Explicit so context-manager primitives (``LockedStore``) compose
        # without losing the audit trace on enter / exit.
        target = object.__getattribute__(self, "_target")
        method = type(target).__enter__
        channel = object.__getattribute__(self, "_channel")
        cls_name = type(target).__name__
        try:
            result = method(target)
        except Exception as exc:
            audit.audit_sink().emit(
                channel=channel,
                entry={
                    "primitive": cls_name, "method": "__enter__",
                    "ok": False, "error": type(exc).__name__,
                },
            )
            raise
        audit.audit_sink().emit(
            channel=channel,
            entry={"primitive": cls_name, "method": "__enter__", "ok": True},
        )
        # Returning ``self`` keeps the ``with`` binding wrapped so
        # method calls inside the block stay audited.
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        target = object.__getattribute__(self, "_target")
        method = type(target).__exit__
        channel = object.__getattribute__(self, "_channel")
        cls_name = type(target).__name__
        try:
            result = method(target, exc_type, exc, tb)
        except Exception as raised:
            audit.audit_sink().emit(
                channel=channel,
                entry={
                    "primitive": cls_name, "method": "__exit__",
                    "ok": False, "error": type(raised).__name__,
                },
            )
            raise
        audit.audit_sink().emit(
            channel=channel,
            entry={"primitive": cls_name, "method": "__exit__", "ok": True},
        )
        return result


def with_audit(primitive: _T, *, channel: str = "security-call") -> _T:
    """Wrap *primitive* so every public-method call surfaces in the audit sink.

    Returns a delegating proxy that forwards attribute access (and
    context-manager protocol) to the wrapped primitive. Slotted classes
    and context-manager primitives are both supported.
    """
    return _AuditProxy(primitive, channel)  # type: ignore[return-value]
