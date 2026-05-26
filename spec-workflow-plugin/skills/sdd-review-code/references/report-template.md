# Code Review Report Template

Extends the base report skeleton from `$SKILLS/sdd-common/references/review-conventions.md`
with code-review-specific sections.

## Contents
- [Report Structure](#report-structure)
  - [Header](#1-header)
  - [Executive Summary](#2-executive-summary)
  - [Overall Status](#3-overall-status)
  - [Dimension Scorecards](#4a-dimension-scorecards)
  - [Findings (Severity-Ordered)](#5-findings-severity-ordered)
  - [Positive Observations](#6-positive-observations)
  - [Fix Loop Status](#7-fix-loop-status-if-applicable)

## Report Structure

### 1. Header

```
# Code Review Report
- **Project**: {project name}
- **Spec**: {spec name} (spec-aware mode) or "Standalone" (standalone mode)
- **Date**: {date}
- **Scope**: {file count} files reviewed
- **Mode**: spec-aware | standalone
```

### 2. Executive Summary

2-3 sentence overview: what was reviewed, key findings, overall assessment.
Lead with the most important finding.

### 3. Overall Status

Use status definitions from `$SKILLS/sdd-common/references/review-conventions.md`:
- **PASS**: All dimensions score ≥4/5, no critical findings
- **NEEDS WORK**: Any dimension scores 3/5
- **FAIL**: Any dimension scores ≤2/5

### 4a. Dimension Scorecards

| Dimension | Score | Status | Key Finding |
|-----------|-------|--------|-------------|
| Code Quality | X/5 | ✅/⚠️/❌ | Brief note |
| Architecture | X/5 | ✅/⚠️/❌ | Brief note |
| Security | X/5 | ✅/⚠️/❌ | Brief note |
| Performance | X/5 | ✅/⚠️/❌ | Brief note |
| Testing | X/5 | ✅/⚠️/❌ | Brief note |
| Conventions | X/5 | ✅/⚠️/❌ | Brief note |
| General Principles | X/5 | ✅/⚠️/❌ | Brief note |
| Task Compliance | X/5 | ✅/⚠️/❌ | (spec-aware only) |

Omit dimensions that were skipped (conditional dimensions not applicable).

### 4b. Principle Scorecard

**Overall Principles Score:** X/5

Generate one row per principle from `$SKILLS/sdd-common/references/general-principles.md § Scoring`.
Each row: Principle | Weight | Score | Evidence (non-empty).

### 4c. Anti-Pattern Checks

Generate one row per anti-pattern from `references/criteria-code-quality.md § Anti-Pattern Taxonomy`.
Each row: Anti-Pattern | Status | Notes.

### 5. Findings (Severity-Ordered)

List all findings ordered by severity (Critical first, then High, Medium, Low).

| # | Severity | Dimension | File | Line | Finding | Recommendation |
|---|----------|-----------|------|------|---------|----------------|
| 1 | Critical | Security | path/file.ts | 42 | SQL injection | Use parameterized queries |
| 2 | High | Performance | path/file.ts | 88 | N+1 query | Batch fetch with JOIN |

### 6. Positive Observations

List 3-5 things done well. Reinforces good practices.

- {Positive observation 1}
- {Positive observation 2}
- {Positive observation 3}

### 7. Fix Loop Status (if applicable)

| Cycle | Issues Found | Issues Fixed | Remaining |
|-------|-------------|-------------|-----------|
| Initial | N | — | N |
| Cycle 1 | M | K | M-K |
| Cycle 2 | P | Q | P-Q |
