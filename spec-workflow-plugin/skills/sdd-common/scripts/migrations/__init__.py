"""Shared artifact migration framework.

Public API
----------
migrate(data, target_version)
    Apply all registered migrations in sequence from the artifact's current
    schema_version up to target_version. Idempotent.

register(from_ver, to_ver)
    Decorator to register a migration step function.

Generic utilities (reusable across all migration steps)
-------------------------------------------------------
relocate_fields(data, destinations)
    Move root-level fields into named namespaces, keyed by review_type.
rename_fields(data, renames)
    Rename root-level fields.
set_defaults(data, defaults)
    Add fields with defaults if absent.
transform_nested(data, path, fn)
    Apply a function to all values matching a dot-glob path.

All utilities are idempotent when composed with idempotent arguments.
"""

from __future__ import annotations

from typing import Any, Callable

MigrationFn = Callable[[dict], dict]
_REGISTRY: list[tuple[tuple[int, ...], tuple[int, ...], MigrationFn]] = []


def _parse_semver(v: str) -> tuple:
    return tuple(int(x) for x in v.split("."))


def register(from_ver: str, to_ver: str) -> Callable[[MigrationFn], MigrationFn]:
    """Decorator: register a migration step function for a version range."""
    def decorator(fn: MigrationFn) -> MigrationFn:
        _REGISTRY.append((_parse_semver(from_ver), _parse_semver(to_ver), fn))
        _REGISTRY.sort(key=lambda t: t[0])
        return fn
    return decorator


def migrate(data: dict, target_version: str) -> dict:
    """Apply all pending migrations up to target_version. Idempotent."""
    try:
        current = _parse_semver(str(data.get("schema_version", "1.0.0")))
        target = _parse_semver(target_version)
    except (ValueError, IndexError):
        return data
    for from_v, to_v, fn in _REGISTRY:
        if current >= from_v and current < to_v <= target:
            data = fn(data)
            data["schema_version"] = ".".join(str(x) for x in to_v)
            current = to_v
    return data



def relocate_fields(
    data: dict,
    destinations: dict,
    type_key: str = "review_type",
) -> None:
    """Move root-level fields into named namespaces, keyed by a type discriminator.

    destinations: { namespace: { type_value: [field, ...] } }
    Idempotent.
    """
    type_val = data.get(type_key, "")
    for namespace, type_fields in destinations.items():
        target: dict = data.pop(namespace, {})
        for key in type_fields.get(type_val, []):
            if key in data:
                target[key] = data.pop(key)
        data[namespace] = target


def rename_fields(data: dict, renames: dict) -> None:
    """Rename root-level fields. Idempotent — skips if old absent or new exists."""
    for old, new in renames.items():
        if old in data and new not in data:
            data[new] = data.pop(old)


def set_defaults(data: dict, defaults: dict) -> None:
    """Add fields with defaults if absent. Idempotent."""
    for key, default in defaults.items():
        data.setdefault(key, default)


def transform_nested(
    data: dict, path: str, fn: Callable[[Any], Any],
) -> None:
    """Apply fn to all values matching a dot-glob path.

    Supports '*' as a wildcard for dict keys at any level.
    """
    parts = path.split(".")
    _walk_and_apply(data, parts, 0, fn)


def _walk_and_apply(node: Any, parts: list, idx: int, fn: Callable) -> Any:
    if idx == len(parts):
        return fn(node)
    key = parts[idx]
    if key == "*" and isinstance(node, dict):
        for k in node:
            result = _walk_and_apply(node[k], parts, idx + 1, fn)
            if result is not None:
                node[k] = result
    elif isinstance(node, dict) and key in node:
        result = _walk_and_apply(node[key], parts, idx + 1, fn)
        if result is not None:
            node[key] = result
    return None


def transpose_namespace_map(
    ns_map: dict,
) -> dict:
    """Transpose {type: {ns: [fields]}} into relocate_fields() shape."""
    result: dict = {}
    for rtype, namespaces in ns_map.items():
        for ns, fields in namespaces.items():
            result.setdefault(ns, {})[rtype] = fields
    return result
