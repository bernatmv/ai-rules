# Script Tool Patterns

All SDD operations use Python scripts from `sdd-common/scripts/`. No MCP server required.

## Contents

- [Script Reference](#script-reference)
- [Common Invocations](#common-invocations)
- [Pre-Launch Envelope Contract](#pre-launch-envelope-contract)
- [Script Location](#script-location)
- [Invocation](#invocation)
  - [If the shim fails](#if-the-shim-fails)
- [Tool Choice for Common Needs](#tool-choice-for-common-needs)
- [`--project` vs `--workspace`](#--project-vs---workspace)
- [Approval Request Pattern](#approval-request-pattern)
- [Parameter Naming Convention](#parameter-naming-convention)
- [Workspace Flag-Rename Carve-outs](#workspace-flag-rename-carve-outs)
- [Dependencies Table Schema](#dependencies-table-schema)
- [Bootstrap Pattern](#bootstrap-pattern)
- [PR Content Extraction](#pr-content-extraction)
- [Pipeline JSON Envelopes](#pipeline-json-envelopes)
  - [Anti-pattern — `eval`-from-JSON for chained commands](#anti-pattern--eval-from-json-for-chained-commands)

## Script Reference

| Operation | Command |
|-----------|---------|
| Initialize workspace | `.spec-workflow/sdd workspace/init.py [--workspace PATH]` |
| Pre-flight all repos in workspace | `.spec-workflow/sdd workspace/preflight-all.py [--target NAME] [--auto-fix]` |
| Resolve pre-flight advisory | `.spec-workflow/sdd workspace/resolve-advisory.py --name "..."` |
| Request approval | `.spec-workflow/sdd approval/request.py --title "..." --file-paths "a.md" --type document --category spec --target-name "..."` |
| Check approval status | `.spec-workflow/sdd approval/check-status.py --approval-id "..." \| --category-name "..."` |
| Delete approval | `.spec-workflow/sdd approval/delete.py --approval-id "..."` |
| Check spec status | `.spec-workflow/sdd spec/check-status.py --target "..." \| --all \| --type steering` |
| Log implementation | `.spec-workflow/sdd util/log-implementation.py --spec-name "..." --task-id "..." --summary "..." --files-modified JSON --files-created JSON --statistics JSON --artifacts JSON` |
| Create snapshot | `.spec-workflow/sdd spec/create-snapshot.py --file-path "..." --approval-id "..." --trigger initial\|revision_requested\|approved\|manual` |
| Compare snapshots | `.spec-workflow/sdd spec/create-snapshot.py --compare --category-name "..." --file-name "..." --snapshot-a N --snapshot-b N` |
| Archive/unarchive spec | `.spec-workflow/sdd spec/archive.py --target "..." --action archive\|unarchive\|status` |
| Clean up old approvals | `.spec-workflow/sdd approval/cleanup.py [--max-age-days N] [--dry-run]` |
| Detect spec type | `.spec-workflow/sdd spec/detect-type.py <spec-name>` (exit 0=bug-fix, 1=standard, 2=usage error) |
| Parse task progress | `.spec-workflow/sdd util/parse-task-progress.py --tasks-file "..."` |
| Lint tasks format | `.spec-workflow/sdd spec/lint-tasks.py --target <spec-name>` (deterministic per-doc check; exit 0 with `outcome="partial"` on findings) |
| Lint requirements antipatterns | `.spec-workflow/sdd spec/lint-requirements.py --target <spec-name> [--mode standard|bug-fix]` |
| Lint design antipatterns | `.spec-workflow/sdd spec/lint-design.py --target <spec-name>` |
| Check requirements traceability | `.spec-workflow/sdd spec/check-traceability.py --target <spec-name>` |
| Check workspace spec shape | `.spec-workflow/sdd workspace/check-spec-shape.py --workspace PATH --target <feature>/<repo-id> [--doc requirements|design|tasks]` (with `--doc tasks`, the envelope also runs `spec/check-traceability` and surfaces gaps as `data.traceability_errors[]`) |
| Bootstrap workspace feature (manifest + tracker) | `.spec-workflow/sdd workspace/init-feature.py --workspace PATH --target <feature> --repo coordinator:<path>(absolute):<feature> --repo target:<path>(absolute):<sub-spec> [--idempotent | --force]` |
| Retroactive review for missing artifacts | `.spec-workflow/sdd workspace/retroactive-review.py --workspace PATH --target <feature> [--phase requirements|design|tasks] [--phase-repo-id ID] [--dry-run]` |
| Approve workspace phase | `.spec-workflow/sdd workspace/phase-approve.py --target <feature> --doc requirements|design|tasks [--dry-run]` |
| Snapshot review-quality + mark doc reviewed | `.spec-workflow/sdd review/snapshot-and-mark-reviewed.py --target <feature>/<repo-id> --phase requirements\|design\|tasks` — atomically writes the phase snapshot and advances the workspace tracker's `docStatus.{phase}` to `reviewed` (see `$SKILLS/sdd-workspace-create-spec/references/phase-loop.md`). |
| List pending approvals | `.spec-workflow/sdd approval/list-pending.py [--category spec\|steering] [--target NAME]` |
| Update approval status | `.spec-workflow/sdd approval/update-status.py <file> <action: approve\|reject\|needs_revision> "<response>" [--actor <actor>]` |
| Detect spec context | `.spec-workflow/sdd spec/detect-context.py <spec-name> [--workspace PATH]` (exit 0=workspace, 1=standalone, 2=usage error) |
| Check re-review needed | `.spec-workflow/sdd review/check-re-review.py --doc "..." --spec-name "..." --category spec\|steering\|discovery [--workspace PATH]` |
| Create discovery project | `.spec-workflow/sdd discovery/init-project.py --name "..."` |
| Update discovery manifest | `.spec-workflow/sdd discovery/update-manifest.py --name "..." <subcommand> [args...]` |
| Update workspace manifest | `.spec-workflow/sdd workspace/update-manifest.py --target <feature> <subcommand> [args...]` |
| Validate discovery manifest | `.spec-workflow/sdd discovery/validate-manifest.py --name "..."` |
| Resolve template | `.spec-workflow/sdd util/resolve-template.py --type TYPE [--spec-name NAME] [--metadata-only] [--workspace PATH]` — content rendering is the implicit default; `--metadata-only` opts out. `--spec-name` is mandatory for non-steering types. |
| Validate PRD structure | `.spec-workflow/sdd prd/validate-prd.py <prd.md>` (exit 0=pass, 1=issues, 2=usage error) |
| Validate PRD readiness gate | `.spec-workflow/sdd prd/validate-readiness.py --target "..." --gate pre-requirements\|pre-generation [--session-file]` |
| Write PRD session state | `.spec-workflow/sdd prd/write-session-state.py --target "..." --step N --data '{...}'` |
| Delete PRD session state | `.spec-workflow/sdd prd/write-session-state.py --target "..." --delete` |
| Check template compliance | `.spec-workflow/sdd review/check-template-compliance.py <template_file> <document_file>` |
| Count effective lines | `.spec-workflow/sdd review/count-effective-lines.py --file FILE [--file FILE ...]` — single file returns `{ "count": N, "file": "..." }`; multiple files returns `{ "results": [{ "file": "...", "count": N }, ...] }` |
| Prepare review pipeline | `.spec-workflow/sdd review/pipeline-tick.py --phase launch\|check-revalidation\|post-fix\|pre-approval\|ack-calls [args...] [--parent-todo STEP_ID] [--gate-id STEP_ID]` — always exits 0. Every phase returns `next_action_command` for the next step; pass `todo_write_payload` directly to TodoWrite when present (see `$SKILLS/sdd-common/references/review-approval-pipeline.md`). |
| Validate review progress | `.spec-workflow/sdd review/validate-review-progress.py --phase record\|conventions\|check\|reset [args...]` — `record`: `--dimension KEY --read-file --checks-cited N`; `conventions`: `--summary "..."`; `check`: validates all dimensions complete; `reset`: clears state |
| Validate review report | `.spec-workflow/sdd review/validate-review-report.py --report <report.md>` — validates dimension scorecards, principle scorecard, anti-pattern checks; exits 0/1 |
| Print canonical pair keys | `.spec-workflow/sdd review_quality/print-pair-keys.py --type spec\|steering\|prd` — single source of truth for cross-validation pair keys consumed by sub-agents and artifact writers |
| List registered shim commands | `.spec-workflow/sdd util/list-commands.py [--group <group>] [--all]` — emitted as the `next_action_command` when the shim rejects an unknown first arg |
| Render canonical task-prompt suffix | `.spec-workflow/sdd util/render-task-prompts.py --target <slug>` — single source quoted by `prompt-suffix-canonical.md`. **Prefer `.spec-workflow/sdd util/resolve-template.py --type tasks --spec-name <slug>` when drafting from scratch** — it inlines the same scaffolding byte-identically; use `render-task-prompts.py` only to quote the canonical strings in prose or when overriding the default template. |

## Common Invocations

Canonical shim commands for the most frequently called SDD scripts. Copy verbatim; substitute only the `{braced}` tokens. `--help` lists available flags on every script.

```
.spec-workflow/sdd spec/check-status.py --target "{spec-name}"
.spec-workflow/sdd spec/lint-tasks.py --target "{spec-name}" --workspace .
.spec-workflow/sdd spec/check-traceability.py --target "{spec-name}" --workspace .
.spec-workflow/sdd util/resolve-template.py --type {doc-type} --spec-name "{spec-name}" --workspace .
.spec-workflow/sdd util/render-task-prompts.py --target "{spec-name}"
.spec-workflow/sdd util/detect-doc-state.py --category spec --target-name "{spec-name}" --workspace .
.spec-workflow/sdd util/generate-prompt.py --list
.spec-workflow/sdd review/pipeline-tick.py --phase pre-launch-check --category spec --target-name "{spec-name}" -- --doc {doc}.md
```

Emitters in `sdd_core.command_templates` (`build_lint_tasks_command`, `build_check_traceability_command`, `build_render_task_prompts_command`, `build_detect_doc_state_command`, `build_check_re_review_command`, `build_generate_prompt_list_command`, `build_update_quality_command`, the `UPDATE_QUALITY_SCRIPT` constant, etc.) produce the exact strings above; callers that compose these commands into envelopes MUST go through the builders rather than restating the literal.

`build_update_quality_command(*, review_type, scope, staging_path)` — staging-path / sub-agent invocation shape (`--type/--input/--scope`), emitted into prompt prose as a bare path. Sibling `build_review_update_quality_command` is the direct-dispatch shape.

## Pre-Launch Envelope Contract

`pipeline-tick --phase pre-launch-check` returns a stable set of fields per call. Consumers rely on the shape — never introduce ad-hoc keys in replacements.

| Field | Presence | Meaning |
|-------|----------|---------|
| `outcome` | always on validator runs | Disambiguated outcome class. Run `pipeline-tick --phase pre-launch-check --describe-envelope` for the value enum. Branch on `outcome`, not `result`. |
| `template_resolve_commands` | always (when `--doc` is set) | Map of `{doc_filename: resolve-template shim command}` with `--spec-name` threaded through. Execute verbatim to draft the doc. |
| `authoring_guardrails` | present when the target doc has write-time rules | List sourced from `sdd_core/data/requirements_antipatterns.yaml`; enforce every entry while drafting. |
| `pre_launch_checklist_key` | always | Versioned checklist id (e.g. `pre-launch.v1`) so callers can pin a TodoWrite to a known revision. |
| `findings` | on validator runs | Structured findings list — agent-parseable. |
| `findings_file` | on validator runs | Persisted plan file path (sibling to the doc). |
| `repeat_detected` / `repeat_count` / `repeat_limit` | when the same findings recur ≥ 3 times | Escalation marker paired with `ask_question_payload` so agents hand off to the user. |

## Script Location

All scripts are at: `$SKILLS/sdd-common/scripts/{group}/{script-name}`

## Tool Choice for Common Needs

Prefer the native tool the harness exposes for each operation. Bash
invocations cost parallelism and auditability when a native tool would
suffice. Sibling-cancellation rules live in
`parallel-batch-hygiene.md` § "Cascade-Cancel Principle".

| Need | Tool | Anti-pattern |
|------|------|--------------|
| Read a known file path | `Read` | `cat <path>` via Bash |
| Search many files by content | `Grep` | `rg` / `grep` via Bash |
| List files matching a glob | `Glob` | `find` / `ls` via Bash |
| Edit a file at a known location | `StrReplace` / `Edit` | `sed` / `awk` via Bash |
| Probe directory existence | `test -d <path>` | `ls <path>` chained with `&&` — masks the first call's output on the second's non-existence |
| Run a shim-delegated script | `Bash` with `.spec-workflow/sdd ...` | `python3 $SKILLS/.../scripts/...` (only the Layer 3 fallback documented in `bootstrap-pattern.md` is permitted to bypass the shim) |
| Shell ops (pipelines, globbing in args) | `Bash` | `Read` workarounds |

## Invocation

**Rule (low-freedom — one exact shape):**

```
.spec-workflow/sdd {group}/{script-name} [args...]
```

`.spec-workflow/sdd` is a direct-executable shim. It dispatches on its first
positional argument, so `{group}/{script-name}` must follow a **space** — never
be joined by a `/`, and never be prefixed with `python` / `python3`.

`.spec-workflow/sdd` is a single executable, not a directory — `ls
.spec-workflow/sdd/` returns `Not a directory`. Enumerate available
commands with `.spec-workflow/sdd util/list-commands.py`.

### If the shim fails

| Observed | Fix |
|----------|-----|
| `exit code 2` | You prefixed with `python3` or joined with `/`. Re-read the Rule above. |
| `Errno 20: Not a directory` | You did both — drop `python3` *and* replace the `/` after `sdd` with a space. |

When the shim is unavailable (cross-repo sub-agents, custom
toolchains), follow
[`bootstrap-pattern.md` § Three Layer Invocation](bootstrap-pattern.md#three-layer-invocation)
— every other route shells `python3` at the wrong layer.

## `--project` vs `--workspace`

| Flag | Level | Purpose | When to use |
|------|-------|---------|-------------|
| `--project` | Runner (`.spec-workflow/sdd ...`) | Changes CWD + sets `SDD_PROJECT_PATH` for all downstream code | When the script targets a different repo than CWD |
| `--workspace` | Per-script argument | Tells the script where `.spec-workflow/workspace/` lives | When specifying the workspace tracker location (usually the coordinator repo) |

All workspace scripts default `--workspace` to the current directory (`.`).
After `cd`-ing to the coordinator repo root, `--workspace` can be omitted.

**Rule:** Never pass both `--project` and `--workspace` with the same path.
If you use `--project`, the script's CWD is already set, so `--workspace`
defaults correctly and can be omitted.

## Approval Request Pattern

```
.spec-workflow/sdd approval/request.py --title "[Review Title]: [target-name]" --file-paths "[path-to-document]" --type document --category "[spec | steering]" --target-name "[target-name]"
```

**Per-document parameters** (bug fix example):

| Document | Title | File Path | Category | Target Name |
|----------|-------|-----------|----------|---------------|
| requirements.md | "Bug Fix Requirements: fix-{slug}" | `.spec-workflow/specs/fix-{slug}/requirements.md` | spec | fix-{slug} |
| design.md | "Bug Fix Design: fix-{slug}" | `.spec-workflow/specs/fix-{slug}/design.md` | spec | fix-{slug} |
| tasks.md | "Bug Fix Tasks: fix-{slug}" | `.spec-workflow/specs/fix-{slug}/tasks.md` | spec | fix-{slug} |

**Non-chaining rule:** Approval operations must be executed as separate calls —
first `approval/request.py`, then separately `approval/update-status.py` + `approval/delete.py`.
Do NOT chain these in a single command.

## Dependencies Table Schema

Every user-invocable SKILL.md declares its dependencies as a three-column markdown table:

```markdown
| Step | File | Kind |
|------|------|------|
| Step 1 | `$SKILLS/sdd-common/scripts/spec/check-status.py` | run |
| Step 2 | `$SKILLS/sdd-common/references/tool-patterns.md` | read |
| Step 2 | `$SKILLS/sdd-common/scripts/sdd_core/templates.py` | read |
```

The `Kind` column disambiguates executable scripts from reference documents and library modules. It has exactly two values:

| Kind | Meaning |
|------|---------|
| `run` | Executable CLI script — invoke via the shim (`.spec-workflow/sdd {group}/{script}.py ...`) |
| `read` | Reference doc, library module, or cross-skill SKILL.md that is loaded (not executed) |

Rule of thumb: paths ending in `.py` under a `scripts/{group}/` folder with a top-level `main()` are `run`. Everything else (references/*.md, `sdd_core/*.py` library modules, cross-skill SKILL.md loaded via the Task tool) is `read`.

If a script is sometimes executed and sometimes imported, use **two rows** — one `run` and one `read` — and document the distinction in the file column.

## Parameter Naming Convention

| Context | Convention | Example |
|---------|------------|---------|
| CLI arguments | kebab-case | `--workspace`, `--target` |
| Python parameters | snake_case | `target_name`, `project_path` |
| JSON keys | snake_case | `target_name`, `fix_cycle` |

## Workspace Flag-Rename Carve-outs

Workspace shims surface a single canonical pair: `--workspace <path>` for the
repo root and `--target <feature>[/<repo-id>]` for the workflow target. The
legacy per-skill selectors (feature flag, repo-id flag, target-name flag,
target-repo flag, and project-path flag) have been removed from
workspace user-invocable shims; bad input is rejected with a `did_you_mean`
envelope rather than silently aliased.

The flags below are **separate concepts** that survive the rename and stay on
the dispatcher / sub-mutation surface. Lints and reference docs preserve them
as carve-outs:

| Flag | Surface | Why it stays |
|------|---------|--------------|
| `--target-name` (dest=`category_name`) | `approval/request.py`, `approval/check-status.py`, dispatcher locators in `review/` | Approval (approval/request) and dispatcher locator triple — names a category-scoped artifact, not a workflow target. |
| `--repo-id` | `workspace/update-manifest.py` subparser (`set-repo-role`) | Manifest-mutation argument identifying which repo entry to edit; not the workflow target. |
| `--repo-target` | `workspace/set-doc-approval.py` | Doc-approval scope (`coordination` vs a specific repo-id); orthogonal to the workflow target carried by `--target`. |

If you add a new workspace shim, it MUST use `--workspace` / `--target`. If you
add a new dispatcher / mutation flag that collides with one of the carve-out
literals, document it here and update
`internal_lints/skill_md_legacy_flags.py::_ALLOWED_CONTEXTS` so the lint stops
flagging the new surface.

## Bootstrap Pattern

Each subpackage under `$SCRIPTS/` (e.g. `approval/`, `spec/`, `workspace/`) contains a short `_bootstrap.py` that delegates to the root-level helper at `$SCRIPTS/_sdd_bootstrap.py`. This ensures `sdd_core` is on `sys.path` and `sys.dont_write_bytecode = True` when scripts are invoked directly (fallback mode without the runner shim).

This is a **deployment pattern, not code duplication** — do not remove or "simplify" these files. Every per-subpackage `_bootstrap.py` is required for the fallback invocation path described in [`bootstrap-pattern.md`](bootstrap-pattern.md) to work.

The root helper is named `_sdd_bootstrap.py` (not `_bootstrap.py`) to avoid a module-name collision with the shims; see [`bootstrap-pattern.md` § Two Layer Bootstrap Layout](bootstrap-pattern.md#two-layer-bootstrap-layout) for the full rationale.

## PR Content Extraction

When extracting files from a PR for a targeted purpose:

```bash
# Fetch PR branch
git fetch origin pull/{N}/head:pr-{N}

# Path-scoped diff (avoids output explosion on multi-commit PRs)
git diff main...pr-{N} --name-only -- {relevant_path}/

# Extract specific file content
git show pr-{N}:{file_path}
```

Avoid unscoped `git diff main...{branch} --name-only` on PRs with many commits —
this can produce thousands of lines. Always use path filters when the relevant
directory is known.

## Pipeline JSON Envelopes

Never truncate pipeline JSON (no `head -N`, no partial `grep`). Parse the full
envelope — pipeline phases are idempotent on replay, so losing the initial
`required_tool_calls` / `phase_commands` fields forces a round-trip through
the idempotency cache that could otherwise have been avoided.

### Anti-pattern — `eval`-from-JSON for chained commands

Do NOT run `eval "$(<shim> | jq -r '.data.next_action_command_sequence')"` — silent per-step failures are invisible. Run each `data.next_action_steps[]` entry as a separate Bash turn (or chain with literal `&&`). `next_action_command_sequence` is a copy-paste hint; `next_action_steps[]` is the canonical observability surface.
