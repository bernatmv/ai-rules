"""Find and resolve template paths."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from . import paths

__all__ = [
    "ALL_TEMPLATE_TYPES",
    "ResolvedTemplate",
    "TemplateInfo",
    "resolve_template",
    "list_templates",
    "get_reference_dir",
]

_DEFAULT_REFERENCE_DIR = (
    Path(__file__).parent.parent.parent / "references" / "default-templates"
)

_FALLBACK_TEMPLATE_STEMS = [
    "bug-fix-design",
    "bug-fix-requirements",
    "bug-fix-tasks",
    "design",
    "prd",
    "product",
    "requirements",
    "structure",
    "tasks",
    "tech",
    "ui-design",
    "workspace-requirements",
]


def _discover_template_types() -> list[str]:
    """Derive template types from the reference directory (single source of truth).

    Falls back to a hardcoded list when the reference directory is missing
    (e.g., running outside the full skill tree).
    Uses _DEFAULT_REFERENCE_DIR directly (no override at module load time).
    """
    if not _DEFAULT_REFERENCE_DIR.is_dir():
        return list(_FALLBACK_TEMPLATE_STEMS)
    return sorted(
        p.name.removesuffix(paths.TEMPLATE_SUFFIX)
        for p in _DEFAULT_REFERENCE_DIR.glob(paths.TEMPLATE_GLOB)
    )


ALL_TEMPLATE_TYPES = _discover_template_types()


@dataclass
class ResolvedTemplate:
    path: Path
    source: Literal["user", "default"]
    doc_type: str


@dataclass
class TemplateInfo:
    doc_type: str
    has_default: bool
    has_custom: bool
    resolved_path: Path | None
    resolved_source: str | None


def _template_dirs(root: Path) -> tuple[Path, Path]:
    """Return (user_dir, default_dir) for template resolution."""
    return paths.templates_dir(root, user=True), paths.templates_dir(root, user=False)


def resolve_template(doc_type: str, root: Path) -> ResolvedTemplate | None:
    """Resolve template with user-templates/ priority over templates/."""
    user_dir, default_dir = _template_dirs(root)
    filename = f"{doc_type}-template.md"

    user_path = user_dir / filename
    if user_path.is_file():
        return ResolvedTemplate(path=user_path, source="user", doc_type=doc_type)

    default_path = default_dir / filename
    if default_path.is_file():
        return ResolvedTemplate(path=default_path, source="default", doc_type=doc_type)

    return None


def list_templates(root: Path) -> list[TemplateInfo]:
    """Enumerate all template types with resolution status."""
    user_dir, default_dir = _template_dirs(root)
    results = []
    for doc_type in ALL_TEMPLATE_TYPES:
        filename = f"{doc_type}-template.md"
        user_path = user_dir / filename
        default_path = default_dir / filename

        has_custom = user_path.is_file()
        has_default = default_path.is_file()

        if has_custom:
            resolved_path, resolved_source = user_path, "user"
        elif has_default:
            resolved_path, resolved_source = default_path, "default"
        else:
            resolved_path, resolved_source = None, None

        results.append(TemplateInfo(
            doc_type=doc_type,
            has_default=has_default,
            has_custom=has_custom,
            resolved_path=resolved_path,
            resolved_source=resolved_source,
        ))
    return results


def get_reference_dir(override: Path | None = None) -> Path:
    """Return path to default-templates/."""
    return override or _DEFAULT_REFERENCE_DIR
