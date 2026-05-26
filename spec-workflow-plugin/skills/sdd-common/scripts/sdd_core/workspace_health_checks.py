"""Single seam for workspace pre-flight health checks and autofix.

The CLI shim (``workspace/check-health.py``) routes through
:func:`run_all_checks` so each check is independently unit-testable
and the registry order is the source of truth for execution sequence.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

from . import output
from .paths import WORKFLOW_DIR, TEMPLATE_SUFFIX, templates_dir
from .shim import ensure_shim
from .template_resolution import (
    ALL_TEMPLATE_TYPES,
    get_reference_dir,
    list_templates,
)
from .template_sync import (
    SyncResult,
    hash_template,
    sync_defaults_to_workspace,
    sync_user_templates_readme,
)
from .templates import validate_template


__all__ = [
    "CheckContext",
    "CheckResult",
    "CHECKS",
    "REQUIRED_DIRS",
    "register_check",
    "run_all_checks",
    "run_autofix_and_reverify",
    "resolution_summary",
]


@dataclass
class CheckResult:
    """Uniform return type for all repair functions."""

    repaired: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)


class CheckContext:
    """Shared context passed to every registered check.

    Provides a cached :meth:`sync_defaults` so that multiple checks reuse
    the same sync invocation instead of calling it twice.
    """

    def __init__(
        self,
        root: Path,
        auto_fix: bool,
        dry_run: bool = False,
        *,
        force_template_repair: bool = False,
    ):
        self.root = root
        self.auto_fix = auto_fix
        self.dry_run = dry_run
        self.force_template_repair = force_template_repair
        self._sync_result: SyncResult | None = None

    def sync_defaults(self) -> SyncResult:
        if self._sync_result is None:
            self._sync_result = sync_defaults_to_workspace(self.root)
        return self._sync_result

    @property
    def sync_result(self) -> SyncResult | None:
        """Read-only view of the cached sync result (``None`` before first sync)."""
        return self._sync_result


CHECKS: list[Callable[[CheckContext], dict]] = []


def register_check(fn: Callable[[CheckContext], dict]) -> Callable[[CheckContext], dict]:
    """Register a health check function.

    Each check receives a :class:`CheckContext` and returns a dict with at
    least ``name`` and ``status`` (``pass`` / ``fail`` / ``warn``).
    When *auto_fix* is True the check should attempt repair and include
    a ``repaired`` key describing what was fixed.
    """
    CHECKS.append(fn)
    return fn


def _check_with_autofix(
    check_id: str,
    detect_fn: Callable[[CheckContext], list],
    repair_fn: Callable[[CheckContext, list], CheckResult | list[str]],
    ctx: CheckContext,
    *,
    verify_fn: Callable[[CheckContext], list] | None = None,
    fail_status: str = "fail",
) -> dict:
    """Run a detect → repair → re-verify cycle.

    *detect_fn(ctx)* returns a list of issues (empty = healthy).
    *repair_fn(ctx, issues)* attempts fixes and returns either a
    :class:`CheckResult` (full repair envelope) or a list of repaired
    item labels (shorthand for simple "these N were fixed" outcomes).
    *verify_fn(ctx)* re-detects after repair (defaults to *detect_fn*).
    Exceptions from *repair_fn* are captured with detail in the response.

    When ``ctx.dry_run`` is True, detection runs but repair is skipped.
    """
    issues = detect_fn(ctx)
    if not issues:
        return {"name": check_id, "status": "pass"}

    if ctx.dry_run:
        return {
            "name": check_id,
            "status": fail_status,
            "issues": issues,
            "would_repair": True,
        }

    if ctx.auto_fix:
        try:
            result = repair_fn(ctx, issues)
        except (OSError, ValueError, json.JSONDecodeError) as e:
            return {
                "name": check_id,
                "status": "fail",
                "detail": f"Auto-fix failed: {e}",
                "issues": issues,
            }

        if isinstance(result, CheckResult):
            repaired = result.repaired
            warnings = result.warnings
        else:
            repaired = result
            warnings = []

        still_failing = (verify_fn or detect_fn)(ctx)
        base: dict = {"name": check_id, "repaired": repaired}
        if warnings:
            base["warnings"] = warnings
        if still_failing:
            base["status"] = fail_status
            base["still_failing"] = still_failing
        else:
            base["status"] = "pass"
        return base

    return {"name": check_id, "status": fail_status, "issues": issues}


REQUIRED_DIRS = [
    "templates",
    "user-templates",
    "approvals",
    "specs",
    "steering",
    "archive/specs",
]


@register_check
def check_required_dirs(ctx: CheckContext) -> dict:
    wf = ctx.root / WORKFLOW_DIR

    def detect(c: CheckContext) -> list[str]:
        return [d for d in REQUIRED_DIRS if not (wf / d).is_dir()]

    def repair(c: CheckContext, missing: list[str]) -> list[str]:
        for d in missing:
            try:
                (wf / d).mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
        return [d for d in missing if (wf / d).is_dir()]

    return _check_with_autofix("required_dirs", detect, repair, ctx)


@register_check
def check_deferred_tools_preload(ctx: CheckContext) -> dict:
    """Advisory: agent has not yet loaded the host's deferred-tool set.

    Surfaces the preload via the advisories pipeline so the agent sees
    ``— advisories: deferred_tools_preload`` on a cold start. Returns
    ``pass`` on hosts with no deferred tools (Cursor) or once
    :func:`record_deferred_tool_preload` has logged a matching preload.
    """
    from .command_templates import build_resolve_advisory_command
    from .harness import (
        HarnessContradictionError,
        PROBE_HARNESS_RESET_COMMAND,
        try_load_adapter,
    )
    from .transient_state import (
        get_deferred_tool_preload,
        preload_advisory_detail,
        preload_tool_search_command,
    )

    try:
        adapter = try_load_adapter(str(ctx.root))
    except HarnessContradictionError as exc:
        # Surface the contradiction through the standard advisory
        # pipeline rather than burying it as `status: pass`. The
        # dedicated ``check_harness_state_env_consistency`` check
        # below also fires with auto-fix; both branches emit the same
        # ``next_action_command`` so ``collect_warn`` dedups on the
        # shared (name, command) pair when detect-only runs.
        return {
            "name": "harness_state_env_consistency",
            "status": "warn",
            "detail": exc.hint or exc.message,
            "advisory_kind": exc.message,
            "next_action_command": PROBE_HARNESS_RESET_COMMAND,
        }
    tools = tuple(adapter.deferred_tools())
    if not tools:
        return {"name": "deferred_tools_preload", "status": "pass"}
    # Surface only the missing subset so the advisory shrinks as the
    # agent preloads each tool instead of repeating the full set.
    recorded = get_deferred_tool_preload(str(ctx.root), adapter.name)
    missing = tuple(t for t in tools if t not in recorded)
    if not missing:
        return {"name": "deferred_tools_preload", "status": "pass"}
    # ``next_action_command`` is the canonical clear-action — running
    # ``resolve-advisory.py`` records that the prerequisite has been
    # satisfied. ``prerequisite_action_command`` carries the literal
    # ``ToolSearch select:...`` the agent must already have executed
    # before the resolve call lands.
    return {
        "name": "deferred_tools_preload",
        "status": "warn",
        "detail": preload_advisory_detail(missing),
        "next_action_command": build_resolve_advisory_command(
            name="deferred_tools_preload",
            workspace_path=str(ctx.root),
        ),
        "prerequisite_action_command": preload_tool_search_command(missing),
        "prerequisite_required": True,
    }


@register_check
def check_harness_state_present(ctx: CheckContext) -> dict:
    """Ensure ``.sdd-state/harness.json`` is persisted.

    Auto-fix delegates to :func:`sdd_core.harness.load_adapter` so the
    loader's own self-heal path picks whichever detector (env marker or
    safe default) wins for this run — one code path, one warning
    surface.
    """
    from .harness.loader import harness_state_path

    def detect(c: CheckContext) -> list[str]:
        path = harness_state_path(str(c.root))
        return [] if Path(path).is_file() else [path]

    def repair(c: CheckContext, missing: list[str]) -> list[str]:
        # Health-check is the explicit persist surface when no confirmed
        # signal exists; the safe-default loader branch never writes.
        from .harness import load_adapter
        from .harness.loader import persist_state

        adapter = load_adapter(str(c.root))
        persist_state(adapter.name, str(c.root))
        path = harness_state_path(str(c.root))
        return [path] if Path(path).is_file() else []

    return _check_with_autofix(
        "harness_state_present", detect, repair, ctx,
    )


@register_check
def check_harness_state_env_consistency(ctx: CheckContext) -> dict:
    """Detect a stale ``harness.json`` whose env markers disagree.

    Isolated check so callers on Cursor (no deferred tools) still see
    the advisory that ``check_deferred_tools_preload`` would otherwise
    catch. Shares :func:`sdd_core.harness.try_load_adapter` with the
    pipeline so severity parity is structural.
    """
    from .harness import (
        HarnessContradictionError,
        PROBE_HARNESS_RESET_COMMAND,
        try_load_adapter,
    )

    def detect(c: CheckContext) -> list[str]:
        try:
            try_load_adapter(str(c.root))
        except HarnessContradictionError as exc:
            return [exc.message]
        return []

    def repair(c: CheckContext, _issues: list[str]) -> CheckResult:
        # Idempotent auto-repair: clear the stale state file and let
        # the loader re-resolve through the shared detector registry.
        # Routes through ``load_adapter`` + ``persist_state`` so the
        # repair path uses the same single writer as every other
        # state-file mutation.
        from .harness import load_adapter
        from .harness.loader import harness_state_path, persist_state

        state_path = Path(harness_state_path(str(c.root)))
        try:
            state_path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            return CheckResult(
                repaired=[],
                warnings=[f"Failed to clear {state_path}: {exc}"],
            )

        adapter = load_adapter(str(c.root))
        persist_state(adapter.name, str(c.root))
        return CheckResult(repaired=["harness.json"])

    result = _check_with_autofix(
        "harness_state_env_consistency", detect, repair, ctx,
        fail_status="warn",
    )
    # Emit the same recovery command the preload check surfaces so
    # ``collect_warn`` dedups on the (name, next_action_command) pair.
    if result.get("status") == "warn":
        result.setdefault("next_action_command", PROBE_HARNESS_RESET_COMMAND)
    return result


@register_check
def check_default_templates_complete(ctx: CheckContext) -> dict:
    tpl_dir = templates_dir(ctx.root, user=False)

    def detect(c: CheckContext) -> list[str]:
        return [
            dt
            for dt in ALL_TEMPLATE_TYPES
            if not (tpl_dir / f"{dt}{TEMPLATE_SUFFIX}").is_file()
        ]

    def repair(c: CheckContext, missing: list[str]) -> CheckResult:
        """Copy only the specific missing templates, not all."""
        ref_dir = get_reference_dir()
        tpl_dir.mkdir(parents=True, exist_ok=True)
        repaired: list[str] = []
        warnings: list[str] = []
        for dt in missing:
            src = ref_dir / f"{dt}{TEMPLATE_SUFFIX}"
            dst = tpl_dir / src.name
            if src.is_file():
                try:
                    shutil.copy2(str(src), str(dst))
                    repaired.append(dt)
                except OSError as e:
                    warnings.append(f"Failed to copy {src.name}: {e}")
        return CheckResult(repaired=repaired, warnings=warnings)

    return _check_with_autofix("default_templates_complete", detect, repair, ctx)


@register_check
def check_template_content_hash(ctx: CheckContext) -> dict:
    ref_dir = get_reference_dir()
    if not ref_dir.is_dir():
        return {
            "name": "template_content_hash",
            "status": "warn",
            "detail": f"Reference directory not found: {ref_dir}",
        }

    tpl_dir = templates_dir(ctx.root, user=False)
    user_dir = templates_dir(ctx.root, user=True)

    def detect(c: CheckContext) -> list[dict]:
        drifted: list[dict] = []
        for dt in ALL_TEMPLATE_TYPES:
            fn = f"{dt}{TEMPLATE_SUFFIX}"
            rp, wp = ref_dir / fn, tpl_dir / fn
            if not rp.is_file() or not wp.is_file():
                continue
            rh, wh = hash_template(rp), hash_template(wp)
            if rh != wh:
                drifted.append(
                    {
                        "type": dt,
                        "reference_hash": rh,
                        "workspace_hash": wh,
                        "masked_by_user": (user_dir / fn).is_file(),
                    }
                )
        return drifted

    def repair(c: CheckContext, drifted: list[dict]) -> CheckResult:
        c.sync_defaults()
        repaired: list[str] = []
        warnings: list[str] = []
        sync_result = c.sync_result
        if sync_result and sync_result.warnings:
            warnings.extend(sync_result.warnings)
        for entry in drifted:
            fn = f"{entry['type']}{TEMPLATE_SUFFIX}"
            rp, wp = ref_dir / fn, tpl_dir / fn
            if rp.is_file() and wp.is_file() and hash_template(rp) == hash_template(wp):
                repaired.append(entry["type"])
        return CheckResult(repaired=repaired, warnings=warnings)

    return _check_with_autofix(
        "template_content_hash", detect, repair, ctx, fail_status="warn"
    )


@register_check
def check_user_template_health(ctx: CheckContext) -> dict:
    """Validate user templates and detect staleness. Never auto-modifies user files."""
    user_dir = templates_dir(ctx.root, user=True)
    default_dir = templates_dir(ctx.root, user=False)
    issues: list[dict] = []

    for doc_type in ALL_TEMPLATE_TYPES:
        filename = f"{doc_type}{TEMPLATE_SUFFIX}"
        user_path = user_dir / filename
        if not user_path.is_file():
            continue

        entry: dict = {"type": doc_type, "file": filename}

        vresult = validate_template(user_path, doc_type)
        entry["valid"] = vresult.valid
        if vresult.errors:
            entry["errors"] = vresult.errors
        if vresult.warnings:
            entry["warnings"] = vresult.warnings

        default_path = default_dir / filename
        if default_path.is_file():
            user_hash = hash_template(user_path)
            default_hash = hash_template(default_path)
            entry["stale"] = user_hash == default_hash
            if entry["stale"]:
                entry["detail"] = (
                    "User template is identical to default — redundant override"
                )
        else:
            entry["default_missing"] = True
            entry["detail"] = (
                "Default template missing — fallback broken if user resets"
            )

        issues.append(entry)

    if not issues:
        return {"name": "user_template_health", "status": "pass", "overrides": []}

    has_errors = any(not e.get("valid", True) for e in issues)
    has_warnings = any(
        e.get("stale") or e.get("default_missing") or e.get("warnings")
        for e in issues
    )
    status = "warn" if (has_errors or has_warnings) else "pass"
    return {"name": "user_template_health", "status": status, "overrides": issues}


@register_check
def check_user_templates_readme(ctx: CheckContext) -> dict:
    readme = ctx.root / WORKFLOW_DIR / "user-templates" / "README.md"

    def detect(c: CheckContext) -> list[str]:
        return [] if readme.is_file() else ["README.md"]

    def repair(c: CheckContext, issues: list[str]) -> list[str]:
        created: list[str] = []
        skipped: list[str] = []
        sync_user_templates_readme(c.root / WORKFLOW_DIR, created, skipped)
        return created

    return _check_with_autofix("user_templates_readme", detect, repair, ctx)


@register_check
def check_sdd_shim_present(ctx: CheckContext) -> dict:
    shim_path = ctx.root / WORKFLOW_DIR / "sdd"
    if shim_path.is_file():
        from .shim import canonical_content

        if shim_path.read_text() == canonical_content():
            return {"name": "sdd_shim_present", "status": "pass"}
        if ctx.auto_fix:
            action = ensure_shim(ctx.root / WORKFLOW_DIR)
            return {"name": "sdd_shim_present", "status": "pass", "repaired": action}
        return {
            "name": "sdd_shim_present",
            "status": "warn",
            "detail": "Shim content outdated",
            "hint": (
                "Run `.spec-workflow/sdd workspace/ensure-healthy.py "
                "--auto-fix` to regenerate the shim."
            ),
        }

    if ctx.auto_fix:
        try:
            action = ensure_shim(ctx.root / WORKFLOW_DIR)
            if (ctx.root / WORKFLOW_DIR / "sdd").is_file():
                return {
                    "name": "sdd_shim_present",
                    "status": "pass",
                    "repaired": action,
                }
        except OSError as e:
            return {"name": "sdd_shim_present", "status": "fail", "detail": str(e)}

    return {"name": "sdd_shim_present", "status": "fail", "detail": "Missing sdd shim"}


@register_check
def check_prompt_registry_option_bounds(ctx: CheckContext) -> dict:
    """Surface every registry entry outside ``[MIN, MAX]`` as a
    pre-flight advisory. Advisory-only: the registry is code-owned,
    so auto-repair would mask real authoring mistakes.

    Paired with ``sdd_core.prompts._enforce_option_bounds`` which is
    the render-time safety net. Both cite the same constants; the
    pre-flight check is the earlier signal (once per session), the
    renderer advisory is the last-chance signal (per render).
    """
    from .prompts import (
        MAX_PROMPT_OPTIONS, MIN_PROMPT_OPTIONS, load_registry,
    )

    def detect(_c: CheckContext) -> list[str]:
        issues: list[str] = []
        for prompt_type, defn in load_registry().get("prompts", {}).items():
            questions = defn.get("questions") or []
            if not questions:
                continue
            count = len(questions[0].get("options") or [])
            if count < MIN_PROMPT_OPTIONS or count > MAX_PROMPT_OPTIONS:
                issues.append(
                    f"{prompt_type}: {count} options "
                    f"(bounds [{MIN_PROMPT_OPTIONS}, {MAX_PROMPT_OPTIONS}])"
                )
        return issues

    def repair(_c: CheckContext, issues: list[str]) -> CheckResult:
        return CheckResult(repaired=[], warnings=issues)

    return _check_with_autofix(
        "prompt_registry_option_bounds", detect, repair, ctx,
        fail_status="warn",
    )


@register_check
def check_stale_review_staging_files(ctx: CheckContext) -> dict:
    """Delete any pre-existing ``review-assessment-staging.json`` at pre-flight.

    The staging file is written fresh on every review run; any
    residue is leftover from an aborted session or a prior
    ``needs_revision`` loop. Removing it at session start guarantees
    the next ``Write`` never collides with the Write-tool
    precondition. Missing files are a silent no-op.
    """
    from .paths import iter_all_doc_dirs
    from .transient_state import (
        STATE_DIR_NAME,
        iter_staging_filenames,
    )

    def _stale_paths(root: Path) -> list[Path]:
        # Per-gate staging files share the same prefix as the legacy
        # filename — :func:`iter_staging_filenames` enumerates both
        # shapes so a workflow that produced ``review-assessment-staging-
        # <gate_id>.json`` siblings is also cleaned at pre-flight.
        paths: list[Path] = []
        for doc_dir in iter_all_doc_dirs(root):
            state_dir = doc_dir / STATE_DIR_NAME
            for name in iter_staging_filenames(str(state_dir)):
                paths.append(state_dir / name)
        return paths

    def detect(c: CheckContext) -> list[str]:
        root = Path(c.root)
        return [str(p.relative_to(root)) for p in _stale_paths(root)]

    def repair(c: CheckContext, issues: list[str]) -> CheckResult:
        root = Path(c.root)
        deleted: list[str] = []
        for rel in issues:
            target = root / rel
            try:
                target.unlink()
                deleted.append(rel)
            except FileNotFoundError:
                continue
            except OSError:
                continue
        return CheckResult(repaired=deleted)

    return _check_with_autofix(
        "stale_review_staging_files", detect, repair, ctx,
    )


def _compute_top_level_digest(registry: dict) -> str:
    """Recompute the top-level ``contentHash`` per ``_build_registry``.

    Mirrors ``scripts/lib/generate_registry.py::_build_registry`` byte
    for byte so an in-tree drift surfaces here on the next read.
    """
    import hashlib as _hashlib

    blob = (
        json.dumps(registry.get("skills") or [], separators=(",", ":"))
        + json.dumps(registry.get("supportDirs") or [], separators=(",", ":"))
    )
    return _hashlib.sha256(blob.encode()).hexdigest()


@dataclass(frozen=True)
class _ReviewTarget:
    category: str
    target_name: str
    doc_dir: Path
    doc_filenames: tuple[str, ...]


_SPEC_DOC_FILES: tuple[str, ...] = (
    "requirements.md", "design.md", "tasks.md", "ui-design.md",
)
_STEERING_DOC_FILES: tuple[str, ...] = ("product.md", "tech.md", "structure.md")
_DISCOVERY_DOC_FILES: tuple[str, ...] = ("prd.md",)


def _approval_dir(root: Path, category: str, target_name: str) -> Path:
    return root / WORKFLOW_DIR / "approvals" / category / target_name


def _iter_review_targets(root: Path) -> Iterable[_ReviewTarget]:
    spec_root = root / WORKFLOW_DIR / "specs"
    if spec_root.is_dir():
        for spec_dir in sorted(p for p in spec_root.iterdir() if p.is_dir()):
            yield _ReviewTarget(
                category="spec",
                target_name=spec_dir.name,
                doc_dir=spec_dir,
                doc_filenames=_SPEC_DOC_FILES,
            )

    steering_dir = root / WORKFLOW_DIR / "steering"
    if steering_dir.is_dir():
        yield _ReviewTarget(
            category="steering",
            target_name="steering",
            doc_dir=steering_dir,
            doc_filenames=_STEERING_DOC_FILES,
        )

    discovery_root = root / WORKFLOW_DIR / "discovery"
    if discovery_root.is_dir():
        for project_dir in sorted(p for p in discovery_root.iterdir() if p.is_dir()):
            yield _ReviewTarget(
                category="discovery",
                target_name=project_dir.name,
                doc_dir=project_dir,
                doc_filenames=_DISCOVERY_DOC_FILES,
            )


def _latest_approval_mtime(
    root: Path, category: str, target_name: str,
) -> "float | None":
    """Return the newest mtime under the target's approval directory."""
    approval_dir = _approval_dir(root, category, target_name)
    if not approval_dir.is_dir():
        return None
    mtimes = [p.stat().st_mtime for p in approval_dir.glob("*.json") if p.is_file()]
    return max(mtimes) if mtimes else None


def _doc_mtimes(target: _ReviewTarget) -> dict[str, float]:
    """Return ``{doc_filename: mtime}`` for each review doc on disk."""
    out: dict[str, float] = {}
    for doc in target.doc_filenames:
        path = target.doc_dir / doc
        if path.is_file():
            out[doc] = path.stat().st_mtime
    return out


@register_check
def check_unstaged_spec_edits_without_approval(ctx: CheckContext) -> dict:
    """Surface spec-doc edits that postdate the latest approval JSON.

    Fires only for specs that already have at least one approval — a
    fresh spec with no approvals yet is the *creation-mode* case, not
    the *update-mode* case the advisory targets.
    """
    from .command_templates import build_pipeline_tick_update_launch_command

    root = Path(ctx.root)
    issues: list[dict] = []
    for target in _iter_review_targets(root):
        approval_mtime = _latest_approval_mtime(
            root, target.category, target.target_name,
        )
        if approval_mtime is None:
            continue
        doc_mtimes = _doc_mtimes(target)
        unstaged = sorted(
            d for d, m in doc_mtimes.items() if m > approval_mtime
        )
        if not unstaged:
            continue
        issues.append({
            "category": target.category,
            "target_name": target.target_name,
            "docs": unstaged,
            "approval_mtime": approval_mtime,
        })

    if not issues:
        return {"name": "unstaged_spec_edits_without_approval", "status": "pass"}

    first = issues[0]
    next_cmd = build_pipeline_tick_update_launch_command(
        category=first["category"],
        target_name=first["target_name"],
        doc_list=",".join(first["docs"]),
        workflow_mode="update",
    )
    return {
        "name": "unstaged_spec_edits_without_approval",
        "status": "warn",
        "detail": (
            f"{first['category'].title()} edits on disk newer than latest approval — "
            "run update-mode launch envelope to bind the gate sequence."
        ),
        "next_action_command": next_cmd,
        "extra": {"targets": issues},
    }


_DRIFT_ORIGIN_PRIOR = "prior_session"
_DRIFT_ORIGIN_CURRENT = "current_session"


def _classify_drift_origin(
    target: "_ReviewTarget",
    drifted_docs: Iterable[str],
    session_epoch_ms: "int | None",
) -> str:
    """Return ``prior_session`` when every drifted doc's mtime predates the
    active session's start, otherwise ``current_session``.

    No session file (``session_epoch_ms is None``) is treated as
    ``current_session`` so the legacy callers that never minted a
    token retain the original "doc is stale" semantics. The session
    epoch is in milliseconds; doc mtimes are seconds, hence the
    1000x conversion.
    """
    if session_epoch_ms is None:
        return _DRIFT_ORIGIN_CURRENT
    threshold = session_epoch_ms / 1000.0
    for doc in drifted_docs:
        path = target.doc_dir / doc
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return _DRIFT_ORIGIN_CURRENT
        if mtime >= threshold:
            return _DRIFT_ORIGIN_CURRENT
    return _DRIFT_ORIGIN_PRIOR


@register_check
def check_review_quality_stale(ctx: CheckContext) -> dict:
    """Surface specs whose ``review-quality.json`` is out of sync with
    the spec docs.

    Drift detection routes through
    :func:`review_quality.staleness.is_review_artifact_stale` — the
    canonical primitive that prefers content-hash comparison and
    falls back to per-doc timestamp for legacy artifacts.

    Each drifted target carries a ``drift_origin`` field:
    ``prior_session`` when every drifted doc's mtime predates the
    active session's start, ``current_session`` otherwise. The
    aggregate advisory severity downgrades to ``info`` only when *every*
    target is prior-session — drift introduced inside the live session
    keeps the existing surface text.
    """
    from .command_templates import build_review_update_quality_command
    from .session import current_session_epoch_ms
    from review_quality.staleness import is_review_artifact_stale

    root = Path(ctx.root)
    session_epoch_ms = current_session_epoch_ms(root)
    issues: list[dict] = []
    for target in _iter_review_targets(root):
        artifact_path = target.doc_dir / "review-quality.json"
        if not artifact_path.is_file():
            continue
        try:
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        result = is_review_artifact_stale(
            artifact, target.doc_dir, target.doc_filenames,
        )
        if not result.drifted:
            continue
        drift_origin = _classify_drift_origin(
            target, result.drifted_docs, session_epoch_ms,
        )
        issues.append({
            "category": target.category,
            "target_name": target.target_name,
            "drifted_docs": list(result.drifted_docs),
            "kind": result.kind,
            "detail": result.detail,
            "drift_origin": drift_origin,
        })

    if not issues:
        return {"name": "review_quality_stale", "status": "pass"}

    first = issues[0]
    next_cmd = build_review_update_quality_command(
        target=first["target_name"],
        category=first["category"],
    )
    all_prior = all(
        issue.get("drift_origin") == _DRIFT_ORIGIN_PRIOR for issue in issues
    )
    if all_prior:
        detail = (
            "review-quality.json predates the active session — "
            "re-run review/update-quality.py to refresh the artifact."
        )
    else:
        detail = (
            "review-quality.json out of sync with the docs — "
            "re-run review/update-quality.py to refresh the artifact."
        )
    return {
        "name": "review_quality_stale",
        "status": "info",
        "detail": detail,
        "next_action_command": next_cmd,
        "extra": {
            "targets": issues,
            "drift_origin": first["drift_origin"],
        },
    }


_PHASE_SIBLING_PREFIX = "review-quality-"
_PHASE_SIBLING_SUFFIX = ".json"


def _list_phase_siblings(spec_dir: Path) -> list[str]:
    """Return ``review-quality-{phase}.json`` filenames under *spec_dir*.

    Only matches the legacy per-phase shape; the canonical
    ``review-quality.json`` (no phase suffix) is excluded so the check
    never fires on a healthy single-artifact spec.
    """
    if not spec_dir.is_dir():
        return []
    out: list[str] = []
    for entry in sorted(spec_dir.iterdir()):
        if not entry.is_file():
            continue
        name = entry.name
        if not name.startswith(_PHASE_SIBLING_PREFIX):
            continue
        if not name.endswith(_PHASE_SIBLING_SUFFIX):
            continue
        # Reject the canonical filename (which would slice to "" between
        # the prefix and suffix) — only true ``-<phase>`` siblings count.
        middle = name[len(_PHASE_SIBLING_PREFIX):-len(_PHASE_SIBLING_SUFFIX)]
        if not middle:
            continue
        out.append(name)
    return out


@register_check
def check_orphan_review_quality_siblings(ctx: CheckContext) -> dict:
    """Surface specs that still carry legacy per-phase review-quality siblings.

    The canonical artifact is a single ``review-quality.json`` per spec
    with the ``phase_history`` block carrying per-phase approvals. Specs
    that retain legacy ``review-quality-{phase}.json`` files predate the
    fold and need :file:`util/migrate-review-quality.py` to land them
    in the canonical schema. Surfaces as ``warn`` with an explicit
    ``next_action_command`` so the agent has a literal recovery shim.
    """
    from .command_templates import build_migrate_review_quality_command

    root = Path(ctx.root)
    targets: list[dict] = []
    for target in _iter_review_targets(root):
        if target.category != "spec":
            continue
        siblings = _list_phase_siblings(target.doc_dir)
        if not siblings:
            continue
        targets.append({
            "category": target.category,
            "target_name": target.target_name,
            "siblings": siblings,
        })

    if not targets:
        return {"name": "orphan_review_quality_siblings", "status": "pass"}

    first = targets[0]
    next_cmd = build_migrate_review_quality_command(
        spec=first["target_name"],
    )
    return {
        "name": "orphan_review_quality_siblings",
        "status": "warn",
        "detail": (
            f"{len(targets)} spec(s) carry legacy "
            "review-quality-{phase}.json siblings — fold them into the "
            "canonical artifact via util/migrate-review-quality.py."
        ),
        "next_action_command": next_cmd,
        "extra": {"targets": targets},
    }


@register_check
def check_skills_registry_hash_drift(ctx: CheckContext) -> dict:
    """Warn when an installed skill's content hash drifts from the registry.

    Recomputes ``hash_skill_dir(skill_dir)`` for every skill listed in
    ``skills-registry.json`` and compares it to the recorded
    ``contentHash``. Also recomputes the top-level ``contentHash``
    using the same byte-projection as ``_build_registry`` so a
    consumer can distinguish "one skill drifted" from "the entire
    registry was regenerated against a different tree". Mismatch
    surfaces as a single ``warn`` advisory with
    ``action_required=False`` so the auto-fix loop never tries to
    repair it — registry regeneration is an out-of-band ``npm run
    generate-registry`` step. Identical content returns ``pass``.
    """
    from . import paths as _paths
    from .skill_links import hash_skill_dir

    try:
        skills_root = _paths.find_skills_root(ctx.root)
    except FileNotFoundError:
        return {"name": "skills_registry_hash_drift", "status": "pass"}

    registry_path = _paths.common_registry_path(skills_root)
    if not registry_path.is_file():
        return {"name": "skills_registry_hash_drift", "status": "pass"}

    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"name": "skills_registry_hash_drift", "status": "pass"}

    mismatched: list[dict] = []
    for entry in registry.get("skills") or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name") or ""
        recorded = entry.get("contentHash") or ""
        if not name:
            continue
        skill_dir = Path(skills_root) / name
        if not skill_dir.is_dir():
            continue
        actual = hash_skill_dir(skill_dir)
        if recorded and actual and actual != recorded:
            mismatched.append({
                "skill": name,
                "recorded": recorded,
                "actual": actual,
            })

    top_recorded = registry.get("contentHash") or ""
    top_actual = _compute_top_level_digest(registry)
    # Top-level is only checked when the registry actually carries a
    # ``contentHash``; absence means we cannot prove drift, so do not
    # surface a false positive on test scaffolds / minimal registries.
    top_match = (not top_recorded) or top_recorded == top_actual
    top_drifted = bool(top_recorded) and top_recorded != top_actual

    if not mismatched and not top_drifted:
        return {"name": "skills_registry_hash_drift", "status": "pass"}

    if mismatched:
        detail = (
            f"{len(mismatched)} skill(s) drifted from skills-registry.json. "
            "Run 'npm run generate-registry' out-of-band when the change is "
            "intentional; this advisory never auto-fixes."
        )
    else:
        detail = (
            "Top-level registry contentHash drifted from the per-skill "
            "projection. Run 'npm run generate-registry' out-of-band."
        )
    return {
        "name": "skills_registry_hash_drift",
        "status": "warn",
        "detail": detail,
        "extra": {
            "registryVersion": registry.get("registryVersion"),
            "skills_mismatched": [m["skill"] for m in mismatched],
            "top_level_match": top_match,
            "top_level_expected": top_recorded,
            "top_level_actual": top_actual,
        },
    }


def resolution_summary(root: Path) -> list[dict]:
    """Return a template-resolution snapshot for the final payload."""
    resolution: list[dict] = []
    for info in list_templates(root):
        resolution.append(
            {
                "type": info.doc_type,
                "source": info.resolved_source,
                "has_default": info.has_default,
                "has_custom": info.has_custom,
            }
        )
    return resolution


def run_all_checks(
    root: Path,
    *,
    auto_fix: bool = False,
    dry_run: bool = False,
    force_template_repair: bool = False,
    checks: Sequence[Callable[[CheckContext], dict]] | None = None,
) -> dict:
    """Execute every registered check and return a structured result.

    Callers that need to substitute or reorder checks can pass *checks*;
    by default all registered ``CHECKS`` run in registration order.
    """
    ctx = CheckContext(
        root,
        auto_fix=auto_fix,
        dry_run=dry_run,
        force_template_repair=force_template_repair,
    )
    to_run = list(checks) if checks is not None else list(CHECKS)
    results: list[dict] = []
    for check_fn in to_run:
        try:
            result = check_fn(ctx)
        except (OSError, ValueError, subprocess.CalledProcessError) as e:
            result = {
                "name": getattr(check_fn, "__name__", "unknown"),
                "status": "fail",
                "detail": str(e),
            }
        results.append(result)

    healthy = all(c["status"] != "fail" for c in results)
    return {
        "healthy": healthy,
        "checks": results,
        "resolution_summary": resolution_summary(root),
    }


def run_autofix_and_reverify(root: Path, first_pass: dict) -> dict:
    """Re-evaluate after an auto-fix pass and surface residual failures.

    Takes the *first_pass* dict produced by ``run_all_checks(auto_fix=True)``
    and returns a new dict with ``repaired`` + ``still_failing`` keys.
    """
    second_pass = run_all_checks(root, auto_fix=False)
    still_failing = [c for c in second_pass["checks"] if c["status"] == "fail"]
    repaired = [c for c in first_pass["checks"] if c.get("repaired")]
    second_pass["repaired"] = repaired
    second_pass["still_failing"] = still_failing
    return second_pass
