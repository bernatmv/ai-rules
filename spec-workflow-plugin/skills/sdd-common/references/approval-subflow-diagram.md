# Approval Sub-flow Diagram

Shared mermaid subgraph for the per-phase approval/revision loop used by both
spec and steering creation workflows. Each phase runs through the Review and
Approval Pipeline (`review-approval-pipeline.md`).


## Contents

- [Pipeline Wrapper](#pipeline-wrapper)
- [Approval Loop](#approval-loop)
- [Usage](#usage)

## Pipeline Wrapper

Each approval point in creation workflows runs the Review and Approval Pipeline:

```
Pipeline (per-document): Validate → [Optional Review] → approval-formal → scripts
Pipeline (final):        Validate → [Optional Review] → approval-formal → scripts
```

## Approval Loop

```mermaid
flowchart TD
    Create([Create {doc}]) --> Pipeline[Review and Approval Pipeline<br/>per-document scope]
    Pipeline --> Validate[Validate: size check]
    Validate --> ReviewOffer{Review gate?}
    ReviewOffer -->|Review| SubAgent[Sub-agent review<br/>single doc]
    SubAgent --> FixCheck{Issues?}
    FixCheck -->|Fix| Revise[Revise doc] --> Validate
    FixCheck -->|Proceed| Approve
    ReviewOffer -->|Skip| Approve[approval-formal prompt]
    Approve --> Scripts[approval/request.py →<br/>update-status.py →<br/>delete.py]
    Scripts --> Next([Proceed to next phase])

    style Create fill:#e6f3ff
    style Next fill:#e6f3ff
    style FixCheck fill:#ffe6e6
```

## Usage

Both `spec-workflow.md` and `steering-workflow.md` run the pipeline at each
phase. The loop is identical across all document types — only the Pipeline
Parameters row changes.

See `$SKILLS/sdd-common/references/review-approval-pipeline.md` for the
full pipeline reference and `$SKILLS/sdd-common/references/approval-flow.md`
for approval script details (Pattern A and Pattern B).
