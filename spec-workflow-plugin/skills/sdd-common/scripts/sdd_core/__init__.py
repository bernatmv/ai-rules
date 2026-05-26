"""sdd_core — shared library for SDD spec-workflow scripts.

Import submodules directly: ``from sdd_core import paths, output``.
"""

__version__ = "3.3.1"

__all__ = [
    "approvals",
    "audit",
    "cli",
    "constants",
    "delegation",
    "matchers",
    "output",
    "paths",
    "prompts",
    "snapshots",
    "specs",
    "subprocess_dispatch",
    "task_validation",
    "tasks",
    "templates",
    "testing",
    "text",
    "time",
    "transient_state",
    "workspace",
    "workspace_approval",
    "workspace_artifacts",
    "workspace_manifest",
    "workspace_tracker",
    "workspace_validation",
]


def __getattr__(name: str):
    """Lazy-load submodules on first access (PEP 562)."""
    if name in __all__:
        import importlib
        return importlib.import_module(f".{name}", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
