#!/usr/bin/env python3
"""Pipeline thin-waist dispatcher.

One agent-facing verb — the internal dispatcher resolves
``review_gate.required_next_phase`` from the gate session and
forwards to the ``prepare-pipeline.py <phase>`` surface.

Every flag a phase currently accepts remains reachable; the
dispatcher lifts the lifecycle-flag plumbing
(``--parent-todo`` / ``--parent-todo-content`` / ``--gate-id``) and
``launch_args_cache``-derived args off the agent so fewer places
can drift.

Usage:
  pipeline-tick.py --category <c> --target-name <n> [--workspace .]
                   [--phase <override>] [--gate-uuid <uuid>]
                   [-- <extra flags forwarded to the resolved phase>]

Anything after a bare ``--`` is passed verbatim as additional argv to
the resolved phase. The dispatcher itself only parses the locator
flags; it never hand-crafts phase-specific flag strings — those come
from ``launch_args_cache`` (doc_list, review_skill, scope, ...) or the
``review_gate`` (fix_cycle, max_cycles, parent_todo_id, gate_id).

**Agent ergonomics.** Callers may also pass phase flags inline without
the ``--`` separator: any unknown flag that the resolved phase's
``Input`` dataclass accepts is auto-promoted into the passthrough
tail. Unknown flags that no phase accepts produce a structured
``did_you_mean`` error that reports the closest accepted flags and
the required ``--`` passthrough form.

Per-phase accepted flags are derived via :func:`_accepted_flags` from
``registered_phases()[phase].cls.Input`` dataclass reflection — the
registry is the single source of truth, so adding a new Input field
automatically widens the injection surface without a hand-maintained
table drifting against reality.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import dataclasses
import os
import subprocess
import sys
from typing import Any

from sdd_core import cli, output, paths
from sdd_core.advisories import Advisory
from sdd_core.command_templates import build_pipeline_tick_update_launch_command
from sdd_core.doc_config import DOCUMENT_REGISTRY
from sdd_core.harness import load_adapter
from sdd_core.harness.loader import persist_state
from sdd_core.security import constants as security_constants
from sdd_core.category_registry import (
    CATEGORY_REGISTRY,
    default_target_name as _category_default_target,
    is_known_category as _is_known_category,
)
from sdd_core.dispatcher_help import (
    lifecycle_passthrough_flags,
    promote_inline_flags,
    render_phase_help,
)
from review_quality.gate_session import read_session
# Importing the pipeline_phases package triggers every @phase decorator
# so ``registered_phases()`` below sees the complete registry.
import review.pipeline_phases  # noqa: F401
from review.phase_kit import registered_phases
from sdd_core.transient_state import write_current_target

# Phases that pin the workflow's current-target session so downstream
# phase calls (post-review, post-fix, pre-approval) auto-resolve
# ``ctx.target`` / ``ctx.phase`` instead of re-typing the locator
# every tick.
_SESSION_PINNING_PHASES: frozenset[str] = frozenset({"launch"})


__sdd_manifest__ = {
    "summary": "Pipeline thin-waist dispatcher (agent-facing review verb)",
    "verbs": [
        "--category <c> --target-name <n> [--phase <override>]",
        "--category <c> --target-name <n> -- <phase flags>",
    ],
    "aliases": {"--spec-name": "--target-name"},
    "flags": [
        "--category", "--target-name", "--spec-name", "--phase",
        "--gate-uuid", "--workspace", "--dry-run",
    ],
    "passthrough_reference": "sdd-common/references/dispatcher-passthrough.md",
}

# Script-dir neighbours: ``prepare-pipeline.py`` lives side-by-side.
# Resolving via ``__file__`` keeps the dispatcher relocation-safe
# (e.g. when packaged under an alternate skills root).
_HERE = os.path.dirname(os.path.abspath(__file__))
_PREPARE_PIPELINE = os.path.join(_HERE, "prepare-pipeline.py")


# Lifecycle / locator fields that live on the common parent parser —
# they are injected by :func:`_append_from_session` (for parent-todo /
# gate-id) or set directly on ``sub_argv`` (for category / target-name
# / project-path), never by :func:`_append_from_cache`.
_COMMON_FIELDS: frozenset[str] = frozenset({
    "parent_todo", "parent_todo_content", "gate_id",
    "project_path", "category", "target_name",
})


def _accepted_flags(phase: str) -> frozenset[str]:
    """Return the ``--kebab-cased`` flag set a phase's Input dataclass declares.

    Derived from :meth:`review.phase_kit.Phase.Input` fields so the
    phase registry is the single authority — editing an Input
    dataclass flows straight to the dispatcher without a parallel
    ``_PHASE_SPECIFIC_ARGS`` table to maintain.
    """
    spec = registered_phases().get(phase)
    if spec is None or not dataclasses.is_dataclass(spec.cls.Input):
        return frozenset()
    return frozenset(
        f"--{f.name.replace('_', '-')}"
        for f in dataclasses.fields(spec.cls.Input)
        if f.name not in _COMMON_FIELDS
    )


def _split_passthrough(argv: list[str]) -> tuple[list[str], list[str]]:
    """Return ``(own_args, passthrough_args)`` split at the first ``--``.

    Anything after the separator is forwarded verbatim as argv to the
    resolved phase. Using ``--`` (argparse's standard "end of own
    options" marker) keeps the agent-facing CLI consistent with
    standard tool conventions.
    """
    try:
        idx = argv.index("--")
    except ValueError:
        return argv, []
    return argv[:idx], argv[idx + 1:]


def _build_parser() -> argparse.ArgumentParser:
    """Return the locator parser for pipeline-tick's own flags."""
    parser = cli.strict_parser(
        __doc__,
        epilog=(
            "Examples:\n"
            "  # Dispatcher-resolved phase (uses gate session):\n"
            "  pipeline-tick --category steering --target-name steering\n"
            "\n"
            "  # Explicit phase override:\n"
            "  pipeline-tick --category spec --target-name my-feature "
            "--phase post-review\n"
            "\n"
            "  # With phase-specific flags (two supported forms):\n"
            "  # 1. Pass inline — unknown flags auto-promote to the "
            "phase:\n"
            "  pipeline-tick --category steering --target-name steering "
            "--phase launch --review-skill sdd-review-steering-docs "
            "--doc-list \"product.md,tech.md\" --scope per-document\n"
            "  # 2. Pass after an explicit `--` separator:\n"
            "  pipeline-tick --category spec --target-name my-feature -- "
            "--doc requirements.md\n"
            "\n"
            "Every flag the resolved phase's Input dataclass accepts is "
            "valid — the dispatcher reflects on the registry so flag\n"
            "discovery is automatic (see --help output per phase via "
            "`prepare-pipeline.py <phase> --help`).\n"
        ),
    )
    parser.add_argument(
        "--category", default="spec",
        choices=("spec", "steering", "discovery"),
        help="Approval category",
    )
    parser.add_argument(
        "--target-name", "--spec-name", dest="target_name", default="",
        type=cli.name_type("target-name"),
        help="Spec name, steering name, or discovery project name",
    )
    parser.add_argument(
        "--gate-uuid", default=None,
        help=(
            "Gate UUID to tick (reserved for future server-side "
            "lookup). When omitted the dispatcher resolves the "
            "session via --category / --target-name."
        ),
    )
    parser.add_argument(
        "--phase", default=None,
        help=(
            "Override the resolved phase. Defaults to "
            "review_gate.required_next_phase, or 'launch' on fresh "
            "sessions with no state."
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help=(
            "Compute the next envelope without mutating session state. "
            "The emitted envelope is byte-identical to a live tick "
            "modulo persist-side effects (gate session, reference "
            "ledger, quality files)."
        ),
    )
    parser.add_argument(
        "--describe-phase-graph", action="store_true",
        dest="describe_phase_graph",
        help=(
            "Print the canonical phase-transition graph as JSON to "
            "stdout and exit 0. The graph is the single source of "
            "truth for 'given current phase + outcome → next phase'; "
            "envelopes ship one ``next_action_command`` and operators "
            "consult this flag for the full graph."
        ),
    )
    parser.add_argument(
        "--print-field", default=None, dest="print_field",
        metavar="JSONPATH",
        help=(
            "Print exactly one field's string value from the dispatched "
            "envelope to stdout (no JSON wrapper, no trailing whitespace "
            "beyond a newline). The selector is a dotted JSONPath-style "
            "expression starting after ``data`` or, when prefixed with "
            "``$.``, traversing the full envelope. Status banners and "
            "diagnostics still go to stderr — agents read the bare "
            "literal off stdout instead of piping through ``jq``."
        ),
    )
    return parser


def _resolve_phase(gate: dict, override: str | None) -> str:
    """Return the phase name to dispatch to.

    Precedence: explicit ``--phase`` override → gate's recorded
    ``required_next_phase`` → ``launch`` (for a fresh session with no
    gate state yet). ``launch`` is the declarative default because
    every review flow begins there; the override lets operators and
    tests nudge the dispatcher without first seeding a session.
    """
    if override:
        return override
    return gate.get("required_next_phase") or "launch"


def _append_from_session(
    sub_argv: list[str], gate: dict, passthrough: list[str],
) -> None:
    """Inject lifecycle flags from the gate session into ``sub_argv``.

    Skips any flag the caller already supplied via the passthrough
    tail — agents and tests can still override the server-resolved
    value without the dispatcher second-guessing them.
    """
    present = {tok for tok in passthrough if tok.startswith("--")}
    parent_todo = gate.get("parent_todo_id")
    if parent_todo and "--parent-todo" not in present:
        sub_argv += ["--parent-todo", parent_todo]
    gate_id = gate.get("gate_id")
    if gate_id and "--gate-id" not in present:
        sub_argv += ["--gate-id", gate_id]
    parent_todo_content = gate.get("parent_todo_content")
    if parent_todo_content and "--parent-todo-content" not in present:
        sub_argv += ["--parent-todo-content", parent_todo_content]


def _append_from_cache(
    sub_argv: list[str], phase: str,
    gate: dict, cached: dict, passthrough: list[str],
) -> None:
    """Inject ``launch_args_cache`` / gate fields relevant to ``phase``.

    Only flags the phase actually accepts (per :func:`_accepted_flags`)
    get injected — otherwise argparse's strict parser would reject the
    call. ``launch`` is deliberately *not* backfilled from the cache:
    a re-launch must carry explicit intent via the passthrough tail,
    since the cache is populated *by* launch and backfilling from it
    would silently mask bad invocations.
    """
    accepted = _accepted_flags(phase)
    present = {tok for tok in passthrough if tok.startswith("--")}

    def _inject(flag: str, value) -> None:
        if flag in accepted and flag not in present and value not in (None, ""):
            sub_argv.extend([flag, str(value)])

    if phase in {"post-fix", "pre-approval", "check-revalidation"}:
        _inject("--doc-list", cached.get("doc_list"))
    if phase in {"post-fix", "check-revalidation"}:
        _inject("--fix-cycle", gate.get("fix_cycle"))
        _inject("--max-cycles", gate.get("max_cycles"))


def _build_subprocess_argv(
    args: argparse.Namespace, project_path: str,
    phase: str, passthrough: list[str],
    *, session: dict,
) -> list[str]:
    """Build the argv for the internal ``prepare-pipeline.py`` subprocess."""
    gate = session.get("review_gate") or {}
    cached = session.get("launch_args_cache") or {}

    sub_argv: list[str] = [
        phase,
        "--workspace", project_path,
        "--category", args.category,
    ]
    if args.target_name:
        sub_argv += ["--target-name", args.target_name]

    _append_from_session(sub_argv, gate, passthrough)
    _append_from_cache(sub_argv, phase, gate, cached, passthrough)

    sub_argv.extend(passthrough)
    return sub_argv


def _select_envelope_field(envelope: dict, selector: str) -> "Any | None":
    """Walk *envelope* via the dotted *selector* and return the leaf value.

    Selectors that start with ``$.`` traverse from the envelope root;
    everything else is treated as a path under ``data`` (the field
    most agents read). ``None`` when any segment misses or is not
    indexable.
    """
    if not selector:
        return None
    selector = selector.strip()
    if selector.startswith("$."):
        cursor: Any = envelope
        path = selector[2:]
    elif selector == "$":
        return envelope
    else:
        cursor = envelope.get("data") if isinstance(envelope, dict) else None
        path = selector
    for raw in path.split("."):
        seg = raw.strip()
        if not seg:
            continue
        if isinstance(cursor, dict):
            cursor = cursor.get(seg)
        elif isinstance(cursor, list):
            try:
                idx = int(seg)
            except ValueError:
                return None
            if 0 <= idx < len(cursor):
                cursor = cursor[idx]
            else:
                return None
        else:
            return None
        if cursor is None:
            return None
    return cursor


def _format_field_value(value: "Any") -> str:
    """Render a selected field value for stdout emission.

    Strings emit as-is; everything else round-trips through ``json.dumps``
    so structured values stay machine-readable when the operator picked a
    sub-tree rather than a leaf.
    """
    if isinstance(value, str):
        return value
    import json as _json
    return _json.dumps(value)


def _run_phase(
    sub_argv: list[str], *, dry_run: bool = False,
    print_field: "str | None" = None,
) -> int:
    """Dispatch to ``prepare-pipeline.py`` and mirror its stdio + exit.

    Using ``subprocess.run`` with direct stdio inheritance keeps the
    envelope bytes identical to what the phase itself produced — no
    post-processing, no re-encoding. The dispatcher is a forwarder,
    not a transformer.

    When ``dry_run`` is true the subprocess inherits the dry-run env
    flag from :mod:`sdd_core.security.constants` so
    :mod:`sdd_core.output` / :mod:`sdd_core.reference_ledger` skip
    every persist-side effect while the handler's compute path runs
    unchanged. The returned envelope bytes are therefore byte-identical
    to a live tick modulo the persistence the dry-run suppressed.

    When *print_field* is set the dispatcher captures the subprocess
    stdout, parses the envelope, and emits only the selected field's
    string value to stdout. Stderr (status banners, diagnostics) is
    forwarded unchanged so the two streams stay disjoint.
    """
    env = os.environ.copy()
    if dry_run:
        env[security_constants.DRY_RUN_ENV] = security_constants.DRY_RUN_ON_VALUE
    result = subprocess.run(
        [sys.executable, _PREPARE_PIPELINE, *sub_argv],
        capture_output=True, text=True, check=False, env=env,
    )
    if result.stderr:
        sys.stderr.write(result.stderr)
    if print_field:
        import json as _json
        try:
            envelope = _json.loads(result.stdout) if result.stdout else {}
        except _json.JSONDecodeError:
            output.error(
                f"--print-field could not parse phase stdout as JSON",
                hint=(
                    "The selected phase did not emit a JSON envelope; "
                    "drop --print-field and inspect the raw stdout."
                ),
            )
        value = _select_envelope_field(envelope, print_field)
        if value is None:
            return result.returncode if result.returncode != 0 else 1
        sys.stdout.write(_format_field_value(value))
        sys.stdout.write("\n")
        return result.returncode
    if result.stdout:
        sys.stdout.write(result.stdout)
    return result.returncode


def _passthrough_accepted(phase: str) -> frozenset[str]:
    """Return the flag set auto-promotable for *phase*.

    Union of the phase's Input dataclass fields (per
    :func:`_accepted_flags`) with the lifecycle flags every phase
    accepts on the shared parent parser of ``prepare-pipeline.py``.
    """
    return _accepted_flags(phase) | lifecycle_passthrough_flags()


def _auto_promote_unknown(
    unknown: list[str], phase: str,
) -> tuple[list[str], list[str]]:
    """Split ``unknown`` into ``(accepted_by_phase, still_unknown)``.

    Thin wrapper over :func:`sdd_core.dispatcher_help.promote_inline_flags`
    so this dispatcher and any future peer (``pipeline-run.py``, a
    workspace-level dispatcher) share the same promotion grammar. The
    single-authority lives in ``sdd_core.dispatcher_help``.
    """
    return promote_inline_flags(unknown, _passthrough_accepted(phase))


def _report_unknown_flags(unknown: list[str], phase: str) -> None:
    """Emit a JSON error describing unknown top-level flags.

    Structured per the "solve, don't punt" contract in
    ``docs/sdd-update-steering-tool-call-issues.md``. Rendering happens
    in ``sdd_core.dispatcher_help.render_phase_help``; this function is
    the dispatcher-specific envelope layer (error title + hint
    composition + ``output.error`` side effect).
    """
    hint_lines = render_phase_help(unknown, phase, _passthrough_accepted(phase))
    output.error(
        f"Unrecognized top-level flag(s) for pipeline-tick: "
        f"{' '.join(unknown)}",
        hint="\n".join(hint_lines),
    )


def _passthrough_flag_value(passthrough: list[str], flag: str) -> "str | None":
    """Return the value following ``flag`` in *passthrough*, or ``None``.

    Walks the merged passthrough tail so the dispatcher can introspect
    phase flags (``--workflow-mode``, ``--scope``, ``--doc-list``, …)
    without re-parsing argparse. The value form is ``--flag value``;
    the ``--flag=value`` form is also accepted.
    """
    for idx, tok in enumerate(passthrough):
        if tok == flag and idx + 1 < len(passthrough):
            return passthrough[idx + 1]
        if tok.startswith(f"{flag}="):
            return tok.split("=", 1)[1]
    return None


def _all_required_docs_exist(category: str, target_name: str, project_path: str) -> bool:
    """Return ``True`` when every required doc for *category* is on disk.

    Mirrors :mod:`util.detect-doc-state`'s ``summary.all_required_exist``
    field: a doc is required when its key is in ``doc_keys`` and not in
    ``optional_doc_keys``. Resolving directly from
    :data:`DOCUMENT_REGISTRY` avoids spawning the detector subprocess on
    every dispatcher tick — the rule is a pure projection of the
    registry plus on-disk existence.
    """
    registry = DOCUMENT_REGISTRY.get(category)
    if not registry:
        return False
    doc_keys = registry.get("doc_keys") or []
    optional_keys = set(registry.get("optional_doc_keys") or [])
    doc_files = registry.get("doc_files") or {}
    required_keys = [k for k in doc_keys if k not in optional_keys]
    if not required_keys:
        return False
    doc_dir = paths.doc_dir_path(category, target_name, project_path)
    for key in required_keys:
        filename = doc_files.get(key)
        if not filename:
            return False
        if not os.path.isfile(os.path.join(doc_dir, filename)):
            return False
    return True


def _maybe_block_wrong_update_entry(
    *,
    phase: str,
    passthrough: list[str],
    category: str,
    target_name: str,
    project_path: str,
) -> None:
    """Emit ``preflight_required`` when launch is the wrong update entry.

    Update-mode revisions that route through ``--phase launch`` reset
    the gate to the creation-mode checklist (``review-gate.default.v1``)
    instead of the update-mode binding (``update-mode.default.v1``).
    The checklists drive different downstream sequencing, so silently
    dispatching launch would corrupt the workflow. Block early and hand
    the operator the canonical ``--phase update-launch`` literal.
    """
    if phase != "launch":
        return
    if _passthrough_flag_value(passthrough, "--workflow-mode") != "update":
        return
    if _passthrough_flag_value(passthrough, "--scope") != "per-document":
        return
    if not _all_required_docs_exist(category, target_name, project_path):
        return

    doc_list = _passthrough_flag_value(passthrough, "--doc-list") or ""
    review_skill = _passthrough_flag_value(passthrough, "--review-skill")
    parent_todo = _passthrough_flag_value(passthrough, "--parent-todo")
    gate_id = _passthrough_flag_value(passthrough, "--gate-id")
    next_cmd = build_pipeline_tick_update_launch_command(
        category=category,
        target_name=target_name,
        doc_list=doc_list,
        review_skill=review_skill,
        scope="per-document",
        workflow_mode="update",
        parent_todo=parent_todo,
        gate_id=gate_id,
    )
    advisory = Advisory(
        name="wrong_update_entry_phase",
        detail=(
            f"--phase launch --workflow-mode update on an existing "
            f"{category}/{target_name} resets the gate to the "
            "creation-mode checklist; use --phase update-launch instead."
        ),
        action_required=True,
        next_action_command=next_cmd,
        extra={
            "requested_phase": "launch",
            "required_phase": "update-launch",
            "expected_progress_checklist_key": "update-mode.default.v1",
        },
    )
    output.preflight_required(
        {
            "outcome": "preflight_required",
            "advisories": [advisory.to_payload()],
            "requested_phase": "launch",
            "required_phase": "update-launch",
        },
        f"launch blocked: use --phase update-launch for {category}/{target_name}",
        next_action_command=next_cmd,
        hint=(
            "Update mode binds the update-mode.default.v1 checklist; "
            "--phase launch would reset the gate to the creation-mode "
            "checklist. Run the literal in next_action_command."
        ),
    )


def _describe_phase_graph_payload() -> dict:
    """Return the registry-derived phase-graph payload.

    Mirrors :data:`review.transitions.TRANSITIONS` plus the ack /
    entry / terminal sets so callers see the full graph from a single
    JSON document — no need to re-import the module.
    """
    from review.transitions import (
        ACK_PHASES,
        ENTRY_PHASES,
        TERMINAL_PHASES,
        TRANSITIONS,
    )
    registry = registered_phases()
    return {
        "transitions": {
            phase: sorted(nexts) for phase, nexts in TRANSITIONS.items()
        },
        "ack_phases": sorted(ACK_PHASES),
        "entry_phases": sorted(ENTRY_PHASES),
        "terminal_phases": sorted(TERMINAL_PHASES),
        "registered_phases": sorted(registry),
    }


def main() -> None:
    argv_own, passthrough = _split_passthrough(sys.argv[1:])
    parser = _build_parser()
    # ``parse_known_args`` lets agent-typed phase flags slip through to
    # ``unknown``; the dispatcher then promotes them into the
    # passthrough tail so invocations work with or without the ``--``
    # separator.
    args, unknown = parser.parse_known_args(argv_own)

    if getattr(args, "describe_phase_graph", False):
        output.success(
            _describe_phase_graph_payload(),
            "Pipeline phase-graph (canonical source of truth)",
        )

    # Apply per-category default from ``sdd_core.category_registry`` before
    # validating the locator trio. Categories with a non-``None`` default
    # and let the caller omit ``--target-name`` entirely.
    if not args.target_name and _is_known_category(args.category):
        fallback = _category_default_target(args.category)
        if fallback:
            args.target_name = fallback

    if not args.target_name:
        known = ", ".join(sorted(CATEGORY_REGISTRY.keys()))
        output.error(
            "--target-name / --spec-name is required",
            hint=(
                "Provide the spec, steering, or discovery project name "
                "so the dispatcher can locate the gate session. "
                f"Categories with a default target: "
                f"{[c for c, d in CATEGORY_REGISTRY.items() if d.default_target_name]}. "
                f"Known categories: [{known}]."
            ),
        )

    project_path = paths.resolve_project_path(args)

    from sdd_core import preflight_state as _preflight_state
    _preflight_state.gate_on_unresolved_advisories(workspace=project_path)

    # Persist the resolved harness identity on every tick. Idempotent —
    # writing the same name is a no-op. Pairs with the safe-default
    # ``persist=False`` contract so the state file only lands when a
    # confirmed signal picks the adapter. Contradictions exit via
    # ``output.error`` inside ``load_adapter`` — no blanket catch here.
    persist_state(load_adapter(project_path).name, project_path)

    # Dispatcher routing is read-only; downstream phase handlers own the
    # "genuinely-missing session" banner. ``quiet_missing=True`` here
    # avoids a duplicate INFO line on every tick.
    session = read_session(
        args.category, args.target_name, project_path,
        quiet_missing=True,
    )
    gate = session.get("review_gate") or {}
    phase = _resolve_phase(gate, args.phase)

    if unknown:
        promoted, residue = _auto_promote_unknown(unknown, phase)
        if residue:
            _report_unknown_flags(residue, phase)
        # Auto-promoted inline flags take precedence over cache/session
        # injection, matching the explicit ``--`` passthrough semantics.
        passthrough = promoted + passthrough

    # ``discard`` is the operator reset hatch — it deletes a named
    # gate's session state, so requiring a literal ``--gate-id`` here
    # avoids the dispatcher silently injecting one from the session
    # (the same session the operator is asking to drop). The check runs
    # against the merged passthrough tail so both ``--`` and inline
    # forms satisfy it.
    if phase == "discard":
        merged_tail = passthrough
        if "--gate-id" not in merged_tail:
            output.error(
                "discard phase requires --gate-id <id>",
                hint=(
                    "Pass --gate-id <id> after the dispatcher locator "
                    "flags (or behind the `--` separator). The discard "
                    "phase only deletes session state matching the "
                    "named gate; an unset gate-id would have no anchor."
                ),
            )

    _maybe_block_wrong_update_entry(
        phase=phase,
        passthrough=passthrough,
        category=args.category,
        target_name=args.target_name,
        project_path=project_path,
    )

    sub_argv = _build_subprocess_argv(
        args, project_path, phase, passthrough, session=session,
    )
    # Pin the workflow's current-target before dispatching the launch
    # phase so subsequent ticks (post-review, post-fix, pre-approval)
    # resolve ``ctx.target`` / ``ctx.phase`` from the session instead of
    # re-typing the dispatcher locator. Subsequent phases preserve the
    # value; ``cleanup_on_approval`` clears it at workflow boundary.
    if phase in _SESSION_PINNING_PHASES and args.target_name:
        write_current_target(
            args.target_name,
            phase=phase,
            category=args.category,
            project_path=project_path,
        )
    exit_code = _run_phase(
        sub_argv,
        dry_run=bool(getattr(args, "dry_run", False)),
        print_field=getattr(args, "print_field", None),
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    cli.run_main(main)
