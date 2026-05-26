"""Allowlisted subprocess execution for document-sourced commands.

Module is intentionally small and single-purpose: parse a shell-like
string into argv, reject shell metacharacters, match against a tuple
of allowed runner prefixes, and execute with ``shell=False``.
"""
from __future__ import annotations

import re
import shlex
import subprocess
from dataclasses import asdict, dataclass
from typing import Final, Optional

__all__ = ["safe_run_test", "RunResult", "ALLOWED_RUNNERS"]

# Runner allowlist. Each entry is a *prefix* — the first N tokens of
# argv must match exactly. Adding a new entry here is a deliberate
# security decision; reviewers must confirm the runner cannot shell out
# to an arbitrary binary via its own CLI (e.g. ``npm run <script>`` is
# intentionally NOT allowlisted because ``package.json`` scripts are
# operator-controlled and can invoke any binary the scripts field
# names — functionally equivalent to shell).
ALLOWED_RUNNERS: Final[tuple[tuple[str, ...], ...]] = (
    ("pytest",),
    ("python", "-m", "pytest"),
    ("python3", "-m", "pytest"),
    ("python", "-m", "unittest"),
    ("python3", "-m", "unittest"),
    ("npm", "test"),
    ("yarn", "test"),
    ("pnpm", "test"),
    ("bun", "test"),
    ("npx", "jest"),
    ("npx", "vitest"),
    ("go", "test"),
)


# Shell-metacharacter denylist applied to the raw command string
# pre-parse. The set lives on ``SecurityConfig`` so an audit-prescribed
# stricter set propagates through ``override_security_config(...)``;
# this module-level alias is a thin lazy lookup so ``import safe_run_test``
# never needs to reach into config eagerly. A future operator narrowing
# the set takes effect on the next call without re-import.
def _forbidden_chars() -> frozenset[str]:
    from .config import security_config
    return security_config().SUBPROCESS_FORBIDDEN_CHARS


def _default_timeout() -> int:
    from .config import security_config
    return security_config().SUBPROCESS_DEFAULT_TIMEOUT_SECS


def _max_parse_bytes() -> int:
    from .config import security_config
    return security_config().SUBPROCESS_MAX_PARSE_BYTES


_RE_PASSED = re.compile(r"(\d+)\s+passed")
_RE_FAILED = re.compile(r"(\d+)\s+failed")


@dataclass
class RunResult:
    """Structured return from :func:`safe_run_test`.

    Exactly one of (``rejected``, ``error``, executed-fields) is
    populated per invocation.
    """

    command: str
    rejected: Optional[str] = None       # "metacharacter" | "parse" | "runner"
    error: Optional[str] = None          # human-readable failure detail
    passed: int = 0
    failed: int = 0
    exit_code: Optional[int] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


def safe_run_test(
    command: str,
    *,
    project_path: str,
    timeout: "int | None" = None,
) -> RunResult:
    """Execute a document-sourced test command safely.

    Never raises on user input. Always returns a :class:`RunResult`
    carrying one of: ``rejected=<reason>`` (pre-flight veto),
    ``error=<msg>`` (timeout / runtime), or ``passed`` / ``failed`` /
    ``exit_code`` (executed).
    """
    forbidden = _forbidden_chars()
    if timeout is None:
        timeout = _default_timeout()
    if any(ch in command for ch in forbidden):
        return RunResult(
            command=command,
            rejected="metacharacter",
            error="shell metacharacters not allowed",
        )
    try:
        argv = shlex.split(command, posix=True)
    except ValueError as exc:
        return RunResult(
            command=command,
            rejected="parse",
            error=f"shlex parse failed: {exc}",
        )
    from .runners import default_allowlist  # lazy: avoid import cycle
    if not argv or not default_allowlist().is_allowed(argv):
        return RunResult(
            command=command,
            rejected="runner",
            error="runner not in allowlist",
        )
    try:
        proc = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            text=True,
            cwd=project_path,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return RunResult(
            command=command, error=f"timed out after {timeout}s",
        )
    except (FileNotFoundError, OSError) as exc:
        # Allowlisted runner binary is absent on PATH (e.g. ``pytest``
        # not installed). Surface the failure without raising so
        # callers stay inside the ``RunResult`` contract.
        return RunResult(command=command, error=f"exec failed: {exc}")
    return _parse_test_output(command, proc)


def _is_allowlisted(argv: list[str]) -> bool:
    return any(
        argv[: len(prefix)] == list(prefix) for prefix in ALLOWED_RUNNERS
    )


def _parse_test_output(
    command: str, proc: subprocess.CompletedProcess,
) -> RunResult:
    combined = (proc.stdout + proc.stderr)[:_max_parse_bytes()]
    passed = failed = 0
    for line in combined.splitlines():
        if "passed" in line:
            m = _RE_PASSED.search(line)
            if m:
                passed = int(m.group(1))
        if "failed" in line:
            m = _RE_FAILED.search(line)
            if m:
                failed = int(m.group(1))
    return RunResult(
        command=command,
        passed=passed,
        failed=failed,
        exit_code=proc.returncode,
    )
