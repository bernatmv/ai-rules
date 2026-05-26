# Workflow Hand-offs

Canonical skill chains for common SDD workflows.

## Contents
- [New Feature Workflow](#new-feature-workflow)
- [Bug Fix Workflow](#bug-fix-workflow)
- [Steering Document Workflow](#steering-document-workflow)
- [Document Update Workflow](#document-update-workflow)
- [Spec Evolution Workflow](#spec-evolution-workflow)
- [Full Lifecycle Workflow](#full-lifecycle-workflow)
- [Maintenance / Drift Detection](#maintenance--drift-detection)
- [Workspace (Multi-Repo) Spec Creation](#workspace-multi-repo-spec-creation)
- [PRD Workflow](#prd-workflow)
- [Template Management Workflow](#template-management-workflow)
- [Hand-off Protocol](#hand-off-protocol)
  - [Review Handoff Protocol](#review-handoff-protocol)

## New Feature Workflow

> **Note:** `sdd-create-spec` auto-detects workspace context via `detect-context.py` and uses **batch** approval mode when the spec belongs to a workspace. In batch mode, per-document approvals (Steps 4/6/8) are replaced by a single batch approval (Step 10.1).

```
sdd-create-spec → [validate] → [optional: sdd-review-spec-docs via sub-agent] → [optional: fix loop] → approval-formal → sdd-implement-spec → sdd-review-code
```

| From | To | Hand-off |
|------|-----|---------|
| `sdd-create-spec` | Review Gate (sub-agent) | Spec folder with requirements.md, design.md, tasks.md created; Review and Approval Pipeline (final) runs validation then offers opt-in review |
| Review Gate | `approval-formal` | Review complete (or skipped); user approves package via `approval-formal` |
| `sdd-create-spec` (approved) | `sdd-implement-spec` | All spec phases approved; implementation can begin |
| `sdd-implement-spec` | `sdd-review-code` | Tasks implemented with telemetry logs; ready for implementation review |

## Bug Fix Workflow

```
sdd-create-spec (bug-fix mode) → [validate] → [optional: sdd-review-spec-docs via sub-agent] → [optional: fix loop] → approval-formal → sdd-implement-spec → sdd-review-code
```

| From | To | Hand-off |
|------|-----|---------|
| `sdd-create-spec` (bug-fix mode) | Review Gate (sub-agent) | Bug fix spec folder (`fix-{slug}`) with requirements.md, design.md, tasks.md created; Review and Approval Pipeline (final) runs validation then offers opt-in review |
| Review Gate | `approval-formal` | Review complete (or skipped); user approves package via `approval-formal` |
| `sdd-create-spec` (approved) | `sdd-implement-spec` | All spec phases approved; implementation can begin |
| `sdd-implement-spec` | `sdd-review-code` | Tasks implemented with telemetry logs; ready for implementation review |

## Steering Document Workflow

```
sdd-create-steering (per-doc pipeline) → ... → Review and Approval Pipeline (final) → complete
```

| From | To | Hand-off |
|------|-----|---------|
| `sdd-create-steering` (per-doc pipelines) | Review and Approval Pipeline (final) | All three steering docs individually approved via per-document pipeline |
| Pipeline: validate | Review Gate (sub-agent) | Size checks pass; opt-in review offered via `post-change-review` prompt |
| Review Gate | Pipeline: `approval-formal` | Review complete (or skipped); user approves package |

## Document Update Workflow

```
sdd-create-steering/sdd-create-spec (update mode) → [validate] → [optional: sdd-review-*] → approval-formal → complete
```

| From | To | Hand-off |
|------|-----|---------|
| `sdd-create-steering` (update mode) | Review and Approval Pipeline (final) | Changes accepted via `review-action`; validation + formal approval before completion |
| `sdd-create-spec` (update mode) | Review and Approval Pipeline (final) | Changes accepted via `review-action`; validation + formal approval before completion |

## Spec Evolution Workflow

```
sdd-manage-status (refresh tasks) → sdd-review-spec-docs → sdd-manage-status (approve) → sdd-implement-spec (resume)
```

| From | To | Hand-off |
|------|-----|---------|
| `sdd-manage-status` (refresh tasks) | `sdd-review-spec-docs` | Tasks regenerated from updated design; pending re-review |
| `sdd-review-spec-docs` | `sdd-manage-status` | Review report for refreshed tasks; user approves |
| `sdd-manage-status` (approve) | `sdd-implement-spec` | Refreshed tasks approved; implementation resumes from next incomplete task |

## Full Lifecycle Workflow

```
sdd-create-steering → [validate] → [optional: sdd-review-steering-docs via sub-agent] → approval-formal → sdd-create-spec → [validate] → [optional: sdd-review-spec-docs via sub-agent] → approval-formal → sdd-implement-spec → sdd-review-code → sdd-archive-spec
```

| From | To | Hand-off |
|------|-----|---------|
| `sdd-create-steering` | Review Gate (sub-agent) | Steering docs created; Review and Approval Pipeline (final) runs validation then offers opt-in review |
| Review Gate (steering) | `approval-formal` | Steering review complete (or skipped); user approves |
| `sdd-create-steering` (approved) | `sdd-create-spec` | Steering approved; ready to create feature specs |
| `sdd-create-spec` | Review Gate (sub-agent) | Spec docs created; Review and Approval Pipeline (final) runs validation then offers opt-in review |
| Review Gate (spec) | `approval-formal` | Spec review complete (or skipped); user approves |
| `sdd-create-spec` (approved) | `sdd-implement-spec` | Spec approved; implementation begins |
| `sdd-implement-spec` | `sdd-review-code` | Implementation complete; ready for review |
| `sdd-review-code` | `sdd-archive-spec` | Implementation reviewed; archival is optional once the user confirms the spec is fully complete |

## Maintenance / Drift Detection

```
sdd-review-steering-docs (drift detection) → [manual update] → sdd-review-steering-docs
```

Drift detection identifies where steering docs have fallen behind the codebase.
After manual updates, re-run the review to validate corrections.

| Maintenance shim | Inputs | When to invoke |
|------|--------|----------------|
| `workspace/sync-skills-pack.py` | `--workspace PATH --target FEATURE [--dry-run]` | When pre-flight emits a `skills-pack-drift` advisory: run to copy the coordinator's shared references into each target repo. Voluntary; the workflow does not block on drift. |

## Workspace (Multi-Repo) Spec Creation

```
sdd-workspace-create-spec (initialize) → sdd-workspace-create-spec (coordination spec) →
  sdd-workspace-create-spec (review + approve coordination) →
  Phase R: all repos requirements → review → approve →
  Phase D: all repos designs → review → approve →
  Phase T: all repos tasks → review → approve →
  sdd-workspace-create-spec (complete)
    → [per-repo: sdd-implement-spec] (user-initiated, separate sessions)
```

| From | To | Hand-off |
|------|-----|---------|
| `sdd-workspace-create-spec` (initialize) | `sdd-workspace-create-spec` (coordination spec) | Manifest created, target repos initialized |
| `sdd-workspace-create-spec` (coordination spec) | `sdd-workspace-create-spec` (review + approve) | Coordination spec (R/D/T) created via `sdd-create-spec` in batch mode |
| `sdd-workspace-create-spec` (approve coordination) | Phase R: Requirements | Coordination spec approved; `currentPhase` set to `"requirements"` |
| Phase R: Requirements | Phase D: Designs | All repos' requirements approved; `currentPhase` advanced to `"design"` |
| Phase D: Designs | Phase T: Tasks | All repos' designs approved; `currentPhase` advanced to `"tasks"` |
| Phase T: Tasks | `sdd-workspace-create-spec` (complete) | All repos' tasks approved; `currentPhase` set to `"complete"` |
| `sdd-workspace-create-spec` (complete) | `sdd-implement-spec` (per repo) | All sub-specs approved; user runs implementation in each target repo |

## PRD Workflow

```
[optional: sdd-create-discovery] → sdd-create-prd → [validate-prd.py] → [optional: sdd-review-prd via sub-agent] → approval → sdd-create-spec
```

| From | To | Hand-off |
|------|-----|---------|
| `sdd-create-discovery` (approved) | `sdd-create-prd` | Discovery project provides context; PRD auto-registered as artifact in manifest |
| `sdd-create-prd` (generated) | `validate-prd.py` | Structural validation with fix-loop before review gate |
| `sdd-create-prd` | Review Gate (sub-agent) | PRD created; Review and Approval Pipeline (per-document) runs validation then offers opt-in review |
| Review Gate | `approval-formal` | Review complete (or skipped); user approves PRD via Pattern B |
| `sdd-create-prd` (approved) | `sdd-create-spec` | PRD approved; spec creation loads prd.md as feature-specific context alongside steering docs |

### Discovery → PRD Integration

When a discovery project exists at `.spec-workflow/discovery/{feature-name}/`:
- `sdd-create-prd` reads the manifest for context in Step 0
- After PRD generation, `sdd-create-prd` auto-registers prd.md via `.spec-workflow/sdd discovery/update-manifest.py add-artifact`
- The discovery manifest's artifact type detection recognizes `prd.md` as type `prd`

### PRD → Spec Context Loading

The spec creation skill (sdd-create-spec) should detect and load
`prd.md` when present in the spec directory during Step 2 (Read
Steering Docs) as additional feature-specific context. The PRD provides:
- Problem statement → anchors requirements
- Goals → bounds scope
- WHEN/THEN requirements → seed for requirements.md
- NFRs → carry forward to design constraints
- Non-goals → scope boundaries for design and tasks

## Template Management Workflow

```
sdd-manage-template (customize) → edit → sdd-manage-template (validate) → [fix?] → sdd-create-spec/sdd-create-steering
sdd-manage-template (sync) → verify templates in .spec-workflow/templates/
```

| From | To | Hand-off |
|------|-----|---------|
| `sdd-manage-template` (customize) | User edit + validate | Template copied to user-templates/; validate-fix loop |
| `sdd-manage-template` (validate) | `sdd-create-spec` or `sdd-create-steering` | Template validated; ready for document authoring |
| `sdd-manage-template` (sync) | `sdd-create-spec` or `sdd-create-steering` | Default templates refreshed in workspace |

## Hand-off Protocol

When one skill completes, it presents an inline text suggestion for the natural next step. The user can follow the suggestion, ignore it, or do something else.

### Canonical Hand-off Messages

See `prompt-conventions.md` § Canonical Hand-off Messages for the complete table.

### Review Handoff Protocol

When a workflow step offers an optional quality review:

1. Read `$SKILLS/{review-skill}/SKILL.md`
2. Follow its workflow for the target spec, passing `--workspace {path}` if
   the spec lives in a different repo than the current working directory
3. After the review completes, return to the calling workflow's next step

The review skill is read-only — it reports findings but does not modify documents.

> **Note:** Standalone creation skills (`sdd-create-spec`, `sdd-create-steering`) now
> use the Review and Approval Pipeline (`$SKILLS/sdd-common/references/review-approval-pipeline.md` § Review Gate)
> which wraps this handoff in a Task sub-agent with fix-loop capability. The workspace
> skill (`sdd-workspace-create-spec`) delegates to the shared pipeline via its own
> workspace-specific wrapper at `$SKILLS/sdd-workspace-create-spec/references/review-gate-protocol.md`.
