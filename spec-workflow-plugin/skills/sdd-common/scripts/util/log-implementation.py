#!/usr/bin/env python3
"""Log implementation details for a completed task.

Usage: log-implementation.py --spec-name NAME --task-id ID --summary TEXT --files-modified JSON --files-created JSON --statistics JSON --artifacts JSON
"""
from __future__ import annotations
import _bootstrap  # noqa: F401

import json
import os
import uuid

from sdd_core import paths, tasks, output, cli
from sdd_core.time import ts_now, ts_short

ARTIFACT_RENDERERS = {
    "apiEndpoints":  [("Method", "method"), ("Path", "path"), ("Purpose", "purpose"), ("Location", "location")],
    "functions":     [("Name", "name"), ("Purpose", "purpose"), ("Location", "location"), ("Exported", "isExported")],
    "components":    [("Name", "name"), ("Type", "type"), ("Purpose", "purpose"), ("Location", "location")],
    "classes":       [("Name", "name"), ("Purpose", "purpose"), ("Location", "location"), ("Exported", "isExported")],
    "integrations":  None,
    "verifications": [("Description", "description"), ("Scope", "scope"), ("Result", "result"), ("Location", "location")],
}
ARTIFACT_TYPES = list(ARTIFACT_RENDERERS.keys())

REQUIRED_FIELDS = {
    "apiEndpoints":  ["method", "path", "purpose"],
    "functions":     ["name", "purpose", "location"],
    "components":    ["name", "purpose", "location"],
    "classes":       ["name", "purpose", "location"],
    "integrations":  ["description"],
    "verifications": ["description", "scope", "result"],
}


def _validate_artifacts(artifacts: dict) -> None:
    """Validate artifact types and required fields with actionable errors."""
    for art_type, items in artifacts.items():
        if art_type not in ARTIFACT_RENDERERS:
            output.error(
                f"Unknown artifact type '{art_type}'",
                hint=f"Valid types: {', '.join(ARTIFACT_TYPES)}",
            )
        if not items:
            continue
        required = REQUIRED_FIELDS.get(art_type, [])
        for i, item in enumerate(items):
            missing = [f for f in required if not item.get(f)]
            if missing:
                output.error(
                    f"Artifact '{art_type}[{i}]' missing required field(s): {', '.join(missing)}",
                    hint="Expected: {{ {} }}".format(', '.join('{}: "..."'.format(f) for f in required)),
                )


def _render_artifacts(artifacts: dict) -> str:
    """Render artifact tables/lists as markdown."""
    content = ""
    for art_type, items in artifacts.items():
        if not items:
            continue
        content += f"\n### {art_type}\n"
        columns = ARTIFACT_RENDERERS.get(art_type)
        if columns is None:
            for item in items:
                content += f"- **{item.get('description', '')}**\n"
                content += f"  - Frontend: {item.get('frontendComponent', '')}\n"
                content += f"  - Backend: {item.get('backendEndpoint', '')}\n"
                content += f"  - Flow: {item.get('dataFlow', '')}\n"
        else:
            content += "| " + " | ".join(h for h, _ in columns) + " |\n"
            content += "|" + "|".join("---" for _ in columns) + "|\n"
            for item in items:
                content += "| " + " | ".join(str(item.get(f, '')) for _, f in columns) + " |\n"
    return content


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument("--spec-name", required=True, type=cli.name_type("spec-name"))
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--files-modified", default="[]")
    parser.add_argument("--files-created", default="[]")
    parser.add_argument("--statistics", default="{}")
    parser.add_argument("--artifacts", default="{}")
    args = parser.parse_args()

    root = paths.require_workflow_root()

    tasks_file = paths.spec_dir(root, args.spec_name) / "tasks.md"
    if not tasks_file.exists():
        output.error(f"tasks.md not found for spec: {args.spec_name}")

    parsed_tasks = tasks.parse_tasks(tasks_file.read_text())
    task = tasks.get_task_by_id(parsed_tasks, args.task_id)
    if not task:
        output.error(f"Task '{args.task_id}' not found in spec '{args.spec_name}'")

    try:
        artifacts = json.loads(args.artifacts)
    except json.JSONDecodeError:
        output.error("Invalid JSON in --artifacts")

    try:
        files_modified = json.loads(args.files_modified)
        files_created = json.loads(args.files_created)
        statistics = json.loads(args.statistics)
    except json.JSONDecodeError as e:
        output.error(f"Invalid JSON in arguments: {e}")

    pre_existing = statistics.get("preExisting", False)
    if not isinstance(pre_existing, bool):
        output.error(
            "statistics.preExisting must be boolean (true/false)",
            hint='Use --statistics \'{"preExisting": true}\' — not "true" (string)',
        )

    _validate_artifacts(artifacts)

    has_artifacts = any(artifacts.get(k) for k in ARTIFACT_TYPES)
    if not has_artifacts and not pre_existing:
        output.error(
            "Artifacts REQUIRED: at least one non-empty type",
            hint=f"Valid types: {', '.join(ARTIFACT_TYPES)}. "
                 "Or set statistics.preExisting=true for verification-only tasks.",
        )

    log_id = uuid.uuid4().hex[:8]
    timestamp = ts_now()
    short_ts = ts_short()

    log_dir = paths.impl_logs_dir(root, args.spec_name)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"task-{args.task_id}_{short_ts}_{log_id}.md"

    lines_added = statistics.get("linesAdded", 0)
    lines_removed = statistics.get("linesRemoved", 0)
    files_changed = len(files_modified) + len(files_created)

    content = f"""# Implementation Log: Task {args.task_id}

**Summary:** {args.summary}
**Timestamp:** {timestamp}
**Log ID:** {log_id}

## Statistics
- Lines Added: {lines_added}
- Lines Removed: {lines_removed}
- Files Changed: {files_changed}

## Files Modified
"""
    for f in files_modified:
        content += f"- {f}\n"

    content += "\n## Files Created\n"
    for f in files_created:
        content += f"- {f}\n"

    content += "\n## Artifacts\n"
    content += _render_artifacts(artifacts)

    log_file.write_text(content)

    try:
        # Deferred: impl_session is optional; not available in all invocation contexts
        from impl.impl_session import read_session, record_task_complete, write_session
    except ImportError:
        pass
    else:
        session = read_session(args.spec_name, str(root))
        ct = session.get("current_task")
        if ct and ct.get("id") == args.task_id:
            try:
                record_task_complete(session, args.task_id, log_id, pre_existing=pre_existing)
                write_session(args.spec_name, session, str(root))
            except ValueError as exc:
                output.warn(f"Session update skipped: {exc}")

    output.success({"logFile": str(log_file), "logId": log_id, "taskId": args.task_id}, f"Implementation logged for task {args.task_id}")

if __name__ == "__main__":
    cli.run_main(main)
