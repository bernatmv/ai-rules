"""Process-wide one-shot setup for SDD scripts.

Flips ``sys.dont_write_bytecode`` and prepends ``$SCRIPTS/`` to
``sys.path`` exactly once per process. Every per-sub-directory
``_bootstrap.py`` shim delegates here via :func:`apply` after
flipping the bytecode flag locally (belt-and-braces). See
``references/script-conventions.md`` § Bootstrap Pattern.

On Python 3.10+ the source file's ``.pyc`` is written before the
module body executes, so the in-body ``dont_write_bytecode = True``
flip cannot suppress the shim's own bytecode cache. An ``atexit``
hook removes the leaked ``__pycache__`` entries so the bootstrap
chain is byte-for-byte cache-free regardless of interpreter
version.
"""
from __future__ import annotations

import atexit as _atexit
import os as _os
import sys as _sys
from pathlib import Path as _Path

__all__ = ["apply"]


_PYCACHE_PATHS_TO_CLEAN: "set[str]" = set()


def _register_pycache_cleanup(source_file: str) -> None:
    """Track ``<dir-of-source>/__pycache__`` for atexit removal."""
    parent = _Path(source_file).resolve().parent
    _PYCACHE_PATHS_TO_CLEAN.add(str(parent / "__pycache__"))


def _cleanup_leaked_pycache() -> None:
    for cache_dir in _PYCACHE_PATHS_TO_CLEAN:
        if not _os.path.isdir(cache_dir):
            continue
        for name in _os.listdir(cache_dir):
            if name.endswith((".pyc", ".pyo")):
                try:
                    _os.unlink(_os.path.join(cache_dir, name))
                except OSError:
                    pass
        try:
            _os.rmdir(cache_dir)
        except OSError:
            pass


def _install_scripts_dir() -> None:
    _sys.dont_write_bytecode = True
    scripts_dir = _os.path.normpath(
        _os.path.dirname(_os.path.abspath(__file__))
    )
    if scripts_dir not in _sys.path:
        _sys.path.insert(0, scripts_dir)
    # Track the runner package's own ``__pycache__`` (sdd_core/) so
    # ``python3 .../sdd_core <script>`` invocations stay cache-free.
    _PYCACHE_PATHS_TO_CLEAN.add(
        _os.path.join(scripts_dir, "sdd_core", "__pycache__"),
    )


def apply(anchor_file: str, depth: int = 1) -> None:
    """Invoked by per-sub-directory ``_bootstrap.py`` shims.

    ``anchor_file`` is the caller's ``__file__``; ``depth`` is the
    number of parent directories to walk up to reach ``scripts/``
    (1 for top-level sub-directories like ``spec/``; 2 for nested
    layouts like ``internal_lints/``).
    """
    _sys.dont_write_bytecode = True
    scripts_dir = str(_Path(anchor_file).resolve().parents[depth])
    if scripts_dir not in _sys.path:
        _sys.path.insert(0, scripts_dir)
    _register_pycache_cleanup(anchor_file)
    if getattr(_sys, "_sdd_bootstrapped", False):
        return
    _sys._sdd_bootstrapped = True  # type: ignore[attr-defined]


if not getattr(_sys, "_sdd_bootstrapped", False):
    _sys._sdd_bootstrapped = True  # type: ignore[attr-defined]
    _install_scripts_dir()
    _atexit.register(_cleanup_leaked_pycache)
