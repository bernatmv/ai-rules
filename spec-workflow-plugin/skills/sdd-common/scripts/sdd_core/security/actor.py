"""Actor-kind policy: human vs agent for approval transitions.

The default policy accepts ``SDD_HUMAN_APPROVAL=1`` as proof.
Signature-based strategies (GPG / SSH against ``authorizedBy``)
implement the same Protocol — call sites pass
``default_actor_policy()`` and never change.

``SDD_ACTOR_POLICY_OVERRIDE`` is a test seam (parity with
``SDD_HARNESS_OVERRIDE``). Accepted values are restricted to fixture
names baked into this module; anything else is ignored.
"""
from __future__ import annotations

import argparse
import os
from enum import Enum
from typing import Mapping, Protocol, runtime_checkable

from . import constants
from ._seam import Seam

__all__ = [
    "ActorKind",
    "ActorKindPolicy",
    "PROTOCOL_VERSION",
    "EnvHumanApprovalPolicy",
    "default_actor_policy",
    "set_actor_policy",
]

PROTOCOL_VERSION = 1


class ActorKind(Enum):
    HUMAN = "human"
    AGENT = "ai-agent"


@runtime_checkable
class ActorKindPolicy(Protocol):
    """Strategy interface — one method, one question."""

    protocol_version: int

    def authorise(
        self,
        env: Mapping[str, str],
        args: argparse.Namespace,
    ) -> ActorKind: ...


class EnvHumanApprovalPolicy:
    """Accepts ``SDD_HUMAN_APPROVAL=1`` as the sole proof of human actorship.

    Rationale: fail-closed. The ``--actor`` string is untrusted
    operator input — any value (even ``"jguo02"``) is treated as AGENT
    unless the process also sets the env marker. A SKILL body is
    expected to set the marker after a confirmed
    ``approval-confirm-human`` prompt. The ``--actor`` value is
    preserved in the audit log as attribution metadata; it is never
    consulted here.
    """

    protocol_version = PROTOCOL_VERSION

    @property
    def ENV_KEY(self) -> str:
        return constants.HUMAN_APPROVAL_ENV

    @property
    def ENV_VALUE(self) -> str:
        return constants.HUMAN_APPROVAL_VALUE

    def authorise(
        self, env: Mapping[str, str], args: argparse.Namespace,
    ) -> ActorKind:
        if env.get(self.ENV_KEY) == self.ENV_VALUE:
            return ActorKind.HUMAN
        return ActorKind.AGENT


class _AlwaysHumanPolicy:
    """Test-fixture policy — reachable only via SDD_ACTOR_POLICY_OVERRIDE."""

    protocol_version = PROTOCOL_VERSION

    def authorise(
        self, env: Mapping[str, str], args: argparse.Namespace,
    ) -> ActorKind:
        return ActorKind.HUMAN


class _AlwaysAgentPolicy:
    """Test-fixture policy — reachable only via SDD_ACTOR_POLICY_OVERRIDE."""

    protocol_version = PROTOCOL_VERSION

    def authorise(
        self, env: Mapping[str, str], args: argparse.Namespace,
    ) -> ActorKind:
        return ActorKind.AGENT


_OVERRIDE_FIXTURES: "dict[str, ActorKindPolicy]" = {
    constants.ACTOR_OVERRIDE_ALWAYS_HUMAN: _AlwaysHumanPolicy(),
    constants.ACTOR_OVERRIDE_ALWAYS_AGENT: _AlwaysAgentPolicy(),
}

_seam: Seam[ActorKindPolicy] = Seam(
    name="ActorKindPolicy",
    protocol=ActorKindPolicy,
    default=EnvHumanApprovalPolicy(),
    protocol_version=PROTOCOL_VERSION,
)


def default_actor_policy() -> ActorKindPolicy:
    """Return the policy in force for this process.

    Resolution order:
      1. ``SDD_ACTOR_POLICY_OVERRIDE`` env var, if set to a known
         fixture name (test-only).
      2. The policy registered via :func:`set_actor_policy` (tests).
      3. :class:`EnvHumanApprovalPolicy` (production default).
    """
    override = os.environ.get(constants.ACTOR_POLICY_OVERRIDE_ENV, "").strip()
    if override:
        fixture = _OVERRIDE_FIXTURES.get(override)
        if fixture is not None:
            return fixture
        # Unknown override names fall through — a typo'd test env var
        # must not silently weaken authorisation in production.
    return _seam.get()


def set_actor_policy(policy: ActorKindPolicy) -> None:
    _seam.set(policy)
