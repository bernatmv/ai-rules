"""Unified accessor namespace for the security primitives.

Callers import :data:`api` once; tests mock one symbol; tracing
decorators wrap one object. Direct accessor calls remain valid — this
namespace is additive convenience, not a replacement.
"""
from __future__ import annotations

from . import actor as _actor
from . import audit as _audit
from . import config as _config
from . import dry_run as _dry_run
from . import hash as _hash
from . import runners as _runners
from . import store as _store

__all__ = ["api"]


class _Api:
    """Aggregate accessor namespace — one attribute per security primitive."""

    @property
    def locked_store(self):
        return _store.locked_store

    @property
    def allowlist(self):
        return _runners.default_allowlist

    @property
    def actor_policy(self):
        return _actor.default_actor_policy

    @property
    def config(self):
        return _config.security_config

    @property
    def hasher(self):
        return _hash.hasher

    @property
    def audit(self):
        return _audit.audit_sink

    @property
    def dry_run(self):
        return _dry_run.dry_run_gate


api = _Api()
