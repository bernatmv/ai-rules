"""Canonical command templates emitted by the pipeline.

Every substantive CLI shape the agent is expected to run is emitted by
the pipeline verbatim; reconstructing from prose is the failure mode
this module eliminates.

Guiding rules:
  * Placeholders use ``{foo}`` only. No ``…``, no ``<foo>``, no prose
    like "your approval id here".
  * Each template is a single line so token inflation is predictable
    and response-length calibration doesn't truncate us.
  * A ``placeholder_substitution_note`` is emitted alongside so
    literalism-first readers substitute only the named tokens.
"""
from __future__ import annotations

import ast
import difflib
import functools
import os
import shlex as _shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Final, Iterable, Mapping

from sdd_core.phase_inner_flags import allowed_flags_for_phase
from sdd_core.security.constants import HUMAN_APPROVAL_ENV, HUMAN_APPROVAL_VALUE

# Module-private — every external caller goes through ``build_shim_command``
# so the literal has a single owner. The internal lint flags any
# ``.spec-workflow/sdd `` literal outside this file.
_SDD_SHIM_PREFIX = ".spec-workflow/sdd "

COORDINATOR_REPO_TYPE = "coordinator"
DOC_TYPE_WORKSPACE_REQUIREMENTS = "workspace-requirements"

__all__ = [
    "APPROVAL_PLACEHOLDER_NOTE",
    "COORDINATOR_REPO_TYPE",
    "DEFAULT_APPROVE_RESPONSE",
    "DOC_TYPE_WORKSPACE_REQUIREMENTS",
    "PhaseLocator",
    "PostFixRecommendation",
    "PostReviewState",
    "RelaunchInput",
    "RenderedCommand",
    "placeholder_note",
    "approval_commands",
    "approve_with_human_env",
    "ceremony_prompt_command",
    "template_resolve_command",
    "build_shim_command",
    "build_template_resolve_commands",
    "build_lint_requirements_command",
    "build_lint_tasks_command",
    "build_check_traceability_command",
    "build_render_task_prompts_command",
    "build_pre_launch_check_command",
    "build_detect_doc_state_command",
    "build_check_re_review_command",
    "build_compound_discovery_command",
    "build_generate_prompt_list_command",
    "build_baseline_refresh_command",
    "build_internal_lint_command",
    "build_template_repair_command",
    "build_ensure_healthy_command",
    "build_workspace_preflight_all_command",
    "build_workspace_init_feature_command",
    "build_workspace_phase_approve_command",
    "build_workspace_update_manifest_command",
    "build_workspace_update_tracker_command",
    "build_resolve_advisory_command",
    "build_check_spec_shape_command",
    "build_approval_formal_prompt_command",
    "build_workspace_batch_approve_phase_prompt_command",
    "build_lint_design_command",
    "build_validate_review_artifact_command",
    "build_retroactive_review_command",
    "build_review_snapshot_command",
    "build_review_launch_command",
    "build_relaunch_from_cache_command",
    "build_relaunch_command",
    "build_check_revalidation_command",
    "build_phase_history_command",
    "build_post_fix_command",
    "build_post_fix_command_with_recommended",
    "promote_post_fix_phase_command",
    "build_sync_skills_pack_command",
    "build_pipeline_tick_launch_command",
    "build_pipeline_tick_update_launch_command",
    "build_pipeline_tick_discard_command",
    "build_pipeline_tick_print_field_command",
    "build_pipeline_tick_post_fix_command",
    "build_recovery_launch_command",
    "build_review_pipeline_launch_command",
    "build_review_action_prompt_command",
    "build_review_update_quality_command",
    "build_update_quality_command",
    "UpdateQualityCommand",
    "UPDATE_QUALITY_SCRIPT",
    "build_spec_batch_approval_prompt_command",
    "build_single_doc_approval_prompt_command",
    "build_request_commands_suite",
    "build_migrate_legacy_snapshot_command",
    "build_migrate_review_quality_command",
    "did_you_mean",
    "available_scripts",
    "validate_against_registry",
]


@dataclass(frozen=True)
class RelaunchInput:
    """Strict-typed input for :func:`build_relaunch_command`.

    Carries the exact set of fields the relaunch literal needs.
    Construct from a session via :meth:`from_session`; the conversion
    rejects empty caches with ``ValueError`` so handlers can surface a
    structured ``output.error`` envelope instead of emitting a partial
    command literal.
    """

    launch_flags: dict[str, Any] = field(default_factory=dict)
    locator: dict[str, str] = field(default_factory=dict)
    fix_cycle: "int | None" = None
    gate_id: "str | None" = None
    review_mode: "str | None" = None

    @classmethod
    def from_session(
        cls,
        session: dict,
        *,
        project_path: "str | os.PathLike[str]" = "",
        fix_cycle: "int | None" = None,
        gate_id: "str | None" = None,
        review_mode: "str | None" = None,
    ) -> "RelaunchInput":
        """Materialise a :class:`RelaunchInput` from a session dict.

        Reads ``review_gate.launch_flags`` first, then falls back to
        ``launch_args_cache`` for sessions persisted before the
        per-gate flag set was added. Raises ``ValueError`` if neither
        carries enough state to rebuild the launch literal.
        """
        from review_quality.gate_session import (
            GATE_LAUNCH_ARGS_CACHE,
            GATE_LAUNCH_FLAGS,
            GATE_REVIEW_GATE,
        )

        gate = (session or {}).get(GATE_REVIEW_GATE) or {}
        cache = (session or {}).get(GATE_LAUNCH_ARGS_CACHE) or {}
        persisted = gate.get(GATE_LAUNCH_FLAGS) or {}
        if not persisted:
            persisted = {
                "review_skill": cache.get("review_skill") or "",
                "doc_list": cache.get("doc_list", ""),
                "scope": cache.get("scope", ""),
            }
        if not any(persisted.get(k) for k in ("review_skill", "doc_list")):
            raise ValueError(
                "session lacks launch_flags / launch_args_cache; cannot "
                "reconstruct relaunch command"
            )
        project = os.fspath(project_path) if project_path else cache.get("project_path", "")
        locator = {
            "category": cache.get("category", ""),
            "target_name": cache.get("target_name", ""),
            "project_path": project,
        }
        return cls(
            launch_flags=dict(persisted),
            locator=locator,
            fix_cycle=fix_cycle,
            gate_id=gate_id,
            review_mode=review_mode,
        )


@dataclass(frozen=True)
class RenderedCommand:
    """Validated phase-tick command shape.

    Builders construct one to assert ``inner_flags.keys() ⊆
    allowed_flags_for_phase(phase)``. Construction is the only
    validation point — a phase that does not appear in
    ``data/phase_inner_flags.yaml`` raises, as does a flag the phase's
    argparse rejects.
    """

    phase: str
    inner_flags: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        allowed = allowed_flags_for_phase(self.phase)
        leaked = sorted(set(self.inner_flags) - allowed)
        if leaked:
            raise ValueError(
                f"phase {self.phase!r} rejects flags {leaked}"
            )


@functools.cache
def _required_flag_names_for(script: str) -> frozenset[str]:
    """Return the long-form flags *script* declares ``required=True`` (AST-only)."""
    # Empty set on resolution failure — emitter-fixture lint covers that path.
    path = _resolve_script_path(script)
    if path is None or not path.is_file():
        return frozenset()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return frozenset()
    return frozenset(_extract_required_flags(tree))


def _resolve_script_path(script: str) -> "Path | None":
    """Resolve ``'review/update-quality.py'`` to an absolute path under
    the common-skill scripts directory.

    Returns ``None`` when the skills root can't be located or the file
    does not exist — the introspection check then short-circuits to
    a no-op so test environments without an installed skills tree
    still load this module.
    """
    try:
        from sdd_core import paths

        root = paths.find_skills_root()
    except Exception:
        return None
    candidate = paths.common_scripts_dir(root) / script
    return candidate if candidate.exists() else None


def _extract_required_flags(tree: ast.AST) -> set[str]:
    """Walk *tree* and collect argparse flag names declared required.

    Two recognised declarations:
      1. ``parser.add_argument("--flag", ..., required=True, ...)``
      2. ``cli.target_argument(parser, family=...)`` — implies a
         required ``--target`` unless ``required=False`` is passed.
    """
    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "add_argument":
            flag = _required_flag_from_add_argument(node)
            if flag:
                out.add(flag)
            continue
        if _is_target_argument_call(func) and _target_argument_is_required(node):
            out.add("--target")
    return out


def _required_flag_from_add_argument(node: ast.Call) -> "str | None":
    """Return the canonical long-form flag if ``parser.add_argument`` is required."""
    is_required = any(
        kw.arg == "required"
        and isinstance(kw.value, ast.Constant)
        and kw.value.value is True
        for kw in node.keywords
    )
    if not is_required:
        return None
    for arg in node.args:
        if (
            isinstance(arg, ast.Constant)
            and isinstance(arg.value, str)
            and arg.value.startswith("--")
        ):
            return arg.value
    return None


def _is_target_argument_call(func: ast.AST) -> bool:
    if isinstance(func, ast.Attribute) and func.attr == "target_argument":
        return True
    if isinstance(func, ast.Name) and func.id == "target_argument":
        return True
    return False


def _target_argument_is_required(node: ast.Call) -> bool:
    """``target_argument(...)`` defaults to ``required=True``; honour overrides."""
    for kw in node.keywords:
        if kw.arg == "required" and isinstance(kw.value, ast.Constant):
            return bool(kw.value.value)
    return True


def _check_required_flags(
    script: str,
    *,
    parent_flags: Mapping[str, Any],
    flags: Mapping[str, Any],
) -> None:
    """Raise ``TypeError`` if the call omits a flag the target script requires.

    Compares the long-form flag names emitted by the call (kebab-case
    of the kwargs) against :func:`_required_flag_names_for`. A missing
    flag means the emitter and the script's argparse have drifted —
    fail loud at the call site rather than at downstream argparse
    failure or runtime ``parser.error()``.
    """
    required = _required_flag_names_for(script)
    if not required:
        return
    provided: set[str] = set()
    for name, value in {**parent_flags, **flags}.items():
        if value is False or value is None or value == "":
            continue
        provided.add("--" + name.replace("_", "-"))
    missing = sorted(required - provided)
    if missing:
        raise TypeError(
            f"build_shim_command({script!r}, ...): missing required "
            f"flag(s) {missing} declared by {script}'s argparse. "
            "Update the emitter call site (or the script's parser) so "
            "the contract holds."
        )


def build_shim_command(
    script: str,
    *,
    subcommand: "str | None" = None,
    project_path: "str | os.PathLike[str]" = "",
    positional: "tuple[str, ...]" = (),
    parent_flags: "dict[str, object] | None" = None,
    **flags: object,
) -> str:
    """Render a canonical ``.spec-workflow/sdd <script> ...`` shim line.

    Single emitter for every shim invocation surfaced as a
    ``next_action_command``. Flag names convert ``snake_case`` to
    ``--kebab-case`` (so ``spec_name=...`` becomes ``--spec-name``);
    ``True`` renders a bare switch; falsy values are dropped so callers
    can pass optional kwargs without guarding each call site.
    ``--workspace`` is appended after named flags but before the
    ``--`` positional separator.

    *subcommand* — when set, emitted as the first positional token after
    the script path so argparse subparsers see the action verb before
    any flags.

    *parent_flags* — flags registered on the parent parser (before
    ``add_subparsers``). Rendered before the subcommand token so
    argparse sees them in the parent slice; otherwise they fall into
    the subparser's argv and trigger ``required: --target``.

    Pre-render check — when *subcommand* is omitted (flat-parser
    scripts), the emitter cross-checks the call against the target
    script's argparse and raises ``TypeError`` if a ``required=True``
    flag is missing. Subcommand-driven dispatchers (e.g.
    ``review/pipeline-tick.py``) are validated by the per-phase
    inner-flag machinery instead.
    """
    if subcommand is None:
        _check_required_flags(
            script,
            parent_flags=parent_flags or {},
            flags=flags,
        )
    head = f"{_SDD_SHIM_PREFIX}{script}"
    parts: list[str] = [head]
    if parent_flags:
        for name, value in parent_flags.items():
            if value is False or value is None or value == "":
                continue
            flag = "--" + name.replace("_", "-")
            if value is True:
                parts.append(flag)
            else:
                parts.append(f"{flag} {value}")
    if subcommand:
        parts.append(subcommand)
    for name, value in flags.items():
        if value is False or value is None or value == "":
            continue
        flag = "--" + name.replace("_", "-")
        if value is True:
            parts.append(flag)
        else:
            parts.append(f"{flag} {value}")
    if project_path:
        parts.append(f"--workspace {os.fspath(project_path)}")
    if positional:
        parts.append("--")
        parts.extend(str(p) for p in positional)
    return " ".join(parts)


def build_baseline_refresh_command(
    rule_id: str = "",
    *,
    prune: bool = False,
    all_rules: bool = False,
) -> str:
    """Canonical shim line for refreshing baseline manifest entries.

    Pass ``rule_id`` to refresh one rule, ``all_rules=True`` to rewrite
    every rule. ``prune`` drops manifest rows no longer observed.
    """
    if all_rules and rule_id:
        raise ValueError("pass rule_id or all_rules=True, not both")
    if not rule_id and not all_rules:
        raise ValueError("rule_id is required unless all_rules=True")
    return build_shim_command(
        "internal_lints/baseline-refresh.py",
        all=all_rules,
        rule=rule_id if not all_rules else "",
        prune=prune,
    )


def build_internal_lint_command(rule_id: str, *, refresh: bool = False) -> str:
    """Canonical shim line for invoking one internal-lint script.

    Parallel to :func:`build_baseline_refresh_command` — owns the
    ``.spec-workflow/sdd internal_lints/<rule>.py`` shape so SKILL.md
    lint emitters never inline the literal.
    """
    leaf = rule_id.replace("-", "_") if "-" in rule_id else rule_id
    script = leaf if leaf.endswith(".py") else f"{leaf}.py"
    return build_shim_command(
        f"internal_lints/{script}",
        refresh=refresh,
    )


def build_template_repair_command(
    project_path: "str | os.PathLike[str]",
    templates: Iterable[str] = (),
) -> str:
    """Canonical shim line for the opt-in destructive template repair.

    Emits ``--force-template-repair`` so the operator must explicitly
    request the overwrite. The drifted-template names are listed in the
    advisory body, not the command, so the literal stays predictable.
    """
    _ = tuple(templates)
    project = os.fspath(project_path)
    return (
        f"{_SDD_SHIM_PREFIX}workspace/ensure-healthy.py "
        f"--workspace {project} --auto-fix --force-template-repair"
    )


def build_ensure_healthy_command(
    *, workspace_path: str = ".",
) -> str:
    """Canonical shim line for ``workspace/ensure-healthy.py``."""
    return build_shim_command(
        "workspace/ensure-healthy.py",
        project_path=workspace_path if workspace_path != "." else "",
    )


def build_workspace_preflight_all_command(
    project_path: "str | os.PathLike[str]",
    *,
    auto_fix: bool = False,
) -> str:
    """Canonical shim line for the workspace fan-out pre-flight."""
    project = os.fspath(project_path)
    suffix = " --auto-fix" if auto_fix else ""
    return (
        f"{_SDD_SHIM_PREFIX}workspace/preflight-all.py "
        f"--workspace {project}{suffix}"
    )


def build_sync_skills_pack_command(
    *,
    feature: str,
    workspace_path: "str | os.PathLike[str]" = ".",
    dry_run: bool = False,
) -> str:
    """Canonical shim line for ``workspace/sync-skills-pack.py``."""
    project = os.fspath(workspace_path)
    parts = [
        f"{_SDD_SHIM_PREFIX}workspace/sync-skills-pack.py",
        f"--target {_quote(feature)}",
        f"--workspace {project}",
    ]
    if dry_run:
        parts.append("--dry-run")
    return " ".join(parts)


def build_workspace_init_feature_command(
    *,
    feature: str,
    repos: Iterable[str],
    workspace_path: str = ".",
    mode: str = "default",
) -> str:
    """Canonical shim line for ``workspace/init-feature.py``.

    ``mode`` is ``"default"`` / ``"idempotent"`` / ``"force"`` (mutually
    exclusive). ``repos`` items are pre-formatted ``role:path:sub-spec``
    strings — the caller composes them so feature-specific conventions
    stay outside this emitter.
    """
    if mode not in {"default", "idempotent", "force"}:
        raise ValueError(f"mode must be default|idempotent|force, got {mode!r}")
    parts = [
        f"{_SDD_SHIM_PREFIX}workspace/init-feature.py",
        f"--target {_quote(feature)}",
    ]
    if workspace_path and workspace_path != ".":
        parts.append(f"--workspace {workspace_path}")
    for repo in repos:
        parts.append(f"--repo {_quote(str(repo))}")
    if mode == "idempotent":
        parts.append("--idempotent")
    elif mode == "force":
        parts.append("--force")
    return " ".join(parts)


def build_resolve_advisory_command(
    *, name: str, workspace_path: str = ".",
) -> str:
    """Canonical shim line for resolving a persisted pre-flight advisory."""
    return build_shim_command(
        "workspace/resolve-advisory.py",
        name=_quote(name),
        project_path=workspace_path if workspace_path != "." else "",
    )


def build_check_spec_shape_command(
    *,
    workspace_path: "str | os.PathLike[str]",
    feature: str,
    repo_id: str,
    doc: str = "requirements",
) -> str:
    """Canonical shim line for ``workspace/check-spec-shape.py``.

    Used by the "wrong workspace" recovery emitter so the rendered
    ``did_you_mean`` literal has a single owner instead of being
    composed inline at the call site.
    """
    target = f"{feature}/{repo_id}"
    return build_shim_command(
        "workspace/check-spec-shape.py",
        workspace=os.fspath(workspace_path),
        target=target,
        doc=doc,
    )


def build_workspace_phase_approve_command(
    *,
    feature: str,
    doc: str,
    workspace_path: str = ".",
    human_env: bool = False,
) -> str:
    """Canonical shim line for ``workspace/phase-approve.py``.

    With ``human_env=True`` the command is wrapped in the H1 env var
    so the caller can use the result as a retry shim emitted from a
    preflight gate.
    """
    base = build_shim_command(
        "workspace/phase-approve.py",
        project_path=workspace_path if workspace_path != "." else "",
        target=_quote(feature),
        doc=doc,
    )
    if human_env:
        return f"{HUMAN_APPROVAL_ENV}={HUMAN_APPROVAL_VALUE} {base}"
    return base


_PROMPT_TYPE_APPROVAL_FORMAL = "approval-formal"
_PROMPT_TYPE_WORKSPACE_BATCH_APPROVE_PHASE = "workspace-batch-approve-phase"
_PROMPT_TYPE_APPROVAL_CONFIRM_HUMAN = "approval-confirm-human"
_PROMPT_TYPE_REVIEW_ACTION = "review-action"
_PROMPT_TYPE_SPEC_BATCH_APPROVAL = "spec-batch-approval"
_PROMPT_TYPE_SINGLE_DOC_APPROVAL = "single-doc-approval"


def validate_against_registry(
    prompt_type: str,
    params: Mapping[str, Any] | Iterable[str],
    *,
    registry: dict | None = None,
) -> list[str]:
    """Return the registry's required-but-missing param names for *prompt_type*.

    Empty list means every required key is present. Unknown prompt
    types raise :class:`KeyError` so callers can route to a richer
    "did you mean" envelope rather than silently passing.

    ``params`` may be a mapping (key→value) or an iterable of supplied
    names — only the key set is consulted. The check uses the
    registry's ``params`` array (the canonical "required" field for
    every entry).
    """
    from sdd_core.prompts import load_registry as _load_registry

    reg = registry or _load_registry()
    prompts = reg.get("prompts", {})
    if prompt_type not in prompts:
        raise KeyError(prompt_type)
    required = list(prompts[prompt_type].get("params", []))
    if isinstance(params, Mapping):
        supplied = set(params.keys())
    else:
        supplied = set(params)
    return [p for p in required if p not in supplied]


def _assert_registry_params(
    prompt_type: str, params: Mapping[str, Any],
) -> None:
    """Raise :class:`ValueError` if registry-required params are missing.

    Builders call this before emitting a literal so the closed-loop
    matcher fails fast at construction time rather than letting a
    half-formed command reach the agent. Registry-load failures are
    swallowed (best-effort): the canonical schema check lives in
    ``util/generate-prompt.py --validate-registry``.
    """
    try:
        missing = validate_against_registry(prompt_type, params)
    except (KeyError, FileNotFoundError):
        return
    if missing:
        raise ValueError(
            f"Builder for {prompt_type!r} missing registry-required params: "
            f"{', '.join(missing)}"
        )


def build_review_action_prompt_command(
    *,
    doc: str,
    workspace_path: str = ".",
) -> str:
    """Render the canonical ``util/generate-prompt.py --type review-action`` literal.

    Single owner of the ``review-action`` prompt-id literal —
    ``update-mode-workflow.md`` Step 6 emits this for the present-changes
    invocation, and any future surface that needs the same prompt-id
    reuses the builder instead of inlining the string. Mirrors
    :func:`build_approval_formal_prompt_command` shape — both target
    the same ``util/generate-prompt.py`` script.
    """
    parts = [
        f"{_SDD_SHIM_PREFIX}util/generate-prompt.py",
        f"--type {_PROMPT_TYPE_REVIEW_ACTION}",
        f'--params doc="{doc}"',
    ]
    if workspace_path and workspace_path != ".":
        parts.append(f"--workspace {workspace_path}")
    return " ".join(parts)


def build_approval_formal_prompt_command(
    *,
    doc_list: str,
    summary: str = "",
    no_skip: bool = True,
) -> str:
    """Render the canonical ``util/generate-prompt.py --type approval-formal`` literal.

    Single owner of the ``approval-formal`` prompt-id literal — the
    pre-approval phase emits this for non-workspace targets, and any
    future surface that needs the same prompt-id reuses the builder
    instead of inlining the string.
    """
    parts = [
        f"{_SDD_SHIM_PREFIX}util/generate-prompt.py",
        f"--type {_PROMPT_TYPE_APPROVAL_FORMAL}",
    ]
    if no_skip:
        parts.append("--no-skip")
    parts.append(f'--params doc="{doc_list}"')
    if summary:
        parts.append(f"--params summary={_shlex.quote(summary)}")
    return " ".join(parts)


def build_workspace_batch_approve_phase_prompt_command(
    *,
    doc_list: str,
    feature: str,
    repo_id: str = "",
    repo_count: int = 0,
    summary: str = "",
) -> str:
    """Render the workspace-aware approval prompt invocation.

    The workspace skill folds the H1 attestation into the operational
    choice, so the rendered ``util/generate-prompt.py --type
    workspace-batch-approve-phase`` literal is what
    :mod:`review.pipeline_phases.pre_approval` emits for workspace
    targets. ``feature`` and ``repo_id`` are surfaced as params so the
    prompt body can reference them; ``repo_count`` is the batch
    cardinality the prompt template expects.
    """
    parts = [
        f"{_SDD_SHIM_PREFIX}util/generate-prompt.py",
        f"--type {_PROMPT_TYPE_WORKSPACE_BATCH_APPROVE_PHASE}",
        f'--params doc="{doc_list}"',
        f"--params feature={_shlex.quote(feature)}",
    ]
    if repo_id:
        parts.append(f"--params repo_id={_shlex.quote(repo_id)}")
    if repo_count:
        parts.append(f"--params repo_count={repo_count}")
    if summary:
        parts.append(f"--params summary={_shlex.quote(summary)}")
    return " ".join(parts)


def build_spec_batch_approval_prompt_command(
    *,
    approval_id: str,
    doc_keys: Iterable[str],
    summary: str = "",
    workspace_path: str = ".",
) -> str:
    """Render the canonical ``util/generate-prompt.py --type spec-batch-approval`` literal.

    Single owner of the ``spec-batch-approval`` prompt-id literal — the
    pre-approval phase emits this for ``category=spec, scope=final`` when
    more than one document needs approval. ``doc_keys`` is collapsed to a
    comma-separated list and surfaced under ``--params docs="…"`` so the
    prompt body can reference the cohort.
    """
    docs_str = ",".join(str(d).strip() for d in doc_keys if str(d).strip())
    if not docs_str:
        raise ValueError(
            "build_spec_batch_approval_prompt_command requires at least one doc_key"
        )
    supplied = {"approval_id": approval_id, "docs": docs_str}
    if summary:
        supplied["summary"] = summary
    _assert_registry_params(_PROMPT_TYPE_SPEC_BATCH_APPROVAL, supplied)
    parts = [
        f"{_SDD_SHIM_PREFIX}util/generate-prompt.py",
        f"--type {_PROMPT_TYPE_SPEC_BATCH_APPROVAL}",
        f"--params approval_id={_shlex.quote(approval_id)}",
        f'--params docs="{docs_str}"',
    ]
    if summary:
        parts.append(f"--params summary={_shlex.quote(summary)}")
    if workspace_path and workspace_path != ".":
        parts.append(f"--workspace {workspace_path}")
    return " ".join(parts)


def build_single_doc_approval_prompt_command(
    *,
    approval_id: str,
    doc_key: str,
    summary: str = "",
    workspace_path: str = ".",
) -> str:
    """Render the canonical ``util/generate-prompt.py --type single-doc-approval`` literal.

    Single owner of the ``single-doc-approval`` prompt-id literal — the
    pre-approval phase emits this for ``category=spec, scope=per-document``.
    Mirrors :func:`build_spec_batch_approval_prompt_command` shape so the
    two spec-approval surfaces feel symmetrical.
    """
    if not doc_key:
        raise ValueError(
            "build_single_doc_approval_prompt_command requires a doc_key"
        )
    supplied = {"approval_id": approval_id, "doc": doc_key}
    if summary:
        supplied["summary"] = summary
    _assert_registry_params(_PROMPT_TYPE_SINGLE_DOC_APPROVAL, supplied)
    parts = [
        f"{_SDD_SHIM_PREFIX}util/generate-prompt.py",
        f"--type {_PROMPT_TYPE_SINGLE_DOC_APPROVAL}",
        f"--params approval_id={_shlex.quote(approval_id)}",
        f'--params doc="{doc_key}"',
    ]
    if summary:
        parts.append(f"--params summary={_shlex.quote(summary)}")
    if workspace_path and workspace_path != ".":
        parts.append(f"--workspace {workspace_path}")
    return " ".join(parts)


def build_workspace_update_tracker_command(
    *,
    feature: str,
    repo_id: str,
    doc: str,
    status: str,
    workspace_path: str = ".",
) -> str:
    """Canonical shim line for ``workspace/update-tracker.py``.

    Mirrors the ``{feature}/{repo-id}`` target convention used by the
    rest of ``build_workspace_*`` emitters. Renders ``--doc-status``
    plus ``--phase`` so the resulting literal directly sets the named
    document's status.
    """
    target = f"{feature}/{repo_id}"
    return build_shim_command(
        "workspace/update-tracker.py",
        project_path=workspace_path if workspace_path != "." else "",
        target=_quote(target),
        phase=doc,
        doc_status=status,
    )


def build_workspace_update_manifest_command(
    *,
    feature: str,
    subcommand: str,
    workspace_path: str = ".",
    **subargs: object,
) -> str:
    """Canonical shim line for ``workspace/update-manifest.py``.

    *subcommand* is the literal subparser name (e.g. ``set-repo-role``).
    ``subargs`` are forwarded as ``--kebab-case`` flags via the existing
    :func:`build_shim_command` snake-to-kebab conversion, so
    ``repo_id="x"`` becomes ``--repo-id x``. Mirrors
    :func:`build_workspace_phase_approve_command` shape so the two
    update flows feel symmetrical.

    ``--target`` and ``--workspace`` are registered on the parent
    parser (via ``cli.target_argument`` / ``cli.strict_parser``); they
    are routed through ``parent_flags`` so the rendered literal places
    them BEFORE the subcommand token. Argparse subparsers do not see
    parent-parser flags written after the subcommand on the command
    line — emitting them post-subcommand triggers
    ``required: --target``.
    """
    parent: dict[str, object] = {"target": _quote(feature)}
    if workspace_path and workspace_path != ".":
        # Emit ``--workspace`` in the parent slice so it parses
        # before the subcommand token (the snake→kebab key path
        # renders ``--workspace`` canonically).
        parent["workspace"] = workspace_path
    return build_shim_command(
        "workspace/update-manifest.py",
        subcommand=subcommand,
        parent_flags=parent,
        **{k: _quote(str(v)) if isinstance(v, str) else v for k, v in subargs.items()},
    )


def build_lint_design_command(
    *,
    spec_name: str,
    project_path: str = ".",
) -> str:
    """Canonical ``spec/lint-design.py`` shim invocation."""
    return build_shim_command(
        "spec/lint-design.py",
        project_path=project_path,
        target=_quote(spec_name),
    )


def build_validate_review_artifact_command(
    *,
    category: str,
    target_name: str,
    project_path: str | None = None,
    strict_presence: bool = False,
) -> str:
    """Canonical ``review/validate-review-artifact.py`` invocation."""
    return build_shim_command(
        "review/validate-review-artifact.py",
        project_path=project_path or "",
        category=category,
        target_name=_quote(target_name),
        strict_presence=strict_presence,
    )


def build_retroactive_review_command(
    *,
    feature: str,
    workspace_path: str = ".",
    phase: str = "",
    repo_id: str = "",
    dry_run: bool = False,
) -> str:
    """Canonical ``workspace/retroactive-review.py`` invocation."""
    return build_shim_command(
        "workspace/retroactive-review.py",
        project_path=workspace_path if workspace_path != "." else "",
        target=_quote(feature),
        phase=phase,
        repo_id=repo_id,
        dry_run=dry_run,
    )


def build_review_snapshot_command(
    *,
    feature: str,
    repo_id: str,
    phase: str,
    workspace_path: str = ".",
) -> str:
    """Canonical ``review/snapshot-and-mark-reviewed.py`` invocation."""
    target = f"{feature}/{repo_id}"
    return build_shim_command(
        "review/snapshot-and-mark-reviewed.py",
        project_path=workspace_path if workspace_path != "." else "",
        target=_quote(target),
        phase=phase,
    )


# Order in which launch flags are rendered into the post-`--` tail of
# ``review/pipeline-tick.py --phase launch``. Pinned so the literal is
# byte-stable across emissions.
_LAUNCH_FLAG_ORDER: tuple[str, ...] = (
    "review_skill",
    "doc_list",
    "scope",
    "workflow_mode",
    "max_cycles",
    "parent_todo",
    "gate_id",
)


# ``max_cycles`` is the gate-state name; ``--max-fix-cycles`` is the
# canonical CLI flag (per ``LaunchInput.max_fix_cycles``). Other keys
# kebab-case directly.
_LAUNCH_FLAG_NAME_OVERRIDES: dict[str, str] = {
    "max_cycles": "--max-fix-cycles",
}


def _launch_flag_name(name: str) -> str:
    return _LAUNCH_FLAG_NAME_OVERRIDES.get(name) or "--" + name.replace("_", "-")


def _render_launch_flag(name: str, value: object) -> "str | None":
    """Render a single launch flag pair as ``--kebab-name <value>`` or ``None``.

    ``None``, empty strings, and ``False`` are dropped so the rendered
    literal is identical to a hand-pasted first launch. ``doc_list`` is
    double-quoted because the dispatcher passthrough preserves the full
    comma-separated string only when shell sees it as one argv element.
    """
    if value in (None, "", False):
        return None
    flag = _launch_flag_name(name)
    if name == "doc_list":
        return f'{flag} "{value}"'
    return f"{flag} {value}"


def build_review_launch_command(
    *,
    launch_flags: dict,
    locator: dict,
    fix_cycle: "int | None" = None,
    gate_id: "str | None" = None,
    review_mode: "str | None" = None,
) -> str:
    """Canonical emitter for ``review/pipeline-tick.py --phase launch``.

    Used for both first launch and re-launch. Routes through one
    builder so the literals are byte-equal modulo the ``--gate-id``
    delta the re-launch path supplies. ``fix_cycle`` is read by the
    launch handler off gate state — never rendered as a CLI flag.

    Raises ``ValueError`` when ``launch_flags`` carries a key whose
    rendered CLI flag is not declared on the launch phase's argparse.
    """
    category = locator.get("category", "")
    target_name = locator.get("target_name", "")
    project_path = locator.get("project_path", "")

    effective_flags: dict[str, Any] = dict(launch_flags or {})
    if gate_id is not None:
        effective_flags["gate_id"] = gate_id
    _ = fix_cycle

    inner_flag_set = {
        _launch_flag_name(name)
        for name, value in effective_flags.items()
        if value not in (None, "", False)
    }
    RenderedCommand(phase="launch", inner_flags={k: "" for k in inner_flag_set})

    parts = [
        f"{_SDD_SHIM_PREFIX}review/pipeline-tick.py",
        f"--category {category}",
        f'--target-name "{target_name}"',
        f"--workspace {project_path}",
        "--phase launch",
        "--",
    ]
    for name in _LAUNCH_FLAG_ORDER:
        rendered = _render_launch_flag(name, effective_flags.get(name))
        if rendered is not None:
            parts.append(rendered)
    if review_mode:
        parts.append(f"--review-mode {review_mode}")
    return " ".join(parts)


# Order in which check-revalidation flags are rendered into the
# post-`--` tail. Pinned so the literal is byte-stable across
# emissions; mirrors :data:`_LAUNCH_FLAG_ORDER`.
_REVAL_FLAG_ORDER: tuple[str, ...] = (
    "doc",
    "fix_cycle",
    "max_cycles",
    "parent_todo",
    "gate_id",
)


def build_check_revalidation_command(
    *,
    category: str,
    target_name: str,
    project_path: str,
    doc: str,
    fix_cycle: int = 0,
    max_cycles: int = 0,
    gate_id: str = "",
    parent_todo: str = "",
) -> str:
    """Canonical ``review/pipeline-tick.py --phase check-revalidation`` shim line.

    Routes one re-validation step for a single doc. The shim head
    flows through :func:`build_shim_command` so the parent-flag /
    subparser-flag split mirrors :func:`build_pre_launch_check_command`
    — single owner for the dispatcher's argv layout.
    """
    parent: dict[str, object] = {
        "category": category,
        "target_name": _quote(target_name),
    }
    if project_path:
        # Render under canonical ``--workspace`` (key name maps to flag).
        parent["workspace"] = project_path

    tail_values: dict[str, object] = {
        "doc": doc,
        "fix_cycle": fix_cycle if fix_cycle else None,
        "max_cycles": max_cycles if max_cycles else None,
        "parent_todo": parent_todo or None,
        "gate_id": gate_id or None,
    }
    positional: list[str] = []
    inner_flag_set: set[str] = set()
    for name in _REVAL_FLAG_ORDER:
        value = tail_values.get(name)
        if value in (None, "", False):
            continue
        flag = f"--{name.replace('_', '-')}"
        positional.append(f"{flag} {value}")
        inner_flag_set.add(flag)
    RenderedCommand(
        phase="check-revalidation",
        inner_flags={k: "" for k in inner_flag_set},
    )

    return build_shim_command(
        "review/pipeline-tick.py",
        parent_flags=parent,
        phase="check-revalidation",
        positional=tuple(positional),
    )


def build_relaunch_command(inp: RelaunchInput) -> str:
    """Render the canonical ``--phase launch`` command from a strict input.

    The strict-typed counterpart of :func:`build_relaunch_from_cache_command`
    — handlers that already have a :class:`RelaunchInput` skip the
    session-dict adapter and route directly here.
    """
    if not isinstance(inp, RelaunchInput):
        raise TypeError(
            "build_relaunch_command requires a RelaunchInput; got "
            f"{type(inp).__name__}"
        )
    return build_review_launch_command(
        launch_flags=inp.launch_flags,
        locator=inp.locator,
        fix_cycle=inp.fix_cycle,
        gate_id=inp.gate_id,
        review_mode=inp.review_mode,
    )


def build_phase_history_command(
    *,
    feature: str,
    workspace_path: str = ".",
    phase: str = "",
) -> str:
    """Canonical ``workspace/phase-history.py`` shim invocation.

    Mirrors :func:`build_workspace_phase_approve_command` so the two
    audit-flavour helpers share one shape. ``--phase`` is optional
    (omitted when empty so the literal stays minimal).
    """
    return build_shim_command(
        "workspace/phase-history.py",
        project_path=workspace_path if workspace_path != "." else "",
        target=_quote(feature),
        phase=phase,
    )


def build_post_fix_command(
    *,
    category: str,
    target_name: str,
    project_path: str,
    doc_list: str,
    fix_cycle: int,
    max_cycles: int,
    user_choice: str,
    parent_todo: str = "",
    gate_id: str = "",
    workflow_mode: str = "create",
) -> str:
    """Canonical ``review/pipeline-tick.py --phase post-fix`` shim line.

    Single emitter for the ``post-fix --user-choice X`` literals every
    handler used to format inline. The vocabulary lives on
    :data:`review_quality.constants.USER_CHOICE_ALLOWED`; this emitter
    does not validate it (the tick runner enforces).

    *workflow_mode* renders ``--workflow-mode`` into the same positional
    list every other tail flag rides; the default ``"create"`` is
    omitted from the literal so existing callers see no change.
    """
    parent: dict[str, object] = {
        "category": category,
        "target_name": _quote(target_name),
    }
    if project_path:
        # Render under canonical ``--workspace`` (key name maps to flag).
        parent["workspace"] = project_path

    positional: list[str] = [f'--doc-list "{doc_list}"']
    inner_flag_set: set[str] = {"--doc-list"}
    if fix_cycle:
        positional.append(f"--fix-cycle {fix_cycle}")
        inner_flag_set.add("--fix-cycle")
    if max_cycles:
        positional.append(f"--max-cycles {max_cycles}")
        inner_flag_set.add("--max-cycles")
    if user_choice:
        positional.append(f"--user-choice {user_choice}")
        inner_flag_set.add("--user-choice")
    if parent_todo:
        positional.append(f"--parent-todo {parent_todo}")
        inner_flag_set.add("--parent-todo")
    if gate_id:
        positional.append(f"--gate-id {gate_id}")
        inner_flag_set.add("--gate-id")
    if workflow_mode and workflow_mode != "create":
        positional.append(f"--workflow-mode {workflow_mode}")
        inner_flag_set.add("--workflow-mode")
    RenderedCommand(
        phase="post-fix",
        inner_flags={k: "" for k in inner_flag_set},
    )

    return build_shim_command(
        "review/pipeline-tick.py",
        parent_flags=parent,
        phase="post-fix",
        positional=tuple(positional),
    )


def build_pipeline_tick_launch_command(
    *,
    category: str,
    target_name: str,
    doc_list: str,
    review_skill: str,
    scope: str = "per-document",
    workflow_mode: str = "create",
    parent_todo: "str | None" = None,
    gate_id: "str | None" = None,
    workspace_path: str = ".",
) -> str:
    """Canonical shim line for ``review/pipeline-tick.py --phase launch``."""
    parent: dict[str, object] = {
        "category": category,
        "target_name": _quote(target_name),
    }
    if workspace_path and workspace_path != ".":
        parent["workspace"] = workspace_path

    positional: list[str] = [
        f"--review-skill {review_skill}",
        f'--doc-list "{doc_list}"',
        f"--scope {scope}",
    ]
    if workflow_mode:
        positional.append(f"--workflow-mode {workflow_mode}")
    if parent_todo:
        positional.append(f"--parent-todo {parent_todo}")
    if gate_id:
        positional.append(f"--gate-id {gate_id}")

    return build_shim_command(
        "review/pipeline-tick.py",
        parent_flags=parent,
        phase="launch",
        positional=tuple(positional),
    )


def build_pipeline_tick_update_launch_command(
    *,
    category: str,
    target_name: str,
    doc_list: str,
    review_skill: "str | None" = None,
    scope: str = "per-document",
    workflow_mode: str = "update",
    parent_todo: "str | None" = None,
    gate_id: "str | None" = None,
    workspace_path: str = ".",
) -> str:
    """Canonical shim line for ``review/pipeline-tick.py --phase update-launch``.

    Single emitter for the update-mode entry envelope. Mirrors the
    creation-mode launch literal byte-for-byte modulo ``--phase`` and
    ``--workflow-mode`` so consumers can compare the two via simple
    string substitution.
    """
    parent: dict[str, object] = {
        "category": category,
        "target_name": _quote(target_name),
    }
    if workspace_path and workspace_path != ".":
        parent["workspace"] = workspace_path

    positional: list[str] = []
    if review_skill:
        positional.append(f"--review-skill {review_skill}")
    positional.append(f'--doc-list "{doc_list}"')
    if scope:
        positional.append(f"--scope {scope}")
    if workflow_mode:
        positional.append(f"--workflow-mode {workflow_mode}")
    if parent_todo:
        positional.append(f"--parent-todo {parent_todo}")
    if gate_id:
        positional.append(f"--gate-id {gate_id}")

    return build_shim_command(
        "review/pipeline-tick.py",
        parent_flags=parent,
        phase="update-launch",
        positional=tuple(positional),
    )


def build_pipeline_tick_discard_command(
    *,
    gate_id: str,
    workspace_path: str = ".",
) -> str:
    """Canonical shim line for ``review/pipeline-tick.py --phase discard``.

    Emitted when the agent or operator chooses to discard the pending
    update-mode change set. The phase handler is registered separately
    (downstream); this emitter owns the literal so every surface that
    surfaces the discard command shares one byte-equal shape.
    """
    if not gate_id:
        raise ValueError(
            "build_pipeline_tick_discard_command requires a non-empty gate_id"
        )
    parts = [
        f"{_SDD_SHIM_PREFIX}review/pipeline-tick.py",
        "--phase discard",
        "--",
        f"--gate-id {gate_id}",
    ]
    if workspace_path and workspace_path != ".":
        parts.insert(1, f"--workspace {workspace_path}")
    return " ".join(parts)


def build_pipeline_tick_print_field_command(
    *,
    field_path: str,
    workspace_path: str = ".",
) -> str:
    """Canonical shim line for ``review/pipeline-tick.py --print-field <jsonpath>``.

    Emits the introspection invocation used to extract a single field
    from the dispatcher's last-rendered envelope. ``field_path`` is the
    JSONPath-like selector the dispatcher accepts; this emitter owns
    the literal so every surface that needs the read-side handle shares
    one byte-equal shape.
    """
    if not field_path:
        raise ValueError(
            "build_pipeline_tick_print_field_command requires a non-empty field_path"
        )
    parts = [
        f"{_SDD_SHIM_PREFIX}review/pipeline-tick.py",
        f"--print-field {field_path}",
    ]
    if workspace_path and workspace_path != ".":
        parts.append(f"--workspace {workspace_path}")
    return " ".join(parts)


_RECOVERY_LAUNCH_BUILDER_BY_MODE: Final[
    Mapping[str, Callable[..., str]]
] = {
    "create": build_pipeline_tick_launch_command,
    "update": build_pipeline_tick_update_launch_command,
}


def build_recovery_launch_command(
    *,
    workflow_mode: str,
    category: str,
    target_name: str,
    doc_list: str,
    review_skill: "str | None" = None,
    workspace_path: str = ".",
    parent_todo: "str | None" = None,
    gate_id: "str | None" = None,
    scope: str = "per-document",
) -> str:
    """Single recovery-launch emitter for stale-doc re-entry."""
    from sdd_core.doc_config import skill_name_for_category

    try:
        builder = _RECOVERY_LAUNCH_BUILDER_BY_MODE[workflow_mode]
    except KeyError:
        raise KeyError(
            f"unknown workflow_mode={workflow_mode!r}; registered modes: "
            f"{sorted(_RECOVERY_LAUNCH_BUILDER_BY_MODE)}"
        ) from None
    resolved_skill = review_skill or skill_name_for_category(category)
    return builder(
        category=category,
        target_name=target_name,
        doc_list=doc_list,
        review_skill=resolved_skill,
        scope=scope,
        workspace_path=workspace_path,
        parent_todo=parent_todo,
        gate_id=gate_id,
        workflow_mode=workflow_mode,
    )


def build_review_pipeline_launch_command(
    *,
    target_name: str,
    category: str,
    workspace_path: str = ".",
    review_skill: "str | None" = None,
    doc_list: "str | None" = None,
    scope: str = "per-document",
    workflow_mode: str = "create",
    parent_todo: "str | None" = None,
    gate_id: "str | None" = None,
) -> str:
    """Single-owner emitter for the agent-facing launch shim line.

    Defaults ``review_skill`` and ``doc_list`` from the category so a
    handoff that only knows the category + target lands a complete,
    invocable command — the missing-flag gap closes structurally
    instead of relying on a hand-edited inline string in
    :file:`handoff-registry.json`. Delegates to the existing
    :func:`build_recovery_launch_command` so create / update modes
    resolve through one builder table; the wrapper exists to (a) make
    the kwargs optional and (b) carry a stable name the
    ``emitted_commands_parse`` lint can target.
    """
    from sdd_core.doc_config import (
        default_doc_list_for_category, skill_name_for_category,
    )

    resolved_skill = review_skill or skill_name_for_category(category)
    resolved_doc_list = doc_list or default_doc_list_for_category(category)
    return build_recovery_launch_command(
        workflow_mode=workflow_mode,
        category=category,
        target_name=target_name,
        doc_list=resolved_doc_list,
        review_skill=resolved_skill,
        workspace_path=workspace_path,
        parent_todo=parent_todo,
        gate_id=gate_id,
        scope=scope,
    )


def build_pipeline_tick_post_fix_command(
    *,
    category: str,
    target_name: str,
    doc_list: str,
    fix_cycle: int,
    max_cycles: int = 2,
    workflow_mode: str = "create",
    user_choice: str = "",
    parent_todo: str = "",
    gate_id: str = "",
    workspace_path: str = ".",
) -> str:
    """Canonical shim line for ``review/pipeline-tick.py --phase post-fix``.

    Wraps :func:`build_post_fix_command` with ``workflow_mode`` threaded
    through the underlying emitter's positional list rather than
    concatenated to the rendered string. Existing callers keep
    ``workflow_mode`` defaulting to ``"create"`` so the rendered literal
    matches the pre-existing post-fix shape; callers that opt into
    update-mode pass ``workflow_mode="update"`` and the literal grows
    one flag.
    """
    return build_post_fix_command(
        category=category,
        target_name=target_name,
        project_path=workspace_path if workspace_path != "." else "",
        doc_list=doc_list,
        fix_cycle=fix_cycle,
        max_cycles=max_cycles,
        user_choice=user_choice,
        parent_todo=parent_todo,
        gate_id=gate_id,
        workflow_mode=workflow_mode,
    )


def build_review_update_quality_command(
    *,
    target: str,
    category: str,
    tier2_payload_path: "str | None" = None,
    workspace_path: str = ".",
) -> str:
    """Canonical shim line for ``review/update-quality.py``.

    Single owner of the artifact-refresh literal. ``category`` selects
    the review type (``spec`` / ``steering`` / ``discovery``) and is
    emitted as the script's required ``--type`` flag.
    ``tier2_payload_path`` is optional — most invocations pass an
    inline JSON string at the call site.
    """
    return build_shim_command(
        "review/update-quality.py",
        project_path=workspace_path if workspace_path != "." else "",
        type=category,
        target=_quote(target),
        tier2_payload=tier2_payload_path or "",
    )


# Bare path for prompt prose (sub-agent invocation form). For the
# ``.spec-workflow/sdd ...`` shim line, use ``build_review_update_quality_command``.
UPDATE_QUALITY_SCRIPT: Final[str] = "review/update-quality.py"


@dataclass(frozen=True)
class UpdateQualityCommand:
    """Sub-agent invocation of ``review/update-quality.py``.

    Bare-path / staging-input form: ``--type / --input / --scope``. Use
    ``parts()`` for argv-shaped consumers and ``render()`` for prompt
    prose embedding (shell-quoted via :func:`shlex.quote`). Emits the
    BARE path; for the executable ``.spec-workflow/sdd ...`` shim form
    use :func:`build_review_update_quality_command`.
    """

    review_type: str
    staging_path: str
    scope: "str | None" = None

    def parts(self) -> list[str]:
        """Return the argv-shaped command parts (script first)."""
        out: list[str] = [
            UPDATE_QUALITY_SCRIPT,
            "--type", self.review_type,
            "--input", self.staging_path,
        ]
        if self.scope:
            out.extend(["--scope", self.scope])
        return out

    def render(self) -> str:
        """Return a shell-safe single-line invocation."""
        return " ".join(_shlex.quote(p) for p in self.parts())


def build_update_quality_command(
    *,
    review_type: str,
    scope: "str | None",
    staging_path: str,
) -> UpdateQualityCommand:
    """Build the sub-agent ``review/update-quality.py`` invocation.

    Validates *review_type* against the registered review types so
    callers can't quietly emit a type the script will reject. ``scope``
    is optional — when ``None``, the script's default (``final``) is
    used implicitly. ``staging_path`` is the absolute path the sub-agent
    has staged the assessment JSON to (e.g. under
    ``.spec-workflow/staging/``).
    """
    from sdd_core.doc_config import DOCUMENT_REGISTRY as _REG
    if review_type not in _REG:
        raise ValueError(
            f"unknown review_type {review_type!r}; expected one of "
            f"{sorted(_REG)}"
        )
    return UpdateQualityCommand(
        review_type=review_type,
        scope=scope,
        staging_path=staging_path,
    )


@dataclass(frozen=True)
class PhaseLocator:
    """Locator coordinates shared by every post-review-derived emitter."""

    project_path: str
    category: str
    target_name: str
    parent_todo: str = ""
    gate_id: str = ""


@dataclass(frozen=True)
class PostReviewState:
    """Gate state inputs for the post-fix recommendation policy."""

    scope: str
    fix_cycle: int
    findings_count: int


@dataclass(frozen=True)
class PostFixRecommendation:
    """Composed result of :func:`build_post_fix_command_with_recommended`.

    ``command`` is the literal post-fix shim line with ``--user-choice``
    already substituted; ``recommended`` is the chosen verb; ``enum`` is
    the full allowed vocabulary; ``excluded`` is the set the policy
    masks out; ``rationale`` documents *why* the recommendation was
    selected.
    """

    command: str
    recommended: str
    enum: tuple[str, ...]
    excluded: tuple[str, ...]
    rationale: str


def build_post_fix_command_with_recommended(
    *,
    category: str,
    target_name: str,
    project_path: str,
    doc_list: str,
    fix_cycle: int,
    max_cycles: int,
    scope: str,
    findings_count: int,
    parent_todo: str = "",
    gate_id: str = "",
    recommended_override: "str | None" = None,
) -> PostFixRecommendation:
    """Compose a literal ``post-fix`` command paired with its recommended choice.

    Returns a :class:`PostFixRecommendation`. Single source for "what
    ``--user-choice`` should an envelope emit *as a literal* given the
    current gate state?". Callers write the fields into
    ``phase_commands.post_fix.{command_with_recommended,
    user_choice_recommended, user_choice_enum, user_choice_excluded,
    rationale}``.

    Composes :func:`build_post_fix_command` for the literal and
    :func:`review_quality.constants.user_choices_for_transition` for
    the enum/excluded sets — neither is re-derived.
    """
    from review_quality.constants import (
        RECOMMENDED_CHOICE_ACCEPT,
        RECOMMENDED_CHOICE_FIX_ALL,
        user_choices_for_transition,
    )

    enum, excluded = user_choices_for_transition(
        scope=scope, fix_cycle=fix_cycle, findings_count=findings_count,
    )
    if recommended_override is not None:
        recommended = recommended_override
        rationale = f"caller-supplied recommendation: {recommended}"
    elif findings_count == 0:
        recommended = RECOMMENDED_CHOICE_ACCEPT
        rationale = "review PASS, 0 findings — attest no-fix path"
    else:
        recommended = RECOMMENDED_CHOICE_FIX_ALL
        rationale = f"review reported {findings_count} actionable finding(s)"

    command = build_post_fix_command(
        category=category,
        target_name=target_name,
        project_path=project_path,
        doc_list=doc_list,
        fix_cycle=fix_cycle,
        max_cycles=max_cycles,
        user_choice=recommended,
        parent_todo=parent_todo,
        gate_id=gate_id,
    )
    return PostFixRecommendation(
        command=command,
        recommended=recommended,
        enum=tuple(enum),
        excluded=tuple(excluded),
        rationale=rationale,
    )


def promote_post_fix_phase_command(
    phase_commands: dict,
    *,
    category: str,
    target_name: str,
    project_path: str,
    doc_list: str,
    fix_cycle: int,
    max_cycles: int,
    scope: str,
    findings_count: int,
    parent_todo: str,
    gate_id: str,
    lifecycle_flags: str = "",
    recommended_override: "str | None" = None,
) -> None:
    """Replace ``phase_commands["post_fix"]`` with a discriminated record.

    Single source for the post-fix shape ``launch`` and ``post-review``
    write. Carries the legacy template under ``command_template`` so any
    reader that still expects a string finds the same literal (with
    ``{fix_cycle}`` / ``{user_choice}`` placeholders) — alongside
    ``command_with_recommended`` which substitutes the recommended
    choice, plus the enum / excluded / rationale fields.
    """
    from review.pipeline_phases.commands import build_phase_cmd
    from review.pipeline_phases.constants import PHASE_POST_FIX

    flags = (
        lifecycle_flags
        or (
            f" --parent-todo {parent_todo} --gate-id {gate_id}"
            if parent_todo and gate_id
            else ""
        )
    )
    legacy_template = build_phase_cmd(
        PHASE_POST_FIX,
        project_path=project_path,
        category=category,
        target_name=target_name,
        extra_args=(
            f'--doc-list "{doc_list}" --fix-cycle {{fix_cycle}} '
            f"--max-cycles {max_cycles} --user-choice {{user_choice}}"
        ),
        lifecycle_flags=flags,
    )
    rec = build_post_fix_command_with_recommended(
        category=category,
        target_name=target_name,
        project_path=project_path,
        doc_list=doc_list,
        fix_cycle=fix_cycle,
        max_cycles=max_cycles,
        scope=scope,
        findings_count=findings_count,
        parent_todo=parent_todo,
        gate_id=gate_id,
        recommended_override=recommended_override,
    )
    phase_commands["post_fix"] = {
        "command_template": legacy_template,
        "command_with_recommended": rec.command,
        "user_choice_enum": list(rec.enum),
        "user_choice_recommended": rec.recommended,
        "user_choice_excluded": list(rec.excluded),
        "rationale": rec.rationale,
    }


def build_relaunch_from_cache_command(
    session: dict,
    *,
    project_path: "str | os.PathLike[str]" = "",
    fix_cycle: "int | None" = None,
    gate_id: "str | None" = None,
) -> str:
    """Reconstruct the canonical ``--phase launch`` command from a session.

    Adapter over :func:`build_relaunch_command` for handlers that hold
    the raw session dict. Raises ``ValueError`` (caught at the call
    site → ``output.error``) when neither ``launch_flags`` nor
    ``launch_args_cache`` carry enough state to rebuild the literal.
    """
    inp = RelaunchInput.from_session(
        session, project_path=project_path,
        fix_cycle=fix_cycle, gate_id=gate_id,
    )
    return build_relaunch_command(inp)


DEFAULT_APPROVE_RESPONSE = "Approved via agent"
"""Canonical comment the agent passes to ``approval/update-status.py``
when approving with no human-authored comment. Emitted as
``approval_commands.approve_default_response`` so the agent copies a
structured field instead of re-typing the literal from prompt text."""


def placeholder_note(
    tokens: Iterable[str],
    *,
    source: str = "request.py's JSON output",
    source_fields: Iterable[str] | None = None,
) -> str:
    """Return the canonical "substitute only these tokens" sentence.

    Keeps every emitted ``placeholder_substitution_note`` consistent so
    literalism-first readers can internalise one phrasing and never
    second-guess whether a new surface means something different.
    """
    token_list = list(tokens)
    if not token_list:
        raise ValueError("placeholder_note requires at least one token")
    wrapped = [f"{{{t}}}" for t in token_list]
    if len(wrapped) == 1:
        joined = wrapped[0]
    elif len(wrapped) == 2:
        joined = f"{wrapped[0]} and {wrapped[1]}"
    else:
        joined = ", ".join(wrapped[:-1]) + f", and {wrapped[-1]}"
    clause = f"Replace {joined} with values from {source}"
    if source_fields:
        fields = ", ".join(f"data.{f}" for f in source_fields)
        clause += f" ({fields})"
    return clause + ". Do not modify any other token."


APPROVAL_PLACEHOLDER_NOTE = placeholder_note(
    ("approvalId", "approvalFilePath"),
    source="request.py's JSON output",
    source_fields=("approvalId", "approvalFilePath"),
)


def _quote(value: str) -> str:
    """Minimal shell-safe double-quoting for emitted templates."""
    return '"' + str(value).replace('"', '\\"') + '"'


def approval_commands(
    *,
    title: str,
    file_paths: Iterable[str] | str,
    category: str,
    target_name: str,
) -> dict:
    """Return a dict of fully-formed approval CLI shapes with placeholders.

    The returned dict contains the three canonical entries plus a
    substitution note. Every template uses ``{approvalId}`` and
    ``{approvalFilePath}`` consistently so downstream callers can
    substitute with literal string replacement.
    """
    if not isinstance(file_paths, str):
        file_paths_str = ",".join(str(p) for p in file_paths)
    else:
        file_paths_str = file_paths

    request = (
        f"{_SDD_SHIM_PREFIX}approval/request.py "
        f"--title {_quote(title)} "
        f"--file-paths {_quote(file_paths_str)} "
        f"--type document --category {category} "
        f"--target-name {_quote(target_name)}"
    )
    update_status = (
        f"{_SDD_SHIM_PREFIX}approval/update-status.py "
        "{approvalFilePath} {action} {response}"
    )
    update_status_approve = (
        f"{HUMAN_APPROVAL_ENV}={HUMAN_APPROVAL_VALUE} "
        f"{_SDD_SHIM_PREFIX}approval/update-status.py "
        "{approvalFilePath} approve {response}"
    )
    delete = (
        f"{_SDD_SHIM_PREFIX}approval/delete.py "
        "--approval-id {approvalId}"
    )
    return {
        "request": request,
        "update_status": update_status,
        "update_status_approve": update_status_approve,
        "delete": delete,
        "approve_default_response": DEFAULT_APPROVE_RESPONSE,
        "placeholder_substitution_note": APPROVAL_PLACEHOLDER_NOTE,
    }


def build_request_commands_suite(
    approval_id: str,
    file_path: str,
) -> dict[str, str]:
    """Return the trio of post-request action shim lines for an approval.

    Single source for the ``approve`` / ``reject`` / ``delete`` literals
    surfaced under ``commands_suite`` on ``approval/request.py``'s JSON
    output. Unlike :func:`approval_commands`, this emitter substitutes
    the concrete ``approval_id`` and ``file_path`` into each command —
    the dict's values are ready-to-run shim lines, not placeholder
    templates. The ``approve`` entry is wrapped in the H1 attestation
    env var because the actor-kind policy only accepts the human-in-the-
    loop proof on approve transitions.
    """
    if not approval_id:
        raise ValueError(
            "build_request_commands_suite requires a non-empty approval_id"
        )
    if not file_path:
        raise ValueError(
            "build_request_commands_suite requires a non-empty file_path"
        )
    update_status = (
        f"{_SDD_SHIM_PREFIX}approval/update-status.py {_quote(file_path)}"
    )
    approve = (
        f"{HUMAN_APPROVAL_ENV}={HUMAN_APPROVAL_VALUE} "
        f"{update_status} approve {_quote(DEFAULT_APPROVE_RESPONSE)}"
    )
    reject = f"{update_status} reject {_quote('')}"
    delete = (
        f"{_SDD_SHIM_PREFIX}approval/delete.py "
        f"--approval-id {_quote(approval_id)}"
    )
    return {
        "approve": approve,
        "reject": reject,
        "delete": delete,
    }


def approve_with_human_env(
    *, approval_file_path: str, response: str,
) -> str:
    """Return the human-approval retry invocation.

    The sole accepted proof today is ``SDD_HUMAN_APPROVAL=1``. The
    exported string is what ``update-status.py`` quotes into its
    ``next_action_command`` on H1 rejection and what
    ``human-approval-ceremony.md`` documents — a single source of truth
    across every surface that names the retry shape.
    """
    return (
        f"{HUMAN_APPROVAL_ENV}={HUMAN_APPROVAL_VALUE} {_SDD_SHIM_PREFIX}"
        f"approval/update-status.py {_quote(approval_file_path)} "
        f"approve {_quote(response)}"
    )


def ceremony_prompt_command(target_label: str) -> str:
    """Return the canonical ``approval-confirm-human`` shim line.

    Single source of truth for the command emitted by SKILL.md
    pointers, by ``human-approval-ceremony.md``, and by any future
    aggregator that needs to render the prompt out-of-band.
    """
    return (
        f"{_SDD_SHIM_PREFIX}util/generate-prompt.py "
        f"--type {_PROMPT_TYPE_APPROVAL_CONFIRM_HUMAN} "
        f"--params target_label={_quote(target_label)}"
    )


def template_resolve_command(
    doc_type: str,
    project_path: str = ".",
    *,
    spec_name: str = "",
    include_content: bool = True,
) -> str:
    """Single-line `util/resolve-template.py` invocation.

    Emitting this command verbatim removes the need for callers to
    reconstruct the flag set from prose. ``include_content`` is now
    the default in the underlying script — the emitter passes
    ``--metadata-only`` only when the caller explicitly asks for it,
    so the rendered literal stays one flag shorter on the canonical
    path.
    """
    parts = [
        f"{_SDD_SHIM_PREFIX}util/resolve-template.py",
        f"--type {doc_type}",
    ]
    if spec_name:
        parts.append(f"--spec-name {_quote(spec_name)}")
    if not include_content:
        parts.append("--metadata-only")
    if project_path:
        parts.append(f"--workspace {project_path}")
    return " ".join(parts)


def build_template_resolve_commands(
    doc_list: str,
    *,
    project_path: str = ".",
    spec_name: str = "",
    repo_type: str = "",
) -> dict[str, str]:
    """Return a ``{doc_filename: shim_command}`` map.

    Accepts the comma-separated ``doc_list`` form used throughout the
    pipeline and emits one line per doc using
    :func:`template_resolve_command`. Empty entries are skipped so the
    helper is safe to call with the raw ``--doc-list`` argument.

    When ``repo_type == "coordinator"`` and the doc is ``requirements.md``,
    the rendered ``--type`` swaps to ``workspace-requirements`` so the
    coordinator spec carries the cross-repo skeleton.
    """
    result: dict[str, str] = {}
    coord = (repo_type or "").strip().lower() == COORDINATOR_REPO_TYPE
    for doc in (doc_list or "").split(","):
        doc = doc.strip()
        if not doc:
            continue
        doc_type = doc[:-3] if doc.endswith(".md") else doc
        if coord and doc_type == "requirements":
            doc_type = DOC_TYPE_WORKSPACE_REQUIREMENTS
        result[doc] = template_resolve_command(
            doc_type,
            project_path=project_path or ".",
            spec_name=spec_name,
        )
    return result


def build_lint_requirements_command(
    *,
    spec_name: str,
    project_path: str = ".",
    mode: str | None = None,
) -> str:
    """Canonical ``spec/lint-requirements.py`` shim invocation.

    Single source for the retry command emitted on validation failure
    (``output.error(..., next_action_command=...)``). Keeping the CLI
    string here instead of inlining in each error path satisfies the
    "Solve, don't punt" principle — agents copy the exact command
    rather than reconstructing it from prose.
    """
    return build_shim_command(
        "spec/lint-requirements.py",
        project_path=project_path,
        target=_quote(spec_name),
        mode=mode or "",
    )


def build_lint_tasks_command(
    *,
    spec_name: str = "",
    spec_names: "Iterable[str] | None" = None,
    project_path: str = ".",
) -> str:
    """Canonical ``spec/lint-tasks.py`` shim invocation.

    Pass *spec_name* (single) for the legacy ``--target <a>`` form, or
    *spec_names* (multi) to emit ``--targets <a> <b> …``. Multi-target
    callers receive per-target sub-results under ``data.targets[]``;
    single-target callers see the legacy envelope shape.
    """
    names = list(spec_names) if spec_names else []
    if names:
        head = f"{_SDD_SHIM_PREFIX}spec/lint-tasks.py"
        parts: list[str] = [head, "--targets", *(_quote(n) for n in names)]
        if project_path and project_path != ".":
            parts.append(f"--workspace {os.fspath(project_path)}")
        return " ".join(parts)
    return build_shim_command(
        "spec/lint-tasks.py",
        project_path=project_path,
        target=_quote(spec_name),
    )


def build_check_traceability_command(
    *,
    spec_name: str = "",
    spec_names: "Iterable[str] | None" = None,
    project_path: str = ".",
) -> str:
    """Canonical ``spec/check-traceability.py`` shim invocation.

    Pass *spec_name* (single) for the legacy ``--target <a>`` form, or
    *spec_names* (multi) to emit ``--targets <a> <b> …``. The two
    forms emit byte-identical heads; only the trailing flag differs.
    """
    names = list(spec_names) if spec_names else []
    if names:
        head = f"{_SDD_SHIM_PREFIX}spec/check-traceability.py"
        parts: list[str] = [head, "--targets", *(_quote(n) for n in names)]
        if project_path and project_path != ".":
            parts.append(f"--workspace {os.fspath(project_path)}")
        return " ".join(parts)
    return build_shim_command(
        "spec/check-traceability.py",
        project_path=project_path,
        target=_quote(spec_name),
    )


def build_render_task_prompts_command(*, spec_name: str) -> str:
    """Canonical ``util/render-task-prompts.py`` shim invocation.

    The script registers ``--target`` (family=spec) as the canonical
    selector; ``spec_name`` is mapped onto it.
    """
    return build_shim_command(
        "util/render-task-prompts.py",
        target=_quote(spec_name),
    )


def build_detect_doc_state_command(
    *,
    category: str,
    target_name: str,
    project_path: str = ".",
    gate_id: str = "",
) -> str:
    """Canonical ``util/detect-doc-state.py`` shim invocation."""
    return build_shim_command(
        "util/detect-doc-state.py",
        category=category,
        target_name=_quote(target_name),
        project_path=project_path,
        gate_id=gate_id,
    )


def build_check_re_review_command(
    *,
    doc: str,
    spec_name: str,
    category: str,
    project_path: str = ".",
) -> str:
    """Canonical ``review/check-re-review.py`` shim invocation."""
    return build_shim_command(
        "review/check-re-review.py",
        doc=_quote(doc),
        spec_name=_quote(spec_name),
        category=category,
        project_path=project_path,
    )


def build_generate_prompt_list_command(*, project_path: str = ".") -> str:
    """Canonical ``util/generate-prompt.py --list`` shim invocation.

    Emitted as the recovery command for unknown prompt types so the
    shim shape stays owned by ``command_templates`` even when the
    invocation is effectively constant — a future rename lands in one
    file.
    """
    project = "" if project_path == "." else project_path
    return build_shim_command(
        "util/generate-prompt.py",
        project_path=project,
        list=True,
    )


def build_pre_launch_check_command(
    *,
    doc: str,
    category: str,
    target_name: str,
    project_path: str = ".",
) -> str:
    """Canonical ``pipeline-tick --phase pre-launch-check`` invocation.

    Emitted as the retry command when the pre-launch-check phase hits
    a system error (no results persisted) so the agent can re-run the
    identical shape rather than rebuilding flags from memory. The
    agent-facing verb is always ``pipeline-tick`` — ``--phase`` is
    the dispatcher's internal override.
    """
    positional = (f"--doc {doc}",) if doc else ()
    return build_shim_command(
        "review/pipeline-tick.py",
        project_path=project_path,
        category=category,
        target_name=_quote(target_name),
        phase="pre-launch-check",
        positional=positional,
    )


def build_compound_discovery_command(
    probes: Iterable[str], *, mask_exit: bool = True,
) -> str:
    """Compose a ``;``-chained discovery probe with optional exit masking.

    Discovery probes whose value is the *output* (not the exit status)
    must mask their compound exit code so a single sub-command miss
    does not cancel siblings in a parallel batch (see Rule 5 in
    ``parallel-batch-hygiene.md``). Single source of truth for the
    masking suffix — every emitter that surfaces compound probes
    composes through this helper.
    """
    parts = [str(p).strip() for p in probes if str(p).strip()]
    if not parts:
        return ""
    body = "; ".join(parts)
    if not mask_exit:
        return body
    return "{ " + body + "; } || true"


def build_migrate_legacy_snapshot_command(
    *,
    spec: str,
    doc: str,
    workspace_path: str = ".",
) -> str:
    """Canonical shim line for ``util/migrate-legacy-snapshot.py``.

    Replaces the prose "re-approve to restore snapshot" guidance with a
    single literal command the agent can copy. The script itself is
    landed by a downstream change; this emitter owns the rendered
    invocation so every surface that surfaces the migration step shares
    one byte-equal shape.
    """
    if not spec:
        raise ValueError(
            "build_migrate_legacy_snapshot_command requires a non-empty spec"
        )
    if not doc:
        raise ValueError(
            "build_migrate_legacy_snapshot_command requires a non-empty doc"
        )
    parts = [
        f"{_SDD_SHIM_PREFIX}util/migrate-legacy-snapshot.py",
        f"--spec {_quote(spec)}",
        f"--doc {_quote(doc)}",
    ]
    if workspace_path and workspace_path != ".":
        parts.append(f"--workspace {workspace_path}")
    return " ".join(parts)


def build_migrate_review_quality_command(
    *,
    spec: str = "",
    workspace_path: str = ".",
) -> str:
    """Canonical shim line for ``util/migrate-review-quality.py``.

    Renders a literal command that folds legacy
    ``review-quality-{phase}.json`` siblings into the canonical
    ``review-quality.json`` artifact. Pass an explicit ``spec`` to scope
    the migration; omit it to fold every spec under the workspace via
    ``--all``. Surfaced by the ``orphan_review_quality_siblings``
    advisory so the operator gets a single literal next-action.
    """
    parts = [f"{_SDD_SHIM_PREFIX}util/migrate-review-quality.py"]
    if spec:
        parts.append(f"--spec {_quote(spec)}")
    else:
        parts.append("--all")
    if workspace_path and workspace_path != ".":
        parts.append(f"--workspace {workspace_path}")
    return " ".join(parts)


def did_you_mean(
    typed: str,
    available: Iterable[str],
    k: int = 3,
    *,
    cutoff: float = 0.55,
) -> list[str]:
    """Return up to ``k`` closest matches for ``typed``.

    Matches are case-insensitive. Designed for the ``_bootstrap`` missing-
    script envelope so the agent receives literal follow-up candidates
    without having to enumerate the inventory itself.
    """
    if not typed:
        return []
    available_list = [a for a in available if a]
    if not available_list:
        return []

    seen: list[str] = []
    norm_typed = typed.lower()

    # Exact basename match beats fuzzy matching (keeps "resolve" out of
    # the way when the user typed the full "util/resolve-template.py").
    for candidate in available_list:
        if candidate.lower() == norm_typed:
            seen.append(candidate)

    # Fuzzy — whole-path then basename pass.
    lowered = [a.lower() for a in available_list]
    lower_to_original = dict(zip(lowered, available_list))
    matches = difflib.get_close_matches(norm_typed, lowered, n=max(k, 5), cutoff=cutoff)
    for lo in matches:
        original = lower_to_original[lo]
        if original not in seen:
            seen.append(original)

    typed_base = os.path.basename(typed).lower()
    if typed_base and typed_base != norm_typed:
        base_matches = difflib.get_close_matches(
            typed_base,
            [os.path.basename(a).lower() for a in available_list],
            n=max(k, 5),
            cutoff=cutoff,
        )
        for bm in base_matches:
            for cand in available_list:
                if os.path.basename(cand).lower() == bm and cand not in seen:
                    seen.append(cand)

    return seen[:k]


def available_scripts(scripts_root: str) -> list[str]:
    """Enumerate ``group/name.py`` entries under the scripts directory."""
    if not scripts_root or not os.path.isdir(scripts_root):
        return []
    found: list[str] = []
    for group in sorted(os.listdir(scripts_root)):
        group_dir = os.path.join(scripts_root, group)
        if not os.path.isdir(group_dir) or group.startswith("_"):
            continue
        for name in sorted(os.listdir(group_dir)):
            if not name.endswith(".py") or name.startswith("_"):
                continue
            found.append(f"{group}/{name}")
    return found
