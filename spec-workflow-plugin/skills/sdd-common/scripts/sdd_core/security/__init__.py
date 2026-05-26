"""Security primitives for the sdd-common plugin.

All new primitives introduced by the security hardening plan live
here. Modifications to existing modules (paths, cli, approvals,
output) stay in their original locations; this package is strictly
for net-new security-critical code.

The public surface is re-exported from this module so callers can
import short names (``from sdd_core.security import TransactionalStore``)
without reaching into submodules. Tests that need to monkeypatch
module-level attributes are expected to use the full module path.
"""
from __future__ import annotations

from . import constants  # noqa: F401  — re-exported for callers
from .subprocess_safe import (
    ALLOWED_RUNNERS,
    RunResult,
    safe_run_test,
)
from .state import TransactionalStore, atomic_write_text
from .approval_record import (
    ApprovalRecord,
    Verification,
    VerificationState,
)
from .actor import (
    ActorKind,
    ActorKindPolicy,
    EnvHumanApprovalPolicy,
    default_actor_policy,
    set_actor_policy,
)
from .store import (
    LockedStore,
    locked_store,
    set_locked_store_factory,
    reset_locked_store_factory,
)
from .runners import (
    RunnerAllowlist,
    default_allowlist,
    register_runner,
    set_allowlist,
    reset_allowlist,
)
from .config import (
    SecurityConfig,
    security_config,
    set_security_config,
    reset_security_config,
    override_security_config,
)
from .audit import (
    AuditSink,
    audit_sink,
    set_audit_sink,
    reset_audit_sink,
)
from .hash import (
    Hasher,
    hasher,
    set_hasher,
    reset_hasher,
)
from .dry_run import (
    DryRunGate,
    EnvDryRunGate,
    AlwaysDry,
    NeverDry,
    dry_run_gate,
    set_dry_run_gate,
    reset_dry_run_gate,
)
from .approval_record import (
    register_approval_validator,
    reset_approval_validators,
)
from .seal import seal_security, is_sealed
from ._seam import dump_security_provenance, iter_seams
from .api import api

__all__ = [
    "constants",
    "safe_run_test",
    "RunResult",
    "ALLOWED_RUNNERS",
    "TransactionalStore",
    "atomic_write_text",
    "ApprovalRecord",
    "Verification",
    "VerificationState",
    "ActorKind",
    "ActorKindPolicy",
    "EnvHumanApprovalPolicy",
    "default_actor_policy",
    "set_actor_policy",
    "LockedStore",
    "locked_store",
    "set_locked_store_factory",
    "reset_locked_store_factory",
    "RunnerAllowlist",
    "default_allowlist",
    "register_runner",
    "set_allowlist",
    "reset_allowlist",
    "SecurityConfig",
    "security_config",
    "set_security_config",
    "reset_security_config",
    "override_security_config",
    "AuditSink",
    "audit_sink",
    "set_audit_sink",
    "reset_audit_sink",
    "Hasher",
    "hasher",
    "set_hasher",
    "reset_hasher",
    "DryRunGate",
    "EnvDryRunGate",
    "AlwaysDry",
    "NeverDry",
    "dry_run_gate",
    "set_dry_run_gate",
    "reset_dry_run_gate",
    "register_approval_validator",
    "reset_approval_validators",
    "seal_security",
    "is_sealed",
    "dump_security_provenance",
    "iter_seams",
    "api",
]
