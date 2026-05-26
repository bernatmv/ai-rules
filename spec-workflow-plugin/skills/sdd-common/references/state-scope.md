# State Scope

## Summary Table

The review pipeline persists several pieces of state. Each artifact
has a documented scope, lifetime, and owner so consumers never guess.

| Artifact | Scope | Lifetime | Owner |
|----------|-------|----------|-------|
| `.sdd-state/harness.json` | workspace | until `util/probe-harness.py --reset` | `util/probe-harness.py` |
| `.sdd-state/preflight.json` | workspace | persists across approvals; row resolution is session-scoped (see below) | `sdd_core/preflight_state.py` |
| `.sdd-state/session-{epoch_ms}.json` | process (one harness boot) | mint-once per harness; absent until first `get_or_create_session_id` call | `sdd_core/session.py` |
| `reference-acks.json` | workspace | Until `prepare-pipeline.py reset-reference-acks` runs (records persist across gates) | `sdd_core/reference_acks.py` |
| `gate-session.json` | per-gate | one workflow run | `review/pipeline_phases/complete.py` |
| `review-quality.json` | per-category (steering / spec) | one workflow run | `review_quality/update-quality.py` |
| `review-quality-{phase}.json` | per-doc target (per sub-spec × phase) | persists across gates; replaced atomically by the snapshot shim | `review/snapshot-and-mark-reviewed.py` |
| `.archive/ledger-*.jsonl` | per-gate (archived) | retention policy | `sdd_core/transient_state` |
| `__gate__/post_change_review.presented` | workspace | per-gate-cycle (gate_uuid mismatch invalidates) | `launch_preconditions/ledger.py` |

### Preflight + session invariant

`preflight.json` is workspace-scoped and survives approvals.
`approval/update-status.py approve` cleans per-doc-target review state
under `<doc_dir>/.sdd-state/` (gate-session, staging, ledger) and the
workspace `current-target.json`; it never touches `preflight.json` or
`session-*.json`. Approval is per-spec; preflight advisories are
workspace-scoped and cannot be wiped by a sibling spec's approval.

The `session_id` field on a preflight row pins the resolution to one
harness boot. Re-detection (`workspace/ensure-healthy.py`) keeps a
row resolved while its `session_id` matches the active session token
on disk; a fresh process minting a new session re-fires the advisory
because the row's stamped `session_id` no longer matches. This is the
invariant `resolve-advisory.py` writes via
`preflight_state.mark_resolved(name, session_id=...)`.

`review-quality-{phase}.json` lives at
`<repo>/.spec-workflow/specs/<sub-spec>/`, doc-target-scoped (not
state-dir-scoped). Persists across gates; the workspace gate uses its
presence to skip re-review.

The ack ledger records one (path, sha) pair per reference. Pairs persist across gates until `prepare-pipeline.py reset-reference-acks` runs, at which point every pair is cleared and the next launch re-requires ack of the reference bundle.

The post-change-review marker uses the workspace-scoped key
`__gate__/post_change_review.acked` (no `gate_id` suffix). Freshness
is asserted via the marker's `prompt_sha256` extra: a launch supplying
a different prompt-sha re-acks silently and overwrites the extra; an
unchanged sha reuses the prior ack across every subsequent gate.

The companion workspace-scoped marker `__gate__/post_change_review.presented` carries the `gate_uuid` of the cycle that surfaced the prompt. `launch_preconditions/payload.py` compares it to the active `gate_id`; mismatch == new cycle → re-prompt. The two markers are deliberately split so a single ack survives across cycles while presentation re-fires once per cycle.

## Read Semantics

- **Workspace-scoped** artifacts (harness, reference-acks) persist
  across gates. Acks recorded at gate A still satisfy the same
  reference reads at gate B; reset them with the documented command
  when the underlying reference changes.
- **Per-gate** artifacts (gate session) live only for one workflow
  run. The `complete` phase is idempotent — calling it after cleanup
  leaves no residue and emits `output.info` instead of re-creating a
  stub session file.
- **Per-category** artifacts (review quality) are shared across the
  documents of one category but never between spec and steering runs.

## Failure Modes

- Missing `harness.json` → loader auto-heals via the detector registry
  (env marker or safe default). A single warning fires per workspace.
- Missing `gate-session.json` during `complete` → emit an
  `output.info` banner and return without writing. No new session file
  is created.
- Corrupt `harness.json` → structured `output.error` envelope with a
  `next_action_command` that re-probes.
