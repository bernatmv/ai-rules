# Launch Command Shape

> **Used by:** every consumer skill (sdd-create-spec, sdd-create-steering,
> sdd-create-discovery, sdd-implement-spec) that surfaces a literal
> `review/pipeline-tick.py --phase launch` command. Single canonical
> reference — consumer SKILL.md files link here instead of inlining
> examples that drift the moment the emitter changes.
> See also: `harness-task-binding.md`, `update-mode-workflow.md`.

## Contents

- [Flags](#flags)
- [Defaulting rules](#defaulting-rules)
- [Cross-references](#cross-references)

## Flags

| Flag | Type | Required? | Notes |
|---|---|---|---|
| `--review-skill` | string (skill name) | yes | The reviewer skill that scores the artifact (`sdd-review-spec-docs`, `sdd-review-steering-docs`, `sdd-review-prd`). Defaults from `category` when unset — see *Defaulting rules*. |
| `--doc-list` | comma-separated filenames | yes | Documents the launch reviews (`requirements.md,design.md,tasks.md` for spec; `product.md,tech.md,structure.md` for steering). Defaults from `category`. |
| `--scope` | `per-document` \| `final` | optional (default `per-document`) | `per-document` runs one review per doc; `final` aggregates the docs into one review. |
| `--workflow-mode` | `create` \| `resume` \| `update` | optional (default `create`) | `create` is greenfield; `resume` continues an open gate; `update` runs in-place against shipped artifacts. |
| `--parent-todo` | string | optional | Parent TODO id for the review gate. Pair with `--gate-id` — passing one without the other is a recoverable miss. |
| `--gate-id` | string | optional | Gate identifier; pair with `--parent-todo`. |
| `--target-name` | string | yes | Target identifier (spec name, steering family, etc.). The `review/pipeline-tick` runner accepts `--target-name`; workspace shims continue to use `--target`. |
| `--category` | `spec` \| `steering` \| `discovery` | yes | Review category — selects the default review-skill / doc-list. |
| `--workspace` | path | optional (default `.`) | Workspace root the review runs against. |

## Defaulting rules

`build_review_pipeline_launch_command` (single-owner emitter at
`$SCRIPTS/sdd_core/command_templates.py`) resolves `--review-skill`
via `skill_name_for_category(category)` and `--doc-list` via
`default_doc_list_for_category(category)`. A handoff that only knows
`(target, category)` therefore renders a complete, invocable command —
operators run the literal verbatim with no follow-up flag synthesis.
Explicit overrides take precedence over the category-derived defaults.

The default `--scope` is `per-document` so the review surface keeps
one row per document; per-document gates also drive the
`approval_commands_per_doc[]` cardinality on `pre-approval` envelopes.
The default `--workflow-mode` is `create`; `pipeline-tick.py` resolves
resume / update behaviour from session state at run time, so the
literal mode only locks the *first* launch shape.

## Cross-references

- `$SCRIPTS/sdd_core/command_templates.py::build_review_pipeline_launch_command`
  — the canonical emitter; every consumer routes through it.
- `$SCRIPTS/handoff-registry.json` — the `review/pipeline-tick:launch`
  rows declare an `emitter` field so the rendered handoff line stays
  byte-identical to the emitter's output.
- `$SKILLS/sdd-common/references/review-approval-pipeline.md` —
  the post-launch envelope contract (status routing, fix-loop entry).
- `$SKILLS/sdd-common/references/harness-task-binding.md` —
  `required_tool_calls[]` shape and `consumer` routing field.
