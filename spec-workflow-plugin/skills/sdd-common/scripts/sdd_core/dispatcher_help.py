"""Shared helpers for the pipeline-tick dispatcher and its peers.

Extracted from ``review/pipeline-tick.py`` so other entry points
(``prepare-pipeline.py``, future dispatchers / ``pipeline-run.py``) can
consume the same rendering + auto-promotion logic without copy-pasting
the 200 lines it used to occupy inline.

Three public helpers:

* :func:`promote_inline_flags` — splits ``unknown`` argv tokens into
  ``(promoted, residue)`` against a set of accepted flags. Handles
  bare-flag + adjacent-positional grammar (``--flag value``) without
  double-counting ``--flag=value`` pairs.
* :func:`render_phase_help` — builds the structured ``did_you_mean``
  hint text the dispatcher emits when a residue is non-empty. Pure
  function: takes phase name + accepted-flag set + the unknown tokens,
  returns a ``list[str]`` ready for ``"\\n".join(...)``.
* :func:`lifecycle_passthrough_flags` — returns the fixed set of
  lifecycle flags every phase accepts on the shared parent parser.
  Single source of truth for ``pipeline-tick.py`` and any future
  dispatcher that needs to guarantee a flag is always promote-able.

The module is under ``sdd_core`` rather than ``review/`` because the
lifecycle flags + promotion grammar are part of the script-agnostic CLI
contract; review-specific details (phase registry reflection) stay in
``pipeline-tick.py``.
"""
from __future__ import annotations

import difflib
from typing import Iterable


__all__ = [
    "DIFFLIB_UNKNOWN_FLAG_CUTOFF",
    "lifecycle_passthrough_flags",
    "promote_inline_flags",
    "render_phase_help",
]


# difflib cutoff — see ``util/script-index.py`` for the sibling
# constants. Lower than the reverse-flag lookup in
# ``util/script-index.py`` (0.5) because phase flag names share prefixes
# (``--doc-list`` vs ``--doc-path``) that we still want to surface;
# higher than the fuzzy-path tier (0.3) because false positives here
# tell the agent to rename to a still-wrong flag.
DIFFLIB_UNKNOWN_FLAG_CUTOFF = 0.4


# Lifecycle flags the shared parent parser of ``prepare-pipeline.py``
# accepts for every phase. Keep the module-level frozenset as the
# single source of truth; tests assert ``prepare-pipeline.py`` registers
# at least these flags so the two files cannot drift.
_LIFECYCLE_FLAGS: frozenset[str] = frozenset({
    "--parent-todo", "--parent-todo-content", "--gate-id",
})


def lifecycle_passthrough_flags() -> frozenset[str]:
    """Return the set of lifecycle flags valid on every phase.

    Accessor (rather than a direct import of the frozenset) so callers
    that want a defensive copy or a test-time override have a hook. The
    dispatcher unions this with a phase-specific ``accepted_flags`` set
    before calling :func:`promote_inline_flags`.
    """
    return _LIFECYCLE_FLAGS


def promote_inline_flags(
    unknown: list[str], accepted: Iterable[str],
) -> tuple[list[str], list[str]]:
    """Split ``unknown`` argv tokens into ``(promoted, residue)``.

    Tokens beginning ``--`` are promoted when their flag name (prefix
    before ``=``) appears in ``accepted``. Any bare-flag token without
    an ``=`` consumes the adjacent non-flag positional as its value,
    matching argparse's own grammar. Residue tokens carry the same
    look-ahead so the caller can render them back for a clean error
    hint.

    ``accepted`` is consumed once via ``frozenset(...)`` so callers can
    pass any iterable (set, frozenset, list) without paying O(n²) for
    membership checks.
    """
    accepted_set = frozenset(accepted)
    promoted: list[str] = []
    residue: list[str] = []

    def _consume_value(i: int, target: list[str]) -> int:
        """Append ``unknown[i]`` to *target*; consume the adjacent
        positional value when the flag was passed without ``=``.
        Returns the new index (caller bumps by 1 afterwards).
        """
        tok = unknown[i]
        target.append(tok)
        if "=" not in tok and i + 1 < len(unknown) \
                and not unknown[i + 1].startswith("--"):
            target.append(unknown[i + 1])
            return i + 1
        return i

    i = 0
    while i < len(unknown):
        tok = unknown[i]
        if tok.startswith("--"):
            flag = tok.split("=", 1)[0]
            target = promoted if flag in accepted_set else residue
            i = _consume_value(i, target)
        else:
            residue.append(tok)
        i += 1
    return promoted, residue


def render_phase_help(
    unknown: list[str], phase: str, accepted: Iterable[str],
    *, cutoff: float = DIFFLIB_UNKNOWN_FLAG_CUTOFF,
) -> list[str]:
    """Return the hint lines for a ``did_you_mean``-style error.

    Separates data construction (close-match lookup) from rendering
    (``"\\n".join``) and from the ``output.error`` side effect — the
    caller composes the final envelope. Rendering is deterministic:
    sorted accepted-flag list, stable close-match output.
    """
    accepted_sorted = sorted(accepted)
    flags = [tok.split("=", 1)[0] for tok in unknown if tok.startswith("--")]
    suggestions: dict[str, list[str]] = {}
    for flag in flags:
        close = difflib.get_close_matches(
            flag, accepted_sorted, n=3, cutoff=cutoff,
        )
        if close:
            suggestions[flag] = close
    hint_lines = [
        f"Phase '{phase}' does not accept: "
        f"{', '.join(flags) or ' '.join(unknown)}.",
    ]
    if suggestions:
        hint_lines.append("Closest accepted phase flags:")
        for bad, near in suggestions.items():
            hint_lines.append(f"  {bad} -> {', '.join(near)}")
    hint_lines.append(
        f"Phase flags accepted by '{phase}': "
        + (", ".join(accepted_sorted) or "(none)")
    )
    hint_lines.append(
        "Either rerun with the correct flag, or place phase flags after "
        "a bare `--` separator (e.g. "
        "`pipeline-tick --category C --target-name N -- --flag value`)."
    )
    return hint_lines
