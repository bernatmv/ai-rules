# Review Workflow Base

Shared workflow skeleton for SDD document-review skills. Each consuming skill
provides its own parameters and references individual steps from this file.

**Consumers:** `sdd-review-spec-docs`, `sdd-review-steering-docs`
**Partial consumer:** `sdd-review-code` (steps H, I only)

## Contents
- [How to Use This File](#how-to-use-this-file)
- [Base Step A: Discover Expected Documents](#base-step-a-discover-expected-documents)
- [Base Step B: Locate Documents](#base-step-b-locate-documents)
- [Base Step C: Check Status](#base-step-c-check-status)
- [Base Step D: Determine Review Scope](#base-step-d-determine-review-scope)
- [Base Step E: Apply Per-Document Checklists](#base-step-e-apply-per-document-checklists)
- [Base Step F: Template Compliance Check](#base-step-f-template-compliance-check)
- [Base Step G: Cross-Document Validation](#base-step-g-cross-document-validation)
- [Base Step H: Generate Report](#base-step-h-generate-report)
- [Base Step I: After Review](#base-step-i-after-review)
- [After Report Generation](#after-report-generation)

## How to Use This File

Consuming skills define a **Parameters** table at the start of their Workflow
section, then reference shared steps as:

> Follow **Base Step X** from `$SKILLS/sdd-common/references/review-workflow-base.md`
> with the parameters above.

Domain-specific steps remain inline in each skill's SKILL.md.

---

## Base Step A: Discover Expected Documents

Before composing any parallel batch for the discovery call, observe
the four rules in
`$SKILLS/sdd-common/references/parallel-batch-hygiene.md` — reads
precede runs, Bash probes are defensively suffixed, risky and safe
calls never share a batch, and known file paths use the ``Read`` tool
instead of ``cat``.

Call `{DISCOVERY_TOOL}` (see
`$SKILLS/sdd-common/references/tool-patterns.md`).

Standard documents for this review category:
- {DOCUMENT_LIST — one bullet per document with brief description}

---

## Base Step B: Locate Documents

{LOCATE_STRATEGY — skill provides the specific search logic}

**Matching rules** (when locating by name):
- Exact: user-provided name matches directory/file name exactly
- Partial: name is a substring of directory/file name
- Fuzzy: suggest closest matches if no exact or partial match

---

## Base Step C: Check Status

Use the spec-status check pattern from
`$SKILLS/sdd-common/references/tool-patterns.md` with
`specName: {STATUS_SPEC_NAME}`.

Returns per-phase status. Values: `created` (pending) | `approved` | `missing`

{STATUS_EXTRAS — additional discovery steps if defined by the consuming skill}

---

## Base Step D: Determine Review Scope

| Request | Action |
|---------|--------|
| "Review [all-keyword]" | All available documents |
| "Review [specific-doc]" | Specific document only |
| "Review pending" | Documents with `created` status |
| No docs exist | Report missing with creation guidance |
| Some docs missing | Review available, note gaps |

Skills may append additional scope rows for domain-specific invocations.

---

## Base Step E: Apply Per-Document Checklists

For each document being reviewed, read the corresponding validation criteria file:
- {CRITERIA_MAPPING — one bullet per doc→criteria-file pair}

Evaluate each document against its criteria. Fill in pass/fail for every criterion.

---

## Base Step F: Template Compliance Check

For each document being reviewed, apply the **Template Compliance Validation**
from `$SKILLS/sdd-common/references/template-compliance.md` using the document
mappings listed there. Include the compliance rating in the per-document section
of the report.

**Review-only constraint:** If compliance fails, note the missing headings in the
report. Do NOT modify the reviewed document — the review skill is read-only.
Direct the user to `sdd-create-spec` or `sdd-create-steering` to fix document gaps.

---

## Base Step G: Cross-Document Validation

For each document pair ({CROSS_VALIDATION_PAIRS}):

1. **Identify shared topics**: Extract key concepts, technology names, feature
   names, architectural patterns, and component names from both documents.
2. **Compare coverage**: For each shared topic, compare how each document
   describes it.
3. **Classify issues** using these categories:
   | Category | Definition | Severity |
   |----------|-----------|----------|
   | **Duplication** | Same concept in multiple documents with different wording | Warning |
   | **Conflict** | Two documents make contradictory claims | Critical |
   | **Gap** | A concept referenced in one document has no coverage in the related document | Warning |
   | **Drift** | Documents were once consistent but one has been updated while the other has not | Warning |
4. **Apply authority rules** from the cross-validation criteria file listed in
   your SKILL.md Dependencies table to recommend which document should be the
   single source of truth.
5. Include findings in the report.

---

## Base Step H: Generate Report

Follow the standard report skeleton from
`$SKILLS/sdd-common/references/review-conventions.md`, adding the skill-specific
sections defined in the consuming skill's SKILL.md.

---

## Base Step I: After Review

After review: see `$SKILLS/sdd-common/references/review-conventions.md` § After Review.

## After Report Generation

If the review identified critical or warning findings:
- Report findings to the user with the structured completion prompt
- Suggest the appropriate remediation skill (e.g., `sdd-create-spec` for spec doc fixes)
- Do NOT attempt to fix the reviewed documents within the review skill
