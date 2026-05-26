# Phase Loop — Per-Repo Iteration & Phase-Specific Steps

> Single reference for all phase loops (R, D, T). SKILL.md Steps 2–4.

## Contents

- [Per-Repo Iteration Order](#per-repo-iteration-order)
- [Coordinator-Specific Behavior](#coordinator-specific-behavior)
- [Shared Patterns](#shared-patterns)
  - [Mid-Phase Resume Points](#mid-phase-resume-points)
  - [Error Handling](#error-handling)
  - [Phase Completion Check](#phase-completion-check)
  - [Tracker Updates](#tracker-updates)
- [Batch Review & Approve](#batch-review--approve)
  - [Review Step](#review-step)
  - [Approve Step](#approve-step)
- [Phase R — Requirements](#phase-r--requirements)
  - [Phase R: Create](#phase-r-create)
  - [Phase R: Validate](#phase-r-validate)
  - [Phase R: Review & Approve](#phase-r-review--approve)
- [Phase D — Design & Phase T — Tasks](#phase-d--design--phase-t--tasks)
  - [Phase-specific extras](#phase-specific-extras)

## Per-Repo Iteration Order

Process repos in **tracker order** (`workspace-tracker.json → subSpecs[]`).
Coordinator (`repoType: "coordinator"`) is always first.

Before iterating, resolve `skipPhases` per repo via the manifest:
- `repo.status` is cancelled/failed → skip
- Current phase in `skipPhases` → set `docStatus.{phase} = "skipped"`, continue
- Otherwise → run phase-specific action (see Phase R/D/T below)

## Coordinator-Specific Behavior

When processing `repoType == "coordinator"`:
- **Skip** `extract-delegation` (coordinator uses manifest directly)
- **Use** `coordination-workflow.md` for content formatting (§ section per phase below)
- Coordinator's `subSpecName` equals the feature name

| Phase | coordination-workflow.md Section |
|-------|----------------------------------|
| R     | § Cross-Repo Scope Section       |
| D     | § Per-Repo Design Delegation     |
| T     | § Task Metadata Fields           |

## Shared Patterns

### Mid-Phase Resume Points

When resuming a workspace mid-phase, use the tracker's `docStatus.{phase}`
to determine the correct resume point:

| `docStatus.{phase}` | Resume from |
|----------------------|-------------|
| `pending`            | Create step |
| `created`            | Validate step |
| `validated`          | Review gate |
| `reviewed`           | Approve step |
| `revision_requested` | Create step (apply revision feedback) |

Run `check-status.py --phase {phase}` to see which repos need work
and at which stage. Use `--verify-paths` to confirm spec directories
exist on disk before proceeding (prevents phantom directory issues from
stale sessions).

### Error Handling

Each phase action retries up to **3 times** on failure. After 3 failed attempts:
set `docStatus.{phase} = "failed"`, record repo in `phaseGates.{phase}.reposFailed`,
warn user, continue to next repo.

### Phase Completion Check

After all repos are processed for the current phase:

1. Run `phase-status.py --target {feature} --phase {phase}` to render the
   per-repo summary.
2. After the last repo's `phase-approve.py --doc {phase}` returns success,
   `currentPhase` is **already advanced** — `apply_phase_approval` runs
   `workspace_phase.advance_with_gate(...)` in the same atomic
   `finalize_and_save` write that updates each repo's `docStatus`.
   Calling `advance-phase.py` afterwards is **only** needed for v1.1.0
   trackers (where the atomic write was not yet in place); on v2+ it
   returns `data.alreadyAdvanced=true` and is a no-op.
3. Any repos still need work:
   → present status, ask user how to proceed (retry, skip, cancel)

### Tracker Updates

| Event | Script | docStatus |
|-------|--------|-----------|
| Doc created | `update-tracker.py --status {phase}_created --phase {phase}` | `created` |
| Validation passed | `check-spec-shape.py` (auto, via `--tracker-root`) | `validated` |
| Review completed | `update-tracker.py --phase {phase} --doc-status reviewed` | `reviewed` |
| Review skipped | `update-tracker.py --phase {phase} --doc-status reviewed --review-skipped` | `reviewed` |
| Approved | `phase-approve.py --doc {phase}` | `approved` (also advances `subSpecs[].status` to `{phase}_approved`) |
| Failed (max retries) | `update-tracker.py --status failed` | `failed` |
| Skipped (skipPhases) | (inline) | `skipped` |
| Revision requested | (inline) | `revision_requested` |

## Batch Review & Approve

Each phase executes Review then Approve as a pair. Do NOT skip Review.

### Review Step

> **MANDATORY GATE** — Present the review prompt before Approve.
> The user may choose "Skip review" — but the agent must always ask.
> If about to present approval without having presented review, STOP.

Present the `workspace-batch-review-phase` prompt from the registry with params:
`scope="{scope}" doc="{doc}" repo_count="{N}"`. See `$SKILLS/sdd-common/references/prompt-conventions.md` § Integration Pattern.

| Option | Action |
|--------|--------|
| Review all | For each repo with `docStatus.{doc} == "validated"`, run the canonical launch shim per repo and dispatch the emitted `data.sub_agent_prompt` via the host's sub-agent tool. Validate the artifact via `validate-review-artifact.py` and retry up to 3× per § Error Handling. See `$SKILLS/sdd-common/references/review-approval-pipeline.md § Sub-Agent Guidelines` for the verbatim-pass contract.<br><br>Canonical launch shim: `.spec-workflow/sdd review/pipeline-tick.py --phase launch --review-skill sdd-review-spec-docs --workspace {repo-path} --doc-list "{doc}.md" --category spec --target-name "{sub-spec}" --scope per-document --workflow-mode create --parent-todo {step-id} --gate-id {step-id}`. |
| Review individually | Run the same canonical launch shim once per repo with that repo's `{repo-path}` and `{sub-spec}`; present findings after each. |
| Skip review | Mark as review-skipped, proceed to Approve |

After review: update tracker with `--doc-status reviewed` (add `--review-skipped` if user skipped).

### Approve Step

**Pre-approval check:** Run `phase-status.py` — all active repos must show
`docStatus.{doc} = "reviewed"`. If any show `"validated"`, review was skipped;
go back to Review Step.

Present the `workspace-batch-approve-phase` prompt from the registry with params:
`scope="{scope}" doc="{doc}" repo_count="{N}"`. See `$SKILLS/sdd-common/references/prompt-conventions.md` § Integration Pattern.
`generate-prompt.py` auto-injects `optional_params.retry_shim` from
`sdd_core.command_templates.build_workspace_phase_approve_command(...,
human_env=True)` — the rendered prompt body already carries the H1
attestation sentence and the `SDD_HUMAN_APPROVAL=1` retry-shim
literal.

| `option.id` | Action |
|-------------|--------|
| `approve_all` | Run the prompt's `retry_shim` literal verbatim (already wraps `SDD_HUMAN_APPROVAL=1` around `workspace/phase-approve.py --doc {doc}`). |
| `approve_individual` | Per repo: run `set-doc-approval.py` prefixed with `SDD_HUMAN_APPROVAL=1` (same env var). |
| `needs_revision` | Run `update-status.py needs_revision` — no env marker. |
| `reject` | Run `update-status.py reject` — no env marker. |

**Do NOT present a second `approval-confirm-human` prompt for
workspace phases.** The H1 attestation is folded into the same prompt
as the operational choice (`workspace-batch-approve-phase`
`optional_params.retry_shim`) — see `approval-formal` for the prior
art.

On approve: the rendered `retry_shim` literal runs `workspace/phase-approve.py --doc {doc}` with `SDD_HUMAN_APPROVAL=1` on the first try. The atomic write also bumps `currentPhase` and seals `phaseGates.{doc}`. Legacy single-repo flow → see `manifest-schema.md` § v1.1.0 Vertical Flow (backward compatible).

**Outcome → next action.** When the per-doc envelope reports a
non-trivial outcome at the Approve gate, route by the literal status
string the script emits:

| Outcome | Next action |
|---------|-------------|
| `pre-approval blocked: 1 doc(s) need re-review` | `pipeline-tick --phase launch …` (re-launch the gate after `fix_cycle == max_cycles` and a fresh doc edit; the launch envelope's `reentry_cycle` and `reentry_instruction` confirm the auto-replay window). |
| `tracker-update-skipped` advisory | Run the literal `update-tracker.py` command emitted in the advisory's `next_action_command`. |
| `needs_revision` / `reject` | Loop back to the Validate step with the reviewer's findings; do not re-emit the approval prompt without changes. |

---

## Phase R — Requirements

Sub-steps in order: **Create → Validate → Review → Approve**.

### Phase R: Create

For each repo in tracker order (§ Per-Repo Iteration Order):

1. **Coordinator** → see § Coordinator-Specific Behavior. Target repos continue below.

2. **Extract delegation context** (target repos only):
   ```
   .spec-workflow/sdd workspace/extract-delegation.py \
     --workspace . --target {feature}/{repo-id} --doc-scope requirements
   ```
   Verify `role` is non-empty. `requirements_subset` may be empty when
   the coordination requirements are cross-cutting rather than per-repo —
   this is expected. Use the repo `role` and full coordination requirements
   as context instead.

3. **Init target repo** — run pre-flight per `$SKILLS/sdd-common/references/pre-flight-protocol.md`:
   ```
   .spec-workflow/sdd workspace/ensure-healthy.py --workspace {repoPath}
   ```

4. **Render the template** — read
   `data.template_resolve_commands["requirements.md"]` from the
   `review/pipeline-tick.py --phase pre-launch-check --category spec --target-name {sub-spec} -- --doc requirements.md`
   envelope and run it verbatim. The literal is emitted by
   `command_templates.template_resolve_command(...)`; never hand-author
   the script name or flag spelling. If `pre-launch-check` has not run
   yet, run it first; the cold-path
   `util/resolve-template.py --type requirements ...` literal lives in
   `$SKILLS/sdd-common/references/troubleshooting.md § Template Render
   Fallbacks`.

   **Coordinator repo:** swap `--type requirements` with
   `--type workspace-requirements` so the rendered template includes
   the `Cross-Repo Scope` section (and the optional `Open Questions`
   stub). Target repos use the standard `--type requirements` (sub-spec
   content is per-repo). This mirrors the bug-fix mode swap documented
   in `sdd-create-spec/SKILL.md`.

   Write the returned `data.content` to
   `{repoPath}/.spec-workflow/specs/{subSpecName}/requirements.md`.

5. **Read authoring guardrails** — the same `pre-launch-check`
   envelope from step 4 carries `data.authoring_guardrails[]` (sourced
   from `requirements_antipatterns.yaml`). Each entry is a write-time
   rule the agent MUST honour while drafting. Coordinator
   `requirements.md` is the high-risk surface — it naturally mentions
   the underlying mechanism (script names, HTTP routes, config
   literals) and trips `source-extension` / `http-route` /
   `api-config` rules at validate time. Surface the rule list before
   authoring, not after the lint fires. See also
   `$SKILLS/sdd-common/references/tool-patterns.md` § `Pre-Launch Envelope Contract`
   (specifically the `authoring_guardrails` row).

6. **Create requirements.md** — follow "Write requirements.md" in `sdd-create-spec/SKILL.md`
   for spec `{subSpecName}` in `{repoPath}`. Skip subsequent steps (approval, design, tasks).
   Use delegation context: `role` shapes scope, `requirements_subset` seeds content.

7. **Update tracker**:
   ```
   .spec-workflow/sdd workspace/update-tracker.py \
     --workspace . --target {feature}/{repo-id} \
     --status requirements_created --phase requirements [--auto-generated]
   ```

### Phase R: Validate

For each repo with `docStatus.requirements == "created"`, use the
**coordinator-rooted** form — `--workspace` points at the coordinator
path, `--target` carries the workspace-target form:

```
.spec-workflow/sdd workspace/check-spec-shape.py \
  --workspace {coordinator-path} --target {feature}/{repo-id} \
  --doc requirements
```

The script resolves the target's spec directory via the coordinator's
tracker (`subSpecs[].repoPath`) and auto-updates the coordinator
tracker's `docStatus.requirements` on success — no `--tracker-root`
boilerplate needed.

**Target-rooted alternative.** Pass `--workspace {coordinator-path}`
(an absolute path) regardless of CWD; the coordinator-rooted form
is the single supported shape — see `command-reference.md` for the
flag table.

On success: auto-sets `docStatus.requirements = "validated"`. When
neither `--tracker-root` nor a coordinator-rooted `--workspace` is
supplied, the success envelope carries a `tracker-update-skipped`
advisory with the literal `update-tracker.py` recovery command.
On failure: retry per § Error Handling.

### Phase R: Review & Approve

Follow § Batch Review & Approve with:
`scope = "Requirements"`, `doc = "requirements"`, `N` = active repo count.

---

## Phase D — Design & Phase T — Tasks

Follow Phase R's pattern (Create → Validate → Review → Approve) with substitutions:

| | Phase D | Phase T |
|---|---------|---------|
| **Doc** | `design` | `tasks` |
| **Gate** | `docStatus.requirements == "approved"` | `docStatus.design == "approved"` |
| **Prior docs** | requirements.md | requirements.md + design.md |
| **Delegation `--doc-scope`** | `design` | _(no delegation extract)_ |
| **Create step** | "Write design.md" in `sdd-create-spec` | "Write tasks.md" in `sdd-create-spec` |
| **Tracker status** | `design_created` | `tasks_created` |
| **Review scope** | `"Designs"` | `"Tasks"` |

### Phase-specific extras

- **Template recipe (every Create step)** — read the matching entry
  from `data.template_resolve_commands` on the latest
  `review/pipeline-tick.py --phase pre-launch-check` envelope
  (`requirements.md` → `design.md` → `tasks.md`). The shim literal is
  emitted by `command_templates.template_resolve_command(...)`; do not
  guess script names or flag spellings.
- **Phase D: Validate** — verify sub-spec `design.md` API contracts match coordination `design.md`. Present deltas.
- **Phase T: Create** — run completeness check per `$SKILLS/sdd-common/references/task-validation-rules.md` § Task Completeness Checks. Add missing tasks if gaps found.
- **Phase T: Validate** — verify all requirements have corresponding tasks across repos. Present gaps.

After Phase T's last `phase-approve.py --doc tasks` returns,
`currentPhase = "complete"` is already on disk (the atomic write
sealed `phaseGates.tasks` in the same finalize). On v2+ trackers
`advance-phase.py` is unnecessary; it stays available as the
v1.1.0 fallback.
