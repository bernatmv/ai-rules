# Workspace Safety Rules & Edge Cases

## Contents

- [Safety Rules](#safety-rules)
- [Edge Cases](#edge-cases)

## Safety Rules

**Shared safety rules:** See `$SKILLS/sdd-common/references/safety-rules.md`
§ Approval Safety and § Per-Skill Key Rules (`sdd-workspace-create-spec` row).

Workspace-specific rules:

- **Never modify target repo files outside `.spec-workflow/`.** Workspace operations only create/update spec documents and approval artifacts.
- **Always validate manifest paths before entering target repo.** Run `validate_manifest()` to catch stale paths.
- **Never modify existing scripts' CLI interfaces.** Workspace scripts compose library functions, not CLI wrappers.
- **Always use coordinator's `sdd_core`.** Target repos may have an older vendored copy. The `_SCRIPT_DIR`/`sys.path` pattern ensures correct resolution.
- **Never approve without offering review.** Each phase's Approve sub-step MUST be preceded by the Review sub-step. The agent must present the batch review prompt (via `generate-prompt.py --type workspace-batch-review-phase`) and await the user's choice before proceeding to approval. Skipping the review prompt is a workflow violation even if the agent believes the documents are correct.

## Edge Cases

| Scenario | Action |
|----------|--------|
| Manifest path invalid | Report error, ask user to update manifest |
| Target repo has existing spec with same name | Warn user, ask for alternative sub-spec name |
| Sub-spec creation fails validation 3 times | Set tracker status to "failed", continue to next repo |
| All sub-specs cancelled | Mark workspace as cancelled |
| Target repo `.spec-workflow/` not initialized | Run `.spec-workflow/sdd workspace/init.py --workspace` (idempotent) |
| Target repo `sdd_core` version differs | No impact — workspace scripts use coordinator's `sdd_core` |
| Tracker file corrupted/missing | Re-create from manifest + live polling |
| Coordinator is also a target repo | Structurally prevented — `validate_manifest()` requires exactly one `repoType: "coordinator"` entry. A repo cannot be both coordinator and target. |
