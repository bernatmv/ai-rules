"""Validator registry.

The workflow graph at ``sdd_core/data/workflow-graph.json`` references
validators by id; every id must resolve to a registered function in
this package.

Registration is via the :func:`register` decorator — the function's
``__name__`` becomes the public id (snake_case, matching the graph).
"""
from __future__ import annotations

import argparse
from typing import Any, Callable

from sdd_core.pipeline_phases.types import Validator, ValidatorResult

__all__ = [
    "ValidatorResult",
    "register",
    "get_validator",
    "registered_ids",
    "REGISTRY",
]


# Public registry — keyed by validator id (the function's ``__name__``).
# Iteration order mirrors registration order so reviewer logs stay
# deterministic.
REGISTRY: "dict[str, Validator]" = {}


class _FunctionValidator:
    """Adapter that wraps a plain ``check(ctx, args)`` function as a Validator."""

    def __init__(self, name: str, fn: Callable[..., ValidatorResult]) -> None:
        self.id = name
        self._fn = fn

    def check(
        self,
        ctx: Any,
        args: argparse.Namespace | None = None,
    ) -> ValidatorResult:
        result = self._fn(ctx, args) if args is not None else self._fn(ctx)
        if isinstance(result, ValidatorResult):
            return result
        if isinstance(result, bool):
            return ValidatorResult(ok=result)
        if isinstance(result, dict):
            return ValidatorResult(
                ok=bool(result.get("ok", False)),
                code=str(result.get("code", "")),
                message=str(result.get("message", "")),
                details=result.get("details") or {},
            )
        raise TypeError(
            f"Validator {self.id!r} returned unsupported type: "
            f"{type(result).__name__}"
        )


def register(
    fn: "Callable[..., ValidatorResult] | None" = None,
    *,
    name: str | None = None,
) -> Any:
    """Register *fn* in :data:`REGISTRY` keyed by its ``__name__`` (or *name*).

    Usable as either ``@register`` or ``@register(name="…")``. Re-
    registering the same id is a hard error so accidental shadowing
    fails loudly at import time.
    """

    def _do_register(target: Callable[..., ValidatorResult]) -> Callable[..., ValidatorResult]:
        validator_id = name or target.__name__
        if validator_id in REGISTRY:
            raise ValueError(
                f"Validator {validator_id!r} already registered "
                f"(by {REGISTRY[validator_id]!r})"
            )
        REGISTRY[validator_id] = _FunctionValidator(validator_id, target)
        return target

    if fn is not None:
        return _do_register(fn)
    return _do_register


def get_validator(name: str) -> "Validator | None":
    """Return the registered validator for *name*, or ``None`` if absent."""
    return REGISTRY.get(name)


def registered_ids() -> tuple[str, ...]:
    """Return every registered validator id in declaration order."""
    return tuple(REGISTRY.keys())
