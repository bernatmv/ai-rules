# Bug-Fix Workflow Steps

Steps 0 and 0.1 for bug-fix mode. Referenced from `SKILL.md` § Workflow.

## Triage (Step 0)

Classify severity by reading `triage-criteria.md`. If ambiguous:

Present the `bug-severity` prompt from the registry via AskQuestion.
See `$SKILLS/sdd-common/references/prompt-conventions.md` § Integration Pattern.



| Severity | Routing |
|----------|---------|
| Critical / High | Fast path (Step 0.1) |
| Medium / Low | Standard path (Step 1+) |

## Fast Path (Step 0.1 — Critical/High only)

- Create both requirements.md and design.md, present together for combined review
- Submit two approval requests sequentially, prompt user to review both at once
- Minimal tasks (fix + regression test only)

Present fast path choice:

Present the `bug-fast-path` prompt from the registry via AskQuestion.
See `$SKILLS/sdd-common/references/prompt-conventions.md` § Integration Pattern.


- If `sequential`: fall back to sequential flow (Step 1+)

After fast path approval, proceed to Step 9 (Write tasks.md — minimal: fix + regression test), then Step 11 (Final Review and Approval Pipeline, including opt-in review gate).
