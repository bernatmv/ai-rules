---
name: model-selection
description: >
  Always apply: pick the cheaper capable model and stay at High effort.
  Codex: Sol (gpt-5.6-sol) for planning, complex/critical implementation, design,
  creative, or visual work; Luna (gpt-5.6-luna) for coding that is not critical
  or very complex. Claude Code: Fable 5 (claude-fable-5) for planning,
  complex/critical implementation, design, creative, or visual work; Opus 5
  (claude-opus-5) for coding that is not critical or very complex. Switch with
  /model before substantial work if the session model does not match; set the
  matching model on subagents. After a plan is settled, drop to Luna or Opus 5
  for routine coding. Use at session start, when choosing a model, planning,
  implementing, designing, or spawning subagents.
user-invocable: false
---

**model-selection skill loaded.**

Do not run expensive models on cheap work. Stay at **High** effort. Follow only this harness's mapping.

If the session model does not match the task, switch before doing substantial work. When spawning subagents, set the matching model explicitly.

## Codex

- **Sol** (`gpt-5.6-sol`) at High — planning; implementation of complex or critical tasks; any design, creative, or visual work.
- **Luna** (`gpt-5.6-luna`) at High — coding that is not critical or very complex.

Switch with `/model gpt-5.6-sol` or `/model gpt-5.6-luna`.

## Claude Code

- **Fable 5** (`claude-fable-5`) at High — planning; implementation of complex or critical tasks; any design, creative, or visual work.
- **Opus 5** (`claude-opus-5`) at High — coding that is not critical or very complex.

Switch with `/model fable` or `/model opus`, and `/effort high`.

When unsure: Sol / Fable 5 for planning, design, visual work, or complex/critical implementation; otherwise Luna / Opus 5. After a plan is settled, drop to Luna / Opus 5 for routine coding.
