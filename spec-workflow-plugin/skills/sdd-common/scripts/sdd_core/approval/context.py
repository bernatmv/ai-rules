"""ApprovalContext dataclass + identifier resolution + normalisation."""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .actions import canonical_action
from sdd_core.security.actor import ActorKind, default_actor_policy

__all__ = [
    "ApprovalContext",
    "approval_id_from_path",
    "derive_approval_id",
    "resolve",
]


@dataclass
class ApprovalContext:
    """Normalised view of the parsed arguments.

    ``ignored_flags`` records any compat aliases that were supplied but
    are not part of the script's canonical flag set. Each entry of the
    form ``"--flag=value"`` (mirrors the CLI shape) so the agent can
    echo it back without guessing value formatting.

    ``actor_kind`` is the policy verdict on whether this invocation
    represents a human operator. Computed once at :func:`resolve`
    time so call sites read ``ctx.actor_kind`` instead of re-running
    the policy in every branch.
    """

    approval_path: "str | None" = None
    approval_id: "str | None" = None
    action: "str | None" = None
    response: "str | None" = None
    category: "str | None" = None
    target_name: "str | None" = None
    actor_kind: ActorKind = ActorKind.AGENT
    ignored_flags: list[str] = field(default_factory=list)


def approval_id_from_path(approval_path: "str | None") -> "str | None":
    """Derive ``approval_<ts>_<rand>`` from ``approvals/.../<id>.json``."""
    if not approval_path:
        return None
    stem = Path(approval_path).stem
    if stem.startswith("approval_"):
        return stem
    return None


def derive_approval_id(args) -> "str | None":
    """Best-effort approval_id resolution from mixed-shape args."""
    get = args.get if isinstance(args, dict) else lambda k: getattr(args, k, None)
    approval_id = get("approval_id")
    if approval_id:
        return approval_id
    return approval_id_from_path(get("approval_path"))


def _as_flag_repr(name: str, value: object) -> str:
    if value is None or value is False:
        return f"--{name}"
    return f'--{name}={value}'


def resolve(
    args: argparse.Namespace,
    *,
    required_fields: Iterable[str] = (),
    accepted_compat: Iterable[str] = ("category", "target_name"),
) -> ApprovalContext:
    """Normalise ``args`` into an :class:`ApprovalContext`.

    ``required_fields`` names the fields the script considers canonical
    for its own flag set. Values supplied for other fields are recorded
    in ``ignored_flags`` so the caller can surface them in the JSON
    envelope (instead of silently dropping them).
    """
    required = set(required_fields)
    actor_kind = default_actor_policy().authorise(
        env=os.environ, args=args,
    )

    ctx = ApprovalContext(
        approval_path=getattr(args, "approval_path", None),
        approval_id=derive_approval_id(args),
        action=canonical_action(getattr(args, "status", None)),
        response=getattr(args, "response", None),
        category=getattr(args, "category", None),
        target_name=getattr(args, "target_name", None),
        actor_kind=actor_kind,
    )

    for name in accepted_compat:
        if name in required:
            continue
        value = getattr(args, name, None)
        if value is None:
            continue
        ctx.ignored_flags.append(_as_flag_repr(name.replace("_", "-"), value))

    return ctx
