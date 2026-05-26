"""Thin wrappers around ``git`` subprocess calls.

Each helper degrades gracefully when ``git`` is missing, the directory
is not a working tree, the call times out, or any other ``OSError``
fires. Returning empty / ``False`` instead of raising keeps callers
free from defensive ``try`` / ``except`` blocks for environmental
edge cases.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

__all__ = [
    "GIT_TIMEOUT",
    "ls_files",
    "is_inside_work_tree",
    "tracked_subdirs",
    "log_oneline",
    "diff_name_status",
]


# Median ``git ls-files`` latency on a 5k-file repo is ~200 ms; 10 s is
# >50x headroom while still surfacing genuine hangs.
GIT_TIMEOUT = 10


def _run_git(args: list[str], *, cwd: Path, timeout: int) -> "subprocess.CompletedProcess | None":
    """Run a git subcommand. Return ``None`` on any environmental failure."""
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True, text=True, cwd=str(cwd), timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def ls_files(relpath: str, *, cwd: Path, timeout: int = GIT_TIMEOUT) -> list[str]:
    """Return the lines of ``git ls-files -- <relpath>`` (or ``[]`` on failure)."""
    proc = _run_git(["ls-files", "--", relpath], cwd=cwd, timeout=timeout)
    if proc is None or proc.returncode != 0:
        return []
    return [line for line in proc.stdout.splitlines() if line]


def is_inside_work_tree(cwd: Path, *, timeout: int = GIT_TIMEOUT) -> bool:
    """Return True when ``cwd`` is inside a git working tree."""
    proc = _run_git(
        ["rev-parse", "--is-inside-work-tree"], cwd=cwd, timeout=timeout,
    )
    if proc is None or proc.returncode != 0:
        return False
    return proc.stdout.strip() == "true"


def tracked_subdirs(workflow_dir: Path, cwd: Path, *, timeout: int = GIT_TIMEOUT) -> set[str]:
    """Return immediate subdirectory names tracked under ``workflow_dir``.

    ``workflow_dir`` is interpreted relative to ``cwd``. When the path
    is not in the working tree (or git is unavailable), returns an
    empty set so callers degrade gracefully.
    """
    try:
        rel = workflow_dir.relative_to(cwd)
    except ValueError:
        rel = workflow_dir
    rel_parts = rel.parts
    if not rel_parts:
        return set()

    subdirs: set[str] = set()
    for line in ls_files(str(rel), cwd=cwd, timeout=timeout):
        parts = line.split("/")
        # Only keep entries that nest at least one level inside the dir.
        if len(parts) >= len(rel_parts) + 2 and tuple(parts[: len(rel_parts)]) == rel_parts:
            subdirs.add(parts[len(rel_parts)])
    return subdirs


def diff_name_status(
    *, cwd: Path, ref: str = "HEAD", timeout: int = GIT_TIMEOUT,
) -> list[tuple[str, str]] | None:
    """Return ``[(status, path), ...]`` from ``git diff --name-status <ref>``.

    Returns ``None`` on any environmental failure (no git, detached
    worktree, timeout) so callers can distinguish "no changes" (empty
    list) from "diff unavailable". Status tokens are the raw git
    status letters (``A``, ``M``, ``D``, ``R…``, ``C…``, …); callers
    interpret them.
    """
    proc = _run_git(
        ["diff", "--name-status", ref], cwd=cwd, timeout=timeout,
    )
    if proc is None or proc.returncode != 0:
        return None
    rows: list[tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        rows.append((parts[0].strip(), parts[-1].strip()))
    return rows


def log_oneline(relpath: str, *, cwd: Path, timeout: int = GIT_TIMEOUT) -> bool:
    """Return True when ``git log -1 -- <relpath>`` returns a non-empty line."""
    proc = _run_git(
        ["log", "--oneline", "-1", "--", relpath], cwd=cwd, timeout=timeout,
    )
    if proc is None or proc.returncode != 0:
        return False
    return bool(proc.stdout.strip())


def show_head(
    relpath: str,
    *,
    cwd: Path,
    ref: str = "HEAD",
    timeout: int = GIT_TIMEOUT,
) -> "str | None":
    """Return the file content at *ref* (default ``HEAD``).

    Returns ``None`` when the file is not tracked at that ref, git is
    unavailable, or the directory is not a working tree. Callers that
    bucket findings into NEW vs PRE-EXISTING (so a single legacy issue
    does not freeze the pre-launch gate) read the baseline through this
    helper and diff against the live working-tree result.
    """
    proc = _run_git(
        ["show", f"{ref}:{relpath}"], cwd=cwd, timeout=timeout,
    )
    if proc is None or proc.returncode != 0:
        return None
    return proc.stdout
