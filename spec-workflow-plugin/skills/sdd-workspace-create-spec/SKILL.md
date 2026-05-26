---
name: sdd-workspace-create-spec
description: Creates spec documents across multiple repositories. Creates a coordination
  manifest and spec in the coordinator repo, guides phase-by-phase spec creation
  with mandatory review gates before each approval, and maintains a central
  workspace tracker. Use when asked to create a workspace spec, check workspace
  status, resume a workspace, or approve workspace sub-specs.
allowed-tools: Read Write Edit Bash Agent AskQuestion AskUserQuestion TaskCreate TaskUpdate WebFetch
metadata:
  version: 3.3.1
  category: workflow
  dependencies: [sdd-common, sdd-create-spec, sdd-review-spec-docs, sdd-manage-status]
  author: membership-platforms-sdd-guild
---

> **Paths:** See `$SKILLS/sdd-common/references/path-conventions.md`. Scripts: `.spec-workflow/sdd {group}/{script}.py`.

# SDD: Workspace Create Spec

Coordinates a feature that spans multiple repositories by creating a coordination manifest and spec in the coordinator repo, then guiding phase-by-phase spec creation across all repos (coordinator included).

## Contents

- [Dependencies](#dependencies)
- [Invocation Examples](#invocation-examples)
- [Command Reference](#command-reference)
- [Resume Protocol](#resume-protocol)
- [Workflow](#workflow)
- [Workflow Progress Checklist](#workflow-progress-checklist)
- [Safety Rules & Edge Cases](#safety-rules--edge-cases)
- [Human approval ceremony](#human-approval-ceremony)
- [Completion](#completion)
- [Handoffs](#handoffs)
- [Reference Files](#reference-files)

## Dependencies

> **Load on demand**: Read each file only when the workflow reaches that step — not all upfront.

| Step | File | Kind | Freedom |
|------|------|------|:-:|
| Step 1 | `$SKILLS/sdd-common/references/tool-patterns.md` | read | L |
| Step 1 | `$SKILLS/sdd-common/references/pre-flight-protocol.md` | read | L |
| Step 1 | `$SKILLS/sdd-workspace-create-spec/references/command-reference.md` | read | L |
| Step 1 | `$SKILLS/sdd-workspace-create-spec/references/manifest-schema.md` | read | M |
| Steps 2-4 | `$SKILLS/sdd-workspace-create-spec/references/phase-loop.md` | read | L |
| Steps 2-4 | `$SKILLS/sdd-workspace-create-spec/references/sub-agent-templates.md` (Task sub-agent delegation) | read | M |
| Steps 2-4 | `$SKILLS/sdd-workspace-create-spec/references/coordination-workflow.md` (coordinator formatting) | read | L |
| Steps 2-4 | `$SKILLS/sdd-create-spec/SKILL.md` (sub-agent delegation — read via Task tool, not inline) | read | L |
| Steps 2-4 | `$SKILLS/sdd-workspace-create-spec/references/review-gate-protocol.md` | read | L |
| Steps 2-4 | `$SKILLS/sdd-common/references/review-approval-pipeline.md` (§ Review Gate, § Sub-Agent Guidelines) | read | L |
| Steps 2-4 | `$SKILLS/sdd-common/references/approval-flow.md` | read | L |
| Steps 2-4 | `$SKILLS/sdd-review-spec-docs/SKILL.md` (sub-agent delegation — read via Task tool, not inline) | read | L |
| Steps 2-4 | `$SKILLS/sdd-manage-status/SKILL.md` (sub-agent delegation — read via Task tool, not inline) | read | L |
| Step 4 | `$SKILLS/sdd-common/references/task-validation-rules.md` | read | M |
| Step 5 | `$SKILLS/sdd-common/scripts/workspace/check-status.py` | run | L |
| Steps 2-4, 5 | `$SKILLS/sdd-common/references/workflow-handoffs.md` | read | M |
| Resume | `$SKILLS/sdd-manage-status/SKILL.md` | read | L |
| All | `$SKILLS/sdd-workspace-create-spec/references/safety-and-edge-cases.md` | read | L |
| All | `$SKILLS/sdd-common/references/prompt-conventions.md` | read | M |
| All | `$SKILLS/sdd-common/references/state-scope.md` (scope + lifetime of persisted state) | read | L |

## Invocation Examples

| Request | Action |
|-------------|--------|
| "sdd workspace [feature]" | Create workspace spec across repos |
| "sdd workspace status [feature]" | Check workspace progress |
| "sdd workspace resume [feature]" | Resume workspace workflow |
| "sdd workspace approve [feature]" | Batch approve sub-specs |

**Single-repo notice:** If the manifest has only one repo, inform the user that a standard `sdd create spec` produces equivalent output. Continue unless the user requests the switch.

## Command Reference

See `references/command-reference.md` for the full workspace script reference table (args, options, notes).

**Per-doc review artifacts.** Each repo emits
`review-quality-{requirements|design|tasks}.json` per phase under its
`.spec-workflow/specs/{sub-spec}/` directory. The Approve step
(`.spec-workflow/sdd workspace/phase-approve.py`, gate
`review-artifact-required`) refuses to advance unless the artifact
exists or the tracker carries `reviewMeta.{doc}.reviewSkipped = true`
(set via `.spec-workflow/sdd workspace/update-tracker.py --doc-status reviewed --review-skipped`).


## Resume Protocol

Run the workspace check-status shim below to determine the current step, then skip to the appropriate entry point:

```
.spec-workflow/sdd workspace/check-status.py \
  --workspace . --target {feature}
```

> **Important:** Use `workspace/check-status.py` (not `spec/check-status.py`) for
> workspace coordination status. The spec variant checks individual spec documents
> within a single repo.

| `currentPhase` | `phaseGates.{phase}` | Resume Step |
|----------------|---------------------|-------------|
| `null` (no tracker) | — | Step 1 |
| `requirements` | `.requirements` = `null` | Step 2 (Phase R — check `docStatus` per repo) |
| `requirements` | `.requirements.approvedAt` set | Advance to Phase D |
| `design` | `.design` = `null` | Step 3 (Phase D — check `docStatus` per repo) |
| `design` | `.design.approvedAt` set | Advance to Phase T |
| `tasks` | `.tasks` = `null` | Step 4 (Phase T — check `docStatus` per repo) |
| `tasks` | `.tasks.approvedAt` set | Step 5 |
| `complete` | — | Step 5 |

Within a phase, use `phase-status.py` to find the first repo needing work:

```
.spec-workflow/sdd workspace/phase-status.py \
  --workspace . --target {feature}
```

**Tracker schema routing:** When `check-status.py` reports the legacy schema, follow the legacy vertical flow described in `references/manifest-schema.md`; otherwise the v2.0.0 schema is in effect and the per-repo phase loops below apply directly.

### Conventions

| Convention | Rule |
|------------|------|
| **Working directory** | All workspace commands default `--workspace` to cwd. Ensure cwd is coordinator root, or pass `--workspace <path>`. |
| **Approval terminology** | `approval/update-status.py` accepts both verb (`approve`, `reject`, `needs_revision`) and adjective (`approved`, `rejected`, `needs-revision`) forms — they normalise to the canonical verb. `workspace/set-doc-approval.py` uses adjectives (`approved`, `rejected`). |
| **Prompt handling** | See `$SKILLS/sdd-common/references/prompt-conventions.md` § Integration Pattern. |

## Workflow

### Step 1: Initialize Workspace

> **Resume entry:** See Resume Protocol above.
> **Prompt convention:** All approval prompts follow `$SKILLS/sdd-common/references/prompt-conventions.md` § Structured Prompt Format.

1. Identify the **coordinator repo** (this repo) and **target repos**.
2. For each target repo, run pre-flight per `$SKILLS/sdd-common/references/pre-flight-protocol.md`:
   ```
   .spec-workflow/sdd workspace/ensure-healthy.py --workspace {target-repo-path}
   ```
3. Bootstrap the manifest + tracker via the canonical helper (see `references/manifest-schema.md` for v2.0.0 schema details):
   ```
   .spec-workflow/sdd workspace/init-feature.py \
     --target {feature} \
     --repo coordinator:{coordinator-path}:{feature} \
     --repo target:{repo-path}:{sub-spec} [--repo …]
   ```
   The script writes both `coordination-manifest.json` and `workspace-tracker.json` with `currentPhase = "requirements"` and `docStatus = "pending"` for every sub-spec. Pass `--idempotent` for re-runs (no-op when repos match) or `--force` (H1-gated; snapshots prior state) when overwriting.

   The first `--repo` segment is the `repoType` discriminator
   (`coordinator` / `target`). Each repo's free-form `role` field is
   left empty at bootstrap — the success envelope carries one
   `data.advisories[]` entry per missing role with a fully-formed
   `next_action_command`. Run each emitted shim before starting Phase R
   so `extract-delegation.py` does not warn:
   ```
   .spec-workflow/sdd workspace/update-manifest.py --target {feature} \
     set-repo-role --repo-id {repo-id} --role "<short repo-purpose description>"
   ```

### Steps 2-4: Phase Loop (R → D → T)

Each phase executes four sub-steps **strictly in order**:

1. **Create** — generate the document for each repo
2. **Validate** — run validation scripts
3. ⛔ **Review** — present batch review prompt (**MANDATORY gate**)
   - You MUST present the review prompt before proceeding to step 4.
   - Do NOT proceed to Approve without completing this step.
4. **Approve** — batch approve after review completes or user skips

> **Resume entry:** See Resume Protocol above. Use `currentPhase` and `phaseGates`
> to determine which phase and sub-step to resume from.

| Step | Phase | Reference |
|------|-------|-----------|
| 2 | R — Requirements | `references/phase-loop.md` § Phase R — Requirements |
| 3 | D — Design | `references/phase-loop.md` § Phase D — Design & Phase T — Tasks |
| 4 | T — Tasks | `references/phase-loop.md` § Phase D — Design & Phase T — Tasks |

### Step 5: Complete

After Phase T's last `phase-approve.py --doc tasks` returns,
`currentPhase = "complete"` is already on disk — `apply_phase_approval`
seals `phaseGates.tasks` and bumps `currentPhase` in the same atomic
`finalize_and_save` write. No follow-up `advance-phase.py` call is
needed on v2+ trackers.

> Legacy v1.x flow → see `references/manifest-schema.md` § v1.1.0 Vertical Flow (backward compatible).

When all repos show `approved` in the tracker (or `cancelled`/`failed` for
repos that were skipped):

1. Present overall summary:
   ```
   .spec-workflow/sdd workspace/check-status.py \
     --workspace . --target {feature}
   ```
2. Mark workspace as complete in the tracker.
3. Present final summary with per-repo status.
4. Hand off with inline suggestion:

   "Workspace spec creation complete for `{feature}`. To implement, run
   `sdd implement {subSpecName}` in each target repo."

## Workflow Progress Checklist

Copy and maintain this checklist. Items marked ⛔ are gates — do NOT
proceed past them without completing the gate action. See
`$SKILLS/sdd-common/references/review-gate-pattern.md` for the
validate → review → approve loop and `references/phase-loop.md` for
per-phase sub-step prose.

```
- [ ] Step 1: Workspace initialized, manifest + tracker populated
- [ ] Step 2: Phase R — Requirements
  - [ ] 2.1 Create   2.2 Validate   ⛔ 2.3 Review gate   2.4 Approve
- [ ] Step 3: Phase D — Designs
  - [ ] 3.1 Create   3.2 Validate   ⛔ 3.3 Review gate   3.4 Approve
- [ ] Step 4: Phase T — Tasks
  - [ ] 4.1 Create   4.2 Validate   ⛔ 4.3 Review gate   4.4 Approve
- [ ] Step 5: Workspace complete (`currentPhase = "complete"`)
```

## Safety Rules & Edge Cases

See `references/safety-and-edge-cases.md` for workspace-specific safety rules (e.g., never modify target repo files outside `.spec-workflow/`, always validate manifest paths) and edge case handling (e.g., stale paths, name collisions, validation failures).

## Human approval ceremony

Follow `$SKILLS/sdd-common/references/human-approval-ceremony.md` with `target_label="{spec-name}"` before any `.spec-workflow/sdd approval/update-status.py … approve`.

## Completion

Workspace spec creation complete. To implement, run `sdd implement {sub-spec-name}` in each target repo.

## Handoffs

See `references/handoffs.md` (generated from `$SCRIPTS/handoff-registry.json`).
Regenerate via `.spec-workflow/sdd internal_lints/skill_md_handoff_table.py --rewrite`.

## Reference Files

- `references/command-reference.md` — Full workspace script reference table
- `references/coordination-workflow.md` — Coordinator formatting and workflow
- `references/handoffs.md` — Generated handoff table (mirrors `handoff-registry.json`)
- `references/manifest-schema.md` — Coordination manifest JSON schema (v2.0.0)
- `references/phase-loop.md` — Phase loop procedures for R → D → T cycles
- `references/review-gate-protocol.md` — Review gate protocol for workspace phases
- `references/safety-and-edge-cases.md` — Workspace-specific safety rules and edge cases
- `references/sub-agent-templates.md` — Task sub-agent delegation templates
