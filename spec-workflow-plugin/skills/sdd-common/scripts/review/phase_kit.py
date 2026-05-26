"""Phase registration toolkit — decorator-driven plugin surface.

Single authority for how a phase is wired into the review pipeline.
Each phase module defines a :class:`Phase` subclass decorated with
:func:`phase`; the decorator records the subclass in :data:`_REGISTRY`
and :func:`bind_to_prepare_pipeline` wires every entry into
``prepare-pipeline.py``'s argparse tree on startup.

* :func:`phase` — class decorator that registers a :class:`Phase`
  subclass under a name, records its expected ``emits`` set, and
  generates its internal sub-parser from an :class:`Input` dataclass.
* :class:`Phase` — base class. Handlers subclass it and implement
  :meth:`Phase.handle`. The base owns argparse reflection, input
  validation, dispatch, and uniform post-processing.
* :class:`PhaseInput` — marker base for typed phase inputs
  (a ``@dataclass`` subclass; the marker gives decorators and
  property tests a single handle).
* :class:`PhaseOutput` — marker base for typed phase return
  envelopes; same pattern as :class:`PhaseInput`.
* :data:`registered_phases` — read-only view of every phase the
  decorator has observed. Property tests consume it to assert
  registry parity with :data:`review.transitions.TRANSITIONS`.

Design constraints:

* **Single authority.** Every phase is registered via ``@phase``; no
  function-style ``register(subparsers, common)`` surface coexists.
* **No cycle with sdd_core.cli.** Everything here stays on
  ``argparse``/``dataclasses`` so phase modules can import it
  without a lazy-import dance.
* **Single authority for emits.** The decorator stores ``emits``
  verbatim; drift against :data:`review.transitions.TRANSITIONS` is
  a property-test failure.
"""
from __future__ import annotations

import argparse
import dataclasses
import inspect
from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Iterable

from sdd_core import output
from sdd_core.paths import resolve_project_path

from ._routing import maybe_append_ack_calls as _maybe_append_ack_calls
from .snapshots import PhaseSnapshotBase
from .transitions import TRANSITIONS, ACK_PHASES, ENTRY_PHASES

__all__ = [
    # Classes (CapWords) — every phase-role class uses the Phase* prefix.
    "Phase",
    "PhaseContext",
    "PhaseInput",
    "PhaseOutput",
    "PhaseSpec",
    # Decorator (lowercase per PEP 8 / stdlib convention — cf. @dataclass).
    "phase",
    # Functions (snake_case).
    "bind_to_prepare_pipeline",
    "get_phase",
    "registered_phases",
]


@dataclass(frozen=True)
class PhaseContext:
    """Routing / session context shared by every phase.

    Frozen so the orchestrator can pass the same instance through
    ``handle`` → ``_post_process`` without risk of mid-pipeline
    mutation. Carries the ``category / target_name / project_path``
    fields every routing helper reads directly — routing accepts
    :class:`PhaseContext` without an adapter.
    """

    category: str
    target_name: str
    project_path: str
    gate_id: str = ""
    parent_todo: str = ""

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "PhaseContext":
        """Build a :class:`PhaseContext` from an ``argparse.Namespace``.

        ``target_name`` falls back to ``category`` when unset. Project
        path resolution honours ``--workspace`` and the
        ``SDD_PROJECT_PATH`` env var (see
        :func:`sdd_core.paths.resolve_project_path`). Extra lifecycle
        fields default to ``""`` when absent (matches the common
        parent parser's ``default=None`` convention mapped through
        ``or ""``).
        """
        return cls(
            category=args.category,
            target_name=getattr(args, "target_name", None) or args.category,
            project_path=resolve_project_path(args),
            gate_id=getattr(args, "gate_id", None) or "",
            parent_todo=getattr(args, "parent_todo", None) or "",
        )


class PhaseInput:
    """Base for a phase's typed input dataclass.

    Phases subclass this *and* declare themselves ``@dataclass``:

    >>> @dataclass
    ... class CompleteInput(PhaseInput):
    ...     category: str = "spec"
    ...     target_name: str = ""

    The marker lets property tests walk every phase's ``Input`` type
    without hardcoding names. The marker also carries a runtime
    contract: every Input dataclass declares
    :meth:`validate_for_phase`. The default implementation returns an
    empty list so phases without a phase-time precondition gate inherit
    the no-op LSP fallback. Phases that have one (e.g. ``LaunchInput``)
    override the method to surface a list of human-readable problems
    that the dispatcher routes through :func:`output.recoverable_miss`
    — every missing phase-time argument becomes a typed recovery
    instead of a Python traceback.
    """

    def validate_for_phase(self) -> "list[str]":
        """Return the human-readable list of phase-time precondition
        problems the dispatcher must surface. Empty list = OK.

        Default no-op preserves substitutability — phases without a
        phase-time gate inherit the empty list. Overrides return one
        message per problem; the dispatcher folds the list into a
        recoverable miss with a literal recovery command sequence so
        the agent can retry without parsing a Python stack trace.
        """
        return []


@dataclass(frozen=True)
class PhaseOutput:
    """Base for every phase's typed return envelope.

    Subclasses carry phase-specific fields on top of this uniform
    set; :meth:`Phase._post_process` reads only the base fields.
    Handlers return a :class:`PhaseOutput` subclass; the orchestrator
    persists the snapshot, advances the gate, writes the session, and
    emits the final envelope via :func:`sdd_core.output.success`.

    ``result`` is the JSON-serialisable payload the agent sees.
    ``success_message`` is the human-readable status paired with the
    payload. ``snapshot`` is the typed idempotency envelope persisted
    via :func:`review_quality.gate_session.set_phase_snapshot`; leave
    ``None`` when the phase does not replay. ``next_phase`` feeds
    :func:`advance_gate`. ``terminal`` rides on the emitted envelope
    as the single stop signal. ``lifecycle_flags`` is forwarded to
    :func:`maybe_append_ack_calls`.
    """

    result: dict = dataclasses.field(default_factory=dict)
    success_message: str = ""
    snapshot: "PhaseSnapshotBase | None" = None
    next_phase: str = ""
    terminal: bool = False
    lifecycle_flags: str = ""
    skip_post_process: bool = False


@dataclass(frozen=True)
class PhaseSpec:
    """Everything the registry remembers about a decorated phase.

    Deliberately closed and frozen — reading the spec never mutates
    it. Adding a field is a single edit here; every consumer reads
    via attribute access rather than dict keys so the shape stays
    typed end-to-end.
    """

    name: str
    cls: type["Phase"]
    emits: frozenset[str]
    help: str
    description: str

    @property
    def is_terminal(self) -> bool:
        return not self.emits


# Registry keyed by phase name. Populated only by ``@phase`` decorator
# calls at import time; mutation outside this module is a bug (and
# made obvious by the frozen :class:`PhaseSpec`).
_REGISTRY: dict[str, PhaseSpec] = {}


class Phase:
    """Base class for every declaratively-registered phase.

    Subclasses declare two class-level attributes — ``Input`` and
    ``Output`` — then implement :meth:`handle`. The decorator wires
    everything else (argparse surface, input validation, dispatch,
    uniform post-processing).

    Two dispatch signatures are supported:

    * **Classic** — ``handle(self, args: argparse.Namespace) -> None``
      keeps each ack / entry phase byte-for-byte unchanged. The
      handler owns reading the session, calling routing helpers, and
      emitting via :func:`sdd_core.output.success`.
    * **Typed** — ``handle(self, ctx: PhaseContext, inp: Input) ->
      dict | PhaseOutput | None``. The base orchestrator builds
      ``ctx`` and ``inp`` from the parsed ``argparse.Namespace``, then
      calls :meth:`_post_process` with the return value.
    """

    #: Subclasses override to a :class:`PhaseInput` subclass.
    Input: ClassVar[type[PhaseInput]] = PhaseInput

    #: Subclasses override to a :class:`PhaseOutput` subclass when
    #: typed outputs land. Default stays :class:`PhaseOutput` so
    #: phases that still emit ``dict`` results keep working.
    Output: ClassVar[type[PhaseOutput]] = PhaseOutput

    #: Populated by the decorator so :meth:`handle_args` knows which
    #: registry entry it belongs to. Typed as ``PhaseSpec | None``
    #: because the ``@phase`` decorator runs *after* class body
    #: evaluation.
    spec: ClassVar["PhaseSpec | None"] = None

    def handle(self, *args, **kwargs):  # pragma: no cover - abstract
        """Execute the phase.

        Subclasses override with either:

        * ``handle(self, args)`` — raw-args handler. Handler emits its
          own envelope via :func:`sdd_core.output.success`.
        * ``handle(self, ctx, inp)`` — typed handler. Handler returns a
          :class:`PhaseOutput` (or ``None``); :meth:`_post_process`
          persists + emits.
        """
        raise NotImplementedError

    # -- Typed-handle post-processing hook ---------------------------------

    def _post_process(
        self, ctx: PhaseContext, result: "dict | PhaseOutput | None",
    ) -> None:
        """Run uniform after-``handle`` work for a typed handler.

        A handler that returns ``None`` (or a plain ``dict`` / a
        :class:`PhaseOutput` with ``skip_post_process=True``)
        short-circuits — the handler is responsible for its own
        emission, as the ack phases are.

        When a handler returns a full :class:`PhaseOutput`, the base
        runs the uniform sequence:

        1. Persist any ``required_tool_calls`` onto the gate.
        2. Append the ack-calls follow-up when pending calls exist.
        3. Advance the gate state to ``env.next_phase``.
        4. Persist the typed snapshot (if any).
        5. Write the session file exactly once.
        6. Emit the envelope (riding ``env.terminal`` on the
           single-terminator wire).
        """
        if result is None:
            return
        if not isinstance(result, PhaseOutput):
            # Handlers returning a raw dict already emitted themselves.
            return
        if result.skip_post_process:
            return

        # Function-scope imports avoid a module-load cycle with
        # :mod:`review_quality.gate_session` → :mod:`review.snapshots`
        # → this module.
        from review_quality.gate_session import (
            advance_gate, read_session, set_phase_snapshot, write_session,
        )
        from .pipeline_phases.guards import persist_pending_calls

        session = read_session(
            ctx.category, ctx.target_name, ctx.project_path,
        )
        gate = session.setdefault("review_gate", {})

        persist_pending_calls(gate, result.result)
        _maybe_append_ack_calls(
            result.result, ctx, lifecycle_flags=result.lifecycle_flags,
        )

        if result.next_phase:
            session = advance_gate(
                session, required_next_phase=result.next_phase,
            )

        if result.snapshot is not None:
            set_phase_snapshot(session, result.snapshot)

        write_session(
            ctx.category, ctx.target_name, session, ctx.project_path,
        )

        payload = dict(result.result)
        if result.terminal:
            payload["terminal"] = True
        output.success(payload, result.success_message)

    # -- Registration adapter ----------------------------------------------

    @classmethod
    def register(
        cls, subparsers: argparse._SubParsersAction,
        common: argparse.ArgumentParser,
    ) -> None:
        """Wire this phase into the ``prepare-pipeline.py`` argparse tree.

        Called by :func:`bind_to_prepare_pipeline`. Generates a
        sub-parser, attaches the :class:`Input` dataclass fields as
        per-phase flags, and installs a closure ``_handler`` that
        dispatches to :meth:`handle`. The dispatch shape is chosen
        once at registration time by :meth:`_handle_accepts_typed_args`
        and cached in the closure.
        """
        spec = cls.spec
        if spec is None:  # pragma: no cover - defensive
            raise RuntimeError(
                f"{cls.__name__} has no PhaseSpec — missing @phase decorator?"
            )
        parser = subparsers.add_parser(
            spec.name,
            help=spec.help,
            description=spec.description,
            parents=[common],
        )
        cls._attach_input_flags(parser)
        instance = cls()

        uses_typed_handle = cls._handle_accepts_typed_args()

        if uses_typed_handle:
            def _dispatch(args: argparse.Namespace) -> None:
                cls._validate_input(args)
                ctx = PhaseContext.from_args(args)
                inp = cls._build_input(args)
                # Every typed Input runs ``validate_for_phase`` before
                # ``handle`` so missing phase-time inputs route through
                # ``output.recoverable_miss`` instead of crashing inside
                # the handler. The default no-op preserves Phases that
                # have no phase-time gate.
                cls._maybe_recoverable_miss(inp, ctx)
                result = instance.handle(ctx, inp)
                instance._post_process(ctx, result)
        else:
            def _dispatch(args: argparse.Namespace) -> None:
                cls._validate_input(args)
                instance.handle(args)

        parser.set_defaults(_handler=_dispatch)

    @classmethod
    def _handle_accepts_typed_args(cls) -> bool:
        """Return True when :meth:`handle` has the typed ``(ctx, inp)``
        signature.

        Detection is a single ``inspect.signature`` call on the
        subclass's override of :meth:`handle`. We require exactly two
        positional parameters after ``self`` (``ctx`` and ``inp``) —
        no ``*args`` / ``**kwargs`` fallbacks — because the typed
        dispatch path passes exactly those two. Subclasses that still
        take a single ``args`` parameter keep the raw-args path; the
        abstract base ``handle(*args, **kwargs)`` also falls through
        to raw-args (raises ``NotImplementedError``) but that only
        matters if a subclass forgets to override, which is caught by
        :class:`tests.test_phase_module_contract.TestPhaseModuleContract`.
        """
        override = cls.handle
        if override is Phase.handle:
            # Subclass didn't override handle — abstract fallthrough.
            return False
        try:
            sig = inspect.signature(override)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return False
        params = [
            p for p in sig.parameters.values()
            if p.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        # Drop the implicit ``self`` bound on an unbound method.
        if params and params[0].name == "self":
            params = params[1:]
        return len(params) == 2

    @classmethod
    def _build_input(cls, args: argparse.Namespace) -> PhaseInput:
        """Materialise :attr:`Input` from the parsed ``argparse.Namespace``.

        Filters to declared dataclass fields (mirroring
        :meth:`_validate_input`'s filter), so lifecycle-only fields
        that a given phase's Input does not declare pass through
        untouched. Raises :class:`TypeError` when the class attribute
        isn't a dataclass — a loud signal the subclass forgot the
        ``@dataclass`` decorator, which is always a programmer error
        rather than a runtime one.
        """
        Input = cls.Input
        if not dataclasses.is_dataclass(Input):  # pragma: no cover - defensive
            raise TypeError(
                f"{cls.__name__}.Input is not a dataclass — typed handle "
                "dispatch requires a concrete :class:`PhaseInput` subclass"
            )
        field_names = {f.name for f in dataclasses.fields(Input)}
        kwargs = {
            name: getattr(args, name)
            for name in field_names if hasattr(args, name)
        }
        return Input(**kwargs)

    @classmethod
    def _maybe_recoverable_miss(
        cls, inp: PhaseInput, ctx: "PhaseContext",
    ) -> None:
        """Surface a recoverable miss when the Input flags
        :meth:`validate_for_phase` problems.

        The dispatcher fires :func:`sdd_core.output.recoverable_miss`
        directly on a non-empty list so the envelope is structurally
        ``result``-class with a literal recovery line. Phases that
        author a custom recovery sequence override the helper's choice
        of recovery command by surfacing the problem inside
        :meth:`handle` instead. The default helper composes a
        ``did_you_mean`` style recovery from
        :func:`build_review_pipeline_launch_command` so the operator
        gets a runnable retry literal for any phase whose fall-through
        matches a launch resume.
        """
        problems = inp.validate_for_phase()
        if not problems:
            return
        from sdd_core.command_templates import (
            build_review_pipeline_launch_command,
        )
        category = getattr(ctx, "category", "spec") or "spec"
        target_name = getattr(ctx, "target_name", "") or ""
        project_path = getattr(ctx, "project_path", ".") or "."
        try:
            recovery = build_review_pipeline_launch_command(
                target_name=target_name,
                category=category,
                workspace_path=project_path,
                workflow_mode="create",
            )
        except (KeyError, ValueError):
            # Fall back to a generic recovery hint if we cannot
            # synthesise a category-aware launch literal — better to
            # surface the typed miss than to crash the dispatcher.
            recovery = (
                ".spec-workflow/sdd review/pipeline-tick.py "
                f"--category {category} --target-name {target_name} "
                f"--workspace {project_path} --phase launch"
            )
        output.recoverable_miss(
            {"phase": cls.__name__, "problems": list(problems)},
            f"{cls.__name__}: missing phase-time input(s)",
            next_action_command_sequence=recovery,
            problems=list(problems),
            hint=(
                "Re-run the launch with the listed flags supplied; the "
                "phase guards against missing inputs at the dispatch "
                "boundary so partial commands surface as recoverable "
                "misses, not Python tracebacks."
            ),
        )

    @classmethod
    def _validate_input(cls, args: argparse.Namespace) -> None:
        """Instantiate :attr:`Input` from ``args`` to fire dataclass
        ``__post_init__`` validators.

        Cross-argument invariants live on the Input dataclass. Only
        declared fields are passed through, so ``argparse.Namespace``
        attributes beyond the dataclass shape (``_handler``,
        ``phase``) are ignored.

        ``ValueError`` raised from ``__post_init__`` is routed through
        :meth:`_maybe_recoverable_miss` so dataclass-validation misses
        emit a structurally result-class envelope carrying an invocable
        recovery shim instead of a Python traceback.
        """
        Input = cls.Input
        if Input is PhaseInput or not dataclasses.is_dataclass(Input):
            return
        field_names = {f.name for f in dataclasses.fields(Input)}
        kwargs = {
            name: getattr(args, name)
            for name in field_names if hasattr(args, name)
        }
        try:
            Input(**kwargs)
        except ValueError as exc:
            cls._dataclass_validation_recoverable_miss(args, str(exc))

    @classmethod
    def _dataclass_validation_recoverable_miss(
        cls, args: argparse.Namespace, message: str,
    ) -> None:
        """Surface a dataclass ``__post_init__`` failure as a recoverable miss.

        Reuses :meth:`_maybe_recoverable_miss` recovery semantics but
        keeps the original validation message in the ``problems`` list
        so the operator sees what the dataclass rejected.
        """
        from sdd_core.command_templates import (
            build_review_pipeline_launch_command,
        )
        category = getattr(args, "category", "spec") or "spec"
        target_name = getattr(args, "target_name", "") or ""
        project_path = getattr(args, "project_path", ".") or "."
        try:
            recovery = build_review_pipeline_launch_command(
                target_name=target_name,
                category=category,
                workspace_path=project_path,
                workflow_mode="create",
            )
        except (KeyError, ValueError):
            recovery = (
                ".spec-workflow/sdd review/pipeline-tick.py "
                f"--category {category} --target-name {target_name} "
                f"--workspace {project_path} --phase launch"
            )
        problems = [message]
        output.recoverable_miss(
            {"phase": cls.__name__, "problems": problems},
            f"{cls.__name__}: input dataclass rejected",
            next_action_command_sequence=recovery,
            problems=problems,
            hint=(
                f"{message} — execute next_action_command_sequence, "
                "then retry."
            ),
        )

    @classmethod
    def _attach_input_flags(cls, parser: argparse.ArgumentParser) -> None:
        """Reflect the :class:`Input` dataclass onto ``parser``.

        Each non-lifecycle dataclass field becomes a ``--kebab-cased``
        flag. Lifecycle fields (``parent_todo``, ``gate_id``,
        ``project_path``, ``category``, ``target_name``) live on the
        common parent parser and are skipped here; a phase that does
        not consume a lifecycle field simply omits it from its Input.
        """
        if not dataclasses.is_dataclass(cls.Input):
            return
        common_fields = {
            "parent_todo", "parent_todo_content", "gate_id",
            "project_path", "category", "target_name",
        }
        for field in dataclasses.fields(cls.Input):
            if field.name in common_fields:
                continue
            flag = "--" + field.name.replace("_", "-")
            meta = field.metadata or {}
            kwargs: dict[str, Any] = {
                "dest": field.name,
                "help": meta.get("help", ""),
            }
            # ``metavar`` overrides argparse's default uppercase echo of
            # the dest name — surfaces like ``--references
            # name=<sha>,name=<sha>`` that pre-date the migration stay
            # byte-identical in the captured help fixtures.
            metavar = meta.get("metavar")
            if metavar is not None:
                kwargs["metavar"] = metavar
            # A field can opt into a ``choices=`` enum via metadata;
            # keeps ``_attach_input_flags`` closed-for-modification as
            # more phases with constrained vocabularies migrate.
            choices = meta.get("choices")
            if choices is not None:
                kwargs["choices"] = tuple(choices)
            default = (
                field.default if field.default is not dataclasses.MISSING
                else field.default_factory() if field.default_factory is not dataclasses.MISSING  # type: ignore[misc]
                else None
            )
            kwargs["default"] = default
            ftype = field.type
            # ``from __future__ import annotations`` may deliver the
            # type as a string — match against the string form too so
            # the reflection still classifies ``bool`` / ``int`` fields
            # correctly after the module opts into PEP 563 annotations.
            if ftype is bool or ftype == "bool":
                kwargs["action"] = "store_true"
                kwargs.pop("default", None)
            elif ftype is int or ftype == "int":
                kwargs["type"] = int
            parser.add_argument(flag, **kwargs)


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def phase(
    *,
    name: str,
    emits: Iterable[str] = (),
    help: str = "",
    description: str = "",
) -> Callable[[type[Phase]], type[Phase]]:
    """Register a :class:`Phase` subclass under ``name``.

    Parameters
    ----------
    name:
        Phase name as it appears on the gate session
        ``required_next_phase`` and in :data:`TRANSITIONS`.
    emits:
        Shadow of :data:`TRANSITIONS[name]`. Property tests assert
        ``set(emits) == TRANSITIONS[name]`` for every migrated
        phase — so editing ``emits`` without a matching
        :data:`TRANSITIONS` change fails CI rather than silently
        drifting.
    help / description:
        Forwarded to ``subparsers.add_parser`` when the phase is
        wired into ``prepare-pipeline.py`` via
        :func:`bind_to_prepare_pipeline`. Defaults pull from
        ``cls.__doc__`` when caller omits them.
    """
    emit_set = frozenset(emits)

    def decorate(cls: type[Phase]) -> type[Phase]:
        if not inspect.isclass(cls) or not issubclass(cls, Phase):
            raise TypeError(
                f"@phase must decorate a Phase subclass; got {cls!r}"
            )
        doc = (cls.__doc__ or "").strip()
        resolved_help = help or (doc.splitlines()[0] if doc else name)
        resolved_description = description or doc or resolved_help
        spec = PhaseSpec(
            name=name,
            cls=cls,
            emits=emit_set,
            help=resolved_help,
            description=resolved_description,
        )
        existing = _REGISTRY.get(name)
        if existing is not None and existing.cls is not cls:
            raise RuntimeError(
                f"Phase '{name}' already registered by "
                f"{existing.cls.__module__}.{existing.cls.__qualname__}; "
                f"refusing to overwrite with {cls.__module__}."
                f"{cls.__qualname__}"
            )
        cls.spec = spec
        _REGISTRY[name] = spec
        return cls

    return decorate


# ---------------------------------------------------------------------------
# Introspection helpers
# ---------------------------------------------------------------------------


def registered_phases() -> dict[str, PhaseSpec]:
    """Return a shallow copy of the phase registry.

    A copy so callers cannot accidentally mutate the live registry;
    the :class:`PhaseSpec` values themselves are frozen so a shallow
    copy is safe.
    """
    return dict(_REGISTRY)


def get_phase(name: str) -> PhaseSpec | None:
    """Return the :class:`PhaseSpec` for ``name`` or ``None``."""
    return _REGISTRY.get(name)


def bind_to_prepare_pipeline(
    subparsers: argparse._SubParsersAction,
    common: argparse.ArgumentParser,
) -> None:
    """Wire every decorator-registered phase into ``prepare-pipeline.py``.

    Single authority for dispatch: every phase lands in :data:`_REGISTRY`
    via the ``@phase`` decorator at module import time (driven by
    :mod:`review.pipeline_phases` package import), and this function
    simply walks the registry calling :meth:`Phase.register` on each
    entry.
    """
    for spec in _REGISTRY.values():
        spec.cls.register(subparsers, common)


def _validate_registry_against_transitions() -> list[str]:
    """Return drift descriptions between :data:`_REGISTRY` and
    :data:`TRANSITIONS` — empty list means parity holds.

    Exposed so property tests import the derivation rather than
    re-implementing it. The derivation is permissive in two places:

    * Phases in :data:`ACK_PHASES` / :data:`ENTRY_PHASES` are allowed
      to live in the registry without appearing in :data:`TRANSITIONS`
      (they are injected / standalone, never graph-next).
    * Phases in :data:`TRANSITIONS` are allowed to be absent from
      :data:`_REGISTRY` until their per-session migration lands.
    """
    drifts: list[str] = []
    for spec in _REGISTRY.values():
        if spec.name in TRANSITIONS:
            expected = TRANSITIONS[spec.name]
            if spec.emits != expected:
                drifts.append(
                    f"Phase '{spec.name}' emits {sorted(spec.emits)} but "
                    f"TRANSITIONS says {sorted(expected)}"
                )
        elif spec.name not in ACK_PHASES and spec.name not in ENTRY_PHASES:
            drifts.append(
                f"Phase '{spec.name}' is registered but missing from "
                "TRANSITIONS / ACK_PHASES / ENTRY_PHASES"
            )
    return drifts
