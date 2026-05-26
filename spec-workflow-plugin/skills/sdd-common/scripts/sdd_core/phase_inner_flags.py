"""Loader for ``data/phase_inner_flags.yaml``.

The data file is the single source of truth for the per-phase
inner-flag allowlist that ``RenderedCommand.__post_init__`` validates
emitted commands against.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .data_loader import load_yaml

__all__ = [
    "DATA_FILENAME",
    "PhaseFlagSchema",
    "FlagBundle",
    "load_phase_inner_flags",
    "load_bundle",
    "allowed_flags_for_phase",
    "canonical_flags",
    "deprecated_aliases",
]


DATA_FILENAME = "phase_inner_flags.yaml"


@dataclass(frozen=True)
class PhaseFlagSchema:
    required: tuple[str, ...]
    optional: tuple[str, ...]

    @property
    def allowed(self) -> frozenset[str]:
        return frozenset(self.required) | frozenset(self.optional)


@dataclass(frozen=True)
class FlagBundle:
    phases: dict[str, PhaseFlagSchema]
    canonical_flags: dict[str, str]
    deprecated_aliases: dict[str, tuple[str, ...]]


_CACHE: FlagBundle | None = None


def _coerce_string_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(v) for v in value if isinstance(v, str))


def _coerce_phase(raw: Any) -> PhaseFlagSchema:
    if not isinstance(raw, dict):
        return PhaseFlagSchema(required=(), optional=())
    return PhaseFlagSchema(
        required=_coerce_string_list(raw.get("required")),
        optional=_coerce_string_list(raw.get("optional")),
    )


def load_bundle(*, refresh: bool = False) -> FlagBundle:
    """Return the cached YAML bundle.

    Pass ``refresh=True`` from tests that mutate the data file.
    """
    global _CACHE
    if _CACHE is not None and not refresh:
        return _CACHE
    raw = load_yaml(DATA_FILENAME) or {}
    phases_raw = raw.get("phases") or {}
    phases: dict[str, PhaseFlagSchema] = {}
    if isinstance(phases_raw, dict):
        for name, payload in phases_raw.items():
            phases[str(name)] = _coerce_phase(payload)
    canon_raw = raw.get("canonical_flags") or {}
    canonical: dict[str, str] = {}
    if isinstance(canon_raw, dict):
        for concept, flag in canon_raw.items():
            if isinstance(flag, str):
                canonical[str(concept)] = flag
    aliases_raw = raw.get("deprecated_aliases") or {}
    aliases: dict[str, tuple[str, ...]] = {}
    if isinstance(aliases_raw, dict):
        for canon_flag, alias_list in aliases_raw.items():
            aliases[str(canon_flag)] = _coerce_string_list(alias_list)
    _CACHE = FlagBundle(
        phases=phases,
        canonical_flags=canonical,
        deprecated_aliases=aliases,
    )
    return _CACHE


def load_phase_inner_flags(*, refresh: bool = False) -> dict[str, PhaseFlagSchema]:
    """Return ``{phase_name: PhaseFlagSchema}``."""
    return load_bundle(refresh=refresh).phases


def allowed_flags_for_phase(phase: str) -> frozenset[str]:
    """Return the allowed inner-flag set for ``phase``.

    Raises ``ValueError`` when the phase is not registered. Fail-closed
    so a typo or stale phase name is caught at builder construction.
    """
    schema = load_bundle().phases.get(phase)
    if schema is None:
        raise ValueError(f"unknown phase: {phase!r}")
    return schema.allowed


def canonical_flags() -> dict[str, str]:
    """Return ``{concept: canonical_flag_name}``."""
    return dict(load_bundle().canonical_flags)


def deprecated_aliases() -> dict[str, tuple[str, ...]]:
    """Return ``{canonical_flag: (alias, ...)}``."""
    return {k: tuple(v) for k, v in load_bundle().deprecated_aliases.items()}
