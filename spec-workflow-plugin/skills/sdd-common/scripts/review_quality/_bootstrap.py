"""Path anchor — see references/script-conventions.md § Bootstrap Pattern."""
import sys as _sys

_sys.dont_write_bytecode = True

from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
import _sdd_bootstrap  # noqa: F401

_sdd_bootstrap.apply(__file__)
