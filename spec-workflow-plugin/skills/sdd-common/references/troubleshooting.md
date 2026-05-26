# Troubleshooting

Common error scenarios and resolutions for all SDD skills.

## Contents

- [Reading advisory action fields](#reading-advisory-action-fields)
- [`.spec-workflow/` Directory Missing](#spec-workflow-directory-missing)
- [Approval Files Corrupted or Empty](#approval-files-corrupted-or-empty)
- [Spec Folder Not Found](#spec-folder-not-found)
- [Permission Errors Writing Files](#permission-errors-writing-files)
- [Script Execution Errors](#script-execution-errors)
- [Script Output Parsing Errors](#script-output-parsing-errors)
- [Snapshot Creation Failures](#snapshot-creation-failures)
- [Shell Antipatterns](#shell-antipatterns)
- [Antipattern Lint Dispatch Warning](#antipattern-lint-dispatch-warning)
- [Template Render Fallbacks](#template-render-fallbacks)
- [Stray `.sdd-state` Outside `.spec-workflow/`](#stray-sdd-state-outside-spec-workflow)
- [Warn-First Launch Preconditions](#warn-first-launch-preconditions)
- [Common Error → Recovery](#common-error--recovery)

## Reading advisory action fields

When an advisory carries both `prerequisite_action_command` and
`next_action_command`:

1. Read `prerequisite_action_command` first. This is the root-cause
   action you must already have completed (for example, the
   `ToolSearch select:...` literal that loads deferred tool schemas).
2. Run `next_action_command` only after the prerequisite is satisfied.
   This is the canonical clear-action that resolves the advisory
   (typically `.spec-workflow/sdd workspace/resolve-advisory.py --name
   <advisory>`).

Advisories that omit `prerequisite_action_command` have no
prerequisite — run `next_action_command` directly.

## `.spec-workflow/` Directory Missing

**Symptom:** File operations fail because `.spec-workflow/` doesn't exist.

**Resolution:**
1. Run `.spec-workflow/sdd workspace/init.py` — creates the directory structure automatically
2. Or create manually:
   ```
   mkdir -p .spec-workflow/specs .spec-workflow/steering .spec-workflow/approvals .spec-workflow/templates
   ```

## Approval Files Corrupted or Empty

**Symptom:** Approval JSON files fail to parse or are 0 bytes.

**Resolution:**
1. Check the file contents manually
2. If 0 bytes, the write was interrupted — delete and re-request approval
3. If malformed JSON, check `.spec-workflow/approval-audit.log` for the `previousContent` field to reconstruct
4. Re-request the approval via `sdd-manage-status`

## Spec Folder Not Found

**Symptom:** `spec-status` returns `missing` for all phases, or spec folder doesn't exist.

**Resolution:**
1. Verify the spec name: `ls .spec-workflow/specs/`
2. Check for typos or naming mismatches (use kebab-case)
3. If the spec hasn't been created yet, use `sdd-create-spec` (supports both standard and bug-fix modes) or create it manually

## Permission Errors Writing Files

**Symptom:** File write operations fail with permission denied.

**Resolution:** Run `ls -la <path>`; if output shows non-writable mode,
re-run with corrected ownership before retrying.

## Script Execution Errors

**Symptom:** A Python script exits with a non-zero code or unexpected output.

**Cause:** Input validation failure (exit 1), system error (exit 2), or missing dependency.

**Resolution:**
1. Check stderr output — scripts follow the conventions in `script-conventions.md` with structured error messages and hints
2. Exit code 1: fix the input (bad arguments, missing argument, missing file, malformed input, validation failure)
3. Exit code 2: fix the system issue (permission denied, disk full, corrupt data, unreachable dependency)
4. If Python is missing: run `python3 --version` to confirm 3.9+ is available.
5. If `sdd_core` import fails, scripts must run from the correct directory (scripts expect `sdd_core/` as a sibling package).

## Script Output Parsing Errors

Re-read `$SKILLS/sdd-common/references/script-conventions.md` before retrying.

## Snapshot Creation Failures

**Symptom:** Snapshot not created after approval status change or manual trigger.

**Resolution:**
1. Verify the source file exists at the path specified in the approval JSON
2. Check that `.spec-workflow/` directory exists (run `.spec-workflow/sdd workspace/init.py` if needed)
3. Snapshot creation is best-effort — failures are silently skipped to avoid blocking approval workflows
4. For manual snapshots, use `.spec-workflow/sdd spec/create-snapshot.py` directly and check stderr for errors

## Shell Antipatterns

- Never pipe a bare directory path into `grep` without `-r` —
  `grep "pat" dir/` treats `dir/` as a single file, emits *"Is a
  directory"* to stderr, and exits 2, short-circuiting any `&&`
  chain. Use `grep -lr "pat" dir/`, `find dir/ -type f -exec grep`,
  or `ls dir/<specific-file>` when the path is known.
- Prefer `set -euo pipefail` in multi-step shell blocks so a
  mid-chain failure halts cleanly rather than silently producing
  partial output.

## Antipattern Lint Dispatch Warning

**Symptom:** Spec validation surfaces a single warning row with rule
`antipattern-dispatch-{doc}` (e.g. `antipattern-dispatch-requirements`)
and message `Could not run spec/lint-{doc}.py: …`.

**Cause:** A signature mismatch between
`sdd_core/workspace_validation.py :: run_antipattern_lint` and
`sdd_core.subprocess_dispatch.run_dispatched`.

**Resolution:**
1. The current canonical call is
   `run_dispatched(script, *args, capture_output=True)` — argv is
   unpacked, no `check` kwarg.
2. The `except` is narrow (`FileNotFoundError`,
   `subprocess.CalledProcessError`, `OSError`) so future signature
   drift surfaces as a test failure rather than a silent warning.
3. Antipattern lint locks the canonical signature: any future drift
   surfaces as a test failure (signature lock + findings-emission rules
   under `tests/test_sdd_core/test_workspace_validation.py`).

## Template Render Fallbacks

**Symptom:** A workflow step needs a rendered template but no
`pre-launch-check` envelope is available, so the canonical
`data.template_resolve_commands` map cannot be consulted.

**Resolution:** Run the cold-path resolver directly. The literal
mirrors the canonical envelope command for the same inputs:

```
.spec-workflow/sdd util/resolve-template.py \
  --type {requirements|design|tasks|workspace-requirements|...} \
  --spec-name {spec-name} \
  --content --workspace {project-path}
```

Coordinator repos in workspace flows pass
`--type workspace-requirements` so the rendered template carries the
`Cross-Repo Scope` section. Target repos use `--type requirements`.

## Stray `.sdd-state` Outside `.spec-workflow/`

**Symptom:** A `.sdd-state/` directory turns up in an unexpected
location (e.g. repo root, `$HOME`, an arbitrary cwd) and the agent
cannot account for the writer.

**Resolution:**
1. Ensure the workflow root exists — run
   `.spec-workflow/sdd workspace/init.py` if `.spec-workflow/` is
   missing under the project.
2. Re-run the workflow that produced the directory; every cross-cutting
   state writer routes through `sdd_core.paths.workflow_state_path` /
   `sdd_core.paths.state_dir`, which require a verified workflow root.
3. The `no-inline-state-dir-literal` lint forbids new literal usages
   in source — failing CI catches future regressions.

## Warn-First Launch Preconditions

First launch of a review gate with unread references emits
`severity: warn` plus a copy-paste Bash chain in
`next_action_command_sequence`. This is the expected UX — see
`pre-flight-protocol.md § Batched Reference-Read Ack`. The stderr
`WARNING:` prefix is informational; the envelope's `status: warn`
(not `error`) confirms the ladder rung.

Source of truth: `$SKILLS/sdd-common/scripts/review/pipeline_phases/launch_preconditions/policy.py::decide_read_severity`.

## Common Error → Recovery

| Symptom | Recovery |
|---------|----------|
| `Pre-approval blocked: 1 doc(s) need re-review` | Re-launch the gate via the emitter-produced `pipeline-tick --phase launch …` literal (canonical recovery for `fix_cycle == max_cycles` + fresh doc edit). The launch envelope's `reentry_cycle` / `reentry_instruction` anchor the second pass; the review-quality artifact stays authoritative for routing. Workspace mirror: `$SKILLS/sdd-workspace-create-spec/references/phase-loop.md § Approve Step` (Outcome → next action). |
| Task references an orphan id | The shape lives in `_ORPHAN_REF_MESSAGE_TEMPLATE` on `workspace/check-spec-shape.py`. Re-issue the task with a numeric requirement id matching `requirements.md`; non-numeric tokens are not accepted. |
