"""YAML data loaders for ``sdd_core/data/*.yaml`` registries.

Centralises the PyYAML ``safe_load`` + missing-package degradation so
each lint or helper that consumes a phrase / pattern registry shares
one degradation path. Failures (missing file, malformed YAML, missing
optional ``yaml`` dep) return an empty payload so the caller's
hard-coded fallbacks still fire.
"""
from __future__ import annotations

from pathlib import Path

__all__ = ["load_yaml", "load_yaml_phrase_set", "DATA_DIR"]


DATA_DIR = Path(__file__).resolve().parent / "data"


def load_yaml(filename: str) -> dict:
    """Return the parsed YAML payload at ``DATA_DIR/<filename>``.

    Empty dict on any failure (missing file, malformed YAML, missing
    optional ``yaml`` dep) so callers degrade gracefully.
    """
    try:
        import yaml  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return {}
    path = DATA_DIR / filename
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def load_yaml_phrase_set(filename: str, *, key: str) -> tuple[str, ...]:
    """Return the phrase tuple under *key* in ``DATA_DIR/<filename>``.

    Empty tuple on any failure — callers degrade gracefully when PyYAML
    is unavailable or the file is malformed.
    """
    try:
        import yaml  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return ()
    path = DATA_DIR / filename
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ()
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return ()
    raw = data.get(key) or []
    return tuple(str(item) for item in raw if isinstance(item, str))
