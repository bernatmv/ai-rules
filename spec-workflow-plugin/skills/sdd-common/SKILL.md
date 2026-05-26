---
name: sdd-common
description: Internal shared reference hub loaded as a dependency by other SDD skills.
  Not directly invoked by users. Contains review conventions, tool patterns, template
  compliance, approval handling, detection rules, telemetry, general principles,
  cross-validation, and size limit references.
allowed-tools: Read Write Edit Bash Agent
user-invocable: false
metadata:
  version: 3.3.1
  category: common
  dependencies: []
  author: membership-platforms-sdd-guild
---

# SDD: Common Reference

This skill is a reference hub. Consumer skills reference individual files directly
via their Dependencies tables — do not load this body unless debugging file locations.

## Contents

- [Path Convention](#path-convention)
- [Directory Index](#directory-index)

## Path Convention

All cross-skill file references use the `$SKILLS/` prefix, which resolves to
the IDE's skills directory relative to the workspace root (`.cursor/skills/`
in Cursor, `.claude/skills/` in Claude Code). This makes paths
depth-independent — the same path works from any file at any nesting level.

| Prefix | Resolves to | When to use |
|--------|-------------|-------------|
| `$SKILLS/` | IDE skills dir (`.cursor/skills/` or `.claude/skills/`) | Any cross-skill reference |
| `references/` | Same skill's `references/` dir | Within-skill references from SKILL.md |
| `@consumer/` | Consuming skill's root | Shared templates (review-workflow-base.md) |
| (none) | Same directory | Bare filename in same folder |

**Runtime resolution:**
- `$SKILLS/` → `.cursor/skills/` (Cursor) or `.claude/skills/` (Claude Code)
- `$SCRIPTS/` → `$SKILLS/sdd-common/scripts/`
- Scripts: always invoke via `.spec-workflow/sdd {group}/{script}.py [args...]`
- Prompt access: `.spec-workflow/sdd util/generate-prompt.py --type {type}` (do NOT read `prompt-registry.json` directly)

**TOC policy:** SKILL.md files list `##` headings only in Contents; `###` steps are navigable under their parent sections. Reference docs and steering docs include `###`-level TOC entries.

**Examples:**
- `$SKILLS/sdd-common/references/approval-flow.md` — from any file, any depth
- `$SKILLS/sdd-common/scripts/spec/check-status.py` — cross-skill script
- Within-skill: `references/approval-flow.md` from a SKILL.md
- Consumer-relative: `@consumer/references/cross-validation-criteria.md`

## Directory Index

### references/ — Shared protocol and convention documents

| File | Purpose |
|------|---------|
| `approval-flow.md` | Approval request/check/delete lifecycle (Pattern A & B) |
| `template-compliance.md` | Template resolution and variable substitution rules |
| `review-approval-pipeline.md` | Shared pipeline (validate → review gate → approve) with merged gate protocol, fix-loop state machine, and sub-agent guidelines |
| `safety-rules.md` | Hard constraints: sequential phases, one-at-a-time, no skipping |
| `update-mode-workflow.md` | Targeted-edit flow for existing docs |
| `prompt-conventions.md` | Prompt type keys and generation patterns |
| `detection-rules.md` | Bug-fix vs standard mode detection |
| `common-edge-cases.md` | Shared edge case handling (missing template, rejected approval, etc.) |
| `pre-approval-validation.md` | Size and structure checks run before each approval |
| `requirements-antipatterns.md` | Rule groups, severities, and suppression tags for `requirements.md` (source of truth: `scripts/sdd_core/data/requirements_antipatterns.yaml`) |
| `size-limits.md` | Effective-line limits per document type |
| `prompt-suffix-canonical.md` | Verbatim lifecycle suffix embedded in task `_Prompt` fields |
| `sub-agent-review-templates.md` | Human-readable reference for review sub-agent templates (agents use `review/prepare-pipeline.py` instead) |
| `snapshot-conventions.md` | Approval snapshot directory layout and metadata format |
| `cross-validation.md` | Cross-document consistency checks |
| `fix-loop-protocol.md` | Code-review-specific bindings for the fix-loop state machine (`review-approval-pipeline.md` § Fix-Loop) |
| `review-conventions.md` | Review output format and severity levels |
| `review-gate-pattern.md` | Shared review gate workflow used by creation skills (validate → review → approve) |
| `general-principles.md` | High-level SDD design principles |
| `tool-patterns.md` | Common script invocation patterns (`.spec-workflow/sdd` prefix, JSON output) |
| `path-conventions.md` | Cross-skill `$SKILLS/` prefix resolution, file reference syntax |
| `quality-artifact-base.md` | Shared JSON envelope and score conventions for quality artifacts |
| `review-workflow-base.md` | Shared review workflow skeleton (Base Steps A–I) used by all review skills |
| `refactoring-validation.md` | Objectives-based and function-parity refactoring checklists |
| `script-conventions.md` | Script output format, error handling, and shim usage conventions |
| `task-validation-rules.md` | Deterministic task structure checks (lifecycle suffix, prompts, traceability) |
| `telemetry.md` | Implementation logging workflow and artifact requirements |
| `troubleshooting.md` | Common error patterns and resolution steps |
| `workflow-handoffs.md` | Post-completion handoff suggestions between skills |
| `state-scope.md` | Scope + lifetime + owner table for every persisted artifact (harness.json, reference-acks, gate session, review quality, ledger) |
| `harness-detection.md` | Priority ladder, env-marker table, safe-default policy, contradictions vs warnings, two entry points |
| `harness-notes.md` | Adapter-rendered payload shapes (TODO variants, AskQuestion prompts, sub-agent dispatch) |
| `harness-task-binding.md` | Pipeline ↔ harness contract: symbolic id_hint reconciliation, adapter mapping, why numeric ids are agent-local |
| `human-approval-ceremony.md` | Pre-approve ceremony, H1 gate, retry shim. |
| `approval-subflow-diagram.md` | Mermaid diagram for approval subflows (supplementary) |
| `test-cases.md` | Internal test scenarios for SDD scripts |
| `default-templates/` | `*-template.md` — canonical default document templates mirrored into workspace |

### scripts/ — Python tooling

| Directory | Purpose | Key Files |
|-----------|---------|-----------|
| `approval/` | Approval CRUD operations | `request.py`, `check-status.py`, `update-status.py`, `delete.py`, `cleanup.py`, `list-pending.py` |
| `review/` | Review execution and quality measurement | `update-quality.py`, `check-template-compliance.py`, `count-effective-lines.py`, `validate-review-artifact.py`, `prepare-pipeline.py` |
| `review_quality/` | Review scoring engine (data + queries) | `registry.py` (data constants), `registry_helpers.py` (query functions), `builders.py`, `validation.py`, `scoring.py` (derivation + sub-agent score normalization), `tier1.py`, `io.py`, `paths.py`, `gate_session.py` (review gate session I/O), `staleness.py` (doc staleness checks), `todo_lifecycle.py` (fix-loop TODO payloads) |
| `spec/` | Spec lifecycle detection and validation | `check-status.py`, `detect-type.py`, `detect-context.py`, `archive.py`, `create-snapshot.py`, `lint-tasks.py`, `check-traceability.py` |
| `util/` | Prompt generation, template management, diagnostics | `generate-prompt.py`, `manage-template.py`, `resolve-template.py`, `log-implementation.py`, `parse-task-progress.py`, `check-pre-existing.py`, `detect-doc-state.py` |
| `discovery/` | Discovery project manifest operations | `init-project.py`, `update-manifest.py`, `validate-manifest.py` |
| `workspace/` | Multi-repo workspace orchestration | `init.py`, `check-status.py`, `batch-approve.py`, `advance-phase.py`, `phase-status.py`, `phase-approve.py`, `update-tracker.py`, `reconcile-tracker.py`, `extract-delegation.py`, `check-spec-shape.py`, `set-doc-approval.py`, `confirm-batch-approval.py` |
| `sdd_core/` | Shared Python library (approvals, specs, templates, paths) | `doc_config.py` (DOCUMENT_REGISTRY), `approvals.py`, `specs.py`, `templates.py`, `paths.py`, `tasks.py`, `output.py`, `cli/` (parser + run_main package), `text.py`, `time.py`, `snapshots.py`, `prompts.py`, `delegation.py`, `workspace.py`, `task_validation.py`, `testing.py` |
| (root) | Top-level helper | `skill_helpers.py` |
