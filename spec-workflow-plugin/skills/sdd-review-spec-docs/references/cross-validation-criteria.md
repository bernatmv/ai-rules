# Spec Document Cross-Validation Criteria

Applies the **Cross-Document Validation Framework** from `$SKILLS/sdd-common/references/cross-validation.md`
to the three spec documents.

## Document Pairs

| Pair | What to Check |
|------|--------------|
| requirements.md ↔ design.md | Each requirement maps to design elements; acceptance criteria have implementation approach; technical feasibility demonstrated |
| design.md ↔ tasks.md | Each component has implementing tasks; `_Leverage:` matches code reuse analysis; test tasks cover testing strategy |
| requirements.md ↔ tasks.md | Every requirement has an implementing task (`_Requirements:`); test tasks verify all acceptance criteria; no orphan tasks |

## Authority Rules

| Topic | Authority |
|-------|----------|
| What to build and why | requirements.md |
| How to build it | design.md |
| Step-by-step plan | tasks.md |

## Duplication Checks

| Pair | Common Duplication | Pass | Fail |
|------|--------------------|------|------|
| req ↔ tasks | Requirements text repeated verbatim in task descriptions | Tasks reference `_Requirements:` IDs | Copy-pasted requirement prose in task body |
| design ↔ tasks | Design component descriptions duplicated in task `_Prompt:` | Tasks summarize briefly, detail lives in design.md | Full design paragraphs in `_Prompt:` |
| req ↔ design | Acceptance criteria restated as design constraints | Design references criteria by ID | Same criteria rewritten with different wording |

## Conflict Checks

| Pair | Conflict Type | Severity |
|------|--------------|----------|
| design ↔ tasks | Task file paths don't match design.md component locations | 🔴 Critical |
| design ↔ tasks | Task restrictions contradict design.md decisions | 🔴 Critical |
| design ↔ tasks | Task `_Leverage:` references don't match design.md code reuse analysis | 🟡 Warning |
| req ↔ design | Design approach doesn't address a stated requirement | 🔴 Critical |
| req ↔ tasks | Requirement has no implementing task (`_Requirements:` gap) | 🔴 Critical |
| req ↔ tasks | Task exists with no `_Requirements:` back-reference (orphan) | 🟡 Warning |

## Gap Checks

| Gap Type | Check | Severity |
|----------|-------|----------|
| Untraceable requirement | Requirement has no task with matching `_Requirements:` ref | 🔴 Critical |
| Design component without task | design.md component has no implementing task | 🟡 Warning |
| Test strategy gap | design.md testing strategy level has no corresponding test task | 🟡 Warning |
| Acceptance criteria gap | Acceptance criterion has no verifying test task | 🟡 Warning |
