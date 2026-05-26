# Implementation Troubleshooting

Common failure patterns and recovery for the task execution loop.
Consult before escalating to the user at the 3-attempt limit.

For common MCP and filesystem errors, see `$SKILLS/sdd-common/references/troubleshooting.md`.

## Step 4e: Test Failures

| Symptom | Likely Cause | Recovery |
|---------|-------------|---------|
| `ModuleNotFoundError` / `ImportError` | Wrong import path or missing dependency | Re-read `_Leverage` files for correct import patterns used elsewhere |
| Fixture not found | Wrong scope or missing `conftest.py` entry | Search existing test files for fixture definitions (`rg "def {fixture_name}"`) |
| Assertion fails on model field | Wrong field name, type, or default | Re-read design.md data model; search implementation logs for how the model is created |
| Integration test timeout | External service not mocked | Search implementation logs for mock patterns; apply same mock style |
| `AttributeError: ... has no attribute` | Wrong API usage | Search existing implementation logs for the correct call signature |
| All tests pass locally but CI fails | Environment difference | Check `_Restrictions` in `_Prompt` for env-specific constraints |

## Step 4f: Log-Implementation Failures

| Exit Code | Error Pattern | Recovery |
|-----------|--------------|---------|
| 1 | `spec not found` | Run `.spec-workflow/sdd spec/check-status.py --all` to verify exact spec name |
| 1 | `task id not found` | Re-read tasks.md — confirm task ID format (e.g. `1.1`, not `task-1`) |
| 1 | `no artifacts` / `empty artifacts` | Add at least one non-empty entry to `--functions`, `--components`, `--classes`, `--apiEndpoints`, or `--integrations` |
| 2 | `permission denied` | Check that `.spec-workflow/specs/{spec-name}/Implementation Logs/` exists and is writable |
| 2 | `path traversal` | Ensure `--spec-name` contains no `/` or `..` characters |

## Step 4d: Implementation Issues

| Situation | Action |
|-----------|--------|
| Endpoint / function already exists | Check Step 4b logs before writing — reuse and extend the existing implementation |
| Unsure how existing utilities work | Read all files listed in `_Leverage` before writing any code |
| Task prompt conflicts with design.md | design.md is authoritative; `_Restrictions` may be conservative — flag the conflict in the log |
| Success criteria are ambiguous | Re-read the `Success` section in `_Prompt`; if still unclear after 1 attempt, escalate |
