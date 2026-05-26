# Harness Detection

> **Related protocols:** Called from `sdd_core.harness.load_adapter`
> at every script bootstrap. Used by: identity-aware prompt rendering,
> audit-log `harness_name` field. See also: `harness-notes.md`
> (envelope shapes), `prompt-conventions.md` § Integration Pattern.

How harness identity is resolved for the active pipeline. Scripts
consume the result via ``sdd_core.harness.loader.load_adapter``.

## Contents

- [Priority ladder](#priority-ladder)
- [Env-marker table](#env-marker-table)
- [Safe-default policy](#safe-default-policy)
- [Contradictions vs warnings](#contradictions-vs-warnings)
- [Two entry points](#two-entry-points)

## Priority ladder

The **pluggable detector registry** (``sdd_core.harness.detectors``) is
consulted in priority order — lowest priority first:

| Priority | Detector | Inputs | Outcome |
|----------|----------|--------|---------|
| 10 | override | ``SDD_HARNESS_OVERRIDE`` env var | Unknown value → ``output.error`` envelope. |
| 20 | state file | ``.spec-workflow/.sdd-state/harness.json`` | Unknown / malformed → ``output.error`` with a re-probe ``next_action_command``. |
| 30 | env markers | ``CLAUDE_CODE_TASK_VARIANT`` / ``CLAUDE_CODE_VERSION`` / ``CURSOR_AGENT`` / ``CURSOR_WORKSPACE`` | Persists ``harness.json`` and warns once. |
| 90 | safe default | ``DEFAULT_ADAPTER_ORDER[0]`` / ``SDD_HARNESS_DEFAULT`` | Persists ``harness.json`` and warns prominently. |

Adding a host is an ``@register_detector`` edit in ``detectors.py``;
there is no silent Cursor-by-default branch in the loader.

## Env-marker table

Env-marker resolution is **data, not control flow** — the registry
iterates a tuple of ``(predicate, adapter_name)`` rows in declared
order. Claude Code wins over Cursor when both markers are present; the
fall-back is Cursor.

```python
_ENV_MARKER_TABLE = (
    (lambda env: env.get("CLAUDE_CODE_TASK_VARIANT") == "1"
                 and bool(env.get("CLAUDE_CODE_VERSION")),
     "claude-code-task-variant"),
    (lambda env: bool(env.get("CLAUDE_CODE_VERSION")),
     "claude-code-standard"),
    (lambda env: bool(env.get("CURSOR_AGENT")
                      or env.get("CURSOR_WORKSPACE")),
     "cursor"),
)
```

Rule: **Claude Code first, Cursor is the fall-back.** A generic
``CURSOR_WORKSPACE`` setting never masks a genuine
``CLAUDE_CODE_VERSION`` signal.

## Safe-default policy

When no detector returns a strong outcome, the safe-default detector
resolves to ``DEFAULT_ADAPTER_ORDER[0]`` in
``sdd_core/harness/defaults.py``. Operators override the order via
configuration or the ``SDD_HARNESS_DEFAULT`` env var — not a code edit.
The resolution emits a prominent ``WARNING: no harness signals
detected; defaulting to …`` line naming the recovery command.

## Contradictions vs warnings

- **Contradictions** (``output.error``): unknown override, malformed
  state file, unknown adapter named in state, invalid
  ``SDD_HARNESS_DEFAULT``. Each surfaces as a structured error envelope
  with a ``hint`` and a ``next_action_command``.
- **Warnings** (``output.warn``): env-marker auto-probe and safe-default
  fall-through. Fires once per workspace — subsequent resolutions read
  the persisted state file and stay silent.

## Two entry points

- ``load_adapter(project_path)`` — total function; always returns an
  adapter. Weak signals emit ``output.warn``; explicit contradictions
  emit ``output.error``.
- ``detect_adapter_strict(project_path)`` — raises
  ``HarnessNotDetectedError`` when resolution falls through to the
  safe-default detector. Used by tests / probe internals.

Run ``.spec-workflow/sdd util/probe-harness.py`` once per checkout to
persist the detected capabilities. ``--reset`` clears the cache;
``--dry-run`` prints the envelope without writing.
