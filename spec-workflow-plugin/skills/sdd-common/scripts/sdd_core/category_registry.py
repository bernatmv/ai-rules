"""Category registry — approval-category defaults and review-type mapping.

Maps each approval category (``spec``, ``steering``, ``discovery``) to a
default target-name value the dispatcher applies when ``--target-name``
is omitted. Categories whose ``default_target_name`` is ``None`` require
an explicit caller-supplied target.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

__all__ = [
    "CategoryDefaults",
    "CATEGORY_REGISTRY",
    "REVIEW_TYPE_TO_CATEGORY",
    "SCHEMA_VERSION",
    "category_from_review_type",
    "default_target_name",
    "is_known_category",
    "known_categories",
    "review_type_for_category",
    "review_types",
]


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CategoryDefaults:
    """Per-category defaults the dispatcher applies at invocation time.

    ``default_target_name`` is ``None`` when the category always requires
    an explicit target (specs and discovery projects have caller-chosen
    names). Steering docs are repo-global so they share a fixed default.
    """

    default_target_name: Optional[str]


# Single declarative table — edits here propagate to both the
# dispatcher (via ``default_target_name`` below) and the doc-lint
# (via ``test_category_registry_docs``). Extending the pipeline with a
# new category means adding one row here and one paragraph to
# ``review-approval-pipeline.md``.
CATEGORY_REGISTRY: dict[str, CategoryDefaults] = {
    "steering": CategoryDefaults(default_target_name="steering"),
    "spec": CategoryDefaults(default_target_name=None),
    "discovery": CategoryDefaults(default_target_name=None),
}


def default_target_name(category: str) -> Optional[str]:
    """Return the ``default_target_name`` configured for *category*.

    Unknown categories return ``None`` — the caller is responsible for
    producing a user-facing error with the known-category list.
    """
    entry = CATEGORY_REGISTRY.get(category)
    if entry is None:
        return None
    return entry.default_target_name


def is_known_category(category: str) -> bool:
    return category in CATEGORY_REGISTRY


def known_categories() -> tuple[str, ...]:
    return tuple(sorted(CATEGORY_REGISTRY.keys()))


# Reviewer-facing review types map onto pipeline categories. ``prd`` is
# the only alias (discovery-category review surface); ``spec`` and
# ``steering`` are identity. Centralised here so emitters and lints can
# depend on the mapping instead of inlining the alias.
REVIEW_TYPE_TO_CATEGORY: dict[str, str] = {
    "spec": "spec",
    "steering": "steering",
    "prd": "discovery",
}


def category_from_review_type(review_type: str) -> str:
    """Translate a reviewer-facing review type into its pipeline category.

    Unknown review types raise :class:`KeyError`; the caller should wrap
    the call site with ``output.error`` to surface a structured failure.
    """
    return REVIEW_TYPE_TO_CATEGORY[review_type]


def review_type_for_category(category: str) -> str:
    """Return the reviewer-facing review type for *category*.

    Inverse of :func:`category_from_review_type`. Unknown categories raise
    :class:`KeyError` so callers never route through a misleading default.
    """
    for review_type, registered_category in REVIEW_TYPE_TO_CATEGORY.items():
        if registered_category == category:
            return review_type
    raise KeyError(category)


def review_types() -> tuple[str, ...]:
    """Return the sorted tuple of known reviewer-facing review types."""
    return tuple(sorted(REVIEW_TYPE_TO_CATEGORY.keys()))
