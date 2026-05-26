# Task Sub-Agent Skill Invocation Templates (Workspace)

Workspace-specific extensions to the shared sub-agent review templates.

> **Sub-agent dispatch is canonical.** The
> `review/pipeline-tick.py --phase launch` envelope emits the verbatim
> `sub_agent_prompt`, the required `target_repo_facts`, and the
> `phase_commands.{forward_key}` post-review tick — dispatch via
> `adapter.dispatch_hints().tool_name` and pass the prompt verbatim.
> Build the prompt's `{target_repo_facts}` block via
> `sdd_core.sub_agent_prompts.build_target_repo_facts(repo_path)` so the
> parent agent's filesystem access surfaces the target's `CLAUDE.md`,
> `DEVELOP.md`, etc., inline before dispatch (sub-agent sandbox
> cannot read sibling repos). Verbatim-pass contract and the SHA-256
> echo check live in
> `$SKILLS/sdd-common/references/review-approval-pipeline.md
> § Sub-Agent Guidelines`.

## Base Templates

See `$SKILLS/sdd-common/references/review-approval-pipeline.md` § Sub-Agent Guidelines for:
- General sub-agent guidelines
- Spec Docs Review Template (for `sdd-review-spec-docs`)
- Steering Docs Review Template (for `sdd-review-steering-docs`)

## General Template

Follow `$SKILLS/sdd-common/references/review-approval-pipeline.md`
§ Sub-Agent Guidelines. Add these workspace-specific parameters to
the template:

- Workspace phase: `{current_phase}`
- Available documents: `{available_docs}`

## Workspace Review Additions

When invoking the shared Spec Docs Review Template in a workspace context,
append these workspace-specific parameters:

```
Workspace additions:
  - Workspace phase: {phase}
  - The skill's § Workspace Mode section defines which steps to skip
    based on phase and available documents.

Verification: After completion, confirm that the per-doc snapshot
  {repo_path}/.spec-workflow/specs/{sub_spec_name}/review-quality-{doc}.json
exists. If workspace phase is "requirements" or "design", verify that the
reviewed document's `last_reviewed_at` field has a non-null timestamp.
`last_full_review_at` will only be non-null after all three documents
(requirements, design, tasks) have been reviewed.
```
