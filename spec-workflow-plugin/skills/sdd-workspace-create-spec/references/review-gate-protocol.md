# Review Gate Protocol (Workspace)

Workspace-specific wrapper around the shared review gate protocol.
Called from `phase-loop.md` § Batch Review & Approve.

## Core Protocol

Delegates to `$SKILLS/sdd-common/references/review-approval-pipeline.md` § Review Gate
for the core review gate logic (prompt → sub-agent → summary → fix loop).

## Workspace Overrides

The workspace skill overrides these shared protocol parameters:

| Param | Workspace Value |
|-------|-----------------|
| `review_prompt_type` | `workspace-review-offer` (not `post-change-review`) |
| `review_prompt_params` | `scope="{scope}" spec_name="{spec_name}"` |
| `review_skill` | `sdd-review-spec-docs` |
| `review_skill_path` | `$SKILLS/sdd-review-spec-docs/SKILL.md` |

## Caller-Supplied Parameters

| Param | Description | Example |
|-------|-------------|---------|
| `scope` | Label for the prompt's scope field | `"Requirements"` or `"Designs"` or `"Tasks"` |
| `spec_name` | Spec name passed to prompt and review skill | `"{feature}"` or `"{subSpecName}"` |
| `project_path` | Target repo path (omit for coordinator) | `"{repoPath}"` |
| `next_step` | Workflow step to proceed to after this gate | `"Phase R: Approve"` |

## Workspace-Specific Steps

| Stage | Action |
|-------|--------|
| Pre-review | None — tracker is already updated by the phase loop before this gate is invoked. |
| Post-review (review ran) | Run the canonical literal in `phase-loop.md` § Tracker Updates (`workspace/update-tracker.py --workspace {coordinator-path} --target {feature}/{repo-id} --phase {doc} --doc-status reviewed`). |
| Post-skip (review skipped) | Same literal as above with `--review-skipped` appended. |
| Post-fix | None — tracker stays at `reviewed` after the fix loop until approval. |

## Protocol

**MUST present** the review offer prompt. The user decides whether to run
the review or skip — the agent does NOT skip this step autonomously.
See `$SKILLS/sdd-common/references/prompt-conventions.md` § Mandatory Prompt Convention.

Present the `workspace-review-offer` prompt from the registry with params:
`scope="{scope}" spec_name="{spec_name}"`. See `$SKILLS/sdd-common/references/prompt-conventions.md` § Integration Pattern.

| Option | Action |
|--------|--------|
| Run quality review | Follow the shared review gate protocol (sub-agent launch, summary, optional fix loop). After review, update tracker and proceed to `{next_step}`. |
| Skip review | Record `--review-skipped` in tracker and proceed directly to `{next_step}`. |
