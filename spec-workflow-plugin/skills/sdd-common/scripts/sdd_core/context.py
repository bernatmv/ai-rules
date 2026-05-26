"""Workflow context resolver — resolves target/workspace/phase from
flag → session → manifest → gate → env → cwd (first non-empty wins)."""
from __future__ import annotations

import argparse
import functools
import inspect
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Final, Iterable, Mapping, Protocol, runtime_checkable

from sdd_core.paths import WORKSPACE_TRACKER_FILENAME as _TRACKER_FILENAME, GATE_SESSION_FILENAME as _GATE_SESSION_FILENAME  # noqa: E501

__all__ = [
    "WorkflowContext",
    "ContextResolver",
    "ResolverResult",
    "default_resolvers",
    "resolve_context",
    "with_context",
]


# Canonical fields a shim may request. Workflow graph
# ``context_needs`` entries are validated against this set.
CONTEXT_FIELDS: tuple[str, ...] = (
    "target",
    "workspace",
    "phase",
    "category",
    "repo_id",
)


_ENV_MAP: Final[Mapping[str, tuple[str, ...]]] = {
    "workspace": ("SDD_WORKSPACE",),
    "target": ("SDD_TARGET",),
    "phase": ("SDD_PHASE",),
    "category": ("SDD_CATEGORY",),
    "repo_id": ("SDD_REPO_ID",),
}


@dataclass(frozen=True)
class WorkflowContext:
    """Resolved workflow context. Frozen so callers cannot mutate the
    record after the resolver chain returns.

    ``resolved_from`` records the layer that produced each populated
    field (``"flag"`` / ``"session"`` / ``"manifest"`` / ``"gate"`` /
    ``"env"`` / ``"cwd"``). Fields the chain could not resolve appear
    as ``None`` and are absent from ``resolved_from``.
    """

    target: str | None = None
    workspace: str | None = None
    phase: str | None = None
    category: str | None = None
    repo_id: str | None = None
    resolved_from: Mapping[str, str] = field(default_factory=dict)

    @property
    def feature(self) -> str | None:
        if self.target is None:
            return None
        if "/" in self.target:
            return self.target.split("/", 1)[0]
        return self.target

    @property
    def target_with_repo(self) -> str | None:
        if self.target is None:
            return None
        if "/" in self.target:
            return self.target
        if self.repo_id:
            return f"{self.target}/{self.repo_id}"
        return None

    def to_dict(self) -> dict:
        """Serialise as a plain dict; ``None`` fields are dropped to align
        with :func:`sdd_core.output._envelope_extras`."""
        out: dict[str, Any] = {}
        for key in ("target", "workspace", "phase", "category", "repo_id"):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        if self.resolved_from:
            out["resolved_from"] = dict(self.resolved_from)
        return out

    def get(self, name: str) -> Any:
        return getattr(self, name, None)


@dataclass(frozen=True)
class ResolverResult:
    """One layer's contribution. ``source`` populates ``resolved_from``."""

    source: str
    values: Mapping[str, Any]


@runtime_checkable
class ContextResolver(Protocol):
    """Resolver Protocol. Implementations live close to the data they own
    (CLI args → ``cli``; current-target session → ``transient_state``;
    workspace tracker → ``workspace_tracker``)."""

    source: str

    def resolve(
        self,
        args: argparse.Namespace | None,
        *,
        needs: Iterable[str],
        env: Mapping[str, str],
    ) -> ResolverResult:
        ...


# ---------------------------------------------------------------------------
# Built-in resolvers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FlagResolver:
    source: str = "flag"

    def resolve(
        self,
        args: argparse.Namespace | None,
        *,
        needs: Iterable[str],
        env: Mapping[str, str],
    ) -> ResolverResult:
        values: dict[str, Any] = {}
        if args is None:
            return ResolverResult(source=self.source, values=values)
        for field_name in needs:
            value: Any = None
            if field_name == "workspace":
                # ``--workspace`` registered by ``strict_parser`` stores
                # to ``args.project_path``; ``add_workspace_arg`` stores
                # to ``args.workspace`` (default ``"."``, treated as
                # unspecified).
                value = getattr(args, "project_path", None)
                if value in (None, ""):
                    legacy = getattr(args, "workspace", None)
                    if legacy not in (None, "", "."):
                        value = legacy
            else:
                value = getattr(args, field_name, None)
            if value is not None and value != "":
                values[field_name] = value
        return ResolverResult(source=self.source, values=values)


@dataclass(frozen=True)
class _SessionResolver:
    """Reads ``current-target.json`` via ``transient_state``."""

    source: str = "session"

    def resolve(
        self,
        args: argparse.Namespace | None,
        *,
        needs: Iterable[str],
        env: Mapping[str, str],
    ) -> ResolverResult:
        # Lazy import: ``transient_state`` imports ``sdd_core.paths``
        # which already pulls in most of the core; deferring here keeps
        # ``sdd_core.context`` importable from contexts that don't yet
        # have a workflow root.
        from sdd_core.transient_state import read_current_target

        project_path = ""
        if args is not None:
            project_path = (
                getattr(args, "project_path", None)
                or getattr(args, "workspace", None)
                or ""
            )
            if project_path == ".":
                project_path = ""

        record = read_current_target(project_path)
        if not record:
            return ResolverResult(source=self.source, values={})

        wanted = set(needs)
        values: dict[str, Any] = {}
        for key in ("target", "phase", "repo_id", "category"):
            if key in wanted and record.get(key):
                values[key] = record[key]
        return ResolverResult(source=self.source, values=values)


@dataclass(frozen=True)
class _ManifestResolver:
    """Reads ``workspace-tracker.json`` for the active workspace."""

    source: str = "manifest"

    def resolve(
        self,
        args: argparse.Namespace | None,
        *,
        needs: Iterable[str],
        env: Mapping[str, str],
    ) -> ResolverResult:
        wanted = set(needs)
        if not wanted & {"target", "phase", "category", "repo_id"}:
            return ResolverResult(source=self.source, values={})

        workspace = _resolve_workspace_hint(args, env)
        if not workspace:
            return ResolverResult(source=self.source, values={})

        record = _load_tracker(Path(workspace))
        if not record:
            return ResolverResult(source=self.source, values={})

        values: dict[str, Any] = {}
        target = record.get("currentTarget") or record.get("current_target")
        if "target" in wanted and target:
            values["target"] = target
        phase = record.get("currentPhase") or record.get("current_phase")
        if "phase" in wanted and phase:
            values["phase"] = phase
        category = record.get("category")
        if "category" in wanted and category:
            values["category"] = category
        repo_id = record.get("currentRepoId") or record.get("current_repo_id")
        if "repo_id" in wanted and repo_id:
            values["repo_id"] = repo_id
        return ResolverResult(source=self.source, values=values)


@dataclass(frozen=True)
class _GateResolver:
    """Reads ``gate-session.json`` for the active doc target."""

    source: str = "gate"

    def resolve(
        self,
        args: argparse.Namespace | None,
        *,
        needs: Iterable[str],
        env: Mapping[str, str],
    ) -> ResolverResult:
        wanted = set(needs)
        if not wanted & {"target", "phase", "category"}:
            return ResolverResult(source=self.source, values={})

        workspace = _resolve_workspace_hint(args, env)
        if not workspace:
            return ResolverResult(source=self.source, values={})

        record = _load_gate_session(Path(workspace))
        if not record:
            return ResolverResult(source=self.source, values={})

        values: dict[str, Any] = {}
        for key in ("target", "phase", "category"):
            if key in wanted and record.get(key):
                values[key] = record[key]
        return ResolverResult(source=self.source, values=values)


@dataclass(frozen=True)
class _EnvResolver:
    source: str = "env"

    def resolve(
        self,
        args: argparse.Namespace | None,
        *,
        needs: Iterable[str],
        env: Mapping[str, str],
    ) -> ResolverResult:
        values: dict[str, Any] = {}
        wanted = set(needs)
        for field_name, env_keys in _ENV_MAP.items():
            if field_name not in wanted:
                continue
            for key in env_keys:
                value = env.get(key)
                if value:
                    values[field_name] = value
                    break
        return ResolverResult(source=self.source, values=values)


@dataclass(frozen=True)
class _CwdResolver:
    """Last-resort resolver — fills ``workspace`` from ``os.getcwd()``."""

    source: str = "cwd"

    def resolve(
        self,
        args: argparse.Namespace | None,
        *,
        needs: Iterable[str],
        env: Mapping[str, str],
    ) -> ResolverResult:
        if "workspace" not in set(needs):
            return ResolverResult(source=self.source, values={})
        return ResolverResult(
            source=self.source, values={"workspace": os.getcwd()}
        )


def _resolve_workspace_hint(
    args: argparse.Namespace | None, env: Mapping[str, str]
) -> str:
    """Return a workspace path from args / env / cwd for downstream resolvers."""
    if args is not None:
        candidate = (
            getattr(args, "project_path", None)
            or getattr(args, "workspace", None)
        )
        if candidate and candidate != ".":
            return candidate
    return env.get("SDD_WORKSPACE") or os.getcwd()


def _load_tracker(workspace: Path) -> Mapping[str, Any] | None:
    """Read the first ``workspace-tracker.json`` under
    ``<workspace>/<WORKFLOW_DIR>/<WORKSPACE_DIR>/*/``."""
    from sdd_core.paths import WORKFLOW_DIR, WORKSPACE_DIR_NAME

    base = workspace / WORKFLOW_DIR / WORKSPACE_DIR_NAME
    if not base.is_dir():
        return None
    try:
        for entry in base.iterdir():
            tracker = entry / _TRACKER_FILENAME
            if tracker.is_file():
                return json.loads(tracker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return None


def _load_gate_session(workspace: Path) -> Mapping[str, Any] | None:
    """Read the active ``gate-session.json`` (cross-cutting state)."""
    from sdd_core.paths import STATE_DIR_NAME, WORKFLOW_DIR

    candidate = workspace / WORKFLOW_DIR / STATE_DIR_NAME / _GATE_SESSION_FILENAME
    if not candidate.is_file():
        return None
    try:
        return json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def default_resolvers() -> tuple[ContextResolver, ...]:
    """Return the built-in resolver chain in priority order."""
    return (
        _FlagResolver(),
        _SessionResolver(),
        _ManifestResolver(),
        _GateResolver(),
        _EnvResolver(),
        _CwdResolver(),
    )


# ---------------------------------------------------------------------------
# Resolution + decorator
# ---------------------------------------------------------------------------


def resolve_context(
    args: argparse.Namespace | None,
    *,
    needs: Iterable[str] = CONTEXT_FIELDS,
    env: Mapping[str, str] | None = None,
    resolvers: Iterable[ContextResolver] | None = None,
) -> WorkflowContext:
    """Run the resolver chain and produce a :class:`WorkflowContext`.

    First non-empty value per field wins; subsequent resolvers do not
    overwrite. ``resolved_from`` records the source for every populated
    field.
    """
    needs_tuple = tuple(needs)
    env_view: Mapping[str, str] = (
        env if env is not None else dict(os.environ)
    )
    chain = (
        tuple(resolvers) if resolvers is not None else default_resolvers()
    )

    populated: dict[str, Any] = {}
    provenance: dict[str, str] = {}
    for resolver in chain:
        result = resolver.resolve(args, needs=needs_tuple, env=env_view)
        for key, value in result.values.items():
            if key in populated or value in (None, ""):
                continue
            populated[key] = value
            provenance[key] = result.source

    return WorkflowContext(
        target=populated.get("target"),
        workspace=populated.get("workspace"),
        phase=populated.get("phase"),
        category=populated.get("category"),
        repo_id=populated.get("repo_id"),
        resolved_from=provenance,
    )


def with_context(
    *,
    needs: Iterable[str] = CONTEXT_FIELDS,
    test_ctx: WorkflowContext | None = None,
    env: Mapping[str, str] | None = None,
    resolvers: Iterable[ContextResolver] | None = None,
) -> Callable:
    """Decorator: resolve :class:`WorkflowContext` and pass it as ``ctx``.

    Wraps a shim's ``main(args)`` (or ``main(args, ctx)``) callable. The
    wrapped function's signature is inspected once at decoration time
    to decide whether to thread ``ctx`` through; for a callable that
    does not accept ``ctx``, the resolver still runs (for its side
    effects on provenance) and the call signature is preserved.

    ``test_ctx`` injection point bypasses the resolver chain.
    """
    needs_tuple = tuple(needs)

    def _decorator(func: Callable) -> Callable:
        accepts_ctx = _function_accepts_ctx(func)

        @functools.wraps(func)
        def _wrapped(args: argparse.Namespace | None = None, *more, **kwargs):
            if test_ctx is not None:
                ctx = test_ctx
            else:
                ctx = resolve_context(
                    args, needs=needs_tuple, env=env, resolvers=resolvers,
                )
            if accepts_ctx:
                kwargs.setdefault("ctx", ctx)
            return func(args, *more, **kwargs)

        _wrapped.__sdd_context_needs__ = needs_tuple  # type: ignore[attr-defined]
        return _wrapped

    return _decorator


def _function_accepts_ctx(func: Callable) -> bool:
    """True when *func* declares ``ctx`` as a parameter (or accepts ``**kwargs``)."""
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return False
    for name, param in sig.parameters.items():
        if name == "ctx":
            return True
        if param.kind is inspect.Parameter.VAR_KEYWORD:
            return True
    return False
