"""Pluggable harness-identity detector registry.

Detectors resolve the active harness name from context (env, state file,
safe default). They register at import time via :func:`register_detector`
and run in priority order — lowest priority first. The registry always
resolves: higher-priority detectors consume strong signals, a final
safe-default detector guarantees totality.

Errors are reserved for *explicit contradictions* — a user-supplied
value that is wrong. Absence of signal is handled by the safe-default
detector with a loud warning, never a hard failure.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Mapping, Optional

from .defaults import DEFAULT_ADAPTER_ORDER, SafeDefaultError, resolve_safe_default
from .registry import ADAPTERS, available_adapter_names

__all__ = [
    "DetectionContext",
    "DetectionOutcome",
    "Detector",
    "DETECTORS",
    "PROBE_HARNESS_RESET_BARE",
    "register_detector",
    "resolve_detection",
    "HarnessContradictionError",
]


# Bare recovery command — detectors emit this shim-less form so layers
# without the shim can still read it. Workspace-health callers wrap it
# with the ``.spec-workflow/sdd`` prefix via
# :data:`sdd_core.harness.PROBE_HARNESS_RESET_COMMAND`.
PROBE_HARNESS_RESET_BARE = "util/probe-harness.py --reset"


DetectionSource = Literal["override", "state_file", "env_marker", "safe_default"]


@dataclass(frozen=True)
class DetectionContext:
    project_path: str
    env: Mapping[str, str]
    state_path: str


@dataclass(frozen=True)
class DetectionOutcome:
    adapter_name: str
    source: DetectionSource
    warn: Optional[str] = None
    persist: bool = False


Detector = Callable[[DetectionContext], "DetectionOutcome | None"]


class HarnessContradictionError(ValueError):
    """Raised when a detector sees an explicit contradiction.

    ``message`` is a short identifier-style phrase; ``hint`` and
    ``next_action_command`` are forwarded to ``output.error`` by the
    loader when the exception bubbles into a CLI boundary.
    """

    def __init__(
        self,
        message: str,
        *,
        hint: str = "",
        next_action_command: str = "",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.next_action_command = next_action_command


DETECTORS: list[tuple[int, Detector]] = []


def register_detector(priority: int) -> Callable[[Detector], Detector]:
    """Register a detector at the given priority (lower runs first).

    Re-registering the same priority raises ``ValueError`` at import
    time so accidental duplicates surface before the loader is called.
    """
    def _wrap(fn: Detector) -> Detector:
        for existing_priority, existing in DETECTORS:
            if existing_priority == priority and existing is not fn:
                raise ValueError(
                    f"Detector priority {priority} already registered by "
                    f"{getattr(existing, '__name__', repr(existing))}"
                )
        DETECTORS.append((priority, fn))
        DETECTORS.sort(key=lambda entry: entry[0])
        return fn
    return _wrap


def _available_names_csv() -> str:
    return ", ".join(available_adapter_names())


@register_detector(priority=10)
def _override_detector(ctx: DetectionContext) -> Optional[DetectionOutcome]:
    raw = ctx.env.get("SDD_HARNESS_OVERRIDE", "").strip()
    if not raw:
        return None
    if raw not in ADAPTERS:
        raise HarnessContradictionError(
            "unknown_harness_override",
            hint=(
                f"SDD_HARNESS_OVERRIDE={raw!r} is not a registered adapter. "
                f"Available: {_available_names_csv()}"
            ),
            next_action_command="unset SDD_HARNESS_OVERRIDE",
        )
    return DetectionOutcome(adapter_name=raw, source="override")


@register_detector(priority=20)
def _state_file_detector(ctx: DetectionContext) -> Optional[DetectionOutcome]:
    path = ctx.state_path
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, json.JSONDecodeError) as exc:
        raise HarnessContradictionError(
            "malformed_harness_state",
            hint=f"Cannot read {path}: {exc}",
            next_action_command=PROBE_HARNESS_RESET_BARE,
        ) from exc
    if not isinstance(data, dict):
        raise HarnessContradictionError(
            "malformed_harness_state",
            hint=f"{path} is not a JSON object",
            next_action_command=PROBE_HARNESS_RESET_BARE,
        )
    name = data.get("harness")
    if not isinstance(name, str) or name not in ADAPTERS:
        raise HarnessContradictionError(
            "unknown_harness_state",
            hint=(
                f"{path} names harness={name!r}; "
                f"available: {_available_names_csv()}"
            ),
            next_action_command=(
                f"{PROBE_HARNESS_RESET_BARE} && util/probe-harness.py"
            ),
        )
    # Cross-check the cached state against current env markers: if the
    # env resolves to a different adapter, raise rather than returning
    # the stale state (silent fall-through would mis-route subsequent
    # ``Action.todo_write`` envelopes). Agreement or no marker keeps
    # the cache.
    env_name = _match_env_marker(ctx.env)
    if env_name and env_name != name:
        raise HarnessContradictionError(
            "harness_state_env_mismatch",
            hint=(
                f"{path} says harness={name!r} but env markers resolve "
                f"to {env_name!r}. Running on the wrong harness risks "
                f"emitting tool calls the host can't execute."
            ),
            next_action_command=PROBE_HARNESS_RESET_BARE,
        )
    return DetectionOutcome(adapter_name=name, source="state_file")


# Ordered env-marker table: Claude Code first (most specific markers),
# Cursor last (the safe fall-back). Adding a host is a new tuple row;
# the resolver helper below never changes. Claude Code exports
# ``CLAUDECODE`` / ``CLAUDE_CODE_ENTRYPOINT`` in addition to
# ``CLAUDE_CODE_VERSION`` — any one is a strong marker.
def _claude_code_present(env: Mapping[str, str]) -> bool:
    return (
        bool(env.get("CLAUDE_CODE_VERSION"))
        or env.get("CLAUDECODE") == "1"
        or bool(env.get("CLAUDE_CODE_ENTRYPOINT"))
    )


_ENV_MARKER_TABLE: "tuple[tuple[Callable[[Mapping[str, str]], bool], str], ...]" = (
    (
        lambda env: (
            env.get("CLAUDE_CODE_TASK_VARIANT") == "1"
            and _claude_code_present(env)
        ),
        "claude-code-task-variant",
    ),
    (
        lambda env: _claude_code_present(env),
        "claude-code-standard",
    ),
    (
        lambda env: bool(
            env.get("CURSOR_AGENT") or env.get("CURSOR_WORKSPACE")
        ),
        "cursor",
    ),
)


def _match_env_marker(env: Mapping[str, str]) -> Optional[str]:
    for predicate, adapter_name in _ENV_MARKER_TABLE:
        if predicate(env):
            return adapter_name
    return None


@register_detector(priority=30)
def _env_marker_detector(ctx: DetectionContext) -> Optional[DetectionOutcome]:
    name = _match_env_marker(ctx.env)
    if name is None or name not in ADAPTERS:
        return None
    warn = (
        f"harness.json missing; auto-probed {name!r} from env markers "
        "and wrote state file"
    )
    return DetectionOutcome(
        adapter_name=name, source="env_marker",
        warn=warn, persist=True,
    )


@register_detector(priority=90)
def _safe_default_detector(ctx: DetectionContext) -> Optional[DetectionOutcome]:
    try:
        name = resolve_safe_default(ctx.env)
    except SafeDefaultError as exc:
        raise HarnessContradictionError(
            "invalid_safe_default",
            hint=str(exc),
            next_action_command="unset SDD_HARNESS_DEFAULT",
        ) from exc
    warn = (
        f"no harness signals detected; defaulting to {name!r}. "
        "Run `util/probe-harness.py` to pin the correct adapter."
    )
    # Safe-default never persists — only confirmed signals
    # (override / state_file / env_marker) mint ``harness.json`` so a
    # missing env marker in one tick cannot entrench the fallback for
    # every subsequent call.
    return DetectionOutcome(
        adapter_name=name, source="safe_default",
        warn=warn, persist=False,
    )


def resolve_detection(ctx: DetectionContext) -> DetectionOutcome:
    """Walk the detector list in priority order.

    Returns the first non-``None`` outcome. The safe-default detector
    guarantees a resolution unless the registry is empty (raises). Any
    :class:`HarnessContradictionError` from a detector propagates so the
    loader can forward it to ``output.error``.
    """
    for _priority, detector in DETECTORS:
        outcome = detector(ctx)
        if outcome is not None:
            return outcome
    raise HarnessContradictionError(
        "no_detector_resolved",
        hint=(
            "Every detector returned None. DEFAULT_ADAPTER_ORDER was "
            f"{DEFAULT_ADAPTER_ORDER} but nothing registered."
        ),
    )
