# Review Gate Pattern

Shared review gate workflow used by creation skills at every approval point.

## Contents

- [Pipeline](#pipeline)
- [Review Gate Session](#review-gate-session)
- [Conventions](#conventions)

## Pipeline

**Pipeline:** Validate → Review gate → **Post-review** → Pre-approval → Approval prompt → Complete.

1. Use `review/pipeline-tick.py --phase launch` to generate the sub-agent prompt.
   `--parent-todo` and `--gate-id` are **required** for launch.
2. Run the review sub-agent with the generated prompt.
3. **MANDATORY**: Run `--phase post-review` to get the authoritative artifact score.
   Present `artifact_score` and `per_document_scores` from output to the user — NOT the
   sub-agent's narrative score. Post-review creates cycle TODOs (if findings > 0) or
   cancels them (if zero findings), then routes to `post-fix` or `pre-approval`.
4. If fixes needed: apply → run `--phase post-fix` → present `artifact_score`.
5. **MANDATORY**: Run `--phase pre-approval` before presenting approval prompt.
   Pre-approval internally checks both document staleness and cross-validation staleness —
   no separate `check-re-review.py` call is needed.
   Use `approval_prompt_command` from pre-approval output (do NOT guess params).
6. After approval succeeds: run `--phase complete` (or `post_approval_command` from
   pre-approval output) to clean up gate session state.

All review/fix prompts are MANDATORY per `$SKILLS/sdd-common/references/prompt-conventions.md`.

## Review Gate Session

Pass `--workflow-mode create` for fresh docs, `resume` when continuing.
See `$SKILLS/sdd-common/references/review-approval-pipeline.md` § Review Gate Protocol Steps.

**Fix-loop TODO lifecycle:** Pass `--parent-todo <step_id> --gate-id <step_id>`
to all `prepare-pipeline.py` phase calls (required for launch, optional for other phases).
The launch output provides `phase_commands` (exact next-step commands) and
`todo_write_payload` (pass directly to TodoWrite — do NOT reshape keys).

## Conventions

Naming split — prose form is `review gate` (two words); filename form
is `review-gate-*.md` (kebab-case). Keep both shapes when authoring
new docs.
