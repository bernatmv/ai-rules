# Human-approval ceremony

> **Related protocols:** Called from review SKILL.md Dependencies tables
> (never via chain). Used by: `sdd-review-code`, `sdd-review-prd`,
> `sdd-review-spec-docs`, `sdd-review-steering-docs` before every
> `approve` transition.
> Uses: `prompt-conventions.md` § Integration Pattern,
> `approval-flow.md` § Pattern B.
> Harness context: `harness-detection.md`, `harness-notes.md`.

H1 gate: `approval/update-status.py … approve` refuses the transition
unless `SDD_HUMAN_APPROVAL=1` is set on the subprocess. The env var is
the only proof `ActorKindPolicy` accepts today; `--actor` is audit
attribution, not authorisation.

## Contents

- [Ceremony Steps](#ceremony-steps)
- [Audit Event Types](#audit-event-types)
- [Retry On H1 Rejection](#retry-on-h1-rejection)
- [Harness Integration](#harness-integration)
- [See Also](#see-also)

## Ceremony Steps

Before emitting `approval/update-status.py … approve`:

1. Render the confirmation prompt via the shim:

   ```
   .spec-workflow/sdd util/generate-prompt.py \
     --type approval-confirm-human \
     --params target_label="{doc-or-spec-label}"
   ```

   Consume the adapter-shaped output per
   [`prompt-conventions.md` § Integration Pattern](prompt-conventions.md#integration-pattern).

2. Branch on the user's selected option id:

   | `option.id` | Action |
   |-------------|--------|
   | `yes` | Invoke `approval/update-status.py approve` with `SDD_HUMAN_APPROVAL=1` on the subprocess env. |
   | `no` | Invoke `approval/update-status.py needs_revision` — no env marker. |
   | `reject` | Invoke `approval/update-status.py reject` — no env marker. |

   `needs_revision` and `reject` never consult the actor-kind policy.

## Audit Event Types

| `type` | When emitted |
|--------|--------------|
| `approval-status-change` | A status transition was committed (status JSON updated on disk). |
| `approval-attempt-rejected` | H1 gate refused an `approve` transition; nothing was committed to the approval JSON. |

`approval-attempt-rejected` is intent-only — the on-disk approval
status remains whatever it was before the attempt. Forensic readers
can reconcile every committed change against an
`approval-status-change` row and every refused attempt against an
`approval-attempt-rejected` row.

## Retry On H1 Rejection

When the caller forgets step 1, `update-status.py … approve` exits 0
with a structured `preflight_required` envelope whose
`next_action_command` carries the exact retry string. Prefer that
literal over hand-authoring:

```
SDD_HUMAN_APPROVAL=1 .spec-workflow/sdd approval/update-status.py \
  {approvalFilePath} approve {response}
```

Substitute `{approvalFilePath}` from `approval/request.py`'s JSON output
(`data.approvalFilePath`) and `{response}` with the audit comment.
`.spec-workflow/sdd` is the executable shim — never prefix with `python`.

The retry literal above is rendered by
`sdd_core.command_templates.approve_with_human_env(approval_file_path,
response)`. Update-status.py emits it on H1 rejection; this doc quotes
the literal for human readability — the helper is canonical, mismatch
fails the parity test in `tests/test_sdd_core/test_command_templates.py`.

### Workspace Phase Approvals

For the cross-repo workspace flow (`sdd-workspace-create-spec` Phase
R / D / T) the operational choice and the H1 attestation collapse
into a **single** prompt rendered via:

```
.spec-workflow/sdd util/generate-prompt.py \
  --type workspace-batch-approve-phase \
  --params doc=requirements repo_count={N}
```

`scope` is derived automatically from `doc` (`requirements` → `Requirements`,
`design` → `Designs`, `tasks` → `Tasks`); pass it explicitly only when the
display label needs to differ from the canonical mapping.

`generate-prompt.py` auto-injects `optional_params.retry_shim` from
`sdd_core.command_templates.build_workspace_phase_approve_command(...,
human_env=True)` — the same registry contract `approval-formal`
uses today (`prompt-registry.json :: approval-formal :: optional_params`).
Picking **Approve all** or **Approve individually** attests
human-in-the-loop; running the embedded `Retry shim:` literal sets
`SDD_HUMAN_APPROVAL=1` on the `workspace/phase-approve.py` subprocess.
Skip the standalone `approval-confirm-human` step on the workspace
path — the H1 contract is already in the same screen.

| Workspace `option.id` | Action |
|-----------------------|--------|
| `approve_all` | Run the prompt's `retry_shim` literal verbatim (already wraps `SDD_HUMAN_APPROVAL=1`). |
| `approve_individual` | Per repo: run `set-doc-approval.py` prefixed with `SDD_HUMAN_APPROVAL=1` (same env var). |
| `needs_revision` | Run `update-status.py needs_revision` — no env marker. |
| `reject` | Run `update-status.py reject` — no env marker. |

Retry-shim literals are minted by
`build_workspace_phase_approve_command(..., human_env=True)`;
parity-locked in `tests/test_sdd_core/test_command_templates.py`.

## Harness Integration

`util/generate-prompt.py` is harness-agnostic — the active adapter
shapes the payload:

| Harness | Payload | Host tool |
|---------|---------|-----------|
| Cursor | `{questions:[{id, prompt, options:[{id, label, description}]}]}` | `AskQuestion` |
| Claude Code (standard + task variant) | `{question, header, options:[{label, description}]}` | `AskUserQuestion` |

Identity resolution — [`harness-detection.md`](harness-detection.md).
Cross-harness envelope details — [`harness-notes.md` §
AskQuestion/AskUserQuestion prompts](harness-notes.md#askquestion--askuserquestion-prompts).
SKILL bodies never branch on harness identity; pipe
`generate-prompt.py` output straight into the host's prompt tool.

## See Also

- `prompt-registry.json` → `approval-confirm-human` — registered prompt.
- `sdd_core/security/actor.py` — `ActorKindPolicy` strategy; future GPG
  / SSH proofs plug in without SKILL edits.
- `sdd_core/command_templates.py::approve_with_human_env` — retry-shim
  builder (single source of truth).
- `approval/update-status.py` — H1 gate call site; emits the retry
  shim on rejection.
