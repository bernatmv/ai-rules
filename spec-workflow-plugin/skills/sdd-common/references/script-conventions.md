# Script Conventions

All SDD Python scripts follow these output and error conventions.

## Contents

- [Stdout (Success)](#stdout-success)
- [Stderr (Error)](#stderr-error)
- [Exit Codes](#exit-codes)
- [Canonical CLI Flags](#canonical-cli-flags)
- [Script Pattern](#script-pattern)
- [Plan-validate-execute](#plan-validate-execute)
- [JSON Envelope Types](#json-envelope-types)
- [Preferred Import Pattern](#preferred-import-pattern)
- [Bootstrap Pattern](#bootstrap-pattern)
- [Runtime Dependencies](#runtime-dependencies)
- [Exemption baseline](#exemption-baseline)
  - [Promoting `hint=` calls to `next_action_command`](#promoting-hint-calls-to-next_action_command)
- [SKILL.md compliance rules](#skillmd-compliance-rules)
  - [Adjacency & dispatcher-hygiene lints](#adjacency--dispatcher-hygiene-lints)
- [WordMatcher](#wordmatcher)
  - [Composition shapes](#composition-shapes)
  - [Forbidden](#forbidden)

## Stdout (Success)

`{"status": "ok", "data": {...}, "message": "..."}` — JSON with
consistent top-level keys, emitted via `sdd_core.output.success`.

## Stderr (Error)

`{"status": "error", "error": "...", "hint": "...", "context": "...", "next_action_command": "..."}`
— JSON `ErrorResponse` envelope emitted via `sdd_core.output.error`.
Pair every error with a literal `next_action_command` so agents copy
the recovery shim verbatim. Scripts MUST route failures through
`output.error()` rather than raw `print(..., file=sys.stderr)` so
downstream tooling can parse the envelope. See
[JSON Envelope Types](#json-envelope-types).

## Exit Codes

Single canonical policy — every script MUST follow this rule:

- `0` = success, intentional skip, **or any result-class outcome** (search miss, partial coverage, preflight gate). Envelope `status` distinguishes — `"ok"` for completed work, `"result"` for structured outcomes that travel in `data.outcome`.
- `1` = any user-facing error: bad arguments, missing argument, missing file, malformed input, validation failure, business-logic failure.
- `2` = unrecoverable system fault: permission denied, disk full, corrupt internal state, external dependency unreachable.

Result-class outcomes route through dedicated emitters so the exit code stays at 0 and the outcome surfaces in `data.outcome`:

| Emitter | When to call | `data.outcome` |
|---|---|---|
| `output.miss(payload, message)` | Search/listing returned zero rows | `"miss"` |
| `output.partial(payload, message)` | Checker found N>0 issues, no fatal error | `"partial"` |
| `output.preflight_required(payload, message, *, next_action_command, hint, error)` | Gate refused (e.g. H1 actor); top-level `error` / `hint` / `next_action_command` keys preserved for retry envelopes | `"preflight_required"` |

Reserve `output.error` (exit 1) for genuine failures. The `result_class_exit` lint flags `output.error(... exit_code=1)` calls whose message matches a known result-class regex.

Argparse usage errors are routed through `cli.strict_parser` → `output.error()` → exit `1` (not the argparse default of `2`).

Tests must assert exit codes against this policy. See `tests/test_e2e_all_scripts.py::TestExitCodePolicy`.

## Canonical CLI Flags

`cli.strict_parser` auto-registers flags every workflow-scoped script
must honour. Do not redeclare these in the script's own `add_argument`
calls — argparse will raise `conflicting option string`.

| Semantics | Flag | Registered by | Read via |
|-----------|------|---------------|----------|
| Project root | `--workspace PATH` (default: `$SDD_PROJECT_PATH` or cwd) | `cli.strict_parser` (automatic) | `paths.resolve_project_path(args)` |
| One or more file paths | `--file PATH` (repeatable) | per-script `add_argument` | `args.file` |
| Spec name / doc target | positional + `--spec-name` | `cli.add_spec_target_args` | `cli.resolve_spec_target(args, …)` |
| `key=value` pair set | `--params key=value [...]` | per-script `add_argument(action=cli.KeyValueAppend, nargs='*')` | `args.params` |
| Coordinator workspace tracker root | `--tracker-root <abspath \| coordinator \| workspace>` | per-script `add_argument` | `cli.resolve_tracker_root(args)` — bare `.` rejected; `coordinator` is feature-scoped (consults `coordination-manifest.json` for `--tracker-target`'s feature); `workspace` resolves to caller's pre-chdir cwd |

`--params key=value` is the canonical form (repeatable). The argparse
parser (`KeyValueAppend.__doc__` in `sdd_core.cli`) rejects ambiguous
whitespace-bundled multi-pair tokens with a recovery hint pointing at
the canonical form.

`--workspace` also takes effect before argparse runs: `cli.run_main`
calls an `argv` pre-scan that sets `SDD_PROJECT_PATH` and `chdir`s into
the resolved directory. This means scripts that never read
`args.workspace` still see the correct root via
`paths.find_workflow_root()`.

CI enforces the convention in `tests/test_script_cli_conventions.py`:
every executable script in `approval/ spec/ util/ review/ workspace/ prd/ discovery/ impl/`
must surface `--workspace` in its `--help` output.

## Script Pattern

All scripts follow the thin CLI + shared library pattern:

```python
#!/usr/bin/env python3
"""Brief description."""

import argparse
from sdd_core import paths, output

def main():
    parser = argparse.ArgumentParser(description="...")
    args = parser.parse_args()
    root = paths.find_workflow_root()
    output.success({"key": "value"}, "Operation completed")

if __name__ == "__main__":
    main()
```

## Plan-validate-execute

Migration scripts and other one-shot fixers follow a three-phase
shape so re-runs are idempotent and the operator can audit the plan
before any byte hits disk:

- **plan**: enumerate the inputs to act on (files to fold, snapshots
  to backfill). Pure read; no writes.
- **validate**: idempotency check — confirm each input either still
  needs the fix or is already in the target shape. Skip the latter.
- **execute**: atomic write per output. Use `output.atomic_write_json`
  (temp-file + rename) so a partial run never leaves a torn file.

Re-run of a successful migration is a no-op; re-run after partial
failure picks up where the last run stopped.

The canonical example is `util/migrate-review-quality.py`:

1. Plan — list every `review-quality-{phase}.json` sibling under each
   spec dir.
2. Validate — read the canonical `review-quality.json` and confirm
   the sibling's payload is not already folded into `phase_history`.
3. Execute — atomically rewrite `review-quality.json` with the
   appended history entry, then remove the sibling.

`util/migrate-legacy-snapshot.py` follows the same shape: plan
enumerates legacy snapshots missing `canonicalPath`; validate skips
already-backfilled entries; execute rewrites each metadata file in
place.

## JSON Envelope Types

- `StdoutResponse`: `{"status": "ok"|"result", "data": dict, "message": str}` — base shape for stdout envelopes.
- `SuccessResponse(StdoutResponse)`: narrows ``status`` to `Literal["ok"]` — emitted by `output.success()` (always exit 0).
- `ResultResponse(StdoutResponse)`: narrows ``status`` to `Literal["result"]` — emitted by `output.result()` (any exit code).
- `ErrorResponse`: `{"status": "error", "error": str, "hint": str, "context": str}` — emitted by `output.error()`.
- `ResponseEnvelope`: `Union[StdoutResponse, ErrorResponse]` — use for type annotations in tests and downstream consumers.
- `pre_launch_sequence`: list of `{name, status, why, command, read_instruction?}` rows surfaced on the launch envelope. Built by `launch_preconditions/payload.py::build_pre_launch_sequence`. `status` is `"satisfied"` or `"missing"`; `command` is the literal recovery shim; `read_instruction` is only present for `ReferenceReadPrecondition` rows. Emitted on every launch (both success and recoverable-miss envelopes) so agents can echo a positive confirmation rather than only a failure list. Consumers: `review/pipeline_phases/launch/phase.py` (success path) and `review/pipeline_phases/launch/preconditions.py::_run_launch_preconditions` (blocked path).

### Pure helper + caller emit

Some checks emit advisories without exiting (e.g.
`review/pipeline_phases/_advisories.py::detect_v3_reader_drift`). These
are pure functions returning `dict | None`; the caller routes a
non-None return through `output.partial(...)` or attaches it to the
existing emission envelope. Keeps detection composable across
multi-stage pipelines — the same helper can fire from launch
preconditions, post-review, and ad-hoc CLI without restating the
emission contract.

## Preferred Import Pattern

Import directly from the submodule rather than from the top-level package for clarity and to avoid loading unused modules:

```python
# Preferred — explicit and lightweight
from sdd_core.paths import find_workflow_root, approvals_dir
from sdd_core.output import success, error

# Acceptable — loads the full package
from sdd_core import paths, output
```

Both patterns work; direct submodule imports are preferred in new scripts.

## Bootstrap Pattern

Three layers, one per audience: Layer 1 is the canonical operator-facing
shape (`.spec-workflow/sdd <group>/<script>.py`); Layer 2 is the
Python-side seam (`sdd_core.subprocess_dispatch.run_dispatched`); Layer 3
is a direct fallback when the shim is unavailable. The full layer
table, two-layer layout rationale, and the external-tooling
`PYTHONDONTWRITEBYTECODE` rule live in
[`bootstrap-pattern.md`](bootstrap-pattern.md).

`.claude/skills/sdd-common/**` is a generated mirror of
`.cursor/skills/sdd-common/**`. Never hand-edit the `.claude` copy;
run `bash scripts/update-skills.sh` after every change under
`.cursor/skills/**`. CI gates the mirror via
`scripts/check-skills-mirror.sh --strict`.

See [`tool-patterns.md` § Invocation](tool-patterns.md#invocation) for
the agent-facing rule.

## Runtime Dependencies

Scripts run against the user's system Python interpreter — there is no
isolated venv. Any third-party import must be documented here (and in the
failing script's ``ImportError`` handler).

| Package | Used by | Scope | Install |
|---------|---------|-------|---------|
| `PyYAML` (>=6.0) | `sdd_core.requirements_validation` (reads `requirements_antipatterns.yaml`) | Hard dep (spec reviews break without it) | `pip install pyyaml` |
| `pytest` (>=7.0) | `tests/` suite | Dev dep (not required at runtime) | `pip install pytest` |

Import-time guards for third-party packages route through
`sdd_core.deps` — call `require_pyyaml()` from any module that needs
`yaml` so the install hint above stays in lock-step with the runtime
error message (`deps.PYYAML_INSTALL_HINT`).

Everything else (`argparse`, `json`, `pathlib`, `subprocess`, `dataclasses`,
`typing`, `re`, `enum`, `textwrap`, …) ships with CPython 3.10+ and needs
no extra install.

## Exemption baseline

Every internal lint's exemptions live in a single consolidated manifest
at `internal_lints/baselines.json`, keyed by rule id. The aggregator
(`review/check-template-compliance.py --<rule>`) diffs the observed
entries against the manifest and fails when:

- A new exemption lands without a manifest update (drift detected).
- A manifest entry is no longer observed (stale — remove via `--prune`).

Refresh workflow — dry-run diff, rewrite a single rule, rewrite every
rule:

```
.spec-workflow/sdd internal_lints/baseline-refresh.py --rule <id>
.spec-workflow/sdd internal_lints/baseline-refresh.py --rule <id> --prune
.spec-workflow/sdd internal_lints/baseline-refresh.py --all --prune
```



The manifest is additive by default; adding new exemptions by hand is
discouraged — fix the call site instead, or run `--prune` as a
standalone commit so the drop is visible in review.

### Promoting `hint=` calls to `next_action_command`

`hint_only_count` in the lint envelope tracks `output.error(...,
hint=...)` calls that do not also pass `next_action_command=`. They are
informational, not blocking, but each is a candidate for a literal
recovery command. When the situation has a single deterministic next
step, replace `hint="Run X"` with `next_action_command="X"`; keep `hint`
for the human-readable reason. When no recovery command applies (e.g.
"file is corrupted, ask user"), annotate the call with
`# noqa: solve-dont-punt — <reason>` and let the baseline carry it.

## SKILL.md compliance rules

`review/check-template-compliance.py --skill-md <path>` reads its rule
set from `sdd_core/data/skill_md_rules.yaml` via
`sdd_core.skill_md_rules`. Schema:

- `forbidden`: literals that must not appear in any SKILL.md (e.g. stale
  CLI strings replaced by canonical command emitters).
- `per_skill.<skill-name>`: per-skill positive rules — `max_lines` budget
  cap, `require_freedom_column: true` for the Dependencies table, and
  `required_literals` (literal must appear at least once).

Adding a new forbidden literal or a new per-skill rule is a YAML edit
only — no Python change required.

### Adjacency & dispatcher-hygiene lints

Two lints complement the `forbidden` / `per_skill` rule set above:

- **Prompt-invocation adjacency** — every SKILL.md mention of a prompt
  id must carry its `util/generate-prompt.py --type <id>` verb within
  `max_distance_lines` lines. Rule key:
  `prompt_invocation_adjacency` in
  `sdd_core/data/skill_md_rules.yaml`. Lint:

  ```
  .spec-workflow/sdd internal_lints/skill_md_prompt_refs.py --all
  ```

- **Emitter → dispatcher hygiene** — every recovery command a phase
  emits must target `review/pipeline-tick.py --phase <name>`. Phase
  handlers are subcommands on `review/prepare-pipeline.py`, so a
  `--phase` flag only resolves on the dispatcher. Lint:

  ```
  .spec-workflow/sdd internal_lints/emitter_dispatcher_hygiene.py
  ```

Both are invoked from
`.spec-workflow/sdd review/check-template-compliance.py --skill-md`
(prompt adjacency) and the pytest CI sweep (both).

## WordMatcher

`sdd_core.matchers.WordMatcher` owns every literal word/phrase
alternation. Use it — not `re.compile(r"(a|b|c)")` — when **all** of:

- ≥ 2 literal words/phrases joined by `|`.
- Shared boundary policy (start, word, or delimited).
- No back-references or per-alternative capture groups.

Structural regexes (character classes, look-around, positional
quantifiers, argparse scrapers) stay on plain `re`.

### Composition shapes

| Need | API | Example |
|------|-----|---------|
| Standalone match | `matcher.search(text)` / `matcher.match(text)` | `AFFIRM_WORDS.search(reply)` |
| Embed in a larger raw regex | `matcher.pattern_fragment()` → `(?:w1|w2|…)` | `r"\." + _KNOWN_EXTENSIONS.pattern_fragment()` |
| Full `re.Pattern` with shell / regex extras | `matcher.compose(prefix=…, suffix=…, extra_alternatives=(…,))` | `BUG_FIX_HEADING_PHRASES.compose(prefix=r"^##\s+")` |

### Forbidden

CI greps enforce the following bans (see `tests/test_matchers_compose.py` and `tests/test_matchers_migrations.py` for the active assertions):

- `matcher.regex.pattern[N:]` — slicing into internals. Use `pattern_fragment()`.
- `"…" + matcher.regex.pattern` — drops compiled flags. Use `compose()`.
- `boundary="none"` as a composition hack — use `pattern_fragment()` /
  `compose()` instead. `"none"` remains correct for its original
  "match anywhere mid-line" intent (artifact / content markers).
