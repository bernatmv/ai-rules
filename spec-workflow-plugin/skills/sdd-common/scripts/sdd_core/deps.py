"""Hard-dependency guards — one import site per third-party package.

Keeps ``ImportError`` hints (phrasing, install command) in a single
place so ``references/script-conventions.md § Runtime Dependencies``
stays in lock-step with the runtime error message callers see.
"""
from __future__ import annotations

from typing import Any

__all__ = ["require_pyyaml", "PYYAML_INSTALL_HINT"]


PYYAML_INSTALL_HINT = (
    "PyYAML is required to load requirements_antipatterns.yaml. "
    "Install with: pip install pyyaml"
)


def require_pyyaml() -> Any:
    """Return the ``yaml`` module, raising a structured hint when absent.

    Use from any module that needs PyYAML at import time:

        from sdd_core.deps import require_pyyaml
        yaml = require_pyyaml()

    Centralising the import means the install hint ships in exactly one
    location — see ``references/script-conventions.md``.
    """
    try:
        import yaml  # type: ignore[import-untyped]
        return yaml
    except ImportError as exc:  # pragma: no cover - exercised via test
        raise ImportError(PYYAML_INSTALL_HINT) from exc
