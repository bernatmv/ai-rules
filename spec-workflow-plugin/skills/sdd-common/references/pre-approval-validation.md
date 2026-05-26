# Pre-Approval Validation

Shared validation checks run by the Review and Approval Pipeline (Step 1)
before presenting the review gate and approval prompts.

## Contents

- [Scope-Aware Behavior](#scope-aware-behavior)
- [Checks](#checks)
  - [1. Size Limit Check](#1-size-limit-check)
  - [1b. Template Compliance Check](#1b-template-compliance-check)
  - [1c. Requirements Antipattern Check](#1c-requirements-antipattern-check-requirementsmd-only)
  - [2. Cross-Document Consistency Note](#2-cross-document-consistency-note-final-scope-only)
- [Usage](#usage)

## Scope-Aware Behavior

| Scope | Validation |
|-------|------------|
| `per-document` | Size check on the single target doc only |
| `final` | Size checks on all docs in `doc_list` + cross-document consistency note |

## Checks

### 1. Size Limit Check
Run `.spec-workflow/sdd review/count-effective-lines.py --file {doc}` on each target document.
If over limit, include a warning in the prompt context.

### 1b. Template Compliance Check
Run template compliance per document:
```
.spec-workflow/sdd review/check-template-compliance.py {template-file} {document-file}
```
Both arguments are required. Resolve the template first via:
```
.spec-workflow/sdd util/resolve-template.py --type {doc-type} --content
```
Then pass the template path as the first argument and the document path as the second.

### 1c. Requirements Antipattern Check (`requirements.md` only)

When the target `doc` is `requirements.md`, run:

```
.spec-workflow/sdd spec/lint-requirements.py --target {spec-name}
```

Behavior:

| Script exit | Pipeline effect |
|-------------|-----------------|
| 0 with `data.result: "pass"` | Proceed to Step 2 (review gate) |
| 0 with `data.result: "warn"` or `data.result: "info"` | Proceed to Step 2; include issues summary as `pre_check_notes` in the launch payload so the sub-agent and the agent can see them |
| 1 (errors) | **Block the review gate.** Emit `output.error` with the issue list; the agent must fix structural / `path` errors and re-run launch. |
| 2 (system fault) | Block; surface the error via the pipeline's existing unexpected-exit handler. |

Mode detection: The pipeline passes `--mode bug-fix` when the spec name
matches the canonical bug-fix word list (see
`sdd_core.specs.BUG_FIX_WORDS` / `sdd_core.specs.is_bug_fix_spec`).
Otherwise the script auto-detects; explicit flag wins.

Rules and severities are defined in
`$SKILLS/sdd-common/scripts/sdd_core/data/requirements_antipatterns.yaml`
(human-readable mirror at
`$SKILLS/sdd-common/references/requirements-antipatterns.md`).

**Feedback-loop iteration cap.** `--phase pre-launch-check` tracks the
hash of the structured findings list across consecutive runs in a
side-car file (`.pre-launch-repeat.json`). Three identical signatures
in a row trigger a `repeat_detected: true` flag plus an
`ask_question_payload` in the success envelope. The agent must
escalate via `AskQuestion` (options: pause and review, or
acknowledge and continue) instead of looping further. Successful
runs (`ok: true`) clear the counter on the next non-pass result.

### 2. Cross-Document Consistency Note (`final` scope only)
When multiple related documents are validated together (e.g., all three
steering docs, or requirements + design + tasks), note that cross-document
consistency may be affected and recommend running the full review.

## Usage

The pipeline invokes this file automatically — skills do not call it directly.
Contexts where the pipeline runs validation:

- **Per-document creation** (`per-document` scope): after each doc is written, before approval
- **Final creation** (`final` scope): after all docs individually approved, before final approval
- **Update mode**: after changes accepted, before `approval-formal` / `approval-formal-required` (via `final` scope)
- **Workspace mode**: coordination and sub-spec pipelines (via `sdd-create-spec` batch mode)
