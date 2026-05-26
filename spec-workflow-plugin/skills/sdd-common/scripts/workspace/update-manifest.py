#!/usr/bin/env python3
"""Read-modify-write operations on a workspace coordination manifest.

Usage:
  .spec-workflow/sdd workspace/update-manifest.py --target FEATURE set-repo-role \
      --repo-id ID --role "<short repo-purpose description>"

Note: ``--target`` is registered on the parent parser; argparse
requires it BEFORE the subcommand token. Canonical literal:
  .spec-workflow/sdd workspace/update-manifest.py --target {feature} \
      set-repo-role --repo-id {id} --role "{role}"

Mirrors ``discovery/update-manifest.py``'s subcommand pattern. Each
subparser is a thin CLI shell over a library helper in
``sdd_core.workspace_manifest`` — the script never invents its own I/O.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
from pathlib import Path

from sdd_core import cli, handoffs, output
from sdd_core.workspace_manifest import (
    read_manifest,
    validate_manifest,
    write_manifest,
)

# Mirrors workflow-graph.json `sdd-workspace-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace")


def _errors_for_repo(manifest: dict, repo_id: str) -> list[dict]:
    """Return validate_manifest errors that mention *repo_id*.

    Filters by the ``Repo [<index>]`` rule prefix that the validator
    uses for per-repo issues — keeps the gate scoped to the specific
    mutation rather than rejecting on unrelated pre-existing drift.
    """
    repos = manifest.get("repos", []) or []
    target_index = next(
        (i for i, repo in enumerate(repos) if repo.get("id") == repo_id),
        None,
    )
    if target_index is None:
        return []
    result = validate_manifest(manifest)  # type: ignore[arg-type]
    errors = result.get("errors", []) if isinstance(result, dict) else []
    needle = f"Repo [{target_index}]"
    return [e for e in errors if needle in e.get("message", "")]


def _derive_default_role(target: dict) -> str:
    """Derive a sensible default role from repo metadata.

    Pattern: ``{repoType}-{path-basename}``. Empty inputs are dropped so
    a partially-bootstrapped repo entry produces ``coordinator-foo``
    rather than ``-foo`` or ``coordinator-``.
    """
    repo_type = (target.get("repoType") or "").strip()
    repo_path = (target.get("path") or "").strip()
    basename = Path(repo_path).name if repo_path else ""
    parts = [p for p in (repo_type, basename) if p]
    return "-".join(parts) if parts else ""


def _set_repo_role(
    root: Path, args: argparse.Namespace, ctx: object | None = None,
) -> None:
    data = read_manifest(root, args.feature)
    if not data:
        output.error(
            f"No manifest found for feature {args.feature!r}",
            hint=(
                "Run `.spec-workflow/sdd workspace/init-feature.py "
                "--target {feature} --repo ...` first."
            ),
        )
    repos = data.get("repos", []) or []
    # The subparser stores ``--repo-id`` under ``manifest_repo_id`` to
    # avoid colliding with the workspace-target resolver, which writes
    # ``args.repo_id`` from ``--target {feature}[/{repo}]`` and would
    # otherwise overwrite this value to ``None``.
    target_repo_id = args.manifest_repo_id
    target = next(
        (repo for repo in repos if repo.get("id") == target_repo_id), None,
    )
    if target is None:
        known = sorted(r.get("id", "") for r in repos if r.get("id"))
        output.error(
            f"No repo with id {target_repo_id!r} in feature {args.feature!r}",
            hint=f"Known repo ids: {known}",
        )

    raw_role = args.role.strip() if args.role else ""
    if not raw_role:
        raw_role = _derive_default_role(target)
    if not raw_role:
        output.error(
            "--role omitted and could not be derived (repoType + path basename are empty)",
            hint=(
                "Pass --role explicitly, or ensure the manifest entry has "
                "repoType and path populated."
            ),
        )
    new_role = raw_role
    target["role"] = new_role

    # Localised post-mutation validation: refuse to write only when this
    # mutation INTRODUCES a fresh validation error on the touched repo.
    # We do not gate on pre-existing errors elsewhere in the manifest —
    # bootstrap deliberately leaves other repos' ``role`` fields empty
    # and the agent populates them one at a time via repeated calls.
    new_errors = _errors_for_repo(data, target_repo_id)
    if new_errors:
        output.error(
            "Refusing to write — mutation would fail validation",
            context=str(new_errors),
            hint="Fix the inputs and re-run.",
        )

    write_manifest(root, args.feature, data)
    resolved_from = dict(ctx.resolved_from) if ctx is not None else None
    output.success(
        {
            "feature": args.feature,
            "repoId": target_repo_id,
            "role": new_role,
        },
        f"Set repos[{target_repo_id}].role = {new_role!r}",
        ctx=ctx,
        resolved_from=resolved_from,
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


_DISPATCH = {
    "set-repo-role": _set_repo_role,
}


def build_parser() -> argparse.ArgumentParser:
    parser = cli.strict_parser("Update workspace coordination manifest")
    cli.add_workspace_arg(parser)
    cli.target_argument(parser, family="workspace")

    sub = parser.add_subparsers(dest="action", required=True)

    p_role = sub.add_parser(
        "set-repo-role",
        help="Set the free-form ``role`` field on one repo entry.",
    )
    # ``dest="manifest_repo_id"`` keeps the user-facing flag stable
    # (``--repo-id``) while preventing the workspace-target resolver
    # from overwriting it via ``args.repo_id``.
    p_role.add_argument(
        "--repo-id",
        required=True,
        dest="manifest_repo_id",
        type=cli.name_type("repo-id"),
    )
    p_role.add_argument(
        "--role",
        default=None,
        help=(
            "Free-form role text. When omitted, derived from "
            "repoType + path basename."
        ),
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=("target", "workspace"))
    root = cli.resolve_workspace_root(args)
    _DISPATCH[args.action](root, args, ctx)


if __name__ == "__main__":
    cli.run_main(main)
