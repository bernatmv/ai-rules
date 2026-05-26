"""Text utilities for markdown content processing."""
from __future__ import annotations

import re
from typing import Iterator, Literal

__all__ = [
    "KEBAB_RE",
    "LineCategory",
    "iter_content_lines",
    "iter_indexed_lines",
    "iter_line_categories",
    "iter_stripped_lines",
    "iter_paragraphs",
    "extract_sections",
    "ordinal",
]


_ORDINAL_WORDS: dict[int, str] = {
    1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
    6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth",
}


def ordinal(n: int) -> str:
    """Return the human-readable ordinal word for ``n``.

    Falls back to the numeric ``Nth`` suffix form for values outside the
    1..10 vocabulary so callers never need a guard.
    """
    word = _ORDINAL_WORDS.get(n)
    if word:
        return word
    suffix = "th"
    if n % 100 not in (11, 12, 13):
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"

KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


LineCategory = Literal[
    "effective", "blank", "frontmatter", "code_block", "html_comment",
]

_HTML_COMMENT_OPEN = "<!--"
_HTML_COMMENT_CLOSE = "-->"


def iter_line_categories(
    content: str,
) -> Iterator[tuple[int, str, str, LineCategory]]:
    """Yield ``(line_index, raw_line, stripped, category)`` per physical line.

    Category partition is exhaustive — every line maps to one of:
      * ``effective``    — prose, tables, list markers, headings
      * ``blank``        — empty or whitespace-only
      * ``frontmatter``  — inside the leading ``---`` block
      * ``code_block``   — between ```` ``` ```` fences (fences included)
      * ``html_comment`` — inside a multi-line ``<!-- … -->``
    """
    in_frontmatter = False
    in_code_block = False
    in_html_comment = False

    for i, raw in enumerate(content.splitlines()):
        stripped = raw.strip()
        if i == 0 and stripped == "---":
            in_frontmatter = True
            yield i, raw, stripped, "frontmatter"
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            yield i, raw, stripped, "frontmatter"
            continue
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            yield i, raw, stripped, "code_block"
            continue
        if in_code_block:
            yield i, raw, stripped, "code_block"
            continue
        if in_html_comment:
            yield i, raw, stripped, "html_comment"
            if _HTML_COMMENT_CLOSE in raw:
                in_html_comment = False
            continue
        if stripped.startswith(_HTML_COMMENT_OPEN):
            if _HTML_COMMENT_CLOSE not in raw[len(_HTML_COMMENT_OPEN):]:
                in_html_comment = True
            yield i, raw, stripped, "html_comment"
            continue
        if not stripped:
            yield i, raw, stripped, "blank"
            continue
        yield i, raw, stripped, "effective"


def iter_content_lines(content: str) -> Iterator[tuple[int, str, str]]:
    """Yield (line_index, raw, stripped) skipping frontmatter and code blocks.

    Thin filter over :func:`iter_line_categories` — the single
    classifier is the source of truth. Frontmatter and code-block
    partitions are excluded here; blank lines and HTML comments still
    flow through so paragraph-boundary consumers behave unchanged.
    """
    excluded = {"frontmatter", "code_block"}
    for i, raw, stripped, category in iter_line_categories(content):
        if category in excluded:
            continue
        yield i, raw, stripped


def iter_indexed_lines(content: str) -> Iterator[tuple[int, str]]:
    """Yield (line_index, raw_line) skipping frontmatter and code blocks."""
    return ((i, raw) for i, raw, _ in iter_content_lines(content))


def iter_stripped_lines(content: str) -> Iterator[str]:
    """Yield stripped lines, skipping frontmatter and code blocks."""
    return (stripped for _, _, stripped in iter_content_lines(content))


def iter_paragraphs(content: str) -> Iterator[tuple[int, str]]:
    """Yield ``(start_line_0based, collapsed_paragraph)`` per paragraph.

    Soft line-breaks inside a paragraph are collapsed to single spaces so
    paragraph-level regexes match wrapped content. Blank lines are
    paragraph boundaries. Frontmatter and fenced code blocks are skipped
    via ``iter_content_lines`` — identical exclusions to the other
    content scanners (single source of truth for what "content" means).

    ``start_line`` is the 0-based index of the paragraph's first line in
    the source document; call-sites that emit human-facing line numbers
    must add ``1``.
    """
    buf: list[str] = []
    start_line: int | None = None
    for i, _raw, stripped in iter_content_lines(content):
        if stripped == "":
            if buf:
                yield (start_line if start_line is not None else 0,
                       re.sub(r"\s+", " ", " ".join(buf)).strip())
                buf, start_line = [], None
            continue
        if start_line is None:
            start_line = i
        buf.append(stripped)
    if buf:
        yield (start_line if start_line is not None else 0,
               re.sub(r"\s+", " ", " ".join(buf)).strip())


def extract_sections(
    content: str,
    *,
    strip_frontmatter: bool = True,
    skip_code_fences: bool = True,
) -> dict[str, str]:
    """Parse markdown into ``{heading: body_content}`` dict.

    Parameters
    ----------
    strip_frontmatter : bool
        When *True* (default), YAML frontmatter is ignored.
    skip_code_fences : bool
        When *True* (default), fenced code blocks are ignored so
        headings inside code fences are not treated as section breaks.

    When both flags are *True*, this is equivalent to the previous
    ``sdd_core.specs.extract_sections``.  When both are *False*, it
    behaves like the simple ``prd.shared.extract_sections``.
    """
    sections: dict[str, str] = {}
    current_heading: str | None = None
    current_lines: list[str] = []

    if strip_frontmatter or skip_code_fences:
        line_iter: Iterator[tuple[int, str]] = iter_indexed_lines(content)
    else:
        line_iter = enumerate(content.splitlines())

    for _, raw_line in line_iter:
        m = re.match(r"^(#{1,6})\s+(.*)", raw_line)
        if m:
            if current_heading is not None:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = m.group(2).strip()
            current_lines = []
        elif current_heading is not None:
            current_lines.append(raw_line)

    if current_heading is not None:
        sections[current_heading] = "\n".join(current_lines).strip()

    return sections
