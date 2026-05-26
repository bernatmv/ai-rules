"""Subprocess-based checks extracted from builders.py (DIP compliance)."""
from __future__ import annotations

import json
import subprocess
import sys

from .paths import _SCRIPTS_ROOT, script_path
from sdd_core import output


def _check_spec_type(spec_name: str, declared: str) -> None:
    """Warn if declared spec_type contradicts detect-spec-type.py."""
    try:
        r = subprocess.run(
            [sys.executable, script_path("spec/detect-type.py"), spec_name],
            capture_output=True, text=True, cwd=_SCRIPTS_ROOT,
        )
        raw = r.stdout.strip()
        if not raw:
            return
        try:
            data = json.loads(raw)
            detected = data.get("data", {}).get("type", "")
        except (json.JSONDecodeError, AttributeError):
            detected = raw
        if detected and detected != declared:
            output.warn(
                f"spec_type declared as {declared!r} but"
                f" detect-spec-type.py reports {detected!r} for {spec_name!r}"
            )
    except Exception as exc:
        output.warn(f"detect-spec-type.py failed for {spec_name!r}: {exc}")
