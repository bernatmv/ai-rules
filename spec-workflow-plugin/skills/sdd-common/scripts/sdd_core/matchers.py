"""Reusable word/phrase matching without hand-crafted regex alternations.

Stores words as a frozenset (readable, extensible, introspectable) and
auto-compiles an optimized regex. Multi-word phrases are sorted
longest-first so "looks good" matches before "good".

This is a library module — import and use, do not execute directly:
    from sdd_core.matchers import WordMatcher

Three usage shapes:

1. Standalone matching — ``matcher.search(text)`` / ``matcher.match(text)``
   use the configured ``boundary`` mode directly.

2. Embed in a larger regex — ``matcher.pattern_fragment()`` returns a
   non-capturing alternation ``(?:phrase1|phrase2|…)`` with no
   boundaries, suitable for composition inside any outer pattern.

3. Compose with structural shell — ``matcher.compose(prefix=r"^##\\s+")``
   returns a compiled :class:`re.Pattern` built from
   ``prefix + (?:phrases|extra_alternatives) + suffix``. The matcher's
   flags (e.g. :data:`re.IGNORECASE`) are inherited. This is the
   recommended replacement for ``re.compile(r"…" + m.regex.pattern[2:])``
   slicing tricks.
"""
from __future__ import annotations

import re
from typing import Iterable

__all__ = ["WordMatcher", "VALID_BOUNDARIES"]

VALID_BOUNDARIES = frozenset({"start", "word", "delimited", "none"})


class WordMatcher:
    """Match text against an extensible word/phrase set.

    Parameters
    ----------
    words:
        Words or phrases to match. Must be non-empty.
    case_sensitive:
        Default False.
    boundary:
        ``"start"`` — ``^(w1|w2)\\b``  (e.g. affirming feedback)
        ``"word"``  — ``\\b(w1|w2)\\b`` (general word boundary)
        ``"delimited"`` — between ``-``, ``_``, or string edges (e.g. spec names)
        ``"none"``  — match anywhere (e.g. metadata markers)

    Raises
    ------
    ValueError
        If *words* is empty or *boundary* is not one of the valid modes.
    """

    __slots__ = ("_words", "_re", "_boundary", "_case_sensitive", "_fragment")

    def __init__(
        self,
        words: Iterable[str],
        *,
        case_sensitive: bool = False,
        boundary: str = "word",
    ) -> None:
        self._words = frozenset(words)
        if not self._words:
            raise ValueError(
                "WordMatcher requires at least one word. "
                "Got an empty collection."
            )
        if boundary not in VALID_BOUNDARIES:
            raise ValueError(
                f"Unknown boundary mode {boundary!r}. "
                f"Valid modes: {', '.join(sorted(VALID_BOUNDARIES))}"
            )
        self._case_sensitive = case_sensitive
        self._boundary = boundary
        flags = 0 if case_sensitive else re.IGNORECASE
        sorted_words = sorted(self._words, key=len, reverse=True)
        alt = "|".join(re.escape(w) for w in sorted_words)
        # Non-capturing fragment stays the stable composition primitive.
        # ``self._re`` keeps a capturing group for backwards compatibility
        # with callers of ``search(...).group(1)``.
        self._fragment = f"(?:{alt})"

        if boundary == "start":
            pattern = rf"^({alt})\b"
        elif boundary == "word":
            pattern = rf"\b({alt})\b"
        elif boundary == "delimited":
            pattern = rf"(?:^|[-_])({alt})(?:[-_]|$)"
        else:
            pattern = rf"({alt})"

        self._re = re.compile(pattern, flags)

    def match(self, text: str) -> re.Match | None:
        """Apply ``re.match`` (start-of-string) on stripped *text*."""
        return self._re.match(text.strip())

    def search(self, text: str) -> re.Match | None:
        """Apply ``re.search`` (anywhere in string) on *text*."""
        return self._re.search(text)

    def __contains__(self, text: str) -> bool:
        return self.search(text) is not None

    def __repr__(self) -> str:
        return (
            f"WordMatcher({len(self._words)} words, "
            f"boundary={self._boundary!r})"
        )

    @property
    def words(self) -> frozenset[str]:
        return self._words

    @property
    def regex(self) -> re.Pattern:
        return self._re

    @property
    def flags(self) -> int:
        """Return the compiled regex flags (``0`` or :data:`re.IGNORECASE`).

        Exposed so callers composing outside this class can OR the
        matcher's case-sensitivity decision onto their own pattern
        without re-deriving it from ``case_sensitive``.
        """
        return self._re.flags & re.IGNORECASE

    def pattern_fragment(self) -> str:
        """Return the phrase alternation as a non-capturing fragment.

        Shape: ``(?:longest|…|shortest)``. Longest-first sort is
        preserved so composite patterns keep the "longest match wins"
        property. No boundary sentinels, no capturing group — safe to
        embed in any outer regex. This is the stable, public
        composition primitive; avoid reaching into :attr:`regex` for
        string surgery.
        """
        return self._fragment

    def compose(
        self,
        *,
        prefix: str = "",
        suffix: str = "",
        extra_alternatives: Iterable[str] = (),
        extra_flags: int = 0,
    ) -> re.Pattern[str]:
        """Compile ``prefix + (?:<phrases>|<extras>) + suffix``.

        Parameters
        ----------
        prefix, suffix:
            Raw regex snippets placed verbatim on either side of the
            alternation group. The caller owns any structural anchors
            (``^``, ``$``, ``\\s+``) or capture groups needed there.
        extra_alternatives:
            Raw regex tokens OR-ed into the alternation alongside the
            escaped phrases (e.g. ``r"\\[-\\]"``, ``r"FR-\\d"``). Emitted
            verbatim — the caller is responsible for escaping any
            literal metacharacters.
        extra_flags:
            Additional :mod:`re` flags OR-ed with the matcher's own
            flags. Use sparingly; the matcher's case-sensitivity is
            already inherited.

        Returns
        -------
        re.Pattern
            Compiled pattern. The outer ``(?:…)`` is always non-capturing
            so group numbering introduced by ``prefix``/``suffix``
            remains stable.
        """
        extras = tuple(extra_alternatives)
        if extras:
            alternation = "|".join(
                (self._fragment[3:-1], *extras)  # unwrap (?:…) then re-wrap
            )
            group = f"(?:{alternation})"
        else:
            group = self._fragment
        return re.compile(
            f"{prefix}{group}{suffix}",
            self.flags | extra_flags,
        )

    def extended(self, *extra_words: str) -> WordMatcher:
        """Return a new WordMatcher with additional words.

        Preserves boundary mode and case sensitivity from the original.
        """
        return WordMatcher(
            self._words | set(extra_words),
            case_sensitive=self._case_sensitive,
            boundary=self._boundary,
        )
