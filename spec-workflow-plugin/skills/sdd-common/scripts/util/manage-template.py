#!/usr/bin/env python3
"""Template lifecycle management CLI.

Usage:
    manage-template.py [--workspace PATH] list
    manage-template.py [--workspace PATH] show {type} [--resolve]
    manage-template.py [--workspace PATH] customize {type}
    manage-template.py [--workspace PATH] validate {type}
    manage-template.py [--workspace PATH] validate --all
    manage-template.py [--workspace PATH] reset {type} [--force]
    manage-template.py [--workspace PATH] diff {type}
    manage-template.py [--workspace PATH] sync [--dry-run]
    manage-template.py [--workspace PATH] health [--auto-fix]
    manage-template.py [--workspace PATH] plan {type} [--action ACTION]
    manage-template.py [--workspace PATH] validate-plan <plan.json>
    manage-template.py [--workspace PATH] apply-plan <plan.json>

Dispatch is registry-driven (see ``COMMANDS`` below). New subcommands
self-register via the ``@command(name, ...)`` decorator; ``main`` never
needs to change.

Exit code: 0 = success, 1 = user error, 2 = system error
"""
from __future__ import annotations
import _bootstrap  # noqa: F401

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from sdd_core import cli, output, paths
from sdd_core import workspace_health_checks
from sdd_core.paths import WORKFLOW_DIR, require_workflow_root, templates_dir
from sdd_core.templates import (
    ALL_TEMPLATE_TYPES,
    resolve_template,
    validate_template,
    substitute_variables,
    get_default_variables,
    list_templates,
    sync_defaults_to_workspace,
    diff_template,
)
from sdd_core.template_plans import (
    PLAN_SCHEMA_VERSION,
    TEMPLATE_PLAN_ACTIONS,
    build_plan,
    load_plan,
    save_plan,
    validate_plan,
    apply_plan,
)


# ---------------------------------------------------------------------------
# Command registry (Open/Closed: handlers self-register via @command).
# ---------------------------------------------------------------------------


@dataclass
class Command:
    name: str
    help: str
    handler: Callable[[argparse.Namespace, Path], None]
    configure: Callable[[argparse.ArgumentParser], None] = field(
        default=lambda p: None
    )
    # "workflow" (default) requires a workspace; "raw" resolves project_path
    # without requiring ``.spec-workflow/``.
    root_mode: str = "workflow"


COMMANDS: dict[str, Command] = {}


def command(
    name: str,
    *,
    help: str,
    configure: Callable[[argparse.ArgumentParser], None] = lambda p: None,
    root_mode: str = "workflow",
) -> Callable:
    """Register a subcommand handler alongside its subparser configuration."""

    def decorator(fn: Callable[[argparse.Namespace, Path], None]):
        COMMANDS[name] = Command(
            name=name,
            help=help,
            handler=fn,
            configure=configure,
            root_mode=root_mode,
        )
        return fn

    return decorator


def _validate_type(template_type: str) -> None:
    if template_type not in ALL_TEMPLATE_TYPES:
        output.error(
            f"Unknown template type: {template_type}",
            hint=f"Valid types: {', '.join(ALL_TEMPLATE_TYPES)}",
        )


@command("list", help="List all templates with status")
def cmd_list(args: argparse.Namespace, root: Path) -> None:
    templates = list_templates(root)
    items = []
    for t in templates:
        items.append({
            "type": t.doc_type,
            "default": t.has_default,
            "custom": t.has_custom,
            "resolved": str(t.resolved_path.relative_to(root / ".spec-workflow"))
            if t.resolved_path else None,
        })

    standard = sum(1 for t in templates if not t.doc_type.startswith("bug-fix"))
    bugfix = sum(1 for t in templates if t.doc_type.startswith("bug-fix"))

    output.success(
        {"templates": items},
        f"{standard} standard + {bugfix} bug-fix templates found",
    )


def _configure_show(p: argparse.ArgumentParser) -> None:
    p.add_argument("type", help="Template type")
    p.add_argument("--resolve", action="store_true", help="Expand variables with placeholders")


@command("show", help="Display resolved template", configure=_configure_show)
def cmd_show(args: argparse.Namespace, root: Path) -> None:
    template_type = args.type
    _validate_type(template_type)
    resolved = resolve_template(template_type, root)
    if resolved is None:
        output.error(
            f"No template found for type: {template_type}",
            hint="Run init-workspace.py or sync to create default templates",
        )

    content = resolved.path.read_text(encoding="utf-8")
    if args.resolve:
        variables = get_default_variables(spec_name="example-spec", project_path=root)
        content = substitute_variables(content, variables)

    output.success(
        {
            "type": template_type,
            "source": resolved.source,
            "path": str(resolved.path),
            "content": content,
        },
        f"Template: {template_type} (source: {resolved.source})",
    )


def _configure_customize(p: argparse.ArgumentParser) -> None:
    p.add_argument("type", help="Template type")


@command("customize", help="Copy default to user-templates for editing", configure=_configure_customize)
def cmd_customize(args: argparse.Namespace, root: Path) -> None:
    """Build a ``customize`` plan → validate → apply.

    Delegating to the plan pipeline keeps this command and the
    ``plan``/``apply-plan`` subcommands sharing one validation surface.
    """
    template_type = args.type
    _validate_type(template_type)

    plan = build_plan(template_type=template_type, action="customize", root=root)
    errors = validate_plan(plan, root)
    if errors:
        hint = "; ".join(errors)
        output.error(
            f"Cannot customize {template_type}",
            hint=(
                f"{hint}. Edit the existing user template directly or run: "
                f"manage-template.py reset {template_type}"
            ),
        )

    result = apply_plan(plan, root)
    filename = f"{template_type}-template.md"
    output.success(
        {"type": template_type, **result},
        (
            f"Copied {filename} to user-templates/. Edit it, then run: "
            f"manage-template.py validate {template_type}"
        ),
    )


def _configure_validate(p: argparse.ArgumentParser) -> None:
    p.add_argument("type", nargs="?", help="Template type (omit with --all)")
    p.add_argument("--all", action="store_true", help="Validate all user templates")


@command("validate", help="Validate user template(s)", configure=_configure_validate)
def cmd_validate(args: argparse.Namespace, root: Path) -> None:
    if not args.all and not args.type:
        output.error(
            "validate requires a template type or --all",
            hint="Usage: manage-template.py validate <type> | --all",
        )

    types_to_check = ALL_TEMPLATE_TYPES if args.all else [args.type]
    if not args.all:
        _validate_type(args.type)

    results = []
    for ttype in types_to_check:
        filename = f"{ttype}-template.md"
        user_path = templates_dir(root, user=True) / filename
        if not user_path.is_file():
            if not args.all:
                output.error(
                    f"No user template found for type: {ttype}",
                    hint=f"Run: manage-template.py customize {ttype}",
                )
            continue

        result = validate_template(user_path, ttype)
        results.append({
            "type": ttype,
            "valid": result.valid,
            "errors": result.errors,
            "warnings": result.warnings,
            "sections_found": result.sections_found,
            "sections_missing": result.sections_missing,
            "unknown_variables": result.unknown_variables,
        })

    if not results and args.all:
        output.success(
            {"results": []},
            "No user templates found to validate",
        )

    all_valid = all(r["valid"] for r in results)
    msg = "All templates valid" if all_valid else "Validation issues found"
    output.success({"results": results}, msg)


def _configure_reset(p: argparse.ArgumentParser) -> None:
    p.add_argument("type", help="Template type")
    p.add_argument("--force", action="store_true", help="Skip confirmation")


@command("reset", help="Remove user template override", configure=_configure_reset)
def cmd_reset(args: argparse.Namespace, root: Path) -> None:
    template_type = args.type
    _validate_type(template_type)
    filename = f"{template_type}-template.md"
    user_path = templates_dir(root, user=True) / filename

    if not user_path.is_file():
        output.error(
            f"No user template to reset for type: {template_type}",
            hint="No custom template exists — the default is already in use",
        )

    if not args.force:
        output.error(
            f"Reset requires --force to confirm deletion of {filename}",
            hint=f"Run: manage-template.py reset {template_type} --force",
        )

    user_path.unlink()
    output.success(
        {"type": template_type, "deleted": str(user_path)},
        f"Removed user template: {filename}. Default template will now be used.",
    )


def _configure_diff(p: argparse.ArgumentParser) -> None:
    p.add_argument("type", help="Template type")


@command("diff", help="Diff user vs default template", configure=_configure_diff)
def cmd_diff(args: argparse.Namespace, root: Path) -> None:
    template_type = args.type
    _validate_type(template_type)
    result = diff_template(template_type, root)
    if result is None:
        output.error(
            f"No user template found for type: {template_type}",
            hint=f"Run: manage-template.py customize {template_type}",
        )

    if not result:
        output.success(
            {"type": template_type, "diff": "", "identical": True},
            f"User template is identical to default for: {template_type}",
        )
    else:
        output.success(
            {"type": template_type, "diff": result, "identical": False},
            f"Differences found for: {template_type}",
        )


def _configure_health(p: argparse.ArgumentParser) -> None:
    p.add_argument("--auto-fix", action="store_true", help="Attempt to repair issues")


@command(
    "health",
    help="Run workspace health check",
    configure=_configure_health,
    root_mode="raw",
)
def cmd_health(args: argparse.Namespace, root: Path) -> None:
    """Run workspace health checks in-process.

    Calls :mod:`sdd_core.workspace_health_checks` directly instead of
    shelling out to ``workspace/check-health.py`` — avoids spawning a
    second interpreter and depends on a library API rather than CLI
    process output.
    """
    workflow = root / WORKFLOW_DIR
    if not workflow.is_dir():
        output.error(
            f"No {WORKFLOW_DIR}/ directory found at {root}",
            hint="Run workspace/init.py first, or use workspace/ensure-healthy.py",
        )

    result = workspace_health_checks.run_all_checks(root, auto_fix=args.auto_fix)
    if args.auto_fix and not result["healthy"]:
        result = workspace_health_checks.run_autofix_and_reverify(root, result)

    if result["healthy"]:
        output.success(result, "Workspace is healthy")
    else:
        failing = [c["name"] for c in result["checks"] if c["status"] == "fail"]
        output.result(
            result,
            f"Workspace has issues: {', '.join(failing)}",
            exit_code=1,
        )


def _configure_sync(p: argparse.ArgumentParser) -> None:
    p.add_argument("--dry-run", action="store_true", help="Show what would be copied")


@command("sync", help="Re-copy reference templates to workspace", configure=_configure_sync)
def cmd_sync(args: argparse.Namespace, root: Path) -> None:
    if args.dry_run:
        from sdd_core.templates import get_reference_dir
        ref_dir = get_reference_dir()
        if not ref_dir.is_dir():
            output.error(
                f"Reference directory not found: {ref_dir}",
                hint="Skills installation may be incomplete",
                exit_code=2,
            )
        files = sorted(p.name for p in ref_dir.glob("*-template.md"))
        output.success(
            {"would_copy": files, "target": str(templates_dir(root, user=False))},
            f"Dry run: would copy {len(files)} templates",
        )

    result = sync_defaults_to_workspace(root)
    for warning in result.warnings:
        output.warn(warning)

    if result.failed:
        output.error(
            f"Failed to sync {len(result.failed)} templates",
            hint="; ".join(result.failed),
            exit_code=2,
        )

    output.success(
        {"copied": result.copied, "warnings": result.warnings},
        f"Synced {len(result.copied)} templates to .spec-workflow/templates/",
    )


# Plan/validate/apply subcommands — structured pre-commit workflow for
# ``customize`` that surfaces errors before touching the filesystem.


def _configure_plan(p: argparse.ArgumentParser) -> None:
    p.add_argument("type", help="Template type")
    p.add_argument(
        "--action",
        choices=sorted(TEMPLATE_PLAN_ACTIONS),
        default="customize",
        help="Planned action (default: customize)",
    )
    p.add_argument("--out", help="Write plan JSON to this file (otherwise stdout payload)")


@command(
    "plan",
    help="Emit a template-plan.json describing an intended customize/reset/sync",
    configure=_configure_plan,
)
def cmd_plan(args: argparse.Namespace, root: Path) -> None:
    plan = build_plan(
        template_type=args.type,
        action=args.action,
        root=root,
    )
    if args.out:
        save_plan(args.out, plan)
        output.success(
            {"plan_path": args.out, "plan": plan},
            f"Wrote plan to {args.out}",
        )
    else:
        output.success(
            {"plan": plan},
            f"Plan for action={args.action} template={args.type} (schema {PLAN_SCHEMA_VERSION})",
        )


def _configure_validate_plan(p: argparse.ArgumentParser) -> None:
    p.add_argument("plan_file", help="Path to template-plan.json")


@command(
    "validate-plan",
    help="Validate a template-plan.json against template catalog + workspace state",
    configure=_configure_validate_plan,
)
def cmd_validate_plan(args: argparse.Namespace, root: Path) -> None:
    plan = load_plan(args.plan_file)
    errors = validate_plan(plan, root)
    if errors:
        output.result(
            {"plan_file": args.plan_file, "errors": errors},
            f"Plan has {len(errors)} validation error(s)",
            exit_code=1,
        )
    output.success(
        {"plan_file": args.plan_file, "plan": plan},
        "Plan is valid",
    )


def _configure_apply_plan(p: argparse.ArgumentParser) -> None:
    p.add_argument("plan_file", help="Path to template-plan.json")


@command(
    "apply-plan",
    help="Execute a validated template-plan.json",
    configure=_configure_apply_plan,
)
def cmd_apply_plan(args: argparse.Namespace, root: Path) -> None:
    plan = load_plan(args.plan_file)
    errors = validate_plan(plan, root)
    if errors:
        output.error(
            f"Plan failed validation ({len(errors)} error(s))",
            hint="; ".join(errors),
        )
    result = apply_plan(plan, root)
    output.success(result, f"Applied plan action={plan['action']} template={plan['template_type']}")


def main() -> None:
    parser = cli.strict_parser("Template lifecycle management")
    # Phase 0 V-1: ``--workspace`` is auto-registered by strict_parser
    # (with ``dest="project_path"``); the legacy in-script alias
    # registration was removed to avoid an argparse-conflict on import.
    sub = parser.add_subparsers(dest="command", required=True)
    for name, cmd in COMMANDS.items():
        sp = sub.add_parser(name, help=cmd.help)
        cmd.configure(sp)

    args = parser.parse_args()
    project_path = paths.resolve_project_path(args)
    cmd = COMMANDS[args.command]
    if cmd.root_mode == "raw":
        root = Path(project_path).resolve()
    else:
        root = require_workflow_root(project_path)
    cmd.handler(args, root)


if __name__ == "__main__":
    cli.run_main(main)
