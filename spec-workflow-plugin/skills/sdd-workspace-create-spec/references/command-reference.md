# Workspace Command Reference

Hand-maintained reference table for workspace-scope shim commands.

## Contents

- [Workspace shim commands](#workspace-shim-commands)
- [Per-script flag notes](#per-script-flag-notes)

## Workspace shim commands

| Operation | Command |
|-----------|---------|
| Initialize workspace | `.spec-workflow/sdd workspace/init.py [--workspace PATH]` |
| Pre-flight all repos in workspace | `.spec-workflow/sdd workspace/preflight-all.py [--target NAME] [--auto-fix]`[^autofix] |
| Check workspace spec shape | `.spec-workflow/sdd workspace/check-spec-shape.py --workspace <repo-path> --target <sub-spec> [--doc requirements\|design\|tasks]` |
| Bootstrap workspace feature (manifest + tracker) | `.spec-workflow/sdd workspace/init-feature.py --workspace PATH --target <feature> --repo coordinator:<path>(absolute):<feature> --repo target:<path>(absolute):<sub-spec> [--idempotent \| --force]` |
| Retroactive review for missing artifacts | `.spec-workflow/sdd workspace/retroactive-review.py --workspace PATH --target <feature> [--phase requirements\|design\|tasks] [--phase-repo-id ID] [--dry-run]` |
| Approve workspace phase | `.spec-workflow/sdd workspace/phase-approve.py --target <feature> --doc requirements\|design\|tasks [--dry-run]` |

## Per-script flag notes

All workspace-family scripts accept their target via
`--target {feature}[/{repo-id}]`. The notes below document optional
flags and per-script semantics that the manifest table cannot convey
in one line.

| Script | Optional Args | Notes |
|--------|---------------|-------|
| `workspace/init.py` | | Idempotent; safe to re-run |
| `workspace/check-status.py` | `--workspace PATH`, `--poll`, `--phase PHASE` | `--phase` for phase-specific output |
| `workspace/update-tracker.py` | `--workspace PATH`, `--status STATUS`, `--phase`, `--doc-status STATUS`, `--review-skipped`, `--auto-generated`, `--dry-run` | At least one of `--status` or `--doc-status` required. `--doc-status` requires `--phase`. `--review-skipped` records audit trail when user skips review. |
| `workspace/set-doc-approval.py` | `--workspace PATH`, `--approval-id ID`, `--dry-run` | Also updates `docStatus` when target is a repo and status is `approved` |
| `workspace/extract-delegation.py` | `--workspace PATH`, `--doc-scope DOC` | `--doc-scope` reduces file I/O. Target repos only — coordinator skips delegation. |
| `workspace/check-spec-shape.py` | `--workspace PATH`, `--doc DOC` | `--doc` validates one document only |
| `workspace/phase-approve.py` | `--workspace PATH`, `--dry-run` | Atomic batch-approve one doc type across repos. Refuses to advance when any repo is missing `review-quality-{doc}.json`. |
| `workspace/advance-phase.py` | `--workspace PATH`, `--dry-run` | Advances `currentPhase` to next phase |
| `workspace/phase-status.py` | `--workspace PATH`, `--phase PHASE` | Shows per-repo `docStatus` for a phase |
| `workspace/init-feature.py` | `--target FEATURE`, `--repo TYPE:PATH:SUB-SPEC` (repeatable, required; `TYPE` ∈ `coordinator`/`target`), `--workspace PATH`, `--idempotent`, `--force` | First-run create, no-op on identical match, H1-gated replace under `--force`. Bootstrap leaves `role` empty; populate via `workspace/update-manifest.py set-repo-role`. |
| `workspace/update-manifest.py` | `--target FEATURE`, subcommand `set-repo-role --repo-id ID --role "..."` | Read-modify-write the workspace coordination manifest. Manifest validation runs **before** the write — invalid mutations refuse to land. Subcommand surface mirrors `discovery/update-manifest.py`. |
| `workspace/retroactive-review.py` | `--phase`, `--phase-repo-id`, `--dry-run` | Stamps `reviewMeta.{phase}.retroactive=true` once the artifact lands. |

[^autofix]: `--auto-fix` repairs the checks listed in
`sdd_core.advisories._FIXABLE_CHECK_NAMES` (shim/template surface). It
does **not** address `skills_registry_hash_drift`, which surfaces as a
warn-only advisory and is regenerated out-of-band via
`npm run generate-registry`.
