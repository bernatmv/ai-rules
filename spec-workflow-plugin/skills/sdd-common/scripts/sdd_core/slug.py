"""Kebab-case slug suggestions for spec naming.

``spec/check-status.py --suggest-name "free text"`` emits 2–3 candidates
alongside the exact AskQuestion payload so the agent does not decide
*whether* to ask.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

__all__ = [
    "Suggestion",
    "suggest",
    "build_ask_question_payload",
    "RESERVED_NAMES",
    "MAX_CANDIDATES",
    "MAX_SLUG_CHARS",
]


# Slugs we never hand out — they collide with workflow conventions or
# reserved directory names. Deliberately short list; extend sparingly.
RESERVED_NAMES: frozenset[str] = frozenset(
    {
        "archive", "archived", "default", "draft", "example", "new",
        "spec", "steering", "template", "templates", "test", "workspace",
    }
)

# Three candidates is the sweet spot for an AskQuestion prompt — more
# options dilute the signal and longer lists push the user toward
# skimming rather than choosing.
MAX_CANDIDATES = 3
# 60 chars keeps slugs shell-pasteable and well under the 255-char path
# limit on common filesystems once combined with workspace prefixes.
MAX_SLUG_CHARS = 60

_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "can", "do",
        "for", "from", "i", "if", "in", "is", "it", "of", "on", "or",
        "our", "please", "should", "so", "that", "the", "then", "this",
        "to", "want", "we", "with", "would",
    }
)


@dataclass(frozen=True)
class Suggestion:
    """One kebab-case candidate plus the rationale for debug/telemetry."""

    slug: str
    source: str  # 'stem', 'verb-noun', 'hash-suffixed'

    def to_payload(self) -> dict:
        return {"slug": self.slug, "source": self.source}


def _tokens(text: str) -> list[str]:
    raw = re.sub(r"[^a-zA-Z0-9]+", " ", (text or "").strip().lower())
    tokens = [t for t in raw.split() if t]
    # Drop stop-words unless they are the only tokens.
    filtered = [t for t in tokens if t not in _STOP_WORDS]
    return filtered or tokens


def _kebab(tokens: Iterable[str]) -> str:
    return "-".join(tokens)


def _clamp(slug: str) -> str:
    if len(slug) <= MAX_SLUG_CHARS:
        return slug
    return slug[:MAX_SLUG_CHARS].rstrip("-")


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _candidates(text: str) -> list[Suggestion]:
    tokens = _tokens(text)
    if not tokens:
        return []

    candidates: list[Suggestion] = []
    stem = _clamp(_kebab(tokens[:4]))
    if stem:
        candidates.append(Suggestion(stem, "stem"))

    if len(tokens) >= 2:
        pair = _clamp(_kebab([tokens[0], tokens[-1]]))
        if pair and pair != stem:
            candidates.append(Suggestion(pair, "verb-noun"))

    if len(tokens) >= 3:
        triple = _clamp(_kebab(tokens[:3]))
        if triple and triple not in (stem, candidates[-1].slug if candidates else None):
            candidates.append(Suggestion(triple, "triple"))

    return candidates


def _compact_candidate(
    tokens: list[str],
    *,
    max_tokens: int = 3,
    min_salience_len: int = 4,
    max_chars: int = 20,
) -> "Suggestion | None":
    """Return one nouns-only / salience-filtered compact candidate.

    Picks the most distinctive tokens (length ≥ ``min_salience_len``,
    order-preserving) and collapses them into a kebab-case slug capped
    at ``max_tokens`` tokens / ``max_chars`` characters. Returns
    ``None`` when the input has fewer than two salient tokens — callers
    then fall back to the existing ``_candidates`` stem / verb-noun
    / triple strategies.

    Ensures ``suggest()`` always offers at least one ≤ 3 token / ≤ 20
    char slug when the free text has ≥ 2 salient tokens — the long
    compound candidates in ``_candidates`` / ``_discovery_aligned``
    are compounding-first and miss this niche.
    """
    salient = [t for t in tokens if len(t) >= min_salience_len]
    if len(salient) < 2:
        return None
    picked = salient[:max_tokens]
    slug = _kebab(picked)
    if len(slug) > max_chars:
        # Trim token-by-token from the right until we fit the char cap.
        while picked and len(_kebab(picked)) > max_chars:
            picked = picked[:-1]
        slug = _kebab(picked)
        if len(picked) < 2 or not slug:
            return None
    return Suggestion(slug, "compact")


def _discovery_aligned_candidates(
    free_text: str,
    discovery_projects: Iterable[str],
    related_prd_titles: Iterable[str],
) -> list[Suggestion]:
    """Append one discovery-aligned candidate when the free text
    overlaps with an existing discovery project or PRD title.

    Kept additive — the base strategies in ``_candidates`` are never
    rewritten. A candidate is emitted when any free-text token appears
    in either the discovery project name or a linked PRD title. The
    slug is built from the free-text tokens, prepended with the matched
    project name so the suggestion visibly traces back to the approved
    PRD context (honest "do not fabricate": every candidate references
    a known artefact).
    """
    text_tokens = set(_tokens(free_text))
    if not text_tokens:
        return []

    seen: set[str] = set()
    out: list[Suggestion] = []

    def _matches(haystack: str) -> bool:
        return bool(text_tokens & set(_tokens(haystack)))

    # Prefer project-name matches first: the folder name is already a
    # kebab-case slug, so re-using it keeps the suggestion byte-identical
    # to the project naming convention.
    projects = [p for p in discovery_projects if p]
    for project in projects:
        if not _matches(project):
            continue
        base_tokens = _tokens(free_text) or _tokens(project)
        project_tokens = _tokens(project)
        merged: list[str] = []
        for tok in project_tokens + base_tokens:
            if tok not in merged:
                merged.append(tok)
        slug = _clamp(_kebab(merged))
        if slug and slug not in seen:
            seen.add(slug)
            out.append(Suggestion(slug, "discovery-aligned"))

    # PRD-title match: hand off the project name when we can tell which
    # project owns the title. Absent that signal, the title itself is
    # the rationale — tokens come from both PRD title and the free text
    # so the candidate stays anchored to the user's wording.
    for title in related_prd_titles or ():
        if not title or not _matches(title):
            continue
        title_tokens = _tokens(title)
        base_tokens = _tokens(free_text)
        merged: list[str] = []
        for tok in title_tokens + base_tokens:
            if tok not in merged:
                merged.append(tok)
        slug = _clamp(_kebab(merged[:6]))
        if slug and slug not in seen:
            seen.add(slug)
            out.append(Suggestion(slug, "discovery-aligned"))

    return out


def _disambiguate(slug: str, taken: set[str]) -> str:
    if slug not in taken:
        return slug
    for i in range(2, 6):
        cand = _clamp(f"{slug}-{i}")
        if cand not in taken:
            return cand
    return _clamp(f"{slug}-v2")


def suggest(
    free_text: str,
    existing: Iterable[str] = (),
    archived: Iterable[str] = (),
    *,
    max_candidates: int = MAX_CANDIDATES,
    discovery_projects: Iterable[str] = (),
    related_prd_titles: Iterable[str] = (),
) -> list[Suggestion]:
    """Return up to ``max_candidates`` slug suggestions for ``free_text``.

    * Filters reserved names.
    * De-duplicates against ``existing`` + ``archived`` (case-insensitive)
      by appending ``-2``, ``-3``… suffixes.
    * Deterministic given identical inputs.
    * When ``discovery_projects`` or ``related_prd_titles`` intersect
      the free text, prepends one ``discovery-aligned`` candidate so
      overlaps with an approved PRD project surface a spec slug
      anchored to that project. The base stem / verb-noun / triple
      strategies are unchanged — callers passing empty defaults get
      byte-identical output to the context-free behaviour.
    """
    existing_set = {str(s).lower() for s in existing} | {str(s).lower() for s in archived}
    taken = set(existing_set)

    # Order candidates so the agent sees the most actionable choice
    # first: a compact nouns-only slug (when the text has salient
    # tokens), then any discovery-aligned matches, then the base
    # stem / verb-noun / triple strategies. Each source is additive
    # — later sources fill the cap only if earlier ones didn't.
    tokens = _tokens(free_text)
    raw: list[Suggestion] = []
    compact = _compact_candidate(tokens)
    if compact is not None:
        raw.append(compact)
    raw.extend(
        _discovery_aligned_candidates(
            free_text, discovery_projects, related_prd_titles,
        )
    )
    raw.extend(_candidates(free_text))

    uniq: list[Suggestion] = []
    seen_slugs: set[str] = set()
    for cand in raw:
        slug = cand.slug
        if slug in RESERVED_NAMES:
            continue
        if slug in seen_slugs:
            continue
        if slug in taken:
            slug = _disambiguate(slug, taken)
            cand = Suggestion(slug, f"{cand.source}+suffixed")
        if not slug:
            continue
        taken.add(slug)
        seen_slugs.add(slug)
        uniq.append(cand)
        if len(uniq) >= max_candidates:
            break
    return uniq


def build_ask_question_payload(
    free_text: str,
    suggestions: Iterable[Suggestion],
) -> dict:
    """Return the ``AskQuestion`` payload plus user-facing prompt string."""
    options = [
        {"id": s.slug, "label": s.slug} for s in suggestions
    ]
    options.append({"id": "__user_choice__", "label": "Choose a different name"})
    prompt = (
        f"Which slug should we use for the spec derived from "
        f"{free_text!r}?"
    )
    return {
        "user_question_prompt": prompt,
        "ask_question_payload": {
            "questions": [
                {
                    "id": "spec_slug",
                    "prompt": prompt,
                    "options": options,
                }
            ]
        },
    }
