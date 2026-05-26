# Dispatcher Passthrough — `pipeline-tick.py`

How `.spec-workflow/sdd review/pipeline-tick.py` forwards phase-specific
flags to the resolved phase.

This reference is the single source of truth for the passthrough
contract. Agent-typed phase flags (e.g. `--review-skill`, `--scope`,
`--doc-list`) are permitted **only** inside this file; every other
SKILL.md / reference must link here rather than re-documenting the
surface.

## Contents

- [Dispatcher shape](#dispatcher-shape)
- [Two supported forms](#two-supported-forms)
  - [Form 1 — inline auto-promote](#form-1--inline-auto-promote)
  - [Form 2 — explicit `--` separator](#form-2--explicit---separator)
- [Lifecycle flags](#lifecycle-flags)
- [Post-approval state cleanup](#post-approval-state-cleanup)
- [`did_you_mean` recovery contract](#did_you_mean-recovery-contract)
- [Common phase flags, by phase](#common-phase-flags-by-phase)

## Dispatcher shape

The agent-facing entry point is `review/pipeline-tick.py`. Locator flags accepted by review/pipeline-tick: `--category`, `--target-name` / `--spec-name`, `--workspace`, `--phase`, `--gate-uuid`, `--dry-run`. Every other flag is forwarded to the resolved phase subprocess (`prepare-pipeline.py <phase>`).

```
.spec-workflow/sdd review/pipeline-tick.py --category {category} --target-name "{target-name}" \
  --workspace . \
  [--phase {override}]   # optional; gate session resolves otherwise
  <phase flags ...>      # see § Two supported forms
```

The phase is resolved in this order:

1. explicit `--phase {override}` flag
2. `review_gate.required_next_phase` from the gate session
3. `launch` (default for a fresh session)

## Two supported forms

### Form 1 — inline auto-promote

Any unknown flag that the resolved phase's `Input` dataclass accepts is
auto-promoted into the passthrough tail. Use this when the flag names
are unambiguous:

```
.spec-workflow/sdd review/pipeline-tick.py --category steering --target-name steering \
  --phase launch \
  --review-skill sdd-review-steering-docs \
  --doc-list "product.md,tech.md,structure.md" \
  --scope per-document \
  --parent-todo step5 --gate-id step5
```

`--review-skill`, `--doc-list`, `--scope`, `--parent-todo`, and
`--gate-id` all live on the phase (not the dispatcher) and are promoted
automatically because `launch` declares them on its `Input` dataclass.

### Form 2 — explicit `--` separator

Anything after a bare `--` is forwarded verbatim. Use this form when:

- the flag name collides with a dispatcher locator (e.g. a hypothetical
  phase flag also named `--category`);
- the caller wants to be explicit about which flags belong to which
  layer (more auditable in logs);
- the flag does not appear on the phase's `Input` dataclass yet but
  `prepare-pipeline.py` accepts it on the shared parent parser.

```
.spec-workflow/sdd review/pipeline-tick.py --category spec --target-name my-feature \
  -- \
  --doc requirements.md \
  --fix-cycle 1 --max-cycles 2
```

Both forms produce byte-identical subprocess argv; the dispatcher does
not transform phase flags, it only routes them.

### Auto-promotion reflection

Form 1's auto-promotion is driven by reflection over the resolved
phase's `Input` dataclass — specifically `_accepted_flags()` unions the
phase's kebab-cased field names with
`sdd_core.dispatcher_help.lifecycle_passthrough_flags()`. Any flag in
that union is silently promoted into the passthrough tail, even if the
caller intended it as a dispatcher-level flag.

Implications worth knowing:

- Adding a new `Input` field on a phase widens the auto-promotion set
  for every caller the very next commit.
- Unrecognized flags that don't appear on any phase are rejected with
  the `did_you_mean` recovery contract below (they don't silently drop).
- To see exactly which flags the dispatcher decided to promote on any
  run, pass `--dry-run`: the emitted envelope is byte-identical to a
  live tick except no state is mutated, so the resolved subprocess
  argv is observable.

## Lifecycle flags

Three flags are always promote-able because every phase accepts them on
the shared parent parser of `prepare-pipeline.py`:

| Flag | Purpose |
|------|---------|
| `--parent-todo` | TODO lifecycle tracking (see `review-approval-pipeline.md` § Pending Tool Calls) |
| `--parent-todo-content` | Parent TODO display text (preserved across fix cycles) |
| `--gate-id` | Review-gate identifier used by the session |

These are declared in `sdd_core.dispatcher_help.lifecycle_passthrough_flags()`;
`pipeline-tick.py::_passthrough_accepted` unions that set with the
phase's `_accepted_flags` before routing.

## Post-approval state cleanup

When a gate completes via `approval/update-status.py`, the approval
script invokes `sdd_core.transient_state.cleanup_on_approval` to
delete / archive the three transient files under
`<doc_dir>/.sdd-state/`. The dispatcher is not involved in this hook,
but pipeline authors who write new phases should be aware that
`gate-session.json` and the staging file may disappear between
`approve` and the next `pipeline-tick`. See
[`review-approval-pipeline.md`](review-approval-pipeline.md#approval-finalization--transient-state-cleanup)
§ Approval Finalization — Transient State Cleanup for the outcome
matrix and the `cleanup` envelope contract.

## `did_you_mean` recovery contract

When an agent types a flag the dispatcher cannot route, the error
payload is structured for single-round-trip recovery:

```json
{
  "status": "error",
  "error": "Unrecognized top-level flag(s) for pipeline-tick: --reveiw-skill",
  "hint": "Phase 'launch' does not accept: --reveiw-skill.
  Closest accepted phase flags:
    --reveiw-skill -> --review-skill
  Phase flags accepted by 'launch': --doc-list, --review-skill, --scope, ...
  Either rerun with the correct flag, or place phase flags after a bare `--` separator ..."
}
```

The agent reads `hint`, rewrites the flag, and retries — no
reference-doc lookup required. Implementation lives in
`pipeline-tick.py::_report_unknown_flags`.

## Common phase flags, by phase

The phase registry is the authority for every accepted flag (see
`review/phase_kit.py::Phase.Input` dataclasses). The table below is
informational — CI regenerates the accepted flag sets via
`_accepted_flags()`.

| Phase | Common flags (non-exhaustive) |
|-------|-------------------------------|
| `launch` | `--review-skill`, `--doc-list`, `--scope`, `--parent-todo`, `--gate-id` |
| `post-fix` | `--doc-list`, `--fix-cycle`, `--max-cycles`, `--parent-todo`, `--gate-id` |
| `check-revalidation` | `--doc-list`, `--fix-cycle`, `--max-cycles` |
| `pre-approval` | `--doc-list`, `--parent-todo`, `--gate-id` |
| `ack-calls` | (no phase-specific flags beyond the locator set) |
| `ack-reference-reads` | (no phase-specific flags beyond the locator set) |

Run `.spec-workflow/sdd review/prepare-pipeline.py <phase> --help` for
the authoritative, up-to-date surface per phase.
