# Update-Mode `user_gathering.required` Routing

Canonical routing for the `user_gathering.required` field emitted by
`.spec-workflow/sdd util/detect-doc-state.py` when a skill is running
in **update mode** (spec, steering, or PRD).

This reference is the single source of truth for the rule. SKILL.md
files linked below cite this file instead of carrying a near-duplicate
routing table of their own (plan § *Dependency-inversion migration
checklist*, Step 12).

## Contents

- [Default (creation-mode) rule](#default-creation-mode-rule)
- [Update-mode override](#update-mode-override)
- [Rationale](#rationale)
- [Consumers](#consumers)

## Default (creation-mode) rule

When a skill is **creating** a document from scratch,
`detect-doc-state.py` drives the user-gathering branch:

| `user_gathering.required` | Action |
|---------------------------|--------|
| `true`  | Present inferred `context_available` summary and ask the user to confirm or adjust before writing. |
| `false` | Proceed with codebase-derived content. |

## Update-mode override

When a skill is in **update mode** — a targeted edit to an existing
document — the user has already established scope via their edit
request. The creation-mode rule becomes too chatty; the following
three-row table takes over:

| `user_gathering.required` | Scope established from | Action |
|---------------------------|------------------------|--------|
| `true` | User's edit request already names the section(s) / requirement(s) / field(s) to change | Proceed with the targeted edit. Do NOT re-prompt for context. |
| `true` | User gave only the document name (e.g. "update requirements.md" / "update product.md") | Present inferred `context_available` summary and ask the user to confirm scope before editing. |
| `false` | — | Proceed with the targeted edit. |

## Rationale

- `detect-doc-state.py` does not know which step the caller is in, so
  it emits `user_gathering.required` uniformly. The skill decides
  whether the prompt layer has already been paid.
- Update mode's entry criterion — *the user asked to change a specific
  part of an existing document* — is itself a scope signal strong
  enough to skip a second clarification prompt unless the edit request
  is one-sentence-vague.
- The routing is intentionally **low-freedom** (one row per
  observable situation) so the agent has no latitude to improvise a
  fourth branch.

## Consumers

| Skill | Update-mode step |
|-------|------------------|
| [`sdd-create-spec`](../../sdd-create-spec/SKILL.md) | Step 1.1 (Update Mode) |
| [`sdd-create-steering`](../../sdd-create-steering/SKILL.md) | Step 1.1 (Update Mode) |
| [`sdd-create-prd`](../../sdd-create-prd/SKILL.md) | Step 0 / Step 0.1 (Update Mode) |
