"""Shared CLI argument helpers for SDD workspace scripts."""
from __future__ import annotations

import argparse
import os
import re
import sys
import traceback
from pathlib import Path
from typing import Callable, Final, Literal

from .. import output, paths
from ..paths import CATEGORIES as _CATEGORIES
from ._target_resolver import (
    Family,
    apply_target_to_namespace,
    split_workspace_target,
)


CANONICAL_WORKSPACE_FLAG: Final[str] = "--workspace"
SKIP_AUTO_WORKSPACE_ENV: Final[str] = "SDD_SKIP_AUTO_WORKSPACE"
_DEFAULT_TASKS_FILE_KEY: Final[str] = "tasks_file"
_DEFAULT_TASKS_FILE_SUFFIX: Final[str] = "tasks.md"

__all__ = [
    "add_workspace_arg",
    "add_spec_target_args",
    "add_document_selectors",
    "resolve_files",
    "resolve_spec_target",
    "strict_parser",
    "workspace_parser",
    "resolve_workspace_root",
    "resolve_tracker_root",
    "caller_cwd_before_workspace",
    "run_main",
    "KeyValueAppend",
    "ListExtend",
    "name_type",
    "target_argument",
    "split_workspace_target",
    "apply_target_to_namespace",
    "with_context",
    "resolve_context",
    "TRACKER_ROOT_SENTINEL_COORDINATOR",
    "TRACKER_ROOT_SENTINEL_WORKSPACE",
    "compose_tracker_search_roots",
]


# Stable sentinel literals for ``--tracker-root``. Either explicit form
# resolves deterministically; ``.`` and other relative paths are rejected
# at parse time so the caller's intent is unambiguous after the
# pre-argparse chdir performed by :func:`_apply_workspace_from_argv`.
TRACKER_ROOT_SENTINEL_COORDINATOR: Final[str] = "coordinator"
TRACKER_ROOT_SENTINEL_WORKSPACE: Final[str] = "workspace"


def with_context(*args, **kwargs):
    """Re-export :func:`sdd_core.context.with_context` for ``@cli.with_context``.

    Imported lazily so the ``sdd_core.context`` module (which depends on
    :mod:`sdd_core.transient_state`) is only loaded when a shim actually
    decorates its entry point. The decorator factory signature is
    preserved verbatim.
    """
    from sdd_core.context import with_context as _impl

    return _impl(*args, **kwargs)


def resolve_context(*args, **kwargs):
    """Re-export :func:`sdd_core.context.resolve_context` for inline use.

    Shims call this *after* ``parser.parse_args()`` so the flag layer
    in the resolver chain sees ``args.project_path`` / ``args.target``
    before falling back to session / env / cwd. Use this instead of
    :func:`with_context` when ``main()`` does not accept the parsed
    namespace as a parameter.
    """
    from sdd_core.context import resolve_context as _impl

    return _impl(*args, **kwargs)


def name_type(kind: str) -> Callable[[str], str]:
    """``argparse`` ``type=`` factory — validates identifier flags.

    Wraps :func:`sdd_core.paths.validate_name` so argparse surfaces a
    structured :class:`argparse.ArgumentTypeError` on violation rather
    than a bare ``ValueError`` traceback. Use on every identifier flag
    (``--spec-name``, ``--target-name``, ``--feature``, ``--repo-id``,
    etc.).

    Empty strings are treated as "absent" so ``default=""`` callsites
    can keep their existing semantics — argparse runs ``type`` on
    string defaults, and rejecting them would force a churn-y migration
    to ``default=None``. User-supplied empty values still pass
    ``--flag ""`` through unchanged; downstream code already treats
    empty as missing for these flags.
    """
    from ..paths import validate_name

    def _parse(raw: str) -> str:
        if raw == "":
            return raw
        try:
            return validate_name(raw, kind=kind)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(str(exc)) from exc

    _parse.__name__ = f"name_type[{kind}]"
    return _parse


class ListExtend(argparse.Action):
    """Argparse action that extends a list across repeated flag occurrences.

    Fixes the ``nargs='*'`` footgun where each subsequent flag replaces
    the accumulated list rather than extending it. Drop-in for flags
    that accept positional groups (e.g. ``--options id=a,label=A
    id=b,label=B``).
    """

    def __call__(self, parser, namespace, values, option_string=None):
        existing = getattr(namespace, self.dest, None)
        if existing is None:
            existing = []
        elif not isinstance(existing, list):
            # Fail loudly on malformed defaults — declared default
            # must be a list so accumulation semantics stay extend-only.
            parser.error(
                f"{option_string or self.dest}: default must be a list "
                f"for action=ListExtend (got {type(existing).__name__})"
            )
            return
        if isinstance(values, (list, tuple)):
            existing.extend(values)
        else:
            existing.append(values)
        setattr(namespace, self.dest, existing)


class KeyValueAppend(argparse.Action):
    """Argparse action that accumulates ``key=value`` pairs into a dict.

    Use the repeatable ``--params key=value`` form. Multi-token shape
    (``--params a=1 b=2``) is accepted because argparse already splits
    argv tokens. Bundled multi-pair tokens — whether whitespace-bundled
    (``'a=1 b=2'``) or comma-bundled (``'a=1,b=2,c=3'``) — are rejected
    with a recovery hint pointing at the canonical form. The rejection
    message names the bundle shape so the agent's recovery drops the
    right separator.
    """

    _RECOVERY_HINT = (
        "use the repeatable --params key=value form "
        "(one token per pair, no whitespace/comma bundling); "
        "see prompt-conventions.md § Params Quoting"
    )

    @staticmethod
    def _bundle_shape(tok: str) -> "str | None":
        """Return ``'whitespace-bundled'`` / ``'comma-bundled'`` / ``None``."""
        if "=" not in tok or tok.count("=") < 2:
            return None
        if any(ch.isspace() for ch in tok):
            return "whitespace-bundled"
        if "," in tok:
            return "comma-bundled"
        return None

    def __call__(self, parser, namespace, values, option_string=None):
        existing = getattr(namespace, self.dest, None)
        if existing is None:
            existing = {}
        elif not isinstance(existing, dict):
            parser.error(
                f"{option_string or self.dest}: default must be a dict "
                f"for action=KeyValueAppend (got {type(existing).__name__})"
            )
            return
        iterable = values if isinstance(values, (list, tuple)) else [values]
        label = option_string or self.dest
        for tok in iterable:
            if not isinstance(tok, str):
                parser.error(f"{label}: expected key=value, got {tok!r}")
            shape = self._bundle_shape(tok)
            if shape is not None:
                parser.error(
                    f"{label}: ambiguous {shape} token {tok!r}; "
                    f"{self._RECOVERY_HINT}"
                )
            if "=" not in tok:
                parser.error(f"{label}: expected key=value, got {tok!r}")
            key, _, val = tok.partition("=")
            key = key.strip()
            if not key:
                parser.error(f"{label}: empty key in {tok!r}")
            existing[key] = val.strip()
        setattr(namespace, self.dest, existing)


def add_spec_target_args(
    parser: argparse.ArgumentParser,
    *,
    file_key: str = _DEFAULT_TASKS_FILE_KEY,
    file_suffix: str = _DEFAULT_TASKS_FILE_SUFFIX,
    doc_help: str = "Path to tasks.md",
) -> None:
    """Add --spec-name and optional positional file arg with unified resolution.

    Resolution order: explicit file path > --spec-name resolved path.
    """
    parser.add_argument(file_key, nargs="?", default=None, help=doc_help)
    parser.add_argument("--spec-name", default=None, type=name_type("spec-name"),
                        help="Spec name (resolves to .spec-workflow/specs/<name>/<file>)")


def resolve_spec_target(args: argparse.Namespace, file_key: str = _DEFAULT_TASKS_FILE_KEY,
                        file_suffix: str = _DEFAULT_TASKS_FILE_SUFFIX) -> str:
    """Resolve the target file path from parsed args. Exits on error."""
    explicit = getattr(args, file_key, None)
    if explicit:
        return explicit
    if args.spec_name:
        return f".spec-workflow/specs/{args.spec_name}/{file_suffix}"
    output.error(
        f"Either <{file_key}> or --spec-name is required",
        hint=f"Usage: script.py <path> or script.py --spec-name <name>",
    )


# Document-selector helper — single source of truth for the canonical
# "target a document" flag set shared across review/ and spec/ scripts.


def add_document_selectors(
    parser: argparse.ArgumentParser,
    *,
    file: bool = False,
    file_repeatable: bool = False,
    positional_files: bool = False,
    spec_name: bool = False,
    doc: bool = False,
    doc_list: bool = False,
    category: bool = False,
    template: bool = False,
    category_choices: tuple = _CATEGORIES,
) -> None:
    """Register canonical document-selector flags.

    Parameters
    ----------
    file:
        Register ``--file``; pair with ``file_repeatable=True`` to allow
        repeats.
    positional_files:
        Register ``files`` as a bare ``nargs="*"`` positional. Resolution
        order is enforced by :func:`resolve_files`.
    spec_name:
        Register ``--spec-name`` / ``--target-name`` (synonyms). The
        caller maps the resolved name to a file path — this helper is
        selector-only, not a resolver.
    doc:
        Register ``--doc`` (document filename, e.g. ``requirements.md``).
    doc_list:
        Register ``--doc-list`` (comma-separated filenames). Resolved
        alongside ``--category`` / ``--target-name`` via
        :func:`resolve_files` when ``category`` is also registered.
    category:
        Register ``--category`` (``spec`` / ``steering`` / ``discovery``
        by default; override via ``category_choices``). Enables the
        shared "category + doc-list" locator vocabulary that every
        ``review/*`` script now speaks.
    template:
        Register ``--template`` to override the default template file
        (used by ``check-template-compliance.py``).
    """
    if file:
        action = "append" if file_repeatable else "store"
        parser.add_argument(
            "--file", action=action, default=None if not file_repeatable else None,
            help=(
                "Path to the document file"
                + (" (repeatable)" if file_repeatable else "")
            ),
        )
    if positional_files:
        parser.add_argument(
            "files", nargs="*",
            help="Path(s) to document(s)",
        )
    if spec_name:
        parser.add_argument(
            "--target", "--spec-name", "--target-name",
            dest="spec_name", default=None, type=name_type("spec-name"),
            help=(
                "Spec or target name (resolves to "
                ".spec-workflow/specs/<name>/<doc>). Aliases: "
                "--spec-name, --target-name."
            ),
        )
    if doc:
        parser.add_argument(
            "--doc", "--document",
            dest="doc", default=None,
            help="Document filename (e.g. requirements.md)",
        )
    if doc_list:
        parser.add_argument(
            "--doc-list",
            dest="doc_list", default=None,
            help=(
                "Comma-separated document filenames (e.g. "
                "'product.md,tech.md,structure.md'). Resolved relative "
                "to --category + --target-name when provided."
            ),
        )
    if category:
        parser.add_argument(
            "--category",
            dest="category", default=None,
            choices=category_choices,
            help="Document category for path resolution",
        )
    if template:
        parser.add_argument(
            "--template",
            dest="template", default=None,
            help="Override template path (default: doc-type default)",
        )


def resolve_files(
    args: argparse.Namespace,
    *,
    require_at_least_one: bool = True,
) -> list[str]:
    """Resolve document paths from a helper-registered argparse namespace.

    Precedence (mirrors :func:`add_spec_target_args`):
      1. Explicit ``--file`` (list or scalar).
      2. Bare positional ``files``.
      3. ``--category`` + ``--doc-list`` (optionally with
         ``--target-name`` / ``--spec-name``) — the shared
         review-locator vocabulary.
    """
    collected: list[str] = []

    file_val = getattr(args, "file", None)
    if file_val:
        collected.extend(file_val if isinstance(file_val, list) else [file_val])

    positional = getattr(args, "files", None)
    if positional:
        collected.extend(positional)

    category = getattr(args, "category", None)
    doc_list_raw = getattr(args, "doc_list", None)
    if category and doc_list_raw:
        target_name = getattr(args, "spec_name", None) or getattr(args, "target_name", None) or category
        project_path = getattr(args, "project_path", None) or ""
        doc_dir = paths.doc_dir_path(category, target_name, project_path)
        for fn in (x.strip() for x in doc_list_raw.split(",")):
            if fn:
                collected.append(os.path.join(doc_dir, fn))

    if not collected and require_at_least_one:
        output.error(
            "Document path is required",
            hint=(
                "Pass --file PATH, a bare positional path, "
                "--category <cat> --doc-list a,b,c, or --spec-name NAME."
            ),
        )
    return collected


_UNRECOGNIZED_RE = re.compile(r"unrecognized arguments?:\s*(.+)")


# Legacy → canonical flag map; surfaced via did_you_mean.
_LEGACY_FLAG_REPLACEMENTS: dict[str, tuple[str, ...]] = {
    "--project-path": ("--workspace",),
    "--project_path": ("--workspace",),
}


class _JsonErrorParser(argparse.ArgumentParser):
    """``ArgumentParser`` that emits structured JSON errors via ``output.error``.

    Unknown-flag typos (``unrecognized arguments``) downgrade to a
    ``status=result`` + ``severity=warn`` envelope so callers treat them
    as recoverable typos; the script still exits 1 (argparse semantics).
    Genuine validation / missing-file errors keep the hard-error envelope.
    """

    def error(self, message: str) -> None:  # type: ignore[override]
        match = _UNRECOGNIZED_RE.search(message or "")
        if match:
            self._emit_unknown_flag_warn(match.group(1).strip(), message)
            return
        output.error(message, hint="Run with --help to see available flags")

    def _emit_unknown_flag_warn(self, offending: str, message: str) -> None:
        """Emit the warn envelope described on ``_JsonErrorParser.error``."""
        from ..command_templates import did_you_mean

        typed = offending.split()[0] if offending else ""
        alias_groups: list[tuple[str, ...]] = []
        flat_known: list[str] = []
        for action in self._actions:
            opts = tuple(opt for opt in action.option_strings if opt)
            if not opts:
                continue
            alias_groups.append(opts)
            for opt in opts:
                if opt not in flat_known:
                    flat_known.append(opt)

        legacy = _LEGACY_FLAG_REPLACEMENTS.get(typed)
        if legacy:
            suggestions = list(legacy)
        else:
            primary = did_you_mean(typed, flat_known) if typed else []
            suggestions = _expand_alias_groups(primary, alias_groups)

        sibling_hint = _sibling_flag_hint(
            typed, sys.argv[0] if sys.argv else "",
        )
        approval_path_hint = _approval_path_hint(typed)

        payload = {
            "severity": "warn",
            "kind": "unknown_flag",
            "typed": typed,
            "did_you_mean": suggestions,
            "available_flags": sorted(flat_known),
            "next_action_command": (
                f"{os.path.basename(sys.argv[0])} --help"
                if sys.argv else "--help"
            ),
        }
        if sibling_hint:
            payload["sibling_flag_hint"] = sibling_hint
        if approval_path_hint:
            payload["approval_path_hint"] = approval_path_hint
        hint_parts: list[str] = []
        if suggestions:
            hint_parts.append(f"Did you mean: {', '.join(suggestions)}?")
        if approval_path_hint:
            hint_parts.append(approval_path_hint)
        if sibling_hint:
            hint_parts.append(sibling_hint)
        hint_parts.append("Run --help to see available flags.")
        output.result(
            payload,
            message=f"Unknown flag {typed!r}: {' '.join(hint_parts)}",
            exit_code=1,
        )


def _expand_alias_groups(
    primary: list[str], alias_groups: list[tuple[str, ...]],
) -> list[str]:
    """Return ``primary`` with every alias-group it touches fully expanded.

    When ``did_you_mean`` picks one of an action's option strings (e.g.
    ``--target``), the agent benefits from also seeing the other
    aliases on the same action (``--spec-name`` / ``--target-name``)
    so the recovery does not require a second tool call.
    """
    if not primary:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for opt in primary:
        if opt not in seen:
            out.append(opt)
            seen.add(opt)
        for group in alias_groups:
            if opt in group:
                for alias in group:
                    if alias not in seen:
                        out.append(alias)
                        seen.add(alias)
    return out


_APPROVAL_PATH_LIKE_RE = re.compile(r"^[./].*\.json$")


def _approval_path_hint(typed: str) -> str:
    """Return a hint when *typed* looks like a path to an approval JSON file.

    The approval/* scripts accept the approval JSON file as a leading
    positional or via ``--approval-path``. Operators sometimes pass the
    raw path with a stray ``--`` prefix or as an unknown flag value;
    surface the canonical recovery so the second invocation lands the
    correct shape.
    """
    if not typed:
        return ""
    candidate = typed.lstrip("-")
    if not _APPROVAL_PATH_LIKE_RE.match(candidate):
        return ""
    return (
        f"Did you mean --approval-path '{candidate}'? "
        "approval/* scripts accept the approval JSON file via "
        "--approval-path or as the leading positional argument."
    )


def _sibling_flag_hint(typed: str, argv0: str) -> str:
    """Return a single-line hint when *typed* is canonical on a sibling.

    Returns an empty string when no sibling accepts ``typed``, when
    every script in the group accepts it, when reflection fails, when
    ``typed`` is empty, or when ``argv0`` does not look like a
    ``<group>/<script>.py`` shape.
    """
    if not typed or not argv0:
        return ""
    parts = Path(argv0).parts
    if len(parts) < 2:
        return ""
    group, script = parts[-2], parts[-1]
    try:
        from ..flag_context import sibling_flag_acceptance_dict
    except Exception:
        return ""
    try:
        registry = sibling_flag_acceptance_dict(group)
    except Exception:
        return ""
    accepted_by = registry.get(typed, frozenset())
    if not accepted_by:
        return ""
    siblings = sorted(s for s in accepted_by if s != script)
    if not siblings:
        return ""
    return (
        f"Hint: {typed} is accepted by "
        f"{', '.join(f'{group}/{s}' for s in siblings)} "
        f"but not by {group}/{script} — drop the flag here or run a sibling."
    )


def strict_parser(
    description: str, epilog: str = "",
    *, workspace: bool = True,
    **kwargs,
) -> argparse.ArgumentParser:
    """Create an ArgumentParser that emits structured JSON errors.

    Uses :class:`_JsonErrorParser` so ``parser.error()`` emits a JSON error
    envelope via ``output.error()`` instead of argparse's plain-text stderr
    + ``sys.exit(2)``.

    By default registers ``--workspace`` so every workflow-scoped script
    honours the same contract. The flag stores into ``args.project_path``
    so existing downstream attribute reads keep working. Pass
    ``workspace=False`` when a parent parser (via ``parents=[...]``)
    already declares it so argparse does not raise a conflicting-option
    error.

    Resolution order (see :func:`resolve_project_path`):
    ``args.project_path`` → ``$SDD_WORKSPACE`` → current working
    directory.
    """
    parser = _JsonErrorParser(
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        **kwargs,
    )
    if workspace:
        parser.add_argument(
            CANONICAL_WORKSPACE_FLAG, dest="project_path", default=None,
            help=(
                "Workspace root path (default: $SDD_WORKSPACE or "
                "current directory)"
            ),
        )
    return parser


AUTO_APPLY_ENV_GUARD = SKIP_AUTO_WORKSPACE_ENV

# Captured caller cwd before :func:`_apply_workspace_from_argv` chdirs
# into ``--workspace``. ``resolve_tracker_root`` consults this when the
# caller passes the ``workspace`` sentinel so the resolution survives
# the pre-argparse chdir boundary.
_CALLER_CWD: "Path | None" = None


def caller_cwd_before_workspace() -> "Path | None":
    """Return the caller's pre-``--workspace``-chdir cwd.

    Public accessor over :data:`_CALLER_CWD`. Falls back to
    :func:`os.getcwd` when no chdir happened so callers always get a
    usable path. Use this instead of reaching into the private
    attribute (``getattr(cli, "_CALLER_CWD", None)``) so the
    semantics survive future refactors of the chdir machinery.
    """
    if _CALLER_CWD is not None:
        return _CALLER_CWD
    try:
        return Path(os.getcwd())
    except OSError:
        return None


def _compose_tracker_search_roots(
    args: argparse.Namespace, *, include_workspace: bool = True,
) -> list[str]:
    """Return the ordered list of roots used for coordinator lookups.

    Single owner of the (caller_cwd → cwd) + ``--workspace`` ordering
    consumed by :func:`resolve_tracker_root` and external scripts that
    re-derive the same path search.
    """
    roots: list[str] = []
    if _CALLER_CWD is not None:
        roots.append(str(_CALLER_CWD))
    else:
        roots.append(os.getcwd())
    if include_workspace:
        project_path = getattr(args, "project_path", None) or ""
        if project_path:
            roots.append(project_path)
    return roots


def compose_tracker_search_roots(
    args: argparse.Namespace, *, include_workspace: bool = True,
) -> list[str]:
    """Public alias of the internal composer used by sibling scripts."""
    return _compose_tracker_search_roots(args, include_workspace=include_workspace)


def _apply_workspace_from_argv() -> None:
    """Pre-parse side-effect: honour ``--workspace`` before argparse runs.

    Sets ``SDD_WORKSPACE`` (idempotent — first writer wins, so the
    runner's own ``--project`` flag in ``sdd_core/__main__.py`` takes
    precedence) and chdirs into the resolved directory. This way scripts
    that never read ``args.project_path`` still see the intended root via
    ``paths.find_workflow_root()``.

    Set ``$SDD_SKIP_AUTO_WORKSPACE=1`` to disable. Tests that import
    ``main`` in-process use this guard so ``cwd`` does not leak across
    test cases.
    """
    global _CALLER_CWD
    if os.environ.get(AUTO_APPLY_ENV_GUARD) == "1":
        return
    argv = sys.argv
    for i, tok in enumerate(argv):
        if tok == CANONICAL_WORKSPACE_FLAG and i + 1 < len(argv):
            raw = argv[i + 1]
        elif tok.startswith(f"{CANONICAL_WORKSPACE_FLAG}="):
            raw = tok.split("=", 1)[1]
        else:
            continue
        try:
            _CALLER_CWD = Path(os.getcwd())
        except OSError:
            _CALLER_CWD = None
        path = os.path.abspath(raw)
        os.environ.setdefault(paths.WORKSPACE_ENV_VAR, path)
        if os.path.isdir(path):
            try:
                os.chdir(path)
            except OSError:
                pass
        return


def add_workspace_arg(parser: argparse.ArgumentParser) -> None:
    """Add ``--workspace`` flag for cross-repo artifact targeting.

    Idempotent: when ``strict_parser`` (or a parent) already registered
    ``--workspace`` the call is a no-op.
    """
    for action in parser._actions:
        if "--workspace" in getattr(action, "option_strings", ()):
            return
    parser.add_argument(
        "--workspace", default=".",
        help="Target workspace root (default: current directory)",
    )


def workspace_parser(description: str) -> argparse.ArgumentParser:
    """Create a strict ArgumentParser pre-configured with workspace flags.

    Registers ``--workspace`` (default ``.``, ``dest="workspace"``) and
    the canonical ``--target`` selector for ``family="workspace"``.
    Workspace targets accept ``<feature>[/<repo-id>]`` so a single flag
    covers both single-repo and multi-repo invocations.
    """
    parser = strict_parser(description, workspace=False)
    add_workspace_arg(parser)
    target_argument(parser, family="workspace")
    return parser


_TARGET_HELP: dict[str, str] = {
    "workspace": (
        "Workspace target as `<feature>` or `<feature>/<repo-id>` "
        "(splits on first `/`)."
    ),
    "workspace-target": (
        "Sub-spec name within a target repo (pair with --workspace "
        "for the repo root path)."
    ),
    "spec": "Spec name (resolves to .spec-workflow/specs/<name>/)",
    "approval": "Approval id (resolved via approval/store.find_by_id)",
    "discovery": "Discovery project name",
    "prd": "PRD/discovery feature slug",
}

_TARGET_NAME_KIND: dict[str, str] = {
    "workspace": "feature",
    "workspace-target": "spec-name",
    "spec": "spec-name",
    "approval": "approval-id",
    "discovery": "feature",
    "prd": "feature",
}


def target_argument(
    parser: argparse.ArgumentParser,
    *,
    family: Family,
    required: bool = True,
) -> None:
    """Register the canonical ``--target`` flag for *family*.

    Replaces per-script ``--feature`` / ``--repo-id`` / ``--spec-name``
    / positional ``<approval-file>`` declarations. Resolution happens at
    parse time via ``apply_target_to_namespace``; downstream code keeps
    reading the same attribute names it always did.

    Workspace targets accept ``<feature>[/<repo-id>]`` so single-repo
    invocations collapse onto the same flag.
    """
    if family not in _TARGET_HELP:
        raise ValueError(f"Unknown target family: {family!r}")

    kind = _TARGET_NAME_KIND[family]
    if family in ("workspace", "workspace-target"):
        # ``feature/repo-id`` may include a `/`; bypass name_type so the
        # composite form parses, then validate halves in the resolver.
        # ``workspace-target`` also accepts the slash form for handoffs
        # delegated from the coordinator.
        type_fn = str
    else:
        type_fn = name_type(kind)

    parser.add_argument(
        "--target",
        required=required,
        type=type_fn,
        default=None,
        help=_TARGET_HELP[family],
    )

    # Hook a custom parse step that splits and applies on parse.
    _patch_namespace_resolution(parser, family)


def _patch_namespace_resolution(
    parser: argparse.ArgumentParser, family: Family,
) -> None:
    """Wrap ``parser.parse_args`` to populate family-specific attrs.

    Centralising the wiring here keeps the resolver private to ``cli``
    while letting every script body keep its existing attribute reads
    (``args.feature`` / ``args.spec_name`` / etc.).
    """
    original = parser.parse_args

    def _wrapped(args=None, namespace=None):  # type: ignore[no-untyped-def]
        ns = original(args=args, namespace=namespace)
        apply_target_to_namespace(ns, family)
        return ns

    parser.parse_args = _wrapped  # type: ignore[assignment]


def resolve_workspace_root(args: argparse.Namespace) -> Path:
    """Resolve workspace root from the parsed ``--workspace`` arg.

    ``strict_parser`` registers ``--workspace`` with ``dest="project_path"``
    while ``add_workspace_arg`` registers it with ``dest="workspace"``;
    this helper checks both so the resolver works under either path.
    """
    workspace = getattr(args, "workspace", None)
    if not workspace:
        workspace = getattr(args, "project_path", None)
    return paths.find_workflow_root(workspace or ".")


def resolve_tracker_root(
    args: argparse.Namespace,
    *,
    default: "str | Path | None" = None,
    flag: str = "--tracker-root",
) -> "Path | None":
    """Resolve ``--tracker-root`` to an absolute :class:`Path`.

    Accepts:

    - absolute path → returned as :class:`Path` unchanged.
    - sentinel ``"coordinator"`` → workspace tracker root for the
      ``--target`` value, found via
      :func:`paths.find_workspace_tracker_root`.
    - sentinel ``"workspace"`` → the caller's pre-chdir cwd captured by
      :func:`_apply_workspace_from_argv` (or current cwd when no chdir
      happened).
    - missing + *default* → the default is resolved through the same
      rules.
    - missing + no default → returns ``None`` so callers can keep
      ``--tracker-root`` optional.
    - ``"."`` or any other relative path → rejected with
      :func:`output.error` so silent re-interpretation across the chdir
      boundary is impossible.
    """
    raw = getattr(args, "tracker_root", None)
    if raw in (None, ""):
        if default is None:
            return None
        raw = str(default)
    raw_str = str(raw)

    if raw_str == TRACKER_ROOT_SENTINEL_COORDINATOR:
        project_path = getattr(args, "project_path", None) or ""
        feature, _ = split_workspace_target(
            getattr(args, "tracker_target", "") or ""
        )
        search_roots = _compose_tracker_search_roots(args)
        if feature:
            manifest_root = paths.find_coordinator_root_for_feature(
                feature, search_roots=search_roots,
            )
            if manifest_root:
                return Path(manifest_root)
        workspace_root = paths.find_workspace_tracker_root(project_path)
        if workspace_root:
            return Path(workspace_root)
        output.error(
            f"{flag} sentinel {raw_str!r} could not resolve a workspace "
            f"tracker root from {project_path!r}",
            hint=(
                "Pass an absolute path, run from inside a workspace, or "
                "use the 'workspace' sentinel."
            ),
        )

    if raw_str == TRACKER_ROOT_SENTINEL_WORKSPACE:
        captured = _CALLER_CWD
        if captured is None:
            captured = Path(os.getcwd())
        return captured

    if not os.path.isabs(raw_str):
        output.error(
            f"{flag} value {raw_str!r} must be an absolute path or one of "
            f"the sentinels "
            f"{TRACKER_ROOT_SENTINEL_COORDINATOR!r} / "
            f"{TRACKER_ROOT_SENTINEL_WORKSPACE!r}.",
            hint=(
                "Plain relative paths like '.' are silently re-interpreted "
                "across the --workspace chdir boundary. Use an absolute "
                "path or a sentinel."
            ),
        )
    return Path(raw_str)


def run_main(func: Callable[[], None]) -> None:
    """Run a CLI main function with standardized error handling.

    Catches ``FileNotFoundError`` and ``ValueError`` from library code
    and formats them as structured JSON errors via ``output.error()``.
    ``SystemExit`` (from ``output.success``/``output.error``) passes through.
    Unexpected exceptions are caught as a safety net with traceback detail
    so the agent always receives structured JSON — never a raw traceback.
    """
    _apply_workspace_from_argv()
    try:
        func()
    except SystemExit:
        raise
    except (FileNotFoundError, ValueError) as exc:
        output.error(str(exc))
    except Exception as exc:
        tb = traceback.format_exc()
        output.error(
            f"Script crashed: {type(exc).__name__}: {exc}",
            hint=f"Traceback (report to user):\n{tb}",
        )
