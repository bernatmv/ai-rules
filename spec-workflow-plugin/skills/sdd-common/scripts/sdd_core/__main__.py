"""SDD script runner — zero-setup entry point for all SDD skills.

Canonical invocation goes through the workflow shim:
    .spec-workflow/sdd <group>/<script>.py [args...]

This module is the Layer 3 fallback (see
``$SKILLS/sdd-common/references/bootstrap-pattern.md``). Direct invocation
is supported only when the shim is unavailable:
    python3 .cursor/skills/sdd-common/scripts/sdd_core <script> [args...]
    python3 -m sdd_core <script> [args...]   # also works when PYTHONPATH is set

The --project flag sets SDD_WORKSPACE and changes the working directory
to the target project before running the script. Without it, CWD is used.

Script names are resolved relative to the scripts/ directory (the parent of
sdd_core/). The .py extension is optional.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import os
import runpy
from pathlib import Path

# Wire up the cache-cleanup ``atexit`` hook so the runner case
# (``python3 .../sdd_core <script>``) leaves no ``__pycache__``
# residue under ``scripts/sdd_core``. The hook is process-wide and
# idempotent — see ``_sdd_bootstrap.py``.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import _sdd_bootstrap as _sdd_bootstrap  # noqa: F401, E402

_MIN_PYTHON = (3, 9)

if sys.version_info < _MIN_PYTHON:
    import json as _json
    _platform_hints = {
        "darwin": "brew install python@3.12",
        "linux": "apt install python3.12 || your distro's package manager",
    }
    _hint_install = _platform_hints.get(sys.platform, "https://www.python.org/downloads/")
    _hint = (
        f"Python {_MIN_PYTHON[0]}.{_MIN_PYTHON[1]}+ is required; "
        f"this interpreter reports {sys.version_info.major}.{sys.version_info.minor}."
        f" Install a supported interpreter: {_hint_install}"
    )
    _envelope = {
        "status": "error",
        "error": (
            f"unsupported Python version "
            f"{sys.version_info.major}.{sys.version_info.minor} "
            f"(minimum {_MIN_PYTHON[0]}.{_MIN_PYTHON[1]})"
        ),
        "hint": _hint,
        "context": "",
        "next_action_command": "$SHELL --version",
    }
    print(_json.dumps(_envelope), file=sys.stderr)
    sys.exit(1)

SCRIPTS_DIR = Path(__file__).resolve().parent.parent

# Self-bootstrap: ensure sdd_core is importable. When invoked as
# `python3 /path/to/sdd_core`, Python adds sdd_core/ (not its parent)
# to sys.path. This fixes that so child scripts can
# `from sdd_core import ...`.
_scripts_str = str(SCRIPTS_DIR)
if _scripts_str not in sys.path:
    sys.path.insert(0, _scripts_str)

from sdd_core.output import error  # noqa: E402
from sdd_core.command_templates import build_shim_command  # noqa: E402


def _resolve_script(name: str) -> Path:
    """Resolve a script name to an absolute .py path under SCRIPTS_DIR."""
    candidate = SCRIPTS_DIR / name
    if candidate.suffix != ".py":
        candidate = candidate.with_suffix(".py")
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(
        f"Script not found: {name}\n"
        f"  Looked for: {candidate}\n"
        f"  Scripts dir: {SCRIPTS_DIR}"
    )


def _did_you_mean_suggestions(name: str) -> list[str]:
    """Return up to 3 fuzzy matches from the live script inventory."""
    try:
        from sdd_core.command_templates import available_scripts, did_you_mean
    except ImportError:
        return []
    return did_you_mean(name, available_scripts(str(SCRIPTS_DIR)))


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)

    list_cmd = build_shim_command("util/list-commands.py")

    if args[0] == "--project":
        if len(args) < 2:
            error(
                "--project requires a path argument",
                hint="Usage: python3 -m sdd_core --project <path> <script> [args...]",
                next_action_command=list_cmd,
            )
        project_path = Path(args[1]).resolve()
        if not project_path.is_dir():
            error(
                f"Project path does not exist: {project_path}",
                next_action_command=build_shim_command(
                    "workspace/init.py", project_path=str(project_path.parent),
                ),
            )
        # Written (not setdefault) so a stale parent-process value
        # cannot override the dispatcher's --project selection.
        os.environ["SDD_WORKSPACE"] = str(project_path)
        os.chdir(project_path)
        args = args[2:]

    if not args:
        error(
            "No script specified",
            hint="Usage: python3 -m sdd_core <script> [args...]",
            next_action_command=list_cmd,
        )

    script_name = args[0]
    try:
        script_path = _resolve_script(script_name)
    except FileNotFoundError as exc:
        suggestions = _did_you_mean_suggestions(script_name)
        context = ""
        hint_parts: list[str] = [
            "Never prefix the shim with python3. See "
            "$SKILLS/sdd-common/references/tool-patterns.md § Invocation.",
        ]
        if suggestions:
            import json as _json
            context = _json.dumps(
                {"did_you_mean": suggestions},
                separators=(",", ":"), sort_keys=True,
            )
            hint_parts.insert(0, f"Did you mean: {', '.join(suggestions)}?")
        error(
            str(exc),
            hint="\n".join(hint_parts),
            context=context,
            next_action_command=list_cmd,
        )

    sys.argv = [str(script_path)] + args[1:]

    # Add the script's directory to sys.path so `import _bootstrap` works
    # the same way as when Python runs the script directly.
    script_dir = str(script_path.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    runpy.run_path(str(script_path), run_name="__main__")


if __name__ == "__main__":
    main()
