"""Workflow graph loader.

The workflow graph at ``sdd_core/data/workflow-graph.json`` is the
single declarative source for what phases each workflow runs, what
context each phase needs, what gate prompt fires, what handoffs the
success envelope carries, and how transitions advance/reject.

This module owns three things:

1. :func:`load` — read the graph and return the (merged, post-extends)
   workflow definition for a given workflow id. Caches per process.
2. :func:`validate` — return the list of structural / cross-reference
   errors detected at load time. Used by the
   ``workflow_graph_cross_refs`` lint and by the loader on first read.
3. The merge logic for ``extends`` / ``phase_overrides`` /
   ``phases_appended``. One level of inheritance only — the schema
   forbids diamonds.

Schema rules (mirror the plan's V-0 ``Hard rules`` section):

* Every value is a literal string / int / bool / list. No expressions.
* ``preconditions`` and ``validations`` are identifiers that must
  resolve to a registered :class:`sdd_core.pipeline_phases.types.Validator`.
* ``gate_prompt_id`` and ``handoff_ids`` are foreign keys into
  ``prompt-registry.json`` and ``handoff-registry.json``.
* ``transitions`` is a closed dict of ``approve`` / ``reject`` /
  ``back``. Each value is a phase id or ``null``.
* ``extends`` is one level. ``phase_overrides`` patches keys;
  ``phases_appended`` adds rows at the end.
"""
from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

__all__ = [
    "WORKFLOW_GRAPH_FILENAME",
    "Workflow",
    "Phase",
    "AdvisoryPlacement",
    "load",
    "load_all",
    "validate",
    "default_graph_path",
    "list_workflows",
    "advisory_placement",
    "advisory_placements",
]


WORKFLOW_GRAPH_FILENAME = "workflow-graph.json"

# Closed set of transition keys — the schema forbids any other.
_TRANSITION_KEYS: frozenset[str] = frozenset({"approve", "reject", "back"})

# Required keys on every phase entry. ``transitions`` is always
# required because reject/back default to the phase id and approve
# defaults to ``null``; we still want the dict present so callers can
# read ``phase["transitions"]["approve"]`` without a defensive check.
_REQUIRED_PHASE_KEYS: tuple[str, ...] = (
    "id",
    "transitions",
)

# Optional keys with their default factories. Every loaded phase has
# every key present after :func:`_normalise_phase` so downstream
# consumers can read them unconditionally.
_OPTIONAL_PHASE_DEFAULTS: Mapping[str, Any] = {
    "produces": (),
    "preconditions": (),
    "validations": (),
    "gate_prompt_id": "",
    "review_artifacts": (),
    "handoff_ids": (),
}


@dataclass(frozen=True)
class Phase:
    """One phase of a workflow.

    Mirrors the JSON entry verbatim — fields that the JSON omits are
    filled with the defaults from :data:`_OPTIONAL_PHASE_DEFAULTS` so
    callers can read every field unconditionally.
    """

    id: str
    produces: tuple[str, ...] = ()
    preconditions: tuple[str, ...] = ()
    validations: tuple[str, ...] = ()
    gate_prompt_id: str = ""
    review_artifacts: tuple[str, ...] = ()
    handoff_ids: tuple[str, ...] = ()
    transitions: Mapping[str, str | None] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "produces": list(self.produces),
            "preconditions": list(self.preconditions),
            "validations": list(self.validations),
            "gate_prompt_id": self.gate_prompt_id,
            "review_artifacts": list(self.review_artifacts),
            "handoff_ids": list(self.handoff_ids),
            "transitions": dict(self.transitions),
        }


@dataclass(frozen=True)
class Workflow:
    """A loaded, merged workflow definition.

    The merge step has already applied ``extends`` / ``phase_overrides``
    / ``phases_appended`` so consumers see one flat phase list with one
    set of fields per phase.
    """

    id: str
    version: str
    context_needs: tuple[str, ...]
    phases: tuple[Phase, ...]

    def phase_by_id(self, phase_id: str) -> Phase | None:
        for phase in self.phases:
            if phase.id == phase_id:
                return phase
        return None

    def phase_ids(self) -> tuple[str, ...]:
        return tuple(p.id for p in self.phases)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "version": self.version,
            "context_needs": list(self.context_needs),
            "phases": [p.to_dict() for p in self.phases],
        }


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def default_graph_path() -> Path:
    """Return the canonical workflow-graph path inside ``sdd_core/data/``."""
    return Path(__file__).resolve().parent / "data" / WORKFLOW_GRAPH_FILENAME


_GRAPH_CACHE: dict[str, dict] = {}


def _read_graph(path: Path | None) -> dict:
    """Load the JSON file, cached by absolute path."""
    target = (path or default_graph_path()).resolve()
    key = str(target)
    cached = _GRAPH_CACHE.get(key)
    if cached is not None:
        return cached
    if not target.is_file():
        raise FileNotFoundError(f"Workflow graph not found: {target}")
    with open(target, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    if not isinstance(data, dict):
        raise ValueError(f"Workflow graph root must be an object: {target}")
    _GRAPH_CACHE[key] = data
    return data


def _clear_cache() -> None:
    """Test hook: drop the graph cache so reloads see fresh JSON."""
    _GRAPH_CACHE.clear()


def _normalise_phase(raw: Mapping[str, Any]) -> dict:
    """Fill in optional-key defaults; coerce list fields to tuples on construction."""
    if not isinstance(raw, Mapping):
        raise ValueError(f"phase entry must be an object: {raw!r}")
    if "id" not in raw or not isinstance(raw["id"], str) or not raw["id"]:
        raise ValueError("phase entry missing non-empty 'id'")
    transitions = raw.get("transitions") or {}
    if not isinstance(transitions, Mapping):
        raise ValueError(f"phase {raw['id']!r}: transitions must be an object")
    bad_keys = set(transitions.keys()) - _TRANSITION_KEYS
    if bad_keys:
        raise ValueError(
            f"phase {raw['id']!r}: unknown transition keys "
            f"{sorted(bad_keys)!r}; allowed: {sorted(_TRANSITION_KEYS)!r}"
        )
    norm: dict[str, Any] = {"id": raw["id"], "transitions": dict(transitions)}
    for key, default in _OPTIONAL_PHASE_DEFAULTS.items():
        value = raw.get(key, default)
        if isinstance(value, list):
            value = tuple(value)
        norm[key] = value
    return norm


def _phase_from_dict(raw: Mapping[str, Any]) -> Phase:
    norm = _normalise_phase(raw)
    return Phase(
        id=norm["id"],
        produces=tuple(norm["produces"]),
        preconditions=tuple(norm["preconditions"]),
        validations=tuple(norm["validations"]),
        gate_prompt_id=str(norm["gate_prompt_id"] or ""),
        review_artifacts=tuple(norm["review_artifacts"]),
        handoff_ids=tuple(norm["handoff_ids"]),
        transitions=dict(norm["transitions"]),
    )


def _apply_phase_overrides(
    base_phases: list[dict], overrides: Mapping[str, Mapping[str, Any]],
) -> list[dict]:
    """Patch keys in matching base phases. ``overrides`` keyed by phase id.

    Unknown phase ids in ``overrides`` raise — callers that want to
    *append* a phase must use ``phases_appended`` instead.
    """
    result: list[dict] = [copy.deepcopy(p) for p in base_phases]
    by_id: dict[str, dict] = {p["id"]: p for p in result}
    for phase_id, patch in overrides.items():
        if phase_id not in by_id:
            raise ValueError(
                f"phase_overrides references unknown phase {phase_id!r}; "
                f"use phases_appended to add a new phase"
            )
        if not isinstance(patch, Mapping):
            raise ValueError(
                f"phase_overrides[{phase_id!r}] must be an object"
            )
        target = by_id[phase_id]
        for key, value in patch.items():
            if key == "id":
                raise ValueError(
                    f"phase_overrides[{phase_id!r}] cannot rewrite 'id'"
                )
            if key == "transitions" and isinstance(value, Mapping):
                merged = dict(target.get("transitions", {}))
                merged.update(value)
                target["transitions"] = merged
            else:
                target[key] = value
    return result


def _resolve_workflow(
    graph: Mapping[str, Any], workflow_id: str, *, _seen: set[str] | None = None,
) -> dict:
    """Return the merged workflow dict for *workflow_id*.

    Walks ``extends`` (one level) and applies ``phase_overrides`` /
    ``phases_appended``. Cycles raise ``ValueError`` — the schema forbids
    diamonds and self-extension.
    """
    workflows = graph.get("workflows") or {}
    if workflow_id not in workflows:
        raise KeyError(f"Unknown workflow id: {workflow_id!r}")
    raw = workflows[workflow_id]
    if not isinstance(raw, Mapping):
        raise ValueError(f"workflow {workflow_id!r} must be an object")

    seen = set(_seen or ())
    if workflow_id in seen:
        raise ValueError(
            f"workflow extension cycle: {workflow_id!r} already in {seen!r}"
        )
    seen.add(workflow_id)

    extends = raw.get("extends")
    if extends:
        if not isinstance(extends, str):
            raise ValueError(
                f"workflow {workflow_id!r}: extends must be a string"
            )
        # One level of inheritance only — recurse to flatten the parent
        # but error if the parent itself extends.
        parent = _resolve_workflow(graph, extends, _seen=seen)
        if parent.get("extends"):
            raise ValueError(
                f"workflow {workflow_id!r}: multi-level extends is "
                f"forbidden ({extends!r} also extends {parent['extends']!r})"
            )
        base_phases = list(parent.get("phases") or [])
    else:
        base_phases = [
            _normalise_phase(p) for p in (raw.get("phases") or [])
        ]

    overrides = raw.get("phase_overrides") or {}
    if not isinstance(overrides, Mapping):
        raise ValueError(
            f"workflow {workflow_id!r}: phase_overrides must be an object"
        )
    if overrides:
        base_phases = _apply_phase_overrides(base_phases, overrides)

    appended = raw.get("phases_appended") or []
    if not isinstance(appended, list):
        raise ValueError(
            f"workflow {workflow_id!r}: phases_appended must be a list"
        )
    for entry in appended:
        base_phases.append(_normalise_phase(entry))

    context_needs = tuple(raw.get("context_needs") or ())
    version = str(raw.get("version") or "1.0.0")

    return {
        "id": workflow_id,
        "version": version,
        "context_needs": context_needs,
        "phases": base_phases,
        # Preserve the source extends key so callers (and recursion)
        # can detect multi-level chains.
        "extends": raw.get("extends"),
    }


def load(workflow_id: str, *, path: str | Path | None = None) -> Workflow:
    """Return the merged :class:`Workflow` for *workflow_id*.

    Reads ``sdd_core/data/workflow-graph.json`` by default; pass *path*
    for tests. Raises ``KeyError`` for unknown workflows and
    ``ValueError`` for schema violations.
    """
    graph = _read_graph(Path(path) if path is not None else None)
    merged = _resolve_workflow(graph, workflow_id)
    phases = tuple(_phase_from_dict(p) for p in merged["phases"])
    return Workflow(
        id=merged["id"],
        version=merged["version"],
        context_needs=tuple(merged["context_needs"]),
        phases=phases,
    )


def load_all(*, path: str | Path | None = None) -> tuple[Workflow, ...]:
    """Load every workflow in the graph in declaration order."""
    graph = _read_graph(Path(path) if path is not None else None)
    workflows = graph.get("workflows") or {}
    return tuple(load(wid, path=path) for wid in workflows)


def list_workflows(*, path: str | Path | None = None) -> tuple[str, ...]:
    """Return the workflow ids declared in the graph."""
    graph = _read_graph(Path(path) if path is not None else None)
    return tuple((graph.get("workflows") or {}).keys())


# ---------------------------------------------------------------------------
# Advisory placement
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdvisoryPlacement:
    """Declarative advisory placement metadata.

    The graph's ``advisories`` block tells the placement lint:

    * *fires_at_phase* — phase id where the advisory is detected.
    * *refresh_handled_by_phase* — phase id where the workflow
      naturally refreshes the underlying state.
    * *severity_when_phase_mismatch* — severity to use when *fires* is
      earlier than *refresh* (i.e. the workflow will heal it on its
      own and the advisory should not propose a redundant action).
    """

    name: str
    fires_at_phase: str
    refresh_handled_by_phase: str
    severity_when_phase_mismatch: str = "info"


def advisory_placements(
    *, path: str | Path | None = None,
) -> dict[str, AdvisoryPlacement]:
    """Return ``{advisory_name: AdvisoryPlacement}`` for the graph.

    Empty dict when the graph declares no ``advisories`` block.
    Callers iterate the result; the placement lint reads it
    directly to enforce phase-mismatch semantics.
    """
    graph = _read_graph(Path(path) if path is not None else None)
    raw = graph.get("advisories") or {}
    if not isinstance(raw, Mapping):
        return {}
    out: dict[str, AdvisoryPlacement] = {}
    for name, body in raw.items():
        if name.startswith("_") or not isinstance(body, Mapping):
            continue
        out[name] = AdvisoryPlacement(
            name=name,
            fires_at_phase=str(body.get("fires_at_phase") or ""),
            refresh_handled_by_phase=str(body.get("refresh_handled_by_phase") or ""),
            severity_when_phase_mismatch=str(
                body.get("severity_when_phase_mismatch") or "info"
            ),
        )
    return out


def advisory_placement(
    name: str, *, path: str | Path | None = None,
) -> "AdvisoryPlacement | None":
    """Return the :class:`AdvisoryPlacement` for *name*, or ``None``."""
    return advisory_placements(path=path).get(name)


# ---------------------------------------------------------------------------
# Validation (for the cross-refs lint)
# ---------------------------------------------------------------------------


_ADVISORY_REQUIRED_KEYS: tuple[str, ...] = (
    "fires_at_phase",
    "refresh_handled_by_phase",
    "severity_when_phase_mismatch",
)
_ADVISORY_VALID_SEVERITIES: frozenset[str] = frozenset({"info", "warn", "error"})


def _validate_advisories_block(advisories: Mapping[str, Any]) -> list[str]:
    """Return one error per malformed advisory entry."""
    errors: list[str] = []
    for name, body in advisories.items():
        if name.startswith("_"):
            continue  # documentation key
        if not isinstance(body, Mapping):
            errors.append(
                f"advisory {name!r}: must be an object, got "
                f"{type(body).__name__}"
            )
            continue
        for key in _ADVISORY_REQUIRED_KEYS:
            value = body.get(key)
            if not isinstance(value, str) or not value:
                errors.append(
                    f"advisory {name!r}: {key!r} must be a non-empty "
                    f"string, got {value!r}"
                )
        severity = body.get("severity_when_phase_mismatch")
        if (
            isinstance(severity, str)
            and severity
            and severity not in _ADVISORY_VALID_SEVERITIES
        ):
            errors.append(
                f"advisory {name!r}: severity_when_phase_mismatch "
                f"{severity!r} not in {sorted(_ADVISORY_VALID_SEVERITIES)!r}"
            )
    return errors


def _collect_errors_for_phase(
    workflow_id: str,
    phase: Mapping[str, Any],
    phase_ids: Iterable[str],
) -> list[str]:
    """Structural checks for a single phase entry.

    Cross-reference checks (gate_prompt_id / handoff_id resolution)
    happen separately because those references resolve outside this
    module — the lint passes the registries in.
    """
    errors: list[str] = []
    pid = phase.get("id", "?")
    transitions = phase.get("transitions") or {}
    valid_ids = set(phase_ids)
    for key in _TRANSITION_KEYS:
        target = transitions.get(key)
        if target is None:
            continue
        if not isinstance(target, str):
            errors.append(
                f"workflow {workflow_id!r} phase {pid!r}: transition "
                f"{key!r} must be a string or null"
            )
            continue
        if target not in valid_ids:
            errors.append(
                f"workflow {workflow_id!r} phase {pid!r}: transition "
                f"{key!r} → {target!r} not in workflow phase ids "
                f"{sorted(valid_ids)!r}"
            )
    return errors


def validate(
    *,
    path: str | Path | None = None,
    prompt_registry: Mapping[str, Any] | None = None,
    handoff_registry: Mapping[str, Any] | None = None,
    validator_ids: Iterable[str] | None = None,
) -> list[str]:
    """Return every structural + cross-reference error in the graph.

    Empty list means the graph is clean. The cross-refs lint feeds in
    the prompt registry, handoff registry, and the registered validator
    ids; missing registries skip those specific checks (so the loader
    can validate a graph in isolation).
    """
    errors: list[str] = []
    try:
        graph = _read_graph(Path(path) if path is not None else None)
    except (FileNotFoundError, ValueError) as exc:
        return [str(exc)]

    workflows = graph.get("workflows") or {}
    if not isinstance(workflows, Mapping):
        return ["graph 'workflows' must be an object"]

    advisories_block = graph.get("advisories")
    if advisories_block is not None and isinstance(advisories_block, Mapping):
        errors.extend(_validate_advisories_block(advisories_block))

    prompt_ids: set[str] = set()
    if prompt_registry is not None:
        prompts = prompt_registry.get("prompts") or {}
        if isinstance(prompts, Mapping):
            prompt_ids = set(prompts.keys())

    handoff_script_ids: set[str] = set()
    if handoff_registry is not None:
        scripts = handoff_registry.get("scripts") or {}
        if isinstance(scripts, Mapping):
            handoff_script_ids = set(scripts.keys())

    known_validators = set(validator_ids or ())

    for workflow_id in workflows:
        try:
            merged = _resolve_workflow(graph, workflow_id)
        except (KeyError, ValueError) as exc:
            errors.append(str(exc))
            continue
        phases = merged.get("phases") or []
        ids = [p.get("id") for p in phases if isinstance(p, Mapping)]
        if len(ids) != len(set(ids)):
            errors.append(
                f"workflow {workflow_id!r}: duplicate phase ids {ids!r}"
            )
        for phase in phases:
            errors.extend(
                _collect_errors_for_phase(workflow_id, phase, ids)
            )
            pid = phase.get("id", "?")
            gpid = phase.get("gate_prompt_id") or ""
            if gpid and prompt_registry is not None and gpid not in prompt_ids:
                errors.append(
                    f"workflow {workflow_id!r} phase {pid!r}: "
                    f"gate_prompt_id {gpid!r} not in prompt-registry"
                )
            for hid in (phase.get("handoff_ids") or ()):
                if (
                    handoff_registry is not None
                    and hid
                    and hid not in handoff_script_ids
                ):
                    errors.append(
                        f"workflow {workflow_id!r} phase {pid!r}: "
                        f"handoff_id {hid!r} not in handoff-registry"
                    )
            if validator_ids is not None:
                for vid in (phase.get("validations") or ()):
                    if vid and vid not in known_validators:
                        errors.append(
                            f"workflow {workflow_id!r} phase {pid!r}: "
                            f"validation id {vid!r} not registered"
                        )
                for vid in (phase.get("preconditions") or ()):
                    if vid and vid not in known_validators:
                        errors.append(
                            f"workflow {workflow_id!r} phase {pid!r}: "
                            f"precondition id {vid!r} not registered"
                        )
    return errors
