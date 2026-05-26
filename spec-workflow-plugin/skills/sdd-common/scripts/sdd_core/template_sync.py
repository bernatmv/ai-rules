"""Sync default templates to workspace and manage user-templates."""
from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import paths
from .template_resolution import get_reference_dir

__all__ = [
    "SyncResult",
    "hash_template",
    "sync_defaults_to_workspace",
    "sync_user_templates_readme",
]


CONTENT_HASH_LENGTH = 12  # hex chars — enough uniqueness for display, not security


def hash_template(path: Path) -> str:
    """SHA-256 of template content with trailing whitespace stripped per line.

    Returns the first CONTENT_HASH_LENGTH hex characters for readability.
    """
    content = path.read_text(encoding="utf-8")
    normalized = "\n".join(line.rstrip() for line in content.splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:CONTENT_HASH_LENGTH]


@dataclass
class SyncResult:
    copied: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def sync_defaults_to_workspace(
    root: Path,
    reference_dir: Path | None = None,
) -> SyncResult:
    """Copy all reference templates to .spec-workflow/templates/."""
    ref_dir = get_reference_dir(reference_dir)
    target_dir = paths.templates_dir(root, user=False)
    target_dir.mkdir(parents=True, exist_ok=True)

    result = SyncResult()

    if not ref_dir.is_dir():
        result.failed.append(f"Reference directory not found: {ref_dir}")
        return result

    for src_path in sorted(ref_dir.glob(paths.TEMPLATE_GLOB)):
        dst_path = target_dir / src_path.name
        try:
            if dst_path.is_file():
                existing = dst_path.read_text(encoding="utf-8")
                incoming = src_path.read_text(encoding="utf-8")
                if existing != incoming and existing.strip():
                    local_hash = hash_template(dst_path)
                    ref_hash = hash_template(src_path)
                    result.warnings.append(
                        f"{src_path.name}: local copy differs from reference "
                        f"(local: {local_hash}, ref: {ref_hash}) — overwriting. "
                        f"To keep local: move to user-templates/{src_path.name}. "
                        f"To overwrite intentionally: sdd sync templates --force"
                    )
            shutil.copy2(str(src_path), str(dst_path))
            result.copied.append(src_path.name)
        except OSError as e:
            result.failed.append(f"{src_path.name}: {e}")

    return result


def sync_user_templates_readme(
    workflow_root: Path,
    created: list[str],
    skipped: list[str],
    *,
    reference_dir: Path | None = None,
    warn_callback=None,
) -> None:
    """Copy the user-templates README from the reference dir."""
    ref_dir = get_reference_dir(reference_dir)
    readme_src = ref_dir / "user-templates-readme.md"
    readme_dst = workflow_root / "user-templates" / "README.md"
    if readme_src.is_file():
        shutil.copy2(str(readme_src), str(readme_dst))
        created.append("user-templates/README.md")
    else:
        if warn_callback:
            warn_callback(f"Reference README not found: {readme_src}")
        skipped.append("user-templates/README.md")
