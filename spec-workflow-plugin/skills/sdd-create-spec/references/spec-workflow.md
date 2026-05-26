# Spec Development Workflow

## Contents
- [Overview](#overview)
- [Workflow Diagram](#workflow-diagram)
- [Update Mode (Targeted Edit)](#update-mode-targeted-edit)
- [Steps 3–4: Requirements](#steps-34-requirements)
- [Steps 5–6: UI Design (Optional)](#steps-56-ui-design-optional)
- [Steps 7–8: Design](#steps-78-design)
- [Steps 9–10: Tasks](#steps-910-tasks)
- [Creation Completion](#creation-completion)
- [Implementation Hand-off](#implementation-hand-off)
- [Workflow Rules](#workflow-rules)
- [File Structure](#file-structure)

## Overview

> **Scope:** This file covers the document creation pipeline (Steps 3–10) and implementation hand-off. Steps 0–2 (triage, pre-flight, steering docs) are defined in `SKILL.md`.
> Pre-flight follows `$SKILLS/sdd-common/references/pre-flight-protocol.md`.

You guide users through spec-driven development following this workflow. Transform rough ideas into detailed specifications through Requirements → UI Design (optional) → Design → Tasks → Implementation steps. Use web search when available for current best practices. Feature names use kebab-case (e.g., user-authentication). Create ONE spec at a time.

## Workflow Diagram

```mermaid
flowchart TD
    Start([Start: User requests feature]) --> CheckSteering{Steering docs exist?}
    CheckSteering -->|Yes| P1_Load[Read steering docs:<br/>.spec-workflow/steering/*.md]
    CheckSteering -->|No| P1_Template

    P1_Load --> P1_Template[Check user-templates first,<br/>then read template:<br/>requirements-template.md]
    P1_Template --> P1_Research[Web search if available]
    P1_Research --> P1_Create[Create file:<br/>.spec-workflow/specs/{name}/<br/>requirements.md]
    P1_Create --> P1_Pipeline[Review and Approval Pipeline<br/>per-document scope]

    P1_Pipeline -->|approved| P15_Ask{Spec includes<br/>UI changes?<br/>skip if designer handoff}
    P15_Ask -->|No| P2_Template
    P15_Ask -->|Yes| P15_PreWork[Pre-work checklist:<br/>Figma mocks ready?<br/>Design references?<br/>Pause if not ready]
    P15_PreWork -->|ready| P15_Template[Check user-templates first,<br/>then read template:<br/>ui-design-template.md]
    P15_PreWork -->|not ready| P15_Pause([Pause — resume later])
    P15_Template --> P15_Create[Create file:<br/>.spec-workflow/specs/{name}/<br/>ui-design.md]
    P15_Create --> P15_Pipeline[Review and Approval Pipeline<br/>per-document scope]
    P15_Pipeline -->|approved| P2_Template

    P2_Template[Check user-templates first,<br/>then read template:<br/>design-template.md]
    P2_Template --> P2_Analyze[Analyze codebase patterns]
    P2_Analyze --> P2_Create[Create file:<br/>.spec-workflow/specs/{name}/<br/>design.md]
    P2_Create --> P2_Pipeline[Review and Approval Pipeline<br/>per-document scope]

    P2_Pipeline -->|approved| P3_Template[Check user-templates first,<br/>then read template:<br/>tasks-template.md]
    P3_Template --> P3_Break[Convert design to tasks]
    P3_Break --> P3_Create[Create file:<br/>.spec-workflow/specs/{name}/<br/>tasks.md]
    P3_Create --> P3_Pipeline[Review and Approval Pipeline<br/>per-document scope]

    P3_Pipeline -->|approved| Final[Review and Approval Pipeline<br/>final scope]
    Final --> P4_Ready[Spec complete.<br/>Ready to implement?]
    P4_Ready -->|Yes| P4_Status[spec/check-status.py]
    P4_Status --> P4_Task[Edit tasks.md:<br/>Change [ ] to [-]<br/>for in_progress]
    P4_Task --> P4_Code[Implement code]
    P4_Code --> P4_Log[log-implementation.py<br/>Record implementation<br/>details]
    P4_Log --> P4_Complete[Edit tasks.md:<br/>Change [-] to [x]<br/>for completed]
    P4_Complete --> P4_More{More tasks?}
    P4_More -->|Yes| P4_Task
    P4_More -->|No| End([Implementation Complete])

    style Start fill:#e1f5e1
    style End fill:#e1f5e1
    style P1_Pipeline fill:#fff4e6
    style P15_Pipeline fill:#fff4e6
    style P2_Pipeline fill:#fff4e6
    style P3_Pipeline fill:#fff4e6
    style Final fill:#e3f2fd
    style CheckSteering fill:#fff4e6
    style P4_More fill:#fff4e6
    style P4_Log fill:#e3f2fd
```

## Resume

Run `check-status.py` and use `currentPhase` to determine the resume step. Derived from `specs.detect_spec_phase()`.

| `currentPhase` | Resume at |
|----------------|-----------|
| `requirements` | Step 3 (write) or Step 4 (approve, if `pending-approval`) |
| `ui-design` | Step 5 (write) or Step 6 (approve, if `pending-approval`) |
| `design` | Step 5 (UI gate) or Step 7 (write) or Step 8 (approve, if `pending-approval`) |
| `tasks` | Step 9 (write) or Step 10 (approve, if `pending-approval`) |
| `implementation` / `completed` | Step 11 |

## Update Mode (Targeted Edit)

When a spec exists and the user requests a specific change (not full regeneration), use this simplified flow instead of the full creation pipeline. Downstream impacts are checked for cross-document dependencies.

> See `$SKILLS/sdd-common/references/update-mode-workflow.md` for the shared update flow.

### Update Mode Exploration

Exploration depth depends on which document is being changed.

**Full exploration** — for requirements.md and ui-design.md (product decisions):

| Dimension | Questions to Ask |
|-----------|-----------------|
| **Clarify intent** | What specifically should change, and what triggered it? |
| **Challenge scope** | Does this change the contract with engineering? Does it ripple to design.md or tasks.md? |
| **Probe edge cases** | What about failure modes, concurrency, backward compatibility? Boundary conditions for WHEN/THEN changes? |
| **Check PRD alignment** | Does this still align with the approved PRD? Should the PRD be updated first? |

**Light exploration** — for design.md and tasks.md (engineering artifacts):

| Dimension | Questions to Ask |
|-----------|-----------------|
| **Clarify intent** | What specifically should change and why? |
| **Quick consistency check** | Does this still align with requirements.md? Any downstream impact? |

## Creation Completion

After all docs are individually approved, the Final Review and Approval
pipeline runs. See `$SKILLS/sdd-common/references/review-approval-pipeline.md` § Scope Parameter.

## Steps 3–4: Requirements

**Purpose**: Define what to build based on user needs.
See `$SKILLS/sdd-common/references/cross-validation.md § Authority Rules`
for the boundary between requirements (what/why) and design (how).
Machine-checkable subset is at
`$SKILLS/sdd-common/scripts/sdd_core/data/requirements_antipatterns.yaml`
(human doc: `$SKILLS/sdd-common/references/requirements-antipatterns.md`);
it runs automatically in the review-approval pipeline.

**File Operations**:
- Read steering docs: `.spec-workflow/steering/*.md` (if they exist)
- Read PRD: `.spec-workflow/specs/{spec-name}/prd.md` (if it exists — provides feature-specific problem, goals, scope, and requirements context)
- Check for custom template: `.spec-workflow/user-templates/requirements-template.md`
- Read template: `.spec-workflow/templates/requirements-template.md` (if no custom template)
- Create document: `.spec-workflow/specs/{spec-name}/requirements.md`

**Process**:
1. Check if `.spec-workflow/steering/` exists (if yes, read product.md, tech.md, structure.md). Also check if `.spec-workflow/specs/{spec-name}/prd.md` exists (if yes, read it for feature-specific context)
2. Resolve template per `$SKILLS/sdd-common/references/template-compliance.md` § Step 1: Load Canonical Template (type: `requirements`)
3. Research market/user expectations (if web search available)
4. Generate requirements as user stories with EARS criteria
5. Create `requirements.md` at `.spec-workflow/specs/{spec-name}/requirements.md`
   - Verify file exists and is non-empty
6. **Approval gate** — run Review and Approval Pipeline. See SKILL.md § Pipeline Parameters (Step 4 row).

## Steps 5–6: UI Design (Optional)

**Purpose**: Capture UI/UX design details for specs that include user-facing changes. Skipped for backend-only or non-visual specs.

> **IMPORTANT**: `ui-design.md` is a SEPARATE document from `design.md`.
> - `ui-design.md` = UI/UX (layout, components, interactions, accessibility) — Steps 5–6
> - `design.md` = Technical architecture (APIs, data model, testing) — Steps 7–8

**File Operations**:
- Create document: `.spec-workflow/specs/{spec-name}/ui-design.md`
- Template: `ui-design-template.md`

### Designer Handoff Model

This step supports a multi-role workflow where different people author different documents:

1. **PM creates requirements.md** → approves → merges PR to main
2. **Designer picks up the spec** via `sdd resume spec {name}`
3. Resume routing detects "requirements approved, no ui-design.md" → routes to this step
4. Designer completes pre-work and writes `ui-design.md`

When a designer resumes a spec with approved requirements, skip the "Does this spec include UI changes?" question — the designer is here specifically for UI design.

### Pre-Work Checklist

Designers typically prepare assets before writing the spec document. Before creating `ui-design.md`, gather:

1. **Figma mocks / wireframes**: Ask for Figma links to embed in the document. If Figma MCP is available, offer to import component specifications directly into the spec.
2. **Design references**: Design system, component library, style guide, or brand guidelines the design builds on.
3. **Pause option**: If pre-work isn't ready, the user can pause and resume later with `sdd resume spec {name}`. Do not force immediate authoring.

### Process

1. After requirements approval, **MUST ask** the user whether this spec includes UI/UX changes (skip if designer handoff detected — see above)
2. Run pre-work checklist — gather Figma links, design references, and readiness
3. If ready: resolve `ui-design` template, incorporate Figma links and imported component specs, write `ui-design.md`
4. If not ready: inform user they can resume later, exit gracefully
5. **Approval gate** — run Review and Approval Pipeline. See SKILL.md § Pipeline Parameters (Step 6 row).

**Inputs to Steps 7–8**: When ui-design.md exists, the Design step should reference it as an additional input alongside requirements.md.

## Steps 7–8: Design

**Purpose**: Create technical design addressing all requirements.

**File Operations**:
- Create document: `.spec-workflow/specs/{spec-name}/design.md`

**Process**:
1. Resolve template per `$SKILLS/sdd-common/references/template-compliance.md` § Step 1: Load Canonical Template (type: `design`)
2. Analyze codebase for patterns to reuse
3. Research technology choices (if web search available)
4. Generate design with all template sections
5. Create `design.md` at `.spec-workflow/specs/{spec-name}/design.md`
   - Verify file exists and is non-empty
6. **Approval gate** — run Review and Approval Pipeline. See SKILL.md § Pipeline Parameters (Step 8 row).

## Steps 9–10: Tasks

**Purpose**: Break design into atomic implementation tasks.

**File Operations**:
- Create document: `.spec-workflow/specs/{spec-name}/tasks.md`

**Process**:
1. Resolve template per `$SKILLS/sdd-common/references/template-compliance.md` § Step 1: Load Canonical Template (type: `tasks`)
2. Convert design into atomic tasks (1-3 files each)
3. Include file paths and requirement references
4. Add `_DependsOn: {task-ids}_` metadata for tasks with ordering requirements (e.g., service depends on data model, routes depend on service, tests depend on the code they test)
5. **IMPORTANT**: Generate a `_Prompt` field for each task with:
   - Role: specialized developer role for the task
   - Task: clear description with context references
   - Restrictions: what not to do, constraints to follow
   - _Leverage: files/utilities to use
   - _Requirements: requirements that the task implements
   - Success: specific completion criteria
   - **Lifecycle suffix**: Embed the exact text from `$SKILLS/sdd-common/references/prompt-suffix-canonical.md` § Suffix Text at the end of every `_Prompt`. Do NOT paraphrase — copy it verbatim.
   - Start the prompt with "Implement the task for spec {spec-name}:"
6. Create `tasks.md` at `.spec-workflow/specs/{spec-name}/tasks.md`
   - Verify file exists and is non-empty
7. **Approval gate** — run Review and Approval Pipeline. See SKILL.md § Pipeline Parameters (Step 10 row).

8. After successful approval: "Spec complete. Ready to implement?"

## Implementation Hand-off

**Purpose**: Execute tasks systematically.

Spec creation is complete after Steps 9–10 approval. Use `sdd-implement-spec` to begin implementation.

See `$SKILLS/sdd-implement-spec/SKILL.md` and `$SKILLS/sdd-implement-spec/references/task-execution-loop.md` for the full implementation procedure.

## Workflow Rules

- Create documents directly at specified file paths
- Resolve templates per `$SKILLS/sdd-common/references/template-compliance.md` § Step 1: Load Canonical Template
- Follow exact template structures
- Complete steps in sequence (no skipping)
- One spec at a time; use kebab-case for spec names
- All approval gates follow `$SKILLS/sdd-common/references/approval-flow.md`
- Safety rules: see `$SKILLS/sdd-common/references/safety-rules.md`
- Every task marked [x] MUST have a corresponding implementation log
- Steering docs are optional — only create when explicitly requested

## File Structure

```
.spec-workflow/
├── templates/
│   ├── requirements-template.md
│   ├── design-template.md
│   ├── tasks-template.md
│   ├── product-template.md
│   ├── tech-template.md
│   └── structure-template.md
├── user-templates/          # Optional user customizations
├── specs/
│   └── {spec-name}/
│       ├── requirements.md
│       ├── ui-design.md          # Optional — UI/UX design
│       ├── design.md
│       ├── tasks.md
│       └── Implementation Logs/
│           ├── task-1_timestamp_id.md
│           └── ...
├── steering/
│   ├── product.md
│   ├── tech.md
│   └── structure.md
└── approvals/
    └── {spec-name}/
        └── approval_*.json
```
