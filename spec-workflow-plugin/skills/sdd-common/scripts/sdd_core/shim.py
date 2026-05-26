"""Manage the .spec-workflow/sdd runner shim.

The canonical shim template lives at sdd_core/runner-shim.  Both the Python
workspace/init.py and the Bash update-skills.sh flow read from that single
file — this module provides the Python interface.
"""

__all__ = ["canonical_content", "ensure_shim"]

import os
import stat
from pathlib import Path
from typing import Optional

_TEMPLATE_PATH = Path(__file__).with_name("runner-shim")


def canonical_content() -> str:
    """Return the canonical shim content from the template file."""
    return _TEMPLATE_PATH.read_text()


def ensure_shim(workflow_root: Path) -> Optional[str]:
    """Create or update .spec-workflow/sdd. Returns 'created', 'updated', or None."""
    shim_path = workflow_root / "sdd"
    content = canonical_content()

    if shim_path.exists():
        if shim_path.read_text() == content:
            return None
        action = "updated"
    else:
        action = "created"

    shim_path.write_text(content)
    shim_path.chmod(shim_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return action
