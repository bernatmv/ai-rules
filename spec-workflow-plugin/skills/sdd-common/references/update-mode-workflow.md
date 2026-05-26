# Update Mode Workflow

Shared workflow for targeted edits to existing documents.

## Contents

- [Parameters](#parameters)
- [Steps](#steps)
- [Revise re-entry](#revise-re-entry)
- [Dependencies](#dependencies)
- [Multi-Document Batch](#multi-document-batch)
- [Cross-Repo Source](#cross-repo-source)

## Parameters

| Param | Description |
|-------|-------------|
| doc-root | Directory containing the target document(s) |
| review skill | Skill for `review_first` hand-off |
| approval category | `spec` / `steering` / `discovery` |
| target-name | Approval target-name value (spec name, steering name, or discovery project) |
| downstream rules | Skill-specific downstream impact table, or `none` |
| thought-partner | `required-with-triage` = triage then explore; `required` = always explore; `none` = skip |
| thought-partner-questions | Skill-specific exploration reference (when thought-partner ≠ `none`) |
| thought-partner-depth | `full` = multi-turn until one-sentence gate; `light` = single round then proceed |

> **Note:** Scripts take `--workspace`; `doc-root` is agent-only.

## Steps

### Step 1.0: Bind gate sequence

At update-mode entry, run:

```
.spec-workflow/sdd review/pipeline-tick.py --phase update-launch --target-name "{target-name}" --category {category} --workflow-mode update --doc-list "{doc_list}" --parent-todo {step_id} --gate-id {step_id}
```

Pass `todo_write_payload` to TodoWrite. The envelope's
`progress_checklist` (key `update-mode.default.v1`) binds Steps 4 / 6
/ 7.1 / 8.

1. **Read** only the target document(s) from `{doc-root}`.
   After Read, verify the target exists on disk: `ls -la {doc_path} 2>/dev/null`.
   If file not found but Read returned content, treat as non-existent and
   fall through to creation mode. Do not present the collision prompt.

2. **Change Exploration** *(skip when `thought-partner: none`)*

   Determine exploration path:

   **Cosmetic change?** → Step 2a (triage confirmation)
   **Non-cosmetic or ambiguous?** → Step 2b or 2c (full or light exploration)

   **2a. Triage** *(only when `thought-partner: required-with-triage`)*

   Assess which category applies:

   **Cosmetic —** surface-only edits (spelling, grammar, punctuation,
   whitespace, markdown, broken links) localized to one paragraph or
   formatting block, with no change to terms of art, metrics, IDs, or technical decisions.
   Emit `.spec-workflow/sdd util/generate-prompt.py --type cosmetic-change-confirmation --params summary="..."`,
   feed JSON into `AskQuestion`. User confirms → skip to Step 3.

   **Factual sync —** numeric counts, file listings, version numbers,
   or directory trees only; architecture, design principles, product
   goals, and conventions remain unchanged.
   Emit `.spec-workflow/sdd util/generate-prompt.py --type factual-sync-confirmation --params summary="..."`,
   feed JSON into `AskQuestion`. User confirms → skip to Step 3.

   User disagrees or NEITHER cosmetic NOR factual sync → fall through to 2b/2c.

   **2b. Full exploration** *(depth = `full`)*

   Load `thought-partner-questions` reference. Work through each dimension across multiple turns.

   **Gate:** Articulate the proposed change in one sentence. Get user confirmation before Step 3.

   **2c. Light exploration** *(depth = `light`)*

   Load `thought-partner-questions` reference. Ask all dimensions in a single message. Proceed after user responds.

3. **Edit** — make the requested changes directly (no template re-analysis).

4. **Validate** per `pre-approval-validation.md` (size check).

5. **Downstream rules** — apply per skill params. Skip if `none`.

6. **Present changes** — run:

   ```
   .spec-workflow/sdd util/generate-prompt.py --type review-action \
     --params doc={doc}
   ```

   Pass the resulting JSON to AskQuestion (Cursor) or render the
   markdown (Claude Code). See `prompt-conventions.md` § Integration
   Pattern for adapter-output handling.

7. **Handle response:**

   | Response | Action |
   |----------|--------|
   | `accept` | Proceed to Step 7.1 |
   | `review_first` | Run review gate (see protocol below), then proceed to Step 7.1 |
   | `revise` | Return to Step 3 (edit only); see [Revise re-entry](#revise-re-entry) for the gate-replay sequence |
   | `discard` | Cancel and exit |

   **`review_first` protocol.** Run the review gate per
   `$SKILLS/sdd-common/references/review-approval-pipeline.md`
   § Review Gate Protocol Steps. The launch flag-set is documented at
   `launch-command-shape.md`; the post-fix → next_prompt loop is
   handled by the envelope's `phase_commands.post_fix`.

7.1. **Pre-approval gate** (mandatory):
     `.spec-workflow/sdd review/pipeline-tick.py --category {category} --target-name "{target-name}" --phase pre-approval --doc-list "{doc_list}" --parent-todo {step_id} --gate-id {step_id}`
     If `can_approve: false`: follow `required_action`. If output contains `todo_write_payload`, pass to TodoWrite. Do NOT present the approval prompt.
     If `can_approve: true`: proceed to Step 8 using `approval_command` from output.

8. **Approve** — follow `approval-flow.md` § Pattern A with skill params.
   See `prompt-conventions.md` § Integration Pattern for AskQuestion bridging.

   **MUST** invoke `.spec-workflow/sdd approval/request.py` and `.spec-workflow/sdd approval/update-status.py`
   even if the user already confirmed via prompt. The AskQuestion
   confirmation is a user intent signal — the script calls are the
   system-of-record actions. Use `approvalFilePath` from the request
   output as the `{source_file}` argument.

9. **Done** — report downstream suggestions if applicable.

## Revise re-entry

When the user requests revisions (review-action response = `revise` or
free-text "fix suggestions") after Step 7:

1. Apply the edits (Step 3, edit-only).
2. Run:

   ```
   .spec-workflow/sdd review/pipeline-tick.py --phase post-fix --target-name "{target-name}" --category {category} --workflow-mode update --doc-list "{doc_list}" --fix-cycle N --max-cycles 2 --parent-todo {step_id} --gate-id {step_id}
   ```

   The envelope refreshes the `update-mode.default.v1` checklist —
   Steps 4 / 6 / 7.1 / 8 still apply.
3. Continue from Step 4 (Validate). Do not skip.

## Dependencies

| Step | File / Topic | Notes |
|------|-------------|-------|
| Step 1.0 (entry) | `sdd_core.command_templates.build_pipeline_tick_update_launch_command` | Canonical entry literal (see Step 1.0 above) |
| Step 1.0 (entry guard) | Advisory `wrong_update_entry_phase` (emitted by `review/pipeline-tick.py`) | Blocks `--phase launch --workflow-mode update --scope per-document` when the spec's required docs already exist; `next_action_command` matches the Step 1.0 literal byte-for-byte |
| Step 7 (review_first) | `$SKILLS/sdd-common/references/review-approval-pipeline.md` § Review Gate | |

## Multi-Document Batch

When multiple docs are changed as part of a single logical update:
- Edit all docs (Step 3)
- Validate all docs (Step 4, `final` scope)
- Present changes as a batch (Step 6, `doc` = comma-separated list)
- Review via `final` scope sub-agent (all docs together)
- Single approval (Step 8)

## Cross-Repo Source

When the user provides an external reference (PR, branch, or other repo):

1. **Extract** — Fetch the external content using path-scoped diff:
   `git diff main...{branch} --name-only -- {relevant_path}/`
   For PRs: `git fetch origin pull/{N}/head:pr-{N}` first, then diff against `pr-{N}`.

2. **Compare** — For each target doc, diff external vs local:
   - Identify genuinely new content (not in local)
   - Identify conflicting content (different in both)
   - Identify content only in local (preserve)

3. **Present delta** — Show the user a summary of what's new/different,
   not the full documents. Include line-level diffs for conflicts.

4. **Merge** — Apply only the new/changed content into local docs.
   Preserve local-only content unless the user explicitly discards it.

5. Continue from Step 3 (Edit) in the standard update flow.
