# Canonical _Prompt Suffix

The following text MUST appear at the end of every `_Prompt` field in `tasks.md`.
It is the single source of truth for task lifecycle instructions.


## Suffix Text

The canonical prefix + suffix live in ``sdd_core.task_prompts`` —
import from there programmatically, or run the canonical helper below
to print them verbatim:

```
.spec-workflow/sdd util/resolve-template.py --type tasks --spec-name <slug> --workspace .
```

(Content rendering is the implicit default — pass `--metadata-only` for the
path/source-only response.)

This is **the** canonical path: it inlines
``render_task_prompt_prefix(spec_name)`` and
``render_task_lifecycle_suffix(spec_name)`` from ``sdd_core.task_prompts``
into the rendered template body so a fresh ``tasks.md`` ships with the
scaffolding the validator expects. Use this whenever drafting
``tasks.md`` from scratch.

The lower-level helper ``util/render-task-prompts.py --target <slug>``
prints the canonical strings without the surrounding template — use it
**only** when overriding the default scaffold (e.g. quoting the suffix
in prose, or asserting parity in a test).

## Required Keywords (for validation)

| Step | Required keyword/phrase | Must appear before |
|------|------------------------|--------------------|
| 1 | `[-]` or `in_progress` | Step 2 keyword |
| 2 | `Implementation Logs` or `existing logs` | Step 3 keyword |
| 3 | `log-implementation` | Step 4 keyword |
| 4 | `[x]` or `mark the task complete` | (end) |

## Contradiction Patterns (must NOT appear)

- "after implementing" immediately followed by "before starting"
- "mark complete" appearing before "log-implementation"

## Sub-Agent Prompt Substitutions

The review-pipeline launch envelope ships a sub-agent prompt that may
carry the literal placeholder `{gate_score_headline}`. Substitution
rule: the launch handler always replaces this placeholder when any
prior verdict is available. Sources, in order of preference:

1. The `PostReviewSnapshot` persisted on the gate session (carries the
   exact literal the gate rendered when post-review last ran).
2. The canonical `review-quality.json:active.*` block (any prior
   verdict still on disk renders a fresh headline via the same emitter).

The placeholder only survives into the dispatched prompt on a fresh
first launch where neither source carries a verdict — sub-agents that
encounter the literal fall back to rendering the canonical narrative
template per `sub-agent-review-templates.md`. Owner of the substitution:
`review.pipeline_phases.launch.prompt._apply_post_review_substitutions`.
