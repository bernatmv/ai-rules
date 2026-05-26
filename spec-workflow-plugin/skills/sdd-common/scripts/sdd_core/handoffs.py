"""Handoff registry loader for SDD scripts.

Schema and field semantics live in ``scripts/handoff-registry.json``'s
``_doc`` section.
"""
from __future__ import annotations

import functools
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from sdd_core import paths

__all__ = [
    "HANDOFF_REGISTRY_FILENAME",
    "Handoff",
    "current_script_id",
    "load_registry",
    "handoffs_for",
    "script_id",
]

HANDOFF_REGISTRY_FILENAME = "handoff-registry.json"

KNOWN_CTX_PLACEHOLDERS: frozenset[str] = frozenset({
    "workspace", "target", "target_with_repo", "phase", "category", "feature", "repo_id",
})

# Per-process script-id override populated by :func:`script_id`. The
# decorator is opt-in for shims that present multiple ids by phase
# (``pipeline-tick.py:phase=launch`` vs ``:phase=post-review``); the
# default derivation (:func:`current_script_id`) covers everything else.
_SCRIPT_ID_OVERRIDE: str | None = None


@dataclass(frozen=True)
class Handoff:
    """One next-action command surfaced on a success envelope.

    ``id`` is the symbolic identifier referenced from the workflow
    graph. ``command`` is a literal shell-style string with optional
    ``{ctx.<field>}`` placeholders the binder substitutes. ``note`` is
    a short rationale shown to the agent (one line, ≤80 chars).
    """

    id: str
    command: str
    note: str = ""

    def to_dict(self) -> dict:
        payload: dict = {"id": self.id, "command": self.command}
        if self.note:
            payload["note"] = self.note
        return payload


def current_script_id() -> str:
    """Return the canonical handoff id for the current script.

    Resolution order:

    1. The :func:`script_id` decorator override when set.
    2. ``sys.argv[0]`` resolved to a path relative to the
       ``scripts/`` root (sibling of ``prompt-registry.json``).
    3. Bare ``sys.argv[0]`` basename when the path can't be located
       under the scripts root (test invocations, repl, etc.).

    Mirrors :func:`sdd_core.reference_ledger.reference_read_script_id`'s
    "derive from sys.argv[0]" pattern so no shim ever authors a
    ``__sdd_script_id__`` constant by hand.
    """
    if _SCRIPT_ID_OVERRIDE:
        return _SCRIPT_ID_OVERRIDE
    raw = sys.argv[0] if sys.argv else ""
    if not raw:
        return ""
    candidate = Path(raw).resolve(strict=False)
    scripts_root = _scripts_root_or_none()
    if scripts_root is not None:
        try:
            rel = candidate.relative_to(scripts_root)
            return rel.as_posix()
        except ValueError:
            pass
    # Fall back to the basename (without the .py extension) so a script
    # invoked outside the canonical layout still produces a stable id.
    name = Path(raw).name
    if name.endswith(".py"):
        name = name[:-3]
    return name


def _scripts_root_or_none() -> Path | None:
    """Locate the ``scripts/`` root containing ``prompt-registry.json``.

    Walks up from this module's directory until the registry-bearing
    directory is found. Returns ``None`` when the layout differs (e.g.
    a vendored copy that lifted ``sdd_core/`` out of the original tree)
    so callers degrade to the basename fallback rather than crash.
    """
    here = Path(__file__).resolve().parent  # sdd_core/
    parent = here.parent  # scripts/
    if (parent / paths.PROMPT_REGISTRY_FILENAME).is_file():
        return parent
    return None


def _registry_path() -> Path | None:
    root = _scripts_root_or_none()
    if root is None:
        return None
    return root / HANDOFF_REGISTRY_FILENAME


def load_registry(path: str | Path | None = None) -> dict:
    """Load the handoff registry, returning an empty schema on miss.

    Missing-file is acceptable (returns the empty schema). Malformed
    JSON or unexpected top-level shape raises :class:`RuntimeError` —
    a corrupt registry is a developer bug, not a runtime-recoverable
    state. ``path`` overrides the auto-resolved location for tests.
    """
    if path is not None:
        registry_path: Path | None = Path(path)
    else:
        registry_path = _registry_path()
    if registry_path is None or not registry_path.is_file():
        return {"schemaVersion": "1.0.0", "scripts": {}}
    try:
        with open(registry_path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Failed to load handoff registry at {registry_path}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise RuntimeError(
            f"Handoff registry at {registry_path} must be a JSON object; "
            f"got {type(data).__name__}"
        )
    data.setdefault("scripts", {})
    _assert_no_doubled_target_repo_id(data, registry_path)
    _assert_known_ctx_placeholders(data, registry_path)
    return data


_DOUBLED_PLACEHOLDER = "{ctx.target}/{ctx.repo_id}"


def _assert_no_doubled_target_repo_id(data: dict, source: Path) -> None:
    """Reject ``{ctx.target}/{ctx.repo_id}`` literal in any handoff command.

    When ``ctx.target`` already encodes the slash form, the doubled
    placeholder expands to ``<feature>/<repo-id>/<repo-id>``. The
    canonical replacement is ``{ctx.target_with_repo}``.
    """
    scripts = data.get("scripts") or {}
    for script_id_value, entry in scripts.items():
        if not isinstance(entry, dict):
            continue
        for handoff in entry.get("handoffs") or []:
            if not isinstance(handoff, dict):
                continue
            command = str(handoff.get("command") or "")
            if _DOUBLED_PLACEHOLDER in command:
                raise RuntimeError(
                    f"Handoff registry at {source} contains the legacy "
                    f"`{_DOUBLED_PLACEHOLDER}` placeholder in script "
                    f"{script_id_value!r}. Replace with "
                    "`{ctx.target_with_repo}`."
                )


def _assert_known_ctx_placeholders(data: dict, source: Path) -> None:
    """Raise ValueError when any registry string uses an unknown ``{ctx.X}`` placeholder.

    Walks every literal-``command``, every emitter ``kwargs`` value, and
    every ``note`` so the validator covers emitter-pull rows too.
    """
    scripts = data.get("scripts") or {}
    for script_id_value, entry in scripts.items():
        if not isinstance(entry, dict):
            continue
        for handoff in entry.get("handoffs") or []:
            if not isinstance(handoff, dict):
                continue
            strings: list[str] = [
                str(handoff.get("command") or ""),
                str(handoff.get("note") or ""),
            ]
            kwargs = handoff.get("kwargs") or {}
            if isinstance(kwargs, dict):
                strings.extend(
                    str(v) for v in kwargs.values() if isinstance(v, str)
                )
            for source_str in strings:
                for match in re.finditer(
                    r"\{ctx\.([A-Za-z_][A-Za-z0-9_]*)\}", source_str,
                ):
                    field_name = match.group(1)
                    if field_name not in KNOWN_CTX_PLACEHOLDERS:
                        raise ValueError(
                            f"Handoff registry at {source}: script "
                            f"{script_id_value!r} uses unknown "
                            f"placeholder {{ctx.{field_name}}}. "
                            f"Known: {sorted(KNOWN_CTX_PLACEHOLDERS)}"
                        )


_PLACEHOLDER_RE = re.compile(r"\{ctx\.(?P<key>[A-Za-z_][A-Za-z0-9_]*)\}")


def _bind_placeholders(template: str, ctx: dict | object | None) -> str:
    """Substitute ``{ctx.<key>}`` placeholders in *template* against *ctx*.

    Missing keys are preserved verbatim so the agent sees the unbound
    placeholder rather than an empty string — the bug surfaces at the
    handoff site instead of silently producing a malformed command.
    Accepts a dict, a frozen dataclass exposing attribute access, or
    ``None`` (bypasses substitution).
    """
    if ctx is None:
        return template

    def _lookup(name: str) -> str | None:
        if isinstance(ctx, dict):
            value = ctx.get(name)
        else:
            value = getattr(ctx, name, None)
        if value is None:
            return None
        return str(value)

    def _replace(match: "re.Match[str]") -> str:
        key = match.group("key")
        value = _lookup(key)
        return match.group(0) if value is None else value

    return _PLACEHOLDER_RE.sub(_replace, template)


def _resolve_emitter_command(
    emitter_name: str,
    kwargs_template: dict,
    ctx: dict | object | None,
) -> str:
    """Resolve an emitter-form handoff to a literal shim line.

    Looks up ``sdd_core.command_templates.<emitter_name>``, binds each
    kwarg value's placeholders against *ctx*, and dispatches to the
    emitter. Empty kwargs values are dropped before dispatch so the
    emitter's defaults take effect (e.g. ``review_skill`` /
    ``doc_list`` resolve from the category at the emitter site).

    Returns an empty string when the emitter is missing or raises —
    callers fall back to the literal ``command`` field, keeping the
    registry as a routing surface even when the emitter shape drifts.
    """
    try:
        from sdd_core import command_templates as _ct
    except ImportError:
        return ""
    emitter = getattr(_ct, emitter_name, None)
    if emitter is None or not callable(emitter):
        return ""
    bound: dict[str, str] = {}
    for key, raw in (kwargs_template or {}).items():
        if not isinstance(raw, str):
            continue
        value = _bind_placeholders(raw, ctx)
        # If a placeholder did not resolve and the result still carries
        # ``{ctx.X}``, drop the kwarg so the emitter's default wins.
        if "{ctx." in value:
            continue
        if value:
            bound[str(key)] = value
    try:
        return str(emitter(**bound))
    except (TypeError, ValueError, KeyError):
        return ""


def handoffs_for(
    script_id_value: str,
    ctx: dict | object | None = None,
    *,
    registry: dict | None = None,
) -> list[dict]:
    """Return rendered handoffs for *script_id_value* bound against *ctx*.

    Empty list when the script id is absent from the registry — every
    caller can pass the result straight to ``output.success(handoffs=…)``
    without an existence check. Each entry is a JSON-serialisable dict
    matching :meth:`Handoff.to_dict`.

    Rows may declare an optional ``emitter`` field (with ``kwargs``) so
    the rendered command comes from
    ``sdd_core.command_templates.<emitter>`` rather than a static
    string. The literal-``command`` path remains the fallback for rows
    whose flag set is workspace/phase-stable.
    """
    reg = registry if registry is not None else load_registry()
    scripts = reg.get("scripts") or {}
    entry = scripts.get(script_id_value) or {}
    raw_handoffs = entry.get("handoffs") or []
    rendered: list[dict] = []
    for item in raw_handoffs:
        if not isinstance(item, dict):
            continue
        ho_id = str(item.get("id") or "")
        note_template = str(item.get("note") or "")
        emitter_name = str(item.get("emitter") or "")
        command = ""
        if emitter_name:
            kwargs_template = item.get("kwargs") or {}
            if isinstance(kwargs_template, dict):
                command = _resolve_emitter_command(
                    emitter_name, kwargs_template, ctx,
                )
        if not command:
            command = _bind_placeholders(
                str(item.get("command") or ""), ctx,
            )
        note = _bind_placeholders(note_template, ctx)
        if not ho_id or not command:
            continue
        rendered.append(
            Handoff(id=ho_id, command=command, note=note).to_dict()
        )
    return rendered


def script_id(value: str) -> Callable[[Callable], Callable]:
    """Decorator: override :func:`current_script_id` for the wrapped function.

    Use on phase-keyed dispatchers (``pipeline-tick.py:phase=launch``)
    where the script presents multiple ids depending on which phase
    handler is active. Sets a module-level override for the duration of
    the call; clears it on exit so concurrent calls in tests don't
    leak state.
    """
    if not isinstance(value, str) or not value:
        raise ValueError("script_id() requires a non-empty string")

    def _decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def _wrapped(*args, **kwargs):  # type: ignore[no-untyped-def]
            global _SCRIPT_ID_OVERRIDE
            previous = _SCRIPT_ID_OVERRIDE
            _SCRIPT_ID_OVERRIDE = value
            try:
                return func(*args, **kwargs)
            finally:
                _SCRIPT_ID_OVERRIDE = previous

        return _wrapped

    return _decorator
