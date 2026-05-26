# Safety Rules


## Contents

- [Approval Safety](#approval-safety)
- [Workflow Safety](#workflow-safety)
- [Flag / Prompt Lookup](#flag--prompt-lookup)
- [Data Safety](#data-safety)

## Approval Safety

| Rule | Rationale |
|------|-----------|
| Use `sdd-manage-status` for formal approvals; inline approval (Pattern A) is accepted for low-ceremony operations per `approval-flow.md` | Ensures audit trail; Pattern A still calls request + update + delete scripts |
| Skip ≠ auto-approve | Dismissing or skipping an approval prompt means "Skip for now" — do NOT auto-approve. Pause and inform the user that approval is required. |
| Block on delete failure | Return to approval flow — never proceed with stale approval |
| 3-cycle iteration limit | Escalate to user after 3 revision cycles without approval |

### Per-Skill Key Rules

**sdd-create-spec**: Sequential phases (requirements → design → tasks); one spec at a time; Review and Approval Pipeline (`per-document`) for each phase.

**sdd-create-steering**: Sequential phases (product → tech → structure); categoryName must be "steering"; Pipeline (`per-document`) for creation, (`final`) for updates.

**sdd-implement-spec**: All docs must be approved before implementation; log before marking complete.

**sdd-manage-status**: Never auto-approve in a loop; require response text for all transitions.

**sdd-archive-spec**: Never archive without explicit user confirmation.

**sdd-workspace-create-spec**: Never modify target repo files outside `.spec-workflow/`; always validate manifest paths; batch approval via `sdd-create-spec` (auto-detected); use coordinator's `sdd_core`.

**sdd-manage-template**: Never overwrite user-templates without confirmation; reset requires explicit confirmation; sync only touches `.spec-workflow/templates/`.

**sdd-create-discovery**: Read-modify-write for all manifest updates (no partial file writes); no overwrite on create (offer resume); idempotent duplicate warnings; preserve existing files on recovery.

## Workflow Safety

### Agent Output Hygiene (Cursor)

In user-visible text:

1. **Do not narrate internal mechanics** — no "generating prompt",
   "running script", "reading registry".
2. **Present decisions directly** via AskQuestion with no preamble.
3. **Do not echo script paths or command strings.** Use a code block
   if a path must appear for debugging.
4. **State outcomes, then present next decision.** Example:
   "tasks.md created with 3 tasks" → AskQuestion for review.

### Step Continuation

- Steps execute sequentially.
- Write + Approve steps are atomic pairs — never pause between them.
- Self-checks, summaries, and intermediate outputs are NOT stopping points.
- Only mandatory prompts (approval, triage, user-facing decision) pause the workflow.

**Anti-pattern:** Asking "Shall I proceed?" or "Ready to run the pipeline?" after a self-check.

| Rule | Rationale |
|------|-----------|
| Sequential phases | Prevents half-approved state from leaking into next phase |
| One spec at a time | Prevents context mixing; complete or pause before starting another |
| categoryName conventions | Use literal spec name for specs, literal "steering" for steering docs |

### Script Error Handling

All SDD scripts use `cli.run_main()` which catches unhandled exceptions and returns structured JSON errors with traceback detail. If a script returns an error containing "Script crashed:", report the traceback to the user and wait for guidance — do NOT silently work around it or substitute manual checks.

## Flag / Prompt Lookup

The canonical invocation for every SDD script is inlined at its call site (SKILL.md Step N) and in `$SKILLS/sdd-common/references/tool-patterns.md § Common Invocations`. Copy from those sources first. Only fall back to the lookups below when the call site does not inline the command:

| Situation | Fallback call |
|-----------|---------------|
| Unfamiliar SDD script flag | `.spec-workflow/sdd {group}/{script}.py --help` |
| Unknown prompt type key | `.spec-workflow/sdd util/generate-prompt.py --list` |
| Unknown script in a group | `.spec-workflow/sdd util/script-index.py --group {group}` |

If a guessed flag or prompt-type reaches a script, the envelope returns `status: result` with `severity: warn`, a `did_you_mean` list, and a `next_action_command` (see `$SKILLS/sdd-common/scripts/sdd_core/cli.py::_JsonErrorParser` and `util/generate-prompt.py::_emit_unknown_prompt_type_warn`). Treat the warn as a recoverable typo, not a system fault — correct the flag and retry.

## Data Safety

| Rule | Rationale |
|------|-----------|
| Atomic writes | Use tempfile + os.replace() for approval and snapshot files |
| Approval filePath only | Never pass document content in approval requests |
| NEVER write without confirmation | Task refresh, archive operations require explicit user confirmation |
