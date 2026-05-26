"""Launch-precondition data types and skills-root resolver."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Protocol, Union, runtime_checkable

from sdd_core import paths as _paths
from sdd_core import reference_ledger
from review_quality.constants import SCOPE_PER_DOCUMENT

__all__ = [
    "Finding",
    "PreconditionProtocol",
    "Precondition",
    "ReferenceReadPrecondition",
    "PostChangeReviewPrecondition",
    "AdvisoryEchoPrecondition",
    "AnyPrecondition",
    "PreconditionUnion",
    "build_ack_reference_read_command",
    "_FALLBACK_SKILLS_ROOT",
    "_find_skills_ancestor",
    "_skills_root",
    "POST_CHANGE_REVIEW_SCRIPT",
    "POST_CHANGE_REVIEW_PRESENTED_SCRIPT_PREFIX",
    "post_change_review_script_id",
    "post_change_review_presented_script_id",
    "advisory_echoed_script_id",
    "_POST_CHANGE_REVIEW_SCRIPT_PREFIX",
    "_ADVISORY_ECHOED_SCRIPT_PREFIX",
    "_WARN_SEEN_SCRIPT",
    "_GATE_NAMESPACE",
    "_gate_key",
]


def _find_skills_ancestor(start: "str | Path") -> Path:
    """Return the nearest ancestor IDE skills directory.

    Walks upward from ``start`` and returns the first directory whose
    ``sdd-common/SKILL.md`` marker exists, or — when the current path
    is a workspace root — the matching ``.cursor/skills`` or
    ``.claude/skills`` subdirectory. Marker-based rather than counting
    ``parents[N]`` so refactoring the module's filesystem depth does
    not silently break the fallback resolution. Raises
    ``FileNotFoundError`` when no ancestor carries the marker.
    """
    here = Path(start).resolve()
    ide_subdirs = (Path(".cursor") / "skills", Path(".claude") / "skills")
    for candidate in (here, *here.parents):
        direct = candidate / "sdd-common" / "SKILL.md"
        if direct.is_file():
            return candidate
        for sub in ide_subdirs:
            marker = candidate / sub / "sdd-common" / "SKILL.md"
            if marker.is_file():
                return candidate / sub
    raise FileNotFoundError(
        f"No SKILL-bearing skills directory found above {start}"
    )


# Fallback skills root — resolved by ancestor marker search rather
# than by ``parents[N]`` counting. Used when the env override is
# unset *and* the cwd-based probe fails (e.g. tests that execute
# outside an IDE-native skills tree).
_FALLBACK_SKILLS_ROOT = _find_skills_ancestor(__file__)


def _active_harness_name() -> "str | None":
    """Return the persisted adapter name without side effects.

    Reads ``harness.json`` directly so the skills-root probe can prefer
    the harness-native directory without triggering detector warnings
    or auto-persist. Missing / malformed state → ``None`` and the
    skills-root probe falls back to the default probe order.
    """
    try:
        from sdd_core.harness.loader import load_state
        data = load_state()
    except Exception:  # noqa: BLE001 — advisory probe only
        return None
    name = (data or {}).get("harness") if isinstance(data, dict) else None
    return name if isinstance(name, str) and name else None


def _skills_root() -> Path:
    """Resolve the IDE skills root, honouring ``SDD_SKILLS_ROOT``.

    Delegates to :func:`sdd_core.paths.find_skills_root` so the launch
    gate picks up env overrides and both ``.cursor/skills`` and
    ``.claude/skills`` layouts. Passes the active harness name so the
    launch envelope emits paths under the harness-native tree on
    dual-tree workspaces. Falls back to the ``__file__``-derived path
    when the cwd probe can't locate an IDE skills dir.
    """
    try:
        return _paths.find_skills_root(harness_name=_active_harness_name())
    except FileNotFoundError:
        return _FALLBACK_SKILLS_ROOT


@dataclass(frozen=True)
class Precondition:
    """A single precondition the gate enforces.

    ``gate_id_flag_accepted`` declares whether the target script's
    argparse accepts ``--gate-id``. The envelope generator consults
    this per-row flag before appending ``--gate-id``; default is
    ``False`` so new preconditions are safe-by-construction (scripts
    opt in explicitly once they wire the argument).
    """

    name: str
    script: str
    why_blocking: str
    shim_flags: str
    gate_id_flag_accepted: bool = False

    def next_action_command(
        self, *, category: str, target_name: str,
        project_path: str = "", gate_id: str = "",
    ) -> str:
        project = project_path or "."
        parts = [
            f".spec-workflow/sdd {self.script}",
            f"--category {category}",
            f"--target-name {target_name}",
            f"--workspace {project}",
        ]
        if self.shim_flags:
            parts.append(self.shim_flags)
        if gate_id and self.gate_id_flag_accepted:
            parts.append(f"--gate-id {gate_id}")
        return " ".join(parts).strip()

    def applies(self, *, category: str, scope: str, workflow_mode: str) -> bool:
        if self.name == "detect_doc_state":
            return category == "spec"
        return True

    def enforce_level(
        self, entries: "Iterable", *,
        category: str, target_name: str, project_path: str,
    ) -> str:
        return _decide_with_marker(entries, _WARN_SEEN_SCRIPT)

    def has_warn_seen_marker(self, entries: "Iterable") -> bool:
        return _has_marker(entries, _WARN_SEEN_SCRIPT)


@dataclass(frozen=True)
class Finding:
    """One gate finding (missing precondition or warn-seen marker).

    ``previously_warned_in_gate=True`` means the policy escalated a
    warn-seen marker to ``error`` within the current gate; consumers
    emit a Read + ack-reference-reads sequence instead of a bare Read
    directive.
    """

    severity: str
    name: str
    script: str
    why_blocking: str
    next_action_command: str
    previously_warned_in_gate: bool = False
    extra: dict = field(default_factory=dict)

    def to_payload(self) -> dict:
        payload = {
            "name": self.name,
            "script": self.script,
            "why_blocking": self.why_blocking,
            "next_action_command": self.next_action_command,
            "severity": self.severity,
        }
        if self.previously_warned_in_gate:
            payload["previously_warned_in_gate"] = True
        if self.extra:
            payload.update(self.extra)
        return payload


_GATE_NAMESPACE = "__gate__"


def _gate_key(*parts: str) -> str:
    return "/".join((_GATE_NAMESPACE, *parts))


_WARN_SEEN_SCRIPT = _gate_key("launch_preconditions.warn_seen")
_READ_WARN_SEEN_PREFIX = _gate_key("launch_preconditions.read_warn_seen") + "/"


def _read_warn_seen_marker_for(name: str) -> str:
    return _READ_WARN_SEEN_PREFIX + name


def _decide_with_marker(entries: "Iterable", marker: str) -> str:
    for entry in entries:
        if entry.script == marker:
            return "error"
    return "warn"


def _has_marker(entries: "Iterable", marker: str) -> bool:
    return any(entry.script == marker for entry in entries)


@dataclass(frozen=True)
class ReferenceReadPrecondition:
    """Precondition that demands a specific reference file was read.

    ``severity`` selects the enforcement level for a missing read:
    ``"required"`` uses the warn→error cutover; ``"advisory"`` keeps
    the finding at ``warn`` so the launch continues degraded.
    """

    name: str
    reference_rel_path: str
    why_blocking: str
    severity: str = "required"

    def _resolved_absolute(self) -> str:
        return os.path.abspath(str(_skills_root() / self.reference_rel_path))

    def absolute_path(self) -> str:
        """Resolved absolute path (same value used for the ledger id)."""
        return self._resolved_absolute()

    def expected_sha256(self) -> str:
        """Content hash of the reference file.

        Reuses :func:`reference_ledger.hash_file` so ledger integrity
        checks and launch-envelope emission share one hash function.
        Missing / unreadable file yields an empty string.
        """
        return reference_ledger.hash_file(self._resolved_absolute())

    @property
    def script(self) -> str:
        return reference_ledger.reference_read_script_id(self._resolved_absolute())

    def read_instruction(self) -> str:
        """Agent-facing ``Read <abs_path>`` directive for the reference file."""
        return f"Read {self._resolved_absolute()}"

    def next_action_command(
        self, *, category: str, target_name: str,
        project_path: str = "", gate_id: str = "",
    ) -> str:
        """Shell-runnable ``--phase ack-reference-reads`` recovery command."""
        return build_ack_reference_read_command(
            [self],
            category=category, target_name=target_name,
            project_path=project_path, gate_id=gate_id,
        ) or ""

    def applies(self, *, category: str, scope: str, workflow_mode: str) -> bool:
        return True

    def enforce_level(
        self, entries: "Iterable", *,
        category: str, target_name: str, project_path: str,
    ) -> str:
        if self.severity == "advisory":
            return "warn"
        return _decide_with_marker(entries, _read_warn_seen_marker_for(self.name))

    def has_warn_seen_marker(self, entries: "Iterable") -> bool:
        return _has_marker(entries, _read_warn_seen_marker_for(self.name))


def build_ack_reference_read_command(
    preconditions: "Iterable[ReferenceReadPrecondition]",
    *, category: str, target_name: str,
    project_path: str = "", gate_id: str = "",
    sha_resolver: "Callable[[ReferenceReadPrecondition], str] | None" = None,
) -> "str | None":
    """Emit the canonical ``--phase ack-reference-reads`` shim command.

    Handles the single-ref and batched forms uniformly by always building
    the ``--references name=<sha>,...`` argument — the phase handler
    accepts a one-entry list identically to a multi-entry one.

    ``sha_resolver`` defaults to ``expected_sha256()`` (ledger-write
    path); :func:`build_recovery_chain` injects a lambda that emits
    ``${NAME_SHA}`` so the chain defers the hash compute to the shell.
    Returns ``None`` when no precondition yields a non-empty SHA.
    """
    resolver = sha_resolver or (lambda p: p.expected_sha256())
    pairs: list[str] = []
    for pre in preconditions:
        sha = resolver(pre)
        if not sha:
            continue
        pairs.append(f"{pre.name}={sha}")
    if not pairs:
        return None
    project = project_path or "."
    return (
        f".spec-workflow/sdd review/pipeline-tick.py "
        f"--phase ack-reference-reads "
        f"--category {category} --target-name {target_name} "
        f"--workspace {project} --gate-id {gate_id or 'default'} "
        f"--references {','.join(pairs)}"
    )


# Workspace-scoped post-change-review marker — full lifecycle in
# `state-scope.md` § Reference-Ack Ledger.
POST_CHANGE_REVIEW_SCRIPT: str = _gate_key("post_change_review.acked")
_POST_CHANGE_REVIEW_SCRIPT_PREFIX = POST_CHANGE_REVIEW_SCRIPT + "/"


def post_change_review_script_id(gate_id: str = "") -> str:
    """Return the ledger ``script`` identifier for a gate acknowledgement.

    Returns the workspace-scoped constant
    :data:`POST_CHANGE_REVIEW_SCRIPT` regardless of ``gate_id``. The
    parameter is preserved as a thin compatibility wrapper for callers
    that pass it explicitly; new callers should use the constant
    directly.
    """
    return POST_CHANGE_REVIEW_SCRIPT


# Workspace-scoped per-gate-cycle ``presented`` marker. Distinct from
# the ack marker so a single ack survives across cycles while
# presentation re-fires once per cycle (keyed by ``gate_id``).
POST_CHANGE_REVIEW_PRESENTED_SCRIPT_PREFIX: str = (
    _gate_key("post_change_review.presented") + "/"
)


def post_change_review_presented_script_id(gate_id: str = "") -> str:
    """Return the per-gate ledger ``script`` id for the presented marker."""
    return f"{POST_CHANGE_REVIEW_PRESENTED_SCRIPT_PREFIX}{gate_id or 'default'}"


@dataclass(frozen=True)
class PostChangeReviewPrecondition:
    """Precondition demanding the agent presented the post-change-review prompt.

    Scoped to per-document + ``create`` workflow_mode launches. Resume /
    update flows skip the gate because the prompt was (or should have
    been) presented earlier in the session.

    ``gate_id`` lives on the enforcement context, not the dataclass, so
    a single instance serves every gate the caller might launch against
    — ``_precondition_script`` synthesises the gate-specific ledger key.
    """

    name: str = "post_change_review_presented"
    why_blocking: str = (
        "post-change-review prompt must be acknowledged before "
        "--phase launch enters the review gate"
    )

    def next_action_command(
        self, *, category: str, target_name: str,
        project_path: str = "", gate_id: str = "",
    ) -> str:
        project = project_path or "."
        return (
            f".spec-workflow/sdd review/pipeline-tick.py "
            f"--phase ack-post-change-review "
            f"--category {category} --target-name {target_name} "
            f"--workspace {project} --gate-id {gate_id or 'default'}"
        ).strip()

    def applies(self, *, category: str, scope: str, workflow_mode: str) -> bool:
        if category != "spec":
            return False
        return scope == SCOPE_PER_DOCUMENT and workflow_mode == "create"

    def enforce_level(
        self, entries: "Iterable", *,
        category: str, target_name: str, project_path: str,
    ) -> str:
        return "error"

    def has_warn_seen_marker(self, entries: "Iterable") -> bool:
        return False


# Advisory-echoed ledger keys — prefixed so auditors can grep a single
# namespace for every advisory banner the agent has echoed verbatim.
_ADVISORY_ECHOED_SCRIPT_PREFIX = _gate_key("advisory.echoed") + "/"


def advisory_echoed_script_id(advisory_name: str) -> str:
    """Return the ledger ``script`` identifier for an advisory echo."""
    return f"{_ADVISORY_ECHOED_SCRIPT_PREFIX}{advisory_name or 'default'}"


@dataclass(frozen=True)
class AdvisoryEchoPrecondition:
    """Precondition demanding the agent echoed an advisory banner verbatim.

    Paired with :class:`sdd_core.advisories.Advisory` entries whose
    ``user_echo_required`` resolves to ``True``. The gate appends
    ``__gate__/advisory.echoed/<name>`` to the reference ledger after
    the ``--phase ack-advisories`` shim validates the echoed hash.
    """

    advisory_name: str
    why_blocking: str = (
        "advisory banner must be echoed verbatim before --phase launch"
    )

    @property
    def name(self) -> str:
        return f"advisory_echoed_{self.advisory_name}"

    @property
    def script(self) -> str:
        return advisory_echoed_script_id(self.advisory_name)

    def next_action_command(
        self, *, category: str, target_name: str,
        project_path: str = "", gate_id: str = "",
    ) -> str:
        project = project_path or "."
        return (
            f".spec-workflow/sdd review/pipeline-tick.py "
            f"--phase ack-advisories "
            f"--category {category} --target-name {target_name} "
            f"--workspace {project} --gate-id {gate_id or 'default'} "
            f"--advisory-name {self.advisory_name}"
        ).strip()

    def applies(self, *, category: str, scope: str, workflow_mode: str) -> bool:
        return True

    def enforce_level(
        self, entries: "Iterable", *,
        category: str, target_name: str, project_path: str,
    ) -> str:
        return "warn"

    def has_warn_seen_marker(self, entries: "Iterable") -> bool:
        return False


AnyPrecondition = Union[
    Precondition,
    ReferenceReadPrecondition,
    PostChangeReviewPrecondition,
    AdvisoryEchoPrecondition,
]

PreconditionUnion = AnyPrecondition


@runtime_checkable
class PreconditionProtocol(Protocol):
    """Structural protocol satisfied by all precondition dataclasses."""

    @property
    def name(self) -> str: ...
    @property
    def why_blocking(self) -> str: ...
