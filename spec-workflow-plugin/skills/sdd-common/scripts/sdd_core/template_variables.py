"""Variable substitution engine for templates."""
from __future__ import annotations

import re
import subprocess
from datetime import date
from pathlib import Path

__all__ = [
    "KNOWN_VARIABLES",
    "VARIABLE_RE",
    "substitute_variables",
    "get_default_variables",
]

KNOWN_VARIABLES = {"projectName", "featureName", "specName", "date", "author"}

VARIABLE_RE = re.compile(r"\{\{(\w+)\}\}")


def substitute_variables(content: str, variables: dict) -> str:
    """Replace {{varName}} placeholders with provided values."""
    def replacer(match):
        key = match.group(1)
        return variables.get(key, match.group(0))
    return VARIABLE_RE.sub(replacer, content)


def get_default_variables(*, spec_name: str = "", project_path: Path) -> dict:
    """Build standard variable dict: projectName, featureName, date, author."""
    author = "unknown"
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, timeout=5,
            cwd=str(project_path),
        )
        if result.returncode == 0 and result.stdout.strip():
            author = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return {
        "projectName": project_path.name,
        "featureName": spec_name,
        "specName": spec_name,
        "date": date.today().isoformat(),
        "author": author,
    }
