"""Canonical ``--target`` resolver shared across script families."""
from __future__ import annotations

import argparse
from typing import Callable, Literal

__all__ = [
    "Family",
    "split_workspace_target",
    "apply_target_to_namespace",
]


Family = Literal[
    "workspace", "workspace-target", "spec", "approval", "discovery", "prd",
]


def split_workspace_target(value: str) -> tuple[str, "str | None"]:
    """Split ``feature[/repo-id]`` into its components."""
    if "/" in value:
        feature, _, repo_id = value.partition("/")
        return feature, repo_id or None
    return value, None


def _handle_workspace(ns: argparse.Namespace, raw: "str | None") -> None:
    if raw:
        feature, repo_id = split_workspace_target(raw)
        ns.feature = feature
        ns.repo_id = repo_id
    else:
        ns.feature = None
        ns.repo_id = None


def _handle_workspace_target(ns: argparse.Namespace, raw: "str | None") -> None:
    ns.spec_name = raw


def _handle_spec(ns: argparse.Namespace, raw: "str | None") -> None:
    ns.spec_name = raw


def _handle_approval(ns: argparse.Namespace, raw: "str | None") -> None:
    ns.approval_id = raw


def _handle_discovery(ns: argparse.Namespace, raw: "str | None") -> None:
    ns.discovery_name = raw


def _handle_prd(ns: argparse.Namespace, raw: "str | None") -> None:
    ns.feature = raw


_FAMILY_HANDLERS: dict[Family, Callable[[argparse.Namespace, "str | None"], None]] = {
    "workspace": _handle_workspace,
    "workspace-target": _handle_workspace_target,
    "spec": _handle_spec,
    "approval": _handle_approval,
    "discovery": _handle_discovery,
    "prd": _handle_prd,
}


def apply_target_to_namespace(
    args: argparse.Namespace, family: Family,
) -> None:
    """Populate family-specific attrs on *args* from ``args.target``."""
    raw = getattr(args, "target", None) or None
    handler = _FAMILY_HANDLERS.get(family)
    if handler is None:  # pragma: no cover — argparse choices guard prevents this
        raise ValueError(f"Unknown target family: {family!r}")
    handler(args, raw)
