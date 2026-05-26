"""Implementation session I/O — read/write .impl-session.json for task state.

Single-responsibility module for implementation session persistence (SRP).
Mirrors the gate_session.py pattern for review pipelines.

Session file location:
  .spec-workflow/specs/{spec-name}/.impl-session.json
"""
from __future__ import annotations

import os

from sdd_core import output
from sdd_core.time import ts_now

# Bump major on breaking schema changes, minor on additive fields
_SESSION_SCHEMA_VERSION = "1.0.0"
_SESSION_FILENAME = ".impl-session.json"

# --- Key constants (OCP: schema changes surface as KeyError) ----------------

_KEY_SCHEMA_VERSION = "schema_version"
_KEY_SPEC_NAME = "spec_name"
_KEY_STARTED_AT = "started_at"
_KEY_UPDATED_AT = "updated_at"
_KEY_EXECUTION_MODE = "execution_mode"
_KEY_BATCH_RESULT = "batch_result"
_KEY_CURRENT_TASK = "current_task"
_KEY_COMPLETED_TASKS = "completed_tasks"
_KEY_TEST_RESULTS = "test_results"
_KEY_REVIEW_STATUS = "review_status"

# ---------------------------------------------------------------------------


def _default_session() -> dict:
    return {
        _KEY_SCHEMA_VERSION: _SESSION_SCHEMA_VERSION,
        _KEY_SPEC_NAME: None,
        _KEY_STARTED_AT: None,
        _KEY_UPDATED_AT: None,
        _KEY_EXECUTION_MODE: None,
        _KEY_BATCH_RESULT: None,
        _KEY_CURRENT_TASK: None,
        _KEY_COMPLETED_TASKS: [],
        _KEY_TEST_RESULTS: None,
        _KEY_REVIEW_STATUS: None,
    }


def session_path(spec_name: str, project_path: str = ".") -> str:
    """Return .impl-session.json path for the given spec.

    Uses the same path derivation as ``paths.spec_dir`` to avoid divergence.
    """
    from sdd_core.paths import WORKFLOW_DIR
    return os.path.join(project_path, WORKFLOW_DIR, "specs", spec_name, _SESSION_FILENAME)


def read_session(spec_name: str, project_path: str = ".") -> dict:
    """Read session, returning defaults if file absent."""
    path = session_path(spec_name, project_path)
    data = output.safe_read_json(path, default=None)
    if data is None or not isinstance(data, dict):
        return _default_session()
    result = _default_session()
    for key in result:
        if key in data:
            result[key] = data[key]
    return result


def write_session(spec_name: str, session_data: dict, project_path: str = ".") -> None:
    """Atomic-write session to disk, auto-setting updated_at."""
    session_data[_KEY_UPDATED_AT] = ts_now()
    path = session_path(spec_name, project_path)
    output.atomic_write_json(path, session_data, verify_key=_KEY_SCHEMA_VERSION)


def init_session(
    *,
    spec_name: str,
    execution_mode: str,
    project_path: str = ".",
) -> dict:
    """Create a fresh session or resume an existing one.

    If a session already exists:
      - Detects stale state (current_task with no matching completed entry)
      - Resets stale current_task on resume
      - Preserves completed_tasks and batch_result
    """
    path = session_path(spec_name, project_path)
    existing = output.safe_read_json(path, default=None)
    now = ts_now()

    if not existing or not isinstance(existing, dict):
        session = _default_session()
        session[_KEY_SPEC_NAME] = spec_name
        session[_KEY_EXECUTION_MODE] = execution_mode
        session[_KEY_STARTED_AT] = now
        session[_KEY_UPDATED_AT] = now
        write_session(spec_name, session, project_path)
        return session

    full = read_session(spec_name, project_path)

    stale = detect_stale_session(full)
    if stale["is_stale"]:
        full[_KEY_CURRENT_TASK] = None
        output.info(f"Reset stale current_task: {stale['reason']}")

    full[_KEY_EXECUTION_MODE] = execution_mode
    full[_KEY_UPDATED_AT] = now
    write_session(spec_name, full, project_path)
    return full


def record_task_start(session: dict, task_id: str) -> dict:
    """Set current_task; refuse if prior task lacks a log_id in completed_tasks.

    Prevents Glitch 1 (batched logging) by enforcing sequential completion.
    """
    if session.get("current_task") is not None:
        ct = session["current_task"]
        raise ValueError(
            f"Task {ct['id']} is still in-progress. "
            "Complete it before starting another."
        )

    completed = session.get("completed_tasks") or []
    if completed:
        last = completed[-1]
        if not last.get("log_id"):
            raise ValueError(
                f"Task {last['id']} was completed without a log_id. "
                "Run log-implementation.py first."
            )

    session["current_task"] = {
        "id": task_id,
        "status": "in_progress",
        "started_at": ts_now(),
    }
    return session


def record_task_complete(
    session: dict,
    task_id: str,
    log_id: str,
    pre_existing: bool = False,
) -> dict:
    """Move current_task to completed_tasks with log_id.

    Raises if current_task.id doesn't match task_id (prevents out-of-order).
    """
    ct = session.get("current_task")
    if ct is None:
        raise ValueError(
            f"No task in-progress. Cannot complete task {task_id}."
        )
    if ct["id"] != task_id:
        raise ValueError(
            f"Current task is {ct['id']}, not {task_id}. "
            "Cannot complete a different task."
        )

    completed_entry = {
        "id": task_id,
        "logged_at": ts_now(),
        "log_id": log_id,
        "pre_existing": pre_existing,
    }

    completed = session.get("completed_tasks") or []
    completed.append(completed_entry)
    session["completed_tasks"] = completed
    session["current_task"] = None
    return session


def record_test_results(session: dict, passed: int, failed: int) -> dict:
    """Record test execution results in session."""
    session["test_results"] = {
        "last_run": ts_now(),
        "passed": passed,
        "failed": failed,
    }
    return session


def detect_stale_session(session: dict) -> dict:
    """Detect a current_task left from an interrupted session.

    A task is stale if it's in_progress but not in completed_tasks
    (i.e., the session was interrupted between start and completion).
    """
    ct = session.get("current_task")
    if ct is None:
        return {
            "is_stale": False,
            "reason": "No current task",
            "recommendation": None,
        }

    completed_ids = {
        t["id"] for t in (session.get("completed_tasks") or [])
    }
    if ct["id"] in completed_ids:
        return {
            "is_stale": False,
            "reason": "Current task already in completed list",
            "recommendation": None,
        }

    return {
        "is_stale": True,
        "reason": f"Task {ct['id']} stuck in_progress without completion",
        "recommendation": "Reset with init_session (auto-resets on resume)",
    }


def get_task_completion(session: dict, task_id: str) -> dict | None:
    """Return the completed_tasks entry for task_id, or None."""
    for entry in session.get("completed_tasks") or []:
        if entry["id"] == task_id:
            return entry
    return None


def delete_session(spec_name: str, project_path: str = ".") -> bool:
    """Delete session file. Returns True if deleted, False if not found."""
    path = session_path(spec_name, project_path)
    try:
        os.unlink(path)
        return True
    except FileNotFoundError:
        return False
