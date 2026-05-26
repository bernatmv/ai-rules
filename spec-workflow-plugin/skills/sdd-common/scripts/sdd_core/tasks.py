"""Task parsing and progress calculation from tasks.md."""
from __future__ import annotations

import re

from .matchers import WordMatcher

__all__ = [
    "parse_tasks",
    "get_task_by_id",
    "calculate_progress",
    "find_next_pending",
    "is_header",
    "update_task_marker",
    "TASK_LINE_RE",
    "METADATA_RE",
    "CONTENT_MARKERS",
    "CHECKBOX_STATUS_MAP",
    "MARKER_FOR_STATUS",
    "COMPLETED_STATUS",
    "IN_PROGRESS_STATUS",
    "PENDING_STATUS",
]

COMPLETED_STATUS = "completed"
IN_PROGRESS_STATUS = "in_progress"
PENDING_STATUS = "pending"

CHECKBOX_STATUS_MAP = {"x": COMPLETED_STATUS, "-": IN_PROGRESS_STATUS}
MARKER_FOR_STATUS = {COMPLETED_STATUS: "x", IN_PROGRESS_STATUS: "-", PENDING_STATUS: " "}

TASK_LINE_RE = re.compile(r"^\s*-\s*\[(.)\]\s+(\d+(?:\.\d+)*)\.?\s+(.*)")
METADATA_RE = re.compile(r"^\s*-\s*_(\w+):\s*(.*?)_?\s*$")

CONTENT_MARKERS = WordMatcher(
    ["_Requirements:", "_Leverage:", "_Prompt:", "_DependsOn:",
     "Files:", "File:"],
    boundary="none",
)


def is_header(task: dict) -> bool:
    """True if the task is an organizational header with no implementation content.

    Mirrors the isHeader heuristic in task-parser.ts: a task with no metadata
    fields and no content lines containing requirements, leverage, files,
    purpose, or prompt markers is a structural grouping node.
    """
    if task.get("metadata"):
        return False
    for line in task.get("lines", [])[1:]:
        if CONTENT_MARKERS.search(line):
            return False
    return True


def parse_tasks(content: str) -> list[dict]:
    """Parse all tasks from tasks.md content."""
    tasks = []
    current = None

    for line in content.splitlines():
        m = TASK_LINE_RE.match(line)
        if m:
            if current:
                tasks.append(current)
            marker = m.group(1)
            status = CHECKBOX_STATUS_MAP.get(marker, PENDING_STATUS)
            current = {
                "id": m.group(2),
                "description": m.group(3).strip(),
                "status": status,
                "marker": marker,
                "metadata": {},
                "lines": [line]
            }
        elif current:
            current["lines"].append(line)
            mm = METADATA_RE.match(line)
            if mm:
                current["metadata"][mm.group(1)] = mm.group(2).strip()

    if current:
        tasks.append(current)
    return tasks


def get_task_by_id(tasks: list[dict], task_id: str) -> dict | None:
    """Return the task dict matching *task_id*, or ``None`` if not found."""
    for t in tasks:
        if t["id"] == task_id:
            return t
    return None


def calculate_progress(tasks: list[dict]) -> dict[str, int]:
    """Return ``{total, completed, pending, inProgress}`` counts."""
    total = len(tasks)
    completed = sum(1 for t in tasks if t["status"] == COMPLETED_STATUS)
    in_progress = sum(1 for t in tasks if t["status"] == IN_PROGRESS_STATUS)
    pending = sum(1 for t in tasks if t["status"] == PENDING_STATUS)
    return {"total": total, "completed": completed, "pending": pending, "inProgress": in_progress}


def find_next_pending(tasks: list[dict]) -> dict | None:
    """Return the first task with ``status == 'pending'``, or ``None``."""
    for t in tasks:
        if t["status"] == PENDING_STATUS:
            return t
    return None


def update_task_marker(
    content: str, task_id: str, from_marker: str, to_marker: str,
) -> tuple[str, bool]:
    """Replace the checkbox marker for *task_id* in tasks.md content.

    Returns ``(updated_content, was_updated)``.  Only the first matching
    line for *task_id* with *from_marker* is changed.
    """
    id_pattern = re.compile(
        rf"^(\s*-\s*)\[{re.escape(from_marker)}\](\s+{re.escape(task_id)}\.?\s+)",
    )
    lines = content.splitlines()
    updated = False
    for i, line in enumerate(lines):
        if not updated and id_pattern.match(line):
            lines[i] = id_pattern.sub(rf"\g<1>[{to_marker}]\2", line, count=1)
            updated = True
    return "\n".join(lines) + "\n", updated
