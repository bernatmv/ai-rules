"""Typed accessors and mutators for the canonical ``review-quality.json`` artifact.

Defines schema v3 — a single artifact per spec that carries the ``active``
snapshot (current gate result), ``by_scope`` aggregation (per-document and
final views), ``phase_history`` (immutable record of approvals), and
``history`` (capped list of prior ``active`` snapshots).

All readers and writers route through this module. v1 / v2 / legacy v3
artifacts upgrade in-place via :func:`upgrade_if_needed`.

Callers MUST treat atomic_write as raising on failure — do not silently
swallow.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Literal

__all__ = [
    "SCHEMA_VERSION",
    "PER_DOCUMENT_SCOPE",
    "FINAL_SCOPE",
    "ROOT_CAUSE_KINDS",
    "RootCauseKind",
    "ReviewScore",
    "DEFAULT_ROOT_CAUSE_KIND",
    "ReviewQualityDoc",
    "load",
    "get_active",
    "get_active_issues_with_default_kind",
    "get_by_scope",
    "iter_per_doc_active_views",
    "iter_per_document_keys",
    "get_phase_history",
    "set_active",
    "set_by_scope",
    "append_phase_history",
    "append_history",
    "validate_v3",
    "upgrade_if_needed",
    "atomic_write",
    "HISTORY_CAP",
]


# v1=flat, v2=per-phase siblings, v3=single canonical artifact.
SCHEMA_VERSION: int = 3
# Bounded to keep artifact under ~256 KB; prior actives older than 10 are pruned.
HISTORY_CAP: int = 10
PER_DOCUMENT_SCOPE: str = "per-document"
FINAL_SCOPE: str = "final"

# Severity tokens that route into the fix loop. ``info`` is excluded so
# advisory rows stay valid without a ``root_cause_kind`` — they never
# drive routing.
_ACTIONABLE_SEVERITIES: frozenset[str] = frozenset(
    {"critical", "warning", "fail", "conflict"}
)

RootCauseKind = Literal["in_doc", "external_state", "cross_doc", "criteria_dispute"]
ROOT_CAUSE_KINDS: frozenset[str] = frozenset(
    {"in_doc", "external_state", "cross_doc", "criteria_dispute"}
)

# Per-facet score tokens emitted by sub-agents and persisted on
# ``tier2_scores[*][*].score`` and ``final_scope_demotions_predicted``.
# Defined here so the typed input contract in ``sdd_core.review_input``
# imports a single literal alias rather than restating the union.
ReviewScore = Literal["pass", "partial", "fail"]

# Backward-compat default applied at READ time when an existing artifact
# carries findings without ``root_cause_kind``. Schema validation still
# flags the missing field on NEW writes so the field stays required for
# fresh sub-agent output.
DEFAULT_ROOT_CAUSE_KIND: str = "in_doc"


@dataclass
class ReviewQualityDoc:
    """Typed view of a v3 artifact. Conversion is lossy by design — unknown top-level fields are dropped."""

    schema_version: int = SCHEMA_VERSION
    review_type: str = ""
    active: dict[str, Any] = field(default_factory=dict)
    by_scope: dict[str, Any] = field(default_factory=lambda: {
        PER_DOCUMENT_SCOPE: {},
        FINAL_SCOPE: {},
    })
    phase_history: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    schema_upgraded_from: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": self.schema_version,
            "review_type": self.review_type,
            "active": dict(self.active),
            "by_scope": {
                PER_DOCUMENT_SCOPE: dict(
                    self.by_scope.get(PER_DOCUMENT_SCOPE, {})
                ),
                FINAL_SCOPE: dict(self.by_scope.get(FINAL_SCOPE, {})),
            },
            "phase_history": list(self.phase_history),
            "history": list(self.history),
        }
        if self.schema_upgraded_from is not None:
            out["schema_upgraded_from"] = self.schema_upgraded_from
        return out


def load(path: str | Path) -> dict[str, Any]:
    """Read a review-quality artifact and upgrade to v3 if needed.

    Returns a fresh v3 skeleton when *path* does not exist so callers can
    treat first-run and subsequent-run paths identically. Raises
    :class:`ValueError` on malformed JSON; raises :class:`OSError` on
    other I/O failures.
    """
    p = Path(path)
    if not p.is_file():
        return _empty_v3()
    with p.open(encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(
            f"Review-quality artifact at {p} is not a JSON object"
        )
    return upgrade_if_needed(data)


def get_active(doc: dict[str, Any]) -> dict[str, Any]:
    """Return ``active`` as a dict; missing or non-dict values become ``{}``."""
    active = doc.get("active")
    return active if isinstance(active, dict) else {}


def get_active_issues_with_default_kind(
    active: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return the ``active.issues`` list with ``root_cause_kind`` defaulted.

    Legacy artifacts written before the kind requirement landed do not carry
    the field on existing entries. Readers (e.g. the post-review aggregator)
    treat a missing kind as :data:`DEFAULT_ROOT_CAUSE_KIND` so historical
    fixtures keep routing through the unchanged ``fix_all`` branch — only
    new writes have to populate the field. Returns ``[]`` when the dict
    counts shape is in use; it carries no per-finding rows to default.
    """
    if not isinstance(active, dict):
        return []
    issues = active.get("issues")
    if not isinstance(issues, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in issues:
        if not isinstance(entry, dict):
            continue
        row = dict(entry)
        if not row.get("root_cause_kind"):
            row["root_cause_kind"] = DEFAULT_ROOT_CAUSE_KIND
        out.append(row)
    return out


def get_by_scope(
    doc: dict[str, Any], scope: str, doc_key: str | None = None,
) -> dict[str, Any]:
    """Return the snapshot stored under ``by_scope.<scope>[.<doc_key>]``.

    ``scope == "per-document"`` requires a ``doc_key``; ``scope ==
    "final"`` ignores the parameter and returns the final-scope
    snapshot. Missing entries surface as empty dicts.
    """
    by_scope = doc.get("by_scope")
    if not isinstance(by_scope, dict):
        return {}
    bucket = by_scope.get(scope)
    if not isinstance(bucket, dict):
        return {}
    if scope == PER_DOCUMENT_SCOPE:
        if doc_key is None:
            return {}
        entry = bucket.get(doc_key)
        return entry if isinstance(entry, dict) else {}
    return bucket


def iter_per_document_keys(doc: dict[str, Any]) -> Iterator[str]:
    """Yield every key under ``by_scope.per-document`` for the given envelope.

    Keeps the envelope shape contained in this module — callers that need
    to enumerate per-document slot identifiers (without materialising the
    slot bodies) iterate this generator instead of indexing
    ``data["by_scope"]["per-document"]`` directly. Returns an empty
    iterator when *doc* is missing the ``by_scope`` bucket.
    """
    if not isinstance(doc, dict):
        return
    by_scope = doc.get("by_scope")
    if not isinstance(by_scope, dict):
        return
    per_doc = by_scope.get(PER_DOCUMENT_SCOPE)
    if not isinstance(per_doc, dict):
        return
    for key in per_doc:
        yield key


def iter_per_doc_active_views(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Yield each populated ``by_scope.per-document.<key>`` slot as a view.

    Each slot is shaped like an ``active`` snapshot (carries ``issues``,
    ``overall_score``, etc.). Callers that need to walk per-doc findings
    when ``active`` is empty (fresh per-doc-only artifacts) iterate the
    returned views and call schema accessors on each one — keeping the
    envelope shape contained inside this module.
    """
    if not isinstance(doc, dict):
        return []
    by_scope = doc.get("by_scope")
    if not isinstance(by_scope, dict):
        return []
    bucket = by_scope.get(PER_DOCUMENT_SCOPE)
    if not isinstance(bucket, dict):
        return []
    return [slot for slot in bucket.values() if isinstance(slot, dict)]


def get_phase_history(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the ``phase_history`` list.

    Non-list values are coerced to ``[]`` rather than raising — readers
    treat a missing or corrupt history as "no prior phases recorded".
    """
    phases = doc.get("phase_history")
    if not isinstance(phases, list):
        return []
    return [p for p in phases if isinstance(p, dict)]


def set_active(doc: dict[str, Any], snapshot: dict[str, Any]) -> None:
    """Replace ``active`` in-place with *snapshot* (shallow-copied)."""
    if not isinstance(snapshot, dict):
        raise TypeError(
            f"snapshot must be a dict; got {type(snapshot).__name__}"
        )
    doc["active"] = dict(snapshot)


def set_by_scope(
    doc: dict[str, Any], scope: str, doc_key: str | None,
    snapshot: dict[str, Any],
) -> None:
    """Write *snapshot* into ``by_scope.<scope>[.<doc_key>]``.

    For ``scope == "per-document"`` *doc_key* is required and identifies
    the document slot to update. For ``scope == "final"`` *doc_key* is
    ignored and the final-scope snapshot is replaced wholesale.
    """
    if not isinstance(snapshot, dict):
        raise TypeError(
            f"snapshot must be a dict; got {type(snapshot).__name__}"
        )
    by_scope = doc.setdefault("by_scope", {})
    if not isinstance(by_scope, dict):
        by_scope = {}
        doc["by_scope"] = by_scope
    if scope == PER_DOCUMENT_SCOPE:
        if not doc_key:
            raise ValueError(
                "doc_key is required when scope == 'per-document'"
            )
        bucket = by_scope.setdefault(PER_DOCUMENT_SCOPE, {})
        if not isinstance(bucket, dict):
            bucket = {}
            by_scope[PER_DOCUMENT_SCOPE] = bucket
        bucket[doc_key] = dict(snapshot)
        return
    if scope == FINAL_SCOPE:
        by_scope[FINAL_SCOPE] = dict(snapshot)
        return
    raise ValueError(
        f"Unknown scope {scope!r}; expected 'per-document' or 'final'"
    )


def append_phase_history(
    doc: dict[str, Any], entry: dict[str, Any],
) -> None:
    """Append *entry* to ``phase_history`` in chronological order."""
    if not isinstance(entry, dict):
        raise TypeError(
            f"entry must be a dict; got {type(entry).__name__}"
        )
    phases = doc.get("phase_history")
    if not isinstance(phases, list):
        phases = []
        doc["phase_history"] = phases
    phases.append(dict(entry))


def append_history(
    doc: dict[str, Any], prior_active: dict[str, Any],
) -> None:
    """Push *prior_active* onto ``history`` and trim to :data:`HISTORY_CAP`.

    Newest entry lives at index 0 — callers that walk history
    chronologically (oldest → newest) reverse the slice. The cap keeps
    artifact size bounded across long-lived specs.
    """
    if not isinstance(prior_active, dict):
        raise TypeError(
            f"prior_active must be a dict; got {type(prior_active).__name__}"
        )
    if not prior_active:
        return
    history = doc.get("history")
    if not isinstance(history, list):
        history = []
    history.insert(0, dict(prior_active))
    doc["history"] = history[:HISTORY_CAP]


def validate_v3(doc: dict[str, Any]) -> list[str]:
    """Return a list of human-readable validation errors.

    Empty list means the artifact is well-formed enough for the typed
    accessors to operate without raising. The check is intentionally
    structural — semantic validation (score consistency, status / score
    cross-checks) lives in the writer that builds the snapshot.
    """
    errors: list[str] = []
    if not isinstance(doc, dict):
        return [f"artifact must be a JSON object; got {type(doc).__name__}"]
    if doc.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {SCHEMA_VERSION}; "
            f"got {doc.get('schema_version')!r}"
        )
    review_type = doc.get("review_type")
    if not isinstance(review_type, str) or not review_type:
        errors.append("review_type must be a non-empty string")
    active = doc.get("active")
    if not isinstance(active, dict):
        errors.append("active must be a dict")
    else:
        errors.extend(_validate_finding_root_cause_kinds(active))
        errors.extend(_validate_facet_criteria_by_scope(active))
    by_scope = doc.get("by_scope")
    if not isinstance(by_scope, dict):
        errors.append("by_scope must be a dict")
    else:
        per_doc = by_scope.get(PER_DOCUMENT_SCOPE)
        if per_doc is not None and not isinstance(per_doc, dict):
            errors.append("by_scope['per-document'] must be a dict")
        final = by_scope.get(FINAL_SCOPE)
        if final is not None and not isinstance(final, dict):
            errors.append("by_scope['final'] must be a dict")
    phases = doc.get("phase_history")
    if phases is not None and not isinstance(phases, list):
        errors.append("phase_history must be a list")
    history = doc.get("history")
    if history is not None and not isinstance(history, list):
        errors.append("history must be a list")
    elif isinstance(history, list) and len(history) > HISTORY_CAP:
        errors.append(
            f"history exceeds cap ({len(history)} > {HISTORY_CAP})"
        )
    return errors


def _validate_facet_criteria_by_scope(active: dict[str, Any]) -> list[str]:
    """Require ``final_scope_demotions_predicted`` whenever facets ship
    scope-specific criteria.

    ``tier2_facet_criteria_by_scope`` is the publish side: the launch
    envelope names facets whose criteria differ between per-document
    and final scope. ``final_scope_demotions_predicted`` is the predict
    side: the sub-agent must explicitly state which per-doc passes are
    expected to demote at final scope. An empty list is the valid "no
    demotions" answer; the field's *absence* is what signals the
    sub-agent skipped the reconciliation step.
    """
    errors: list[str] = []
    facet_criteria = active.get("tier2_facet_criteria_by_scope")
    if not isinstance(facet_criteria, dict) or not facet_criteria:
        return errors
    demotions = active.get("final_scope_demotions_predicted")
    if demotions is None:
        errors.append(
            "active.final_scope_demotions_predicted is required when "
            "active.tier2_facet_criteria_by_scope names facets with "
            "scope-specific criteria; supply an empty list when no "
            "demotions are predicted."
        )
        return errors
    if not isinstance(demotions, list):
        errors.append(
            "active.final_scope_demotions_predicted must be a list; got "
            f"{type(demotions).__name__}"
        )
    return errors


def _validate_finding_root_cause_kinds(active: dict[str, Any]) -> list[str]:
    """Verify ``root_cause_kind`` on every actionable entry of ``active.issues[]``.

    ``active.issues`` historically held a counts dict (``{critical, warning,
    suggestion}``) that does not carry per-finding metadata. The list shape
    (one entry per finding) is the new representation that supports the
    kind enum and routes through the post-review aggregator. This
    validator only fires on the list shape — dict shapes are passed
    through unchanged so legacy artifacts remain valid.
    """
    errors: list[str] = []
    issues = active.get("issues")
    if not isinstance(issues, list):
        return errors
    legal = sorted(ROOT_CAUSE_KINDS)
    for idx, entry in enumerate(issues):
        if not isinstance(entry, dict):
            errors.append(
                f"active.issues[{idx}] must be a dict; got {type(entry).__name__}"
            )
            continue
        severity = str(entry.get("severity") or "").lower()
        if severity not in _ACTIONABLE_SEVERITIES:
            continue
        kind = entry.get("root_cause_kind")
        if kind is None:
            errors.append(
                f"active.issues[{idx}] missing required 'root_cause_kind' "
                f"(severity={severity!r}); expected one of {legal}"
            )
            continue
        if not isinstance(kind, str) or kind not in ROOT_CAUSE_KINDS:
            errors.append(
                f"active.issues[{idx}] root_cause_kind={kind!r} is not "
                f"one of {legal}"
            )
    return errors


def upgrade_if_needed(doc: dict[str, Any]) -> dict[str, Any]:
    """Return a v3-shaped dict, upgrading from v1 / v2 / legacy v3 if needed.

    A returning v3 dict carries ``schema_upgraded_from`` recording the
    original ``schema_version`` value when an upgrade was applied. v3
    artifacts that already carry the canonical ``active`` shape are
    returned unchanged.
    """
    if not isinstance(doc, dict):
        raise TypeError(
            f"doc must be a dict; got {type(doc).__name__}"
        )
    raw_version = doc.get("schema_version")
    if _is_canonical_v3(doc):
        return doc
    upgraded = _shape_into_v3(doc, raw_version)
    return upgraded


def atomic_write(path: str | Path, doc: dict[str, Any]) -> None:
    """Persist *doc* atomically via :func:`sdd_core.output.atomic_write_json`."""
    from sdd_core import output as _output
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _output.atomic_write_json(str(target), doc, verify_key="schema_version")


def _empty_v3() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "review_type": "",
        "active": {},
        "by_scope": {PER_DOCUMENT_SCOPE: {}, FINAL_SCOPE: {}},
        "phase_history": [],
        "history": [],
    }


def _is_canonical_v3(doc: dict[str, Any]) -> bool:
    """True when *doc* already carries the v3 ``active`` / ``by_scope`` shape.

    The integer ``schema_version == 3`` is the canonical marker. Older
    string ``"3.0.0"`` artifacts predate the in-artifact aggregation
    layout — they share the version label but not the shape, so they
    are reshaped through :func:`_shape_into_v3` like v1 / v2.
    """
    if doc.get("schema_version") != SCHEMA_VERSION:
        return False
    if not isinstance(doc.get("active"), dict):
        return False
    by_scope = doc.get("by_scope")
    if not isinstance(by_scope, dict):
        return False
    return True


# Top-level keys that travel from a pre-v3 artifact into the ``active``
# snapshot. Anything outside this set stays at the top level (review_type,
# schema_version) or is dropped during upgrade (skill / skill_version /
# spec_name / spec_type — those re-derive from the current build).
_ACTIVE_FIELDS: tuple[str, ...] = (
    "overall_status",
    "overall_score",
    "generated_at",
    "last_full_review_at",
    "issues",
    "documents",
    "document_hashes",
    "cross_validation",
    "cross_validation_deduction",
    "comprehension",
    "context",
    "supplemental",
    "tier1_facets",
    "tier2_scores",
    "tier2_facet_criteria_by_scope",
    "final_scope_demotions_predicted",
    "gate_id",
    "scope",
)

_SKILL_TO_REVIEW_TYPE: dict[str, str] = {
    "sdd-review-spec-docs": "spec",
    "sdd-review-steering-docs": "steering",
    "sdd-review-prd": "prd",
}


def _shape_into_v3(
    doc: dict[str, Any], original_version: Any,
) -> dict[str, Any]:
    """Fold a pre-v3 artifact (or non-canonical v3) into the v3 shape.

    Preserves an existing ``active`` dict losslessly: when the caller
    already shaped the snapshot (e.g. partial v3 envelope without a
    populated ``by_scope``), the upgrader keeps every key under
    ``active`` rather than re-deriving from the (likely empty) top
    level.
    """
    review_type = doc.get("review_type")
    existing_active = doc.get("active")
    if not isinstance(review_type, str) or not review_type:
        # Prefer review_type already lifted onto active (partial v3
        # envelopes carry the field there, not at the root).
        if isinstance(existing_active, dict):
            inner_rt = existing_active.get("review_type")
            if isinstance(inner_rt, str) and inner_rt:
                review_type = inner_rt
    if not isinstance(review_type, str) or not review_type:
        review_type = _SKILL_TO_REVIEW_TYPE.get(
            doc.get("skill", ""), "unknown",
        )
    active: dict[str, Any] = (
        dict(existing_active) if isinstance(existing_active, dict) else {}
    )
    for key in _ACTIVE_FIELDS:
        if key in doc and doc[key] is not None and key not in active:
            active[key] = doc[key]
    if "scope" not in active:
        active["scope"] = FINAL_SCOPE

    legacy_history = doc.get("history")
    history_list: list[dict[str, Any]] = []
    if isinstance(legacy_history, dict):
        runs = legacy_history.get("runs")
        if isinstance(runs, list):
            history_list = [r for r in runs if isinstance(r, dict)]
    elif isinstance(legacy_history, list):
        history_list = [r for r in legacy_history if isinstance(r, dict)]
    history_list = history_list[:HISTORY_CAP]

    by_scope_existing = doc.get("by_scope")
    if isinstance(by_scope_existing, dict):
        per_doc = by_scope_existing.get(PER_DOCUMENT_SCOPE)
        final = by_scope_existing.get(FINAL_SCOPE)
        by_scope = {
            PER_DOCUMENT_SCOPE: per_doc if isinstance(per_doc, dict) else {},
            FINAL_SCOPE: final if isinstance(final, dict) else dict(active),
        }
    else:
        by_scope = {PER_DOCUMENT_SCOPE: {}, FINAL_SCOPE: dict(active)}

    phase_history_existing = doc.get("phase_history")
    phase_history = (
        [p for p in phase_history_existing if isinstance(p, dict)]
        if isinstance(phase_history_existing, list)
        else []
    )

    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "review_type": review_type,
        "active": active,
        "by_scope": by_scope,
        "phase_history": phase_history,
        "history": history_list,
    }
    if original_version is not None:
        out["schema_upgraded_from"] = str(original_version)
    return out
