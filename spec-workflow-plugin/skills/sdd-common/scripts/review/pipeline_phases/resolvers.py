"""Path and artifact resolution for review pipeline launches."""
from __future__ import annotations

import pathlib

from sdd_core import output

from . import get_templates, VERIFICATION_PATHS


def resolve_template(review_skill: str) -> str:
    """Look up and return the prompt template for a review skill, or exit with error."""
    templates = get_templates()
    if review_skill not in templates:
        available = ", ".join(sorted(templates))
        output.error(
            f"No template for review skill '{review_skill}'",
            hint=f"Available: {available}",
        )
    return templates[review_skill]


def resolve_verification_file(category: str, target_name: str) -> str:
    """Resolve the verification file path for a review category."""
    verification_pattern = VERIFICATION_PATHS.get(category, VERIFICATION_PATHS["spec"])
    return verification_pattern.format(target_name=target_name)


def resolve_staging_path(
    category: str, target_name: str, project_path: str = "",
    *, gate_id: str = "",
) -> str:
    """Resolve the assessment staging JSON path.

    Per-gate addressable: with a ``gate_id`` the path becomes
    ``.sdd-state/review-assessment-staging-<gate_id>.json`` so multiple
    concurrent gates under the same doc target stage independently.
    Without one (entry-style phases or ad-hoc tooling) the legacy
    ``.sdd-state/review-assessment-staging.json`` shape is preserved.

    ``project_path`` threads the workspace root through so cross-repo
    sub-agents write staging files into the target repo, not the
    coordinator.

    The canonical ``.sdd-state/`` directory is created on demand so
    the sub-agent can write without extra guard logic.
    ``ensure_state_dir`` tolerates failures silently — writers surface
    any real permission errors at their own call site.
    """
    from sdd_core import transient_state
    from sdd_core.output import _dry_run_active

    canonical = transient_state.state_path(
        category, target_name,
        transient_state.staging_filename(gate_id),
        project_path,
    )
    # Pre-create the canonical state dir so the sub-agent's subsequent
    # write lands cleanly. Skipped inside a pipeline dry-run because
    # dry-runs must leave the filesystem untouched.
    if not _dry_run_active():
        transient_state.ensure_state_dir(
            category, target_name, project_path,
        )
    return canonical


def resolve_staging_paths_for_read(
    category: str, target_name: str, project_path: str = "",
    *, gate_id: str = "",
) -> list[str]:
    """Return staging paths a reader should consult, preferring per-gate.

    Transition-cycle helper: returns ``[per_gate_path, legacy_path]``
    when a ``gate_id`` is supplied so a reader can fall back to the
    legacy filename if the per-gate file is absent. Without ``gate_id``
    only the legacy path is returned. Writers always emit the per-gate
    shape (via :func:`resolve_staging_path`); the legacy file is cleaned
    up by the ``discard`` phase or by approval-completion cleanup.
    """
    from sdd_core import transient_state

    primary = transient_state.state_path(
        category, target_name,
        transient_state.staging_filename(gate_id),
        project_path,
    )
    if not gate_id:
        return [primary]
    legacy = transient_state.state_path(
        category, target_name, transient_state.STAGING_FILENAME,
        project_path,
    )
    return [primary, legacy]


def resolve_prd_file_path(target_name: str, project_path: str) -> str | None:
    """Pre-resolve the PRD file path for a spec or discovery project.

    Resolution order (delegates to ``discovery.shared``):

    1. Back-link lookup: scan every ``discovery/*/manifest.json`` for a
       project whose ``specs[].name`` matches ``target_name``; return
       the first PRD artifact attached to it.
    2. Same-name fallback: load ``discovery/{target_name}/manifest.json``
       directly — keeps discovery-category launches working when the
       caller passes the discovery project name rather than a spec name.

    Returns ``None`` when neither path yields a PRD.
    """
    from discovery.shared import find_prd_files, find_prd_for_spec

    project = pathlib.Path(project_path)

    backlinked = find_prd_for_spec(target_name, project)
    if backlinked:
        return backlinked

    # Flat layout observed on discovery projects created before the
    # per-feature hierarchy landed — scan the single top-level folder
    # as a fallback.
    flat_dir = project / ".spec-workflow" / "discovery" / target_name
    if flat_dir.is_dir():
        prd_files = find_prd_files(flat_dir)
        if prd_files:
            return f".spec-workflow/discovery/{target_name}/{prd_files[0]}"

    return None
