# Freedom Column Legend

## Contents

- [Legend](#legend)
- [Enforcement](#enforcement)
- [Best-practice anchor](#best-practice-anchor)

## Legend

Every user-invocable SKILL.md's Dependencies table carries a
`Freedom (L/M/H)` column. The values signal how much agent judgment
each step invites:

- **L — narrow bridge.** Run the exact script or open the exact file
  the row names. No substitutions, no adjacent scripts.
- **M — parameterised.** The step chooses parameters or variants
  (template names, scope flags, retry counts) but the surface itself
  is fixed.
- **H — open field.** The agent applies judgment: drafting prose,
  picking between multiple references, or branching across workflow
  phases.

## Enforcement

`sdd_core/data/skill_md_rules.yaml` carries
`require_freedom_column: true` on every user-invocable skill. The
column is validated at review time by
`.spec-workflow/sdd review/check-template-compliance.py --skill-md`.

## Best-practice anchor

Anthropic's Skill authoring guide (`core principles § set appropriate
degrees of freedom`) recommends publishing the freedom budget beside
the action so agents can calibrate before executing.
