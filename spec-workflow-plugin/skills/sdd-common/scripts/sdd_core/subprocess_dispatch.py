"""Single-seam Layer 2 dispatcher for inter-script Python subprocess invocations.

Production code (workspace fan-outs, future cross-repo runners) and
tests (`tests/_helpers/sdd_shim.run_sdd`) both route through
:func:`run_dispatched`. The four invariants — dispatcher entry,
``PYTHONDONTWRITEBYTECODE=1``, ``PYTHONPATH`` injection, ``--project``
placement — live in **one** function so a future shim shape change
flows through one helper.

See ``references/script-conventions.md`` § Bootstrap Pattern for the
three-layer invocation contract.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping

__all__ = ["run_dispatched", "SCRIPTS_ROOT"]


# Resolve ``.cursor/skills/sdd-common/scripts/`` from this file's
# location. The dispatcher imports `sdd_core` self-bootstraps via
# `sys.path` manipulation in ``__main__.py``, so ``PYTHONPATH``
# injection here keeps `python3 -m sdd_core` discoverable regardless
# of caller cwd.
SCRIPTS_ROOT = Path(__file__).resolve().parent.parent


def run_dispatched(
    script: str,
    *args: str,
    project_path: "str | os.PathLike[str] | None" = None,
    env_extra: "Mapping[str, str] | None" = None,
    timeout: "float | None" = None,
    cwd: "str | os.PathLike[str] | None" = None,
    capture_output: bool = True,
) -> subprocess.CompletedProcess:
    """Invoke an SDD script via ``python3 -m sdd_core <script> [args...]``.

    Builds the canonical
    ``[sys.executable, "-m", "sdd_core",
    *("--project", str(project_path)) if project_path else (),
    script, *args]`` command and overlays env defaults that the
    dispatcher contract requires.

    Parameters
    ----------
    script:
        Script path relative to the scripts root (e.g.
        ``"approval/list-pending.py"``). The dispatcher accepts both
        the explicit ``.py`` suffix and the bare form.
    args:
        CLI arguments passed verbatim to the script.
    project_path:
        When set, the dispatcher's ``--project`` pre-scan runs first
        (sets ``SDD_PROJECT_PATH`` and ``chdir``s into the target).
        ``--project`` precedes the script name as required by
        ``sdd_core/__main__.py``.
    env_extra:
        Mapping of additional env vars merged on top of ``os.environ``.
        Cannot drop ``PYTHONDONTWRITEBYTECODE`` — the helper re-pins
        it after the overlay.
    timeout:
        Seconds before ``subprocess.run`` raises.
    cwd:
        Working directory; defaults to whatever the caller chose.
        Note: when ``project_path`` is set the dispatcher chdirs into
        it before the script runs, so ``cwd`` and ``project_path``
        usually overlap (set both only when probing edge cases).
    capture_output:
        Forwarded to :func:`subprocess.run`. Default keeps the test
        helper contract: capture stdout/stderr as text.

    Returns
    -------
    subprocess.CompletedProcess
        Same shape every caller already expects from
        :func:`subprocess.run` — Liskov-clean.
    """
    env = dict(os.environ)
    existing_pp = env.get("PYTHONPATH", "")
    if str(SCRIPTS_ROOT) not in existing_pp.split(os.pathsep):
        env["PYTHONPATH"] = (
            str(SCRIPTS_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
        )
    if env_extra:
        env.update(env_extra)
    # Re-pin after overlay so callers cannot accidentally re-enable
    # bytecode emission; see Theme K K0 closure.
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    cmd: list[str] = [sys.executable, "-m", "sdd_core"]
    if project_path is not None:
        cmd.extend(("--project", str(project_path)))
    cmd.append(script)
    cmd.extend(args)

    return subprocess.run(
        cmd,
        capture_output=capture_output,
        text=True,
        env=env,
        timeout=timeout,
        cwd=str(cwd) if cwd is not None else None,
    )
