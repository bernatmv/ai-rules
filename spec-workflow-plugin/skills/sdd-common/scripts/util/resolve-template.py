#!/usr/bin/env python3
"""Resolve a template by type, returning path, source, and content.

Usage: resolve-template.py --type TYPE [--spec-name NAME] [--metadata-only] [--workspace PATH]

The default invocation now returns the rendered template *content* —
the agent never has to remember ``--content`` (forgetting it was
the load-bearing failure mode that motivated this default flip).
Pass ``--metadata-only`` for the path/source-only response that
tooling sometimes wants.

``--content`` is accepted as a no-op alias so historical call sites
keep parsing while the agent-facing canon migrates to the new shape.
``--spec-name`` is mandatory for non-steering types so the
substitution can never silently drop placeholder text.

Exit code: 0 success, 1 template not found, 2 usage error.
"""
import _bootstrap  # noqa: F401

from pathlib import Path

from sdd_core import cli, output, paths
from sdd_core.task_prompts import (
    render_task_lifecycle_suffix,
    render_task_prompt_prefix,
)
from sdd_core.template_resolution import resolve_template, ALL_TEMPLATE_TYPES
from sdd_core.template_variables import get_default_variables, substitute_variables


# Steering templates do not carry per-spec placeholders; spec_name
# stays optional for these so existing pipelines can resolve them
# without inventing a synthetic name.
_STEERING_TEMPLATE_TYPES = frozenset({"product", "tech", "structure"})


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument("--type", required=True, choices=ALL_TEMPLATE_TYPES,
                        help="Template type (e.g., product, tech, requirements)")
    parser.add_argument("--spec-name", default="",
                        type=cli.name_type("spec-name"),
                        help="Spec name for variable substitution (optional for steering)")
    parser.add_argument(
        "--metadata-only", action="store_true",
        help=(
            "Return path/source only, omitting rendered content. Default "
            "is content output so the agent does not have to remember "
            "to opt in."
        ),
    )
    parser.add_argument(
        "--content", action="store_true",
        help=(
            "Backwards-compatible alias for the default behaviour. "
            "No effect — content is always returned unless "
            "--metadata-only is set."
        ),
    )
    args = parser.parse_args()

    if (
        args.type not in _STEERING_TEMPLATE_TYPES
        and not args.spec_name
        and not args.metadata_only
    ):
        output.error(
            f"--spec-name is required when --type={args.type!r} for content "
            "rendering. Pass --metadata-only if you only need the path.",
            hint="Example: --type tasks --spec-name <feature-slug>",
            exit_code=2,
        )

    root = Path(paths.resolve_project_path(args)).resolve()
    result = resolve_template(args.type, root)

    if result is None:
        output.error(
            f"No template found for type '{args.type}'",
            hint=f"Expected at .spec-workflow/user-templates/{args.type}-template.md "
                 f"or .spec-workflow/templates/{args.type}-template.md",
            exit_code=1,
        )

    data = {
        "source": result.source,
        "path": str(result.path),
        "docType": result.doc_type,
    }

    if not args.metadata_only:
        raw = result.path.read_text()
        variables = get_default_variables(spec_name=args.spec_name, project_path=root)
        rendered = substitute_variables(raw, variables)
        if args.type == "tasks" and args.spec_name:
            # The template carries the ``{spec_name}`` literal so it
            # stays validator-clean on its own. Swap in the concrete
            # name at resolve time via the shared ``sdd_core.task_prompts``
            # constants.
            prefix_literal = render_task_prompt_prefix("{spec_name}")
            suffix_literal = render_task_lifecycle_suffix("{spec_name}")
            rendered = rendered.replace(
                prefix_literal,
                render_task_prompt_prefix(args.spec_name),
            )
            rendered = rendered.replace(
                suffix_literal,
                render_task_lifecycle_suffix(args.spec_name),
            )
        data["content"] = rendered
        data["variables"] = variables

    output.success(data, f"Template resolved: {result.source} ({result.path.name})")


if __name__ == "__main__":
    cli.run_main(main)
