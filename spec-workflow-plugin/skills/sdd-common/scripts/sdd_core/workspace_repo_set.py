"""Single normaliser for repo-set comparison across manifest + tracker.

The coordination manifest stores repos under ``id``/``path``/``subSpec``
field names; the workspace tracker stores them under ``repoId``/
``repoPath``/``subSpecName``. Both call sites need the same projection
shape (sorted, hashable tuples) for byte-stable equality checks against
a supplied repo set. Sharing one helper guarantees the projection rule
stays identical.
"""
from __future__ import annotations

from typing import Literal

__all__ = ["normalise_repo_set"]


KeyField = Literal["id", "repoId"]


def normalise_repo_set(
    repos: list[dict] | None,
    *,
    key_field: KeyField,
) -> list[tuple[str, str, str, str]]:
    """Return a sorted, hashable projection used to compare repo sets.

    Each tuple is ``(repoType, id, path, subSpec)`` lowercased on the
    type so trivial casing diffs do not cause false drift. The
    ``key_field`` argument selects which alternate field names to read
    (manifest uses ``id``/``path``/``subSpec``; tracker uses
    ``repoId``/``repoPath``/``subSpecName``).
    """
    if key_field == "id":
        id_keys = ("id",)
        path_keys = ("path",)
        sub_keys = ("subSpec",)
    else:
        id_keys = ("id", "repoId")
        path_keys = ("path", "repoPath")
        sub_keys = ("subSpec", "subSpecName")

    out: list[tuple[str, str, str, str]] = []
    for r in repos or []:
        out.append((
            (r.get("repoType") or "").lower(),
            _first(r, id_keys),
            _first(r, path_keys),
            _first(r, sub_keys),
        ))
    return sorted(out)


def _first(record: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = record.get(key)
        if value:
            return value
    return ""
