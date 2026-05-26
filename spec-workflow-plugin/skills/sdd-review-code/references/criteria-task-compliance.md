# Task Compliance Criteria

Spec-aware mode only. Evaluates whether implementation satisfies each task's requirements.

## Contents
- [File Path Compliance](#1-file-path-compliance)
- [Purpose Achievement](#2-purpose-achievement)
- [Requirements Traceability](#3-requirements-traceability)
- [Leverage Reference Utilization](#4-leverage-reference-utilization)
- [Success Criteria Achievement](#5-success-criteria-achievement)
- [Restriction Compliance](#6-restriction-compliance)
- [Summary Table](#summary-table)

---

## 1. File Path Compliance

**Pass:**
- File exists at path specified in task
- Modifications in correct file
- Follows project naming conventions (tech.md)

**Fail:**
- File in wrong location
- Name doesn't match conventions
- Implementation spread across unspecified files

## 2. Purpose Achievement

**Pass:**
- Task's stated purpose fulfilled
- Code achieves intended functionality
- No extraneous functionality beyond scope

**Fail:**
- Core functionality missing
- Purpose only partially achieved
- Scope creep beyond task definition

## 3. Requirements Traceability

**Pass:**
- All `_Requirements:` references addressed
- Acceptance criteria verifiable
- No refs left unimplemented

**Verification:** Map each `_Requirements:` to specific implementing code

**Fail:**
- Referenced requirement not implemented
- Partial implementation
- No clear verification path

## 4. Leverage Reference Utilization

**Pass:**
- All `_Leverage:` references used
- Existing code extended, not duplicated
- Integration with referenced code correct

**Verification:** Check imports and usage of each `_Leverage:` reference

**Fail:**
- `_Leverage:` not imported or used
- Functionality reimplemented instead of reused
- Incorrect usage of referenced code

## 5. Success Criteria Achievement

**Pass:**
- All `_Prompt: Success` criteria met
- Criteria objectively verifiable
- No criteria partially met

**Fail:**
- Success criteria not met
- Met in non-standard way
- Cannot verify from code alone

## 6. Restriction Compliance

**Pass:**
- All `_Prompt: Restrictions` followed
- No constraint violations
- Boundaries respected

**Fail:**
- Direct restriction violation
- Workaround violating intent
- Missing safeguards

---

## Summary Table

| # | Criterion | Pass | Fail |
|---|-----------|------|------|
| 1 | File path compliance | File at specified path, correct naming | Wrong location or naming |
| 2 | Purpose achievement | Stated purpose fulfilled, no scope creep | Core functionality missing |
| 3 | Requirements traceability | All `_Requirements:` addressed | Referenced requirement unimplemented |
| 4 | Leverage reference utilization | All `_Leverage:` used correctly | Reference ignored or reimplemented |
| 5 | Success criteria | All `_Prompt: Success` met | Criteria not met |
| 6 | Restriction compliance | All `_Prompt: Restrictions` followed | Direct violation |
