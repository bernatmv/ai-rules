# Pre-Flight Protocol

Run workspace health verification before any skill workflow, and use the
batched reference-read sequence for cold-start review gates.

## Contents

- [Workspace Health Facade](#workspace-health-facade)
- [Harness Detection](#harness-detection)
- [Deferred-Tool Preload](#deferred-tool-preload)
- [Batched Reference-Read Ack](#batched-reference-read-ack)
- [Skills-Pack Version Drift](#skills-pack-version-drift)
- [Task / Todo Update Cadence](#task--todo-update-cadence)

## Workspace Health Facade

Run the workspace health facade before any skill workflow:

    .spec-workflow/sdd workspace/ensure-healthy.py --workspace {path}

The script handles both first-time initialization and ongoing health verification.
If the workspace is already healthy, this is a fast no-op (stat calls only).

**Feedback loop**: The script auto-fixes and re-verifies internally. If it reports
failure after auto-fix, present the error to the user before proceeding.

**Advisories surfacing**: When `ensure-healthy.py` returns advisories (`warn`
checks, e.g. `template_content_hash` drift), the success message ends with
`— advisories: {names}`. Echo these to the user in one line before proceeding so
they are visible before any spec work begins.

## Harness Detection

The loader resolves the harness via a priority-ordered detector
registry. On first use it persists the detected identity to
`harness.json`. `workspace/ensure-healthy.py --auto-fix` also re-runs
detection through the `harness_state_present` health check. Agents
never read `harness.json` directly.

Run `util/probe-harness.py` explicitly when you want a verbose
detection envelope:

    .spec-workflow/sdd util/probe-harness.py --workspace {path}

The probe reads `SDD_HARNESS_OVERRIDE`, `CURSOR_AGENT`,
`CURSOR_WORKSPACE`, and any of `CLAUDE_CODE_VERSION` /
`CLAUDECODE=1` / `CLAUDE_CODE_ENTRYPOINT` deterministically (no
agent self-report). A failed selfcheck aborts the persist, so the
state file is always consistent with the detected adapter.

## Deferred-Tool Preload

Claude Code variants list `AskUserQuestion` / `TaskCreate` /
`TaskUpdate` / `TodoWrite` / `WebFetch` as deferred tools — the tools
are visible in the deferred-tools index but not callable until the
agent loads the schema via `ToolSearch`. Surface the preload via the
workspace health facade, or run the probe directly:

    .spec-workflow/sdd util/preflight-tools.py --workspace .

The facade advertises this as the `deferred_tools_preload` advisory
and echoes `— advisories: deferred_tools_preload` on the success tail
until the preload completes.

## Batched Reference-Read Ack

Cold-start sequence for any review gate:

1. Run `.spec-workflow/sdd review/pipeline-tick.py --phase launch …`.
   Severity ladder:
   - First launch of a gate with missing reference acks returns
     `status: "ok"` with a stderr warning and
     `missing_preconditions` on the payload. **The payload carries
     `next_action_command_sequence`** — a single copy-paste Bash
     chain that reads every reference, records the batched ack, and
     re-runs `--phase launch`.
   - Subsequent launches in the same session with the same missing
     acks return `status: "blocked"`; dependent phases
     (`post-review`, `post-fix`) refuse to proceed.
2. Execute `next_action_command_sequence` in one Bash turn, equivalent
   to manually running the reads, recording the batched ack, and
   relaunching:

       eval "$(jq -r '.data.next_action_command_sequence' < envelope.json)"

   The chain itself looks like:

       .spec-workflow/sdd review/pipeline-tick.py --category <c> --target-name <n> \
         --phase launch --workspace . \
         --review-skill <skill> --doc-list <docs> --scope <scope> \
         --parent-todo <step> --gate-id <step>
       # read the warning payload, then run:
       eval "$(jq -r '.data.next_action_command_sequence' < envelope.json)"

3. The relaunch that the chain performs clears the gate.

### Severity Ladder — Why Warn First?

A newly-required reference (e.g. adding a new entry to
`DEFAULT_REQUIRED` in
`review/pipeline_phases/launch_preconditions/policy.py`) would
otherwise retroactively block every spec mid-flight at upgrade time.
The warn-first policy lets the agent see the requirement once, ack
via the copy-paste chain, and continue — any genuine skip (ignoring
the warn) is caught on the next call.

Source of truth: `decide_read_severity` in
`review/pipeline_phases/launch_preconditions/policy.py`. Payload
shape: `build_missing_payload` in
`review/pipeline_phases/launch_preconditions/payload.py`.

The ack ledger records one (path, sha) pair per reference. Pairs
persist across gates until
`.spec-workflow/sdd review/pipeline-tick.py --phase reset-reference-acks`
runs, at which point every pair is cleared and the next launch
re-requires ack of the reference bundle.

## Skills-Pack Version Drift

Workspace pre-flight compares the coordinator's `SKILL.md`
`metadata.version` against each target repo's same field. Drift is
warn-only; the workflow continues. `workspace/sync-skills-pack.py` is
the voluntary remediation command — there is no auto-resolution.

## Skills-Registry Hash Drift

`workspace/ensure-healthy.py` runs `check_skills_registry_hash_drift`,
which recomputes each installed skill's content hash and compares it
to the recorded `contentHash` in `skills-registry.json`. Mismatch
surfaces as the warn-level advisory `skills_registry_hash_drift`. It
**never blocks the flow** and **is never auto-resolved** — re-run
`npm run generate-registry` (out-of-band) when the drift signals an
intentional content change.

| Condition | Outcome | Action |
|---|---|---|
| Coordinator and target SKILL.md `metadata.version` match | None | Continue |
| Version mismatch, reference present on target | `skills-pack-drift` advisory at `warn` | Log; continue |
| Version mismatch, reference missing on target | `skills-pack-drift` advisory at `warn` + `next_action_command` to `sync-skills-pack.py` | Log; continue |

## Task / Todo Update Cadence

The harness injects a staleness reminder when ``TaskUpdate`` /
``TodoWrite`` is silent for too long. To avoid the reminder and keep
observability high:

- Transition a task to ``completed`` the moment its exit criteria are
  met — do not wait until the next ``in_progress`` begins.
- No single ``in_progress`` task should span more than 5 tool calls.
  If work overruns, split the task.
- Review-skill workflows use ``review/pipeline-tick.py``'s
  ``todo_write_payload`` — pass directly to ``TodoWrite`` /
  ``TaskUpdate``; do not hand-roll todos. See
  `$SKILLS/sdd-common/references/harness-notes.md` § TODO tool
  variants for payload shape and
  `$SKILLS/sdd-common/references/parallel-batch-hygiene.md` for how
  the TODO call relates to the rest of a batched turn.
- When a conversational step issues multiple prompt or session-state
  writes between ticks, split into a sub-task per readiness gate (or
  per question block) so the cadence stays ahead of the harness
  staleness reminder. The canonical `todo_write_payload` shape comes
  from `.spec-workflow/sdd review/pipeline-tick.py` — see
  `$SKILLS/sdd-common/references/harness-notes.md § TODO tool
  variants`.
