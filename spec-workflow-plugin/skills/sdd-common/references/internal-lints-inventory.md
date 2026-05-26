# Internal Lints Inventory

> **Related protocols:** Linked from `script-conventions.md` § Exemption
> baseline.

## Contents

- [Group A — Python source-quality lints](#group-a--python-source-quality-lints)
- [Group B — SKILL.md content lints](#group-b--skillmd-content-lints)

CI/developer ratchets over SDD's own source. Each rule's exemptions
live in `internal_lints/baselines.json` keyed by rule id; refresh
via `.spec-workflow/sdd internal_lints/baseline-refresh.py [--rule <id>]
[--all] [--prune]`. The single registry of rules lives in
`internal_lints/_dispatch.py::DISPATCH`; adding a new lint is one
`DISPATCH` row plus one `baselines.json::rules` entry.

## Group A — Python source-quality lints

| Rule id | Module |
|---|---|
| `advisory-phase-placement` | `advisory_phase_placement` |
| `approve-ceremony-wired` | `approve_ceremony_wired` |
| `cli-argument-conventions` | `cli_argument_conventions` |
| `emitted-commands-parse` | `emitted_commands_parse` |
| `error-envelopes` | `error_envelopes` |
| `import-paths-resolve` | `import_paths_resolve` |
| `name-type-wired` | `name_type_wired` |
| `no-bare-subprocess-dispatch` | `no_bare_subprocess_dispatch` |
| `no-dataclass-slots` | `no_dataclass_slots` |
| `no-harness-name-collision` | `no_harness_name_collision` |
| `no-plan-trace-in-references` | `no_plan_trace_in_references` (`--scope references` / `--scope scripts` / `--scope all`) |
| `no-shell-true` | `no_shell_true` |
| `no-validate-for-lint` | `no_validate_for_lint` |
| `orphan-sdd-core-modules` | `orphan_sdd_core_modules` |
| `required-tool-calls-schema` | `required_tool_calls_schema` |
| `result-class-exit` | `result_class_exit` (forward + inverse rule — envelopes carrying `next_action_command_sequence` must be result-class) |
| `review-skill-no-string-default` | `review_skill_no_string_default` |
| `security-concrete-import` | `security_concrete_import` |
| `workspace-state-layout` | `workspace_state_layout` |

## Group B — SKILL.md content lints

| Rule id | Module |
|---|---|
| `skill-md-abs-paths` | `skill_md_abs_paths` |
| `skill-md-assessment-staging-literals` | `skill_md_assessment_staging_literals` |
| `skill-md-batch-hygiene` | `skill_md_batch_hygiene` |
| `skill-md-dependency-order` | `skill_md_dependency_order` |
| `skill-md-hand-rendered-options` | `skill_md_hand_rendered_options` |
| `skill-md-pair-key-literals` | `skill_md_pair_key_literals` |
| `skill-md-prompt-refs` | `skill_md_prompt_refs` |
| `skill-md-size-and-disclosure` | `skill_md_size_and_disclosure` |
| `skill-md-toc` | `skill_md_toc` |

## Maintainer notes

The tables above are hand-maintained alongside
`internal_lints/_dispatch.py` and `internal_lints/baselines.json` —
update both when adding or renaming a rule.
