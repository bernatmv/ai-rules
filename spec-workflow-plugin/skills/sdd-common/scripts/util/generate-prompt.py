#!/usr/bin/env python3
"""Generate structured prompts from the prompt registry.

Usage:
  .spec-workflow/sdd util/generate-prompt.py --type {prompt-type} [--params key=value ...] [--format harness|json|markdown]
  .spec-workflow/sdd util/generate-prompt.py {prompt-type} [--params key=value ...]
  .spec-workflow/sdd util/generate-prompt.py --list
  .spec-workflow/sdd util/generate-prompt.py --validate-registry

Examples:
  # Adapter-rendered payload for the active harness (default)
  .spec-workflow/sdd util/generate-prompt.py --type approval-formal --params doc=product.md

  # Cursor-shaped JSON (explicit override)
  .spec-workflow/sdd util/generate-prompt.py --type approval-formal --params doc=product.md --format json

  # Markdown prompt
  .spec-workflow/sdd util/generate-prompt.py --type approval-formal --params doc=product.md --format markdown

  # Dynamic options
  .spec-workflow/sdd util/generate-prompt.py --type approval-formal --params doc=product.md \\
    --options id=approve,label="Approve" --options id=reject,label="Reject"

  # Registry schema check (CI)
  .spec-workflow/sdd util/generate-prompt.py --validate-registry

  # List all prompt types
  .spec-workflow/sdd util/generate-prompt.py --list
"""

import _bootstrap  # noqa: F401

import argparse
import json
import os
import re
import sys
from typing import Callable

from sdd_core.prompts import (
    PromptParamError, list_prompts, load_registry,
    prompt_type_redirect,
    render_prompt, render_prompt_for_harness,
)
from sdd_core import command_templates
from sdd_core.command_templates import (
    build_generate_prompt_list_command,
    did_you_mean,
)
from sdd_core.matchers import WordMatcher
from sdd_core import output, cli


# Display-label derivation: ``doc`` is the source of truth (a doc-name
# like ``requirements`` / ``design`` / ``tasks``); ``scope`` is the
# Title-Case label rendered in the prompt body. Maintaining a tiny
# table here lets the registry drop ``scope`` from required params —
# every workflow that already passes ``doc`` gets the label for free.
_DOC_TO_SCOPE_LABEL: dict[str, str] = {
    "requirements": "Requirements",
    "design": "Designs",
    "tasks": "Tasks",
}


def _doc_to_scope_label(doc: str) -> str:
    """Title-Case label for *doc*, falling back to capitalisation."""
    return _DOC_TO_SCOPE_LABEL.get(doc, doc.capitalize() if doc else doc)


def _approve_with_human_env_shim(_params: dict) -> str:
    from sdd_core.command_templates import approve_with_human_env
    return approve_with_human_env(
        approval_file_path="{approvalFilePath}",
        response="{response}",
    )


def _workspace_phase_approve_shim(_params: dict) -> str:
    from sdd_core.command_templates import (
        build_workspace_phase_approve_command,
    )
    return build_workspace_phase_approve_command(
        feature="{feature}",
        doc="{doc}",
        human_env=True,
    )


# Single dispatch table — adding a fourth retry-aware prompt is one
# row, not a fresh ``if`` branch (Open-Closed via registry).
_RETRY_SHIM_INJECTORS: dict[str, Callable[[dict], str]] = {
    "approval-formal": _approve_with_human_env_shim,
    "approval-formal-required": _approve_with_human_env_shim,
    "workspace-batch-approve-phase": _workspace_phase_approve_shim,
}


def _maybe_inject_retry_shim(prompt_type: str, params: dict) -> None:
    """Auto-populate ``params['retry_shim']`` for retry-aware prompts.

    The registry leaves ``optional_params.retry_shim`` empty so the
    canonical literal flows from one helper instead of being hand-pasted
    into every prompt body. Caller-provided values win.
    """
    if "retry_shim" in params:
        return
    injector = _RETRY_SHIM_INJECTORS.get(prompt_type)
    if injector is not None:
        params["retry_shim"] = injector(params)


# Prompt types whose registry body renders ``{scope}`` derived from
# ``{doc}``. Centralised so adding a new phase prompt that participates
# in the auto-derivation is one row, not a code edit.
_SCOPE_DERIVED_PROMPTS: frozenset[str] = frozenset({
    "workspace-batch-approve-phase",
    "workspace-batch-review-phase",
})


def _maybe_inject_scope_label(prompt_type: str, params: dict) -> None:
    """Derive ``params['scope']`` from ``params['doc']`` for phase prompts.

    The workspace phase prompts render ``{scope}`` in their bodies; the
    label is pure display sugar over the canonical ``doc`` value, so
    requiring callers to pass both is redundant. Caller-provided
    ``scope`` wins.
    """
    if "scope" in params:
        return
    if prompt_type not in _SCOPE_DERIVED_PROMPTS:
        return
    doc = params.get("doc")
    if doc:
        params["scope"] = _doc_to_scope_label(doc)


_HARDCODED_DENOMINATORS = WordMatcher(("5", "6", "15", "16"))
# Only the truthiness of ``.search(...)`` is consumed downstream, so the
# capturing group that the original regex used (group 1 = denominator)
# is intentionally absorbed into the non-capturing fragment.
_HARDCODED_DENOMINATOR_RE = _HARDCODED_DENOMINATORS.compose(
    prefix=r"\b/",
    suffix=r"(?:\.0)?\b",
)


# ``script-index.py`` prefers this manifest over AST reflection when
# present. Declaring it here lets an agent ask the registry
# "which script renders prompts?" and get the exact verbs plus the
# ``--prompt-id`` alias back without ``--help`` spelunking.
__sdd_manifest__ = {
    "summary": "Render structured prompts from the prompt registry",
    "verbs": [
        "--list",
        "--validate-registry",
        "--type <prompt-id> [--params key=value ...] [--format harness|json|markdown]",
        "<prompt-id> [--params key=value ...]",
    ],
    "aliases": {"--prompt-id": "--type"},
    "flags": [
        "--type", "--prompt-id", "--params", "--options",
        "--format", "--exclude-options", "--no-skip", "--list",
        "--validate-registry", "--harness",
    ],
    "produces_key_value_flags": ["--params", "--options"],
}


def _parse_key_value(items, required_keys=None):
    """Parse key=value strings into a dict, optionally validating required keys."""
    result = {}
    for pair in items:
        if "=" not in pair:
            output.error(f"Invalid format: '{pair}'. Expected key=value.")
        key, _, value = pair.partition("=")
        result[key.strip()] = value.strip()
    if required_keys:
        missing = [k for k in required_keys if k not in result]
        if missing:
            output.error(f"Missing required key(s): {', '.join(missing)}. Got: {result}")
    return result


def _parse_params(raw):
    """Normalize --params into a dict.

    ``--params`` is registered with :class:`cli.KeyValueAppend`, so
    argparse hands back a ready-made dict that accumulates across every
    ``--params`` occurrence (merge semantics instead of argparse's
    default "last flag replaces the list" footgun).
    """
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise TypeError(
            f"--params must be a dict (got {type(raw).__name__}); "
            "pass key=value via argparse KeyValueAppend"
        )
    return raw


def _parse_options(raw):
    """Parse dynamic options from --options arguments.

    ``--options`` entries are each a single comma-joined group of
    ``key=value`` pairs (e.g. ``id=a,label=A``). Repeated flags are
    appended into a list by argparse's ``append`` action so every
    occurrence survives.
    """
    if not raw:
        return None
    options = []
    for item in raw:
        parts = _parse_key_value(item.split(","), required_keys=["id", "label"])
        options.append(parts)
    return options


def _suggest_prompt_types_by_param_overlap(
    supplied_params: "dict | list", registry: dict, *, k: int = 3,
) -> list[dict]:
    """Rank registered prompt types by overlap with *supplied_params*.

    Used to power the ``did_you_mean`` envelope when a caller passes
    params that don't satisfy the chosen prompt type's
    ``required_params``. Returns up to *k* entries each carrying the
    prompt id, its required params, and the overlap count — enough for
    the agent to pick the right ``--type`` without re-listing the
    registry.
    """
    if isinstance(supplied_params, dict):
        supplied = set(supplied_params.keys())
    else:
        supplied = set(supplied_params or [])
    prompts = (registry or {}).get("prompts", {}) or {}
    scored: list[tuple[int, int, str, list[str]]] = []
    for name in sorted(prompts.keys()):
        entry = prompts[name]
        required = list(entry.get("params", []))
        if not required:
            continue
        overlap = len(supplied & set(required))
        # Penalise required params the caller didn't supply so a
        # single-param hit doesn't outrank a near-perfect match.
        deficit = len([p for p in required if p not in supplied])
        if overlap == 0:
            continue
        scored.append((overlap, -deficit, name, required))
    scored.sort(reverse=True)
    return [
        {"prompt_type": name, "required_params": required, "overlap": overlap}
        for overlap, _deficit_neg, name, required in scored[:k]
    ]


def _emit_param_mismatch_envelope(
    prompt_type: str,
    err: "PromptParamError",
    supplied_params: dict,
    registry: dict,
) -> None:
    """Emit a structured ``did_you_mean`` envelope on registry-param mismatch.

    Today's flat ``output.error`` is operator-friendly but agent-hostile:
    the recovery path requires re-typing the right prompt id from
    nothing. This envelope ships ``suggestions[]`` ranked by param
    overlap so the agent's next call can land on the right ``--type``,
    plus the original missing/unexpected/required arrays for direct
    inspection.
    """
    suggestions = _suggest_prompt_types_by_param_overlap(
        supplied_params, registry,
    )
    example = " ".join(f"{k}=..." for k in err.required) if err.required else ""
    payload = {
        "ok": False,
        "kind": "prompt_param_mismatch",
        "prompt_type": prompt_type,
        "missing": list(err.missing),
        "unexpected": list(err.unexpected),
        "required": list(err.required),
        "supplied": list(supplied_params.keys()) if isinstance(supplied_params, dict) else list(supplied_params or []),
        "suggestions": suggestions,
        "did_you_mean": [s["prompt_type"] for s in suggestions],
        "error": str(err),
    }
    if example:
        payload["hint"] = f"Example: --params {example}"
    output.result(payload, message=str(err), exit_code=1)


def _emit_unknown_prompt_type_warn(prompt_type, registry, message):
    """Emit a warn-severity ``status=result`` envelope for unknown prompt types.

    Pairs with :func:`sdd_core.prompts.prompt_type_redirect` so well-known
    misses (``task-prompt-*``) carry the exact follow-up command the agent
    should run next. Exit code stays 1 — argparse-equivalent semantics —
    but tone is warn so callers treat it as a recoverable typo.
    """
    available = sorted((registry or {}).get("prompts", {}).keys())
    redirect = prompt_type_redirect(prompt_type)
    suggestions = did_you_mean(prompt_type, available)
    next_action = (
        redirect.get("command") if redirect
        else build_generate_prompt_list_command()
    )
    payload = {
        "severity": "warn",
        "kind": "unknown_prompt_type",
        "typed": prompt_type,
        "did_you_mean": suggestions,
        "available_types": available,
        "next_action_command": next_action,
    }
    if redirect:
        payload["redirect"] = redirect
    output.result(payload, message=message, exit_code=1)


def _build_epilog():
    """Auto-generate help epilog from the prompt registry (DRY)."""
    try:
        registry = load_registry()
    except FileNotFoundError:
        return ""
    lines = ["Prompt types and required params (pass as key=value):"]
    for name, entry in sorted(registry.get("prompts", {}).items()):
        params = entry.get("params", [])
        if params:
            kv = ", ".join(f"{k}=<value>" for k in params)
            param_str = f"--params {kv}"
        else:
            param_str = "(no params)"
        lines.append(f"  {name}: {param_str}")
    return "\n".join(lines)


def _validate_registry_cli():
    """Render every registry entry through every adapter; report drift.

    Exit 0 with a structured summary on success; exit 1 with an error
    envelope naming the first failing ``(entry, adapter)`` pair. Used
    by CI to catch prompt entries that skip an adapter's required
    keys before they hit an agent.
    """
    from sdd_core.harness import ADAPTERS
    registry = load_registry()
    prompts = registry.get("prompts", {})
    errors: list[str] = []
    for name in sorted(prompts.keys()):
        # Fill required template params with a stable placeholder so
        # the renderer doesn't reject the entry for missing substitutions.
        entry = prompts[name]
        # Scenario-style entries (``pipeline-instruction-*``) are
        # dispatched via :func:`render_pipeline_instruction` and don't
        # carry an adapter-shaped ``questions`` array, so they're
        # exercised separately below.
        if "scenarios" in entry and not entry.get("questions"):
            continue
        required = list(entry.get("params", []))
        params = {k: "<validate>" for k in required}
        for adapter_name in sorted(ADAPTERS.keys()):
            try:
                payload = render_prompt_for_harness(
                    name,
                    params=params,
                    harness_name=adapter_name,
                    registry=registry,
                )
            except Exception as exc:
                errors.append(f"{name} / {adapter_name}: {exc}")
                continue
            if not isinstance(payload, dict) or "questions" not in payload:
                errors.append(
                    f"{name} / {adapter_name}: adapter returned "
                    f"unexpected shape {type(payload).__name__}"
                )
    if errors:
        output.error(
            f"{len(errors)} registry entry/adapter combination(s) failed",
            context="\n".join(errors),
        )

    # Hardcoded-denominator lint: any rendered prompt body carrying a
    # literal ``/5``, ``/6``, ``/15``, or ``/16`` fragment is a score
    # contract drift — the narrative denominator must flow through
    # ``ScoringContract.narrative_instruction()``.
    for name in sorted(prompts.keys()):
        entry = prompts[name]
        if "scenarios" in entry and not entry.get("questions"):
            continue
        required = list(entry.get("params", []))
        params = {k: "<validate>" for k in required}
        try:
            rendered = render_prompt(
                name, params=params, fmt="json", registry=registry,
            )
        except Exception:
            continue
        if _HARDCODED_DENOMINATOR_RE.search(rendered):
            output.error(
                "registry_validation_failed",
                hint=(
                    f"Prompt {name!r} contains hardcoded denominator. "
                    "Use ScoringContract.narrative_instruction() instead."
                ),
                next_action_command=command_templates.build_shim_command(
                    "util/generate-prompt.py", print=name,
                ),
            )

    output.success(
        {
            "entries": len(prompts),
            "adapters": sorted(ADAPTERS.keys()),
        },
        "Registry validates against all adapters",
    )


def main(argv=None):
    parser = cli.strict_parser(__doc__, epilog=_build_epilog())
    parser.add_argument("prompt_type_pos", nargs="?", default=None, metavar="PROMPT_TYPE",
                        help="Prompt type (positional form of --type)")
    parser.add_argument(
        "--type", "--prompt-id",
        dest="prompt_type_flag", default=None,
        help="Prompt type ID from the registry (alias: --prompt-id)",
    )
    parser.add_argument(
        "--params", action=cli.KeyValueAppend, nargs="*", default={},
        metavar="key=value",
        help=(
            "Parameter substitutions (e.g., doc=product.md). Repeatable — "
            "each occurrence merges into the accumulated param dict."
        ),
    )
    parser.add_argument(
        "--format", dest="fmt", default=None,
        choices=["harness", "json", "markdown"],
        help=(
            "Output format. Defaults to the active harness adapter's "
            "``prompt_default_format`` — ``harness`` on Cursor, "
            "``markdown`` on Claude Code. ``json`` forces the "
            "Cursor-flavoured registry JSON regardless of adapter."
        ),
    )
    parser.add_argument(
        "--harness", dest="harness_name", default=None,
        help=(
            "Override the detected harness adapter (cursor / "
            "claude-code-standard / claude-code-task-variant). Only "
            "meaningful with --format=harness; falls back to the "
            "loader default otherwise."
        ),
    )
    parser.add_argument(
        "--options", action=cli.ListExtend, nargs="*", default=[],
        metavar="id=x,label=y",
        help=(
            "Dynamic options (id=…,label=…). Accepts multiple groups per "
            "flag; repeatable — each occurrence extends the option list."
        ),
    )
    parser.add_argument(
        "--exclude-options", default="",
        help="Comma-separated option IDs to exclude (e.g., accept)",
    )
    parser.add_argument(
        "--no-skip", action="store_true",
        help=(
            "For the approval-formal prompt, auto-dispatch to the "
            "approval-formal-required variant (drops the skip option). "
            "Applies only when --type is approval-formal."
        ),
    )
    parser.add_argument("--list", action="store_true", help="List all available prompt types")
    parser.add_argument(
        "--validate-registry", action="store_true",
        help=(
            "Walk every registry entry through each adapter and exit "
            "non-zero on the first schema drift. Used by CI."
        ),
    )
    args = parser.parse_args(argv)

    if args.validate_registry:
        _validate_registry_cli()

    if args.list:
        registry = load_registry()
        entries = list_prompts(registry)
        output.success(
            {"prompts": entries},
            f"{len(entries)} prompt type(s) available",
        )

    prompt_type = args.prompt_type_flag or args.prompt_type_pos
    if not prompt_type:
        output.error(
            "--type is required (or pass as positional argument)",
            hint="Usage: generate-prompt.py --type <type> --params ...\n"
                 "   or: generate-prompt.py <type> --params ...\n"
                 "Use --list to see available types.",
        )

    # --no-skip is a thin sugar that flips approval-formal into its
    # -required sibling (drops the skip option). Keeps the single-
    # document terminal contract enforced at the registry level rather
    # than via prose-only rules.
    if args.no_skip and prompt_type == "approval-formal":
        prompt_type = "approval-formal-required"

    params = _parse_params(args.params)
    _maybe_inject_retry_shim(prompt_type, params)
    _maybe_inject_scope_label(prompt_type, params)
    options = _parse_options(args.options)
    exclude = [x.strip() for x in args.exclude_options.split(",") if x.strip()]

    # ``load_adapter`` is the single authority for harness resolution;
    # the adapter picks the default when ``--format`` is omitted.
    fmt = args.fmt
    if fmt is None:
        from sdd_core.harness import load_adapter
        fmt = load_adapter().prompt_default_format()

    try:
        registry = load_registry()
        if fmt == "harness":
            payload = render_prompt_for_harness(
                prompt_type,
                params=params,
                harness_name=args.harness_name,
                options=options,
                registry=registry,
                exclude_options=exclude or None,
            )
            print(json.dumps(payload, indent=2))
        else:
            result = render_prompt(
                prompt_type,
                params=params,
                fmt=fmt,
                options=options,
                registry=registry,
                exclude_options=exclude or None,
            )
            print(result)
    except KeyError as e:
        _emit_unknown_prompt_type_warn(prompt_type, registry, str(e))
    except PromptParamError as e:
        _emit_param_mismatch_envelope(prompt_type, e, params, registry)
    except ValueError as e:
        output.error(str(e))


if __name__ == "__main__":
    cli.run_main(main)
