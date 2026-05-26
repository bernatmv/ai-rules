"""argparse registration for the canonical approval flag set."""
from __future__ import annotations

import argparse
import dataclasses
from typing import Iterable

from .actions import status_choices
from .context import ApprovalContext, approval_id_from_path, resolve

__all__ = ["canonical_args", "parse_and_resolve"]


def canonical_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Register the canonical flag set on an existing parser.

    Only registers flags that are not already present so callers can
    layer this on top of an existing flag set without conflicts.
    """
    existing = {a.option_strings[0] for a in parser._actions if a.option_strings}

    def _add(*flags, **kwargs) -> None:
        if any(f in existing for f in flags):
            return
        parser.add_argument(*flags, **kwargs)

    _add("--approval-path", dest="approval_path", default=None,
         help="Path to approval JSON (canonical form)")
    _add("--approval-id", dest="approval_id", default=None,
         help="Approval identifier (derived from --approval-path when omitted)")
    _add("--status", dest="status", default=None,
         choices=status_choices(),
         help="Action synonym — approved/rejected/needs-revision also accepted")
    _add("--response", dest="response", default=None,
         help="Response text recorded in the audit trail")
    _add("--category", dest="category", default=None,
         choices=("spec", "steering", "discovery"),
         help="Compat alias — accepted and echoed in ignored_flags when not required")
    _add("--target-name", dest="target_name", default=None,
         help="Compat alias — accepted and echoed in ignored_flags when not required")
    return parser


def parse_and_resolve(
    parser: argparse.ArgumentParser,
    *,
    required_fields: Iterable[str] = (),
    accepted_compat: Iterable[str] = ("category", "target_name"),
    accept_path_positional: bool = False,
    args: list[str] | None = None,
) -> tuple[argparse.Namespace, ApprovalContext]:
    """Register canonical args, parse, and resolve into an ApprovalContext.

    Saves the canonical_args + parse_args + resolve triple shared by
    every approval entry-point script.

    *accept_path_positional* — when True, registers ``approval_json``
    as a leading positional so the script accepts both
    ``script.py /path/to/approval.json`` and
    ``script.py --approval-path /path/to/approval.json``. The resolved
    context's ``approval_path`` (and derived ``approval_id``) are filled
    from the positional when the flag form is not used. Off by default
    so callers can opt-in explicitly.
    """
    if accept_path_positional and not _has_positional(parser, "approval_json"):
        parser.add_argument(
            "approval_json", nargs="?", default=None,
            help="Path to approval JSON file (positional; or --approval-path)",
        )
    canonical_args(parser)
    parsed = parser.parse_args(args=args)
    ctx = resolve(
        parsed, required_fields=required_fields, accepted_compat=accepted_compat,
    )
    if (
        accept_path_positional
        and getattr(parsed, "approval_json", None)
        and not ctx.approval_path
    ):
        positional_path = parsed.approval_json
        ctx = dataclasses.replace(
            ctx,
            approval_path=positional_path,
            approval_id=ctx.approval_id or approval_id_from_path(positional_path),
        )
    return parsed, ctx


def _has_positional(parser: argparse.ArgumentParser, dest: str) -> bool:
    """Return True when *dest* is already registered as a positional."""
    for action in parser._actions:
        if action.dest == dest and not action.option_strings:
            return True
    return False
