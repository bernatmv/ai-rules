# Bootstrap Pattern

> **Related protocols:** Cited from `script-conventions.md` § Bootstrap
> Pattern (one-paragraph stub) and `tool-patterns.md` § Invocation
> (one-line cross-link). Owns the canonical three-layer bootstrap
> shape and the external-tooling rule.

## Contents

- [Three Layer Invocation](#three-layer-invocation)
- [Two Layer Bootstrap Layout](#two-layer-bootstrap-layout)
- [External Tooling Invocation](#external-tooling-invocation)

## Three Layer Invocation

Three layers, one per audience. Layer 1 is the canonical operator-facing
shape; Layer 2 is the canonical Python-side seam (production fan-outs and
tests both ride it); Layer 3 is a direct fallback when the shim is
unavailable.

| Layer | Audience | Invocation |
|---|---|---|
| 1 — Agent / shell | Operators, the harness | `.spec-workflow/sdd <group>/<script>.py [args…]` — delegates to `sdd_core/__main__.py`. Cross-repo: `.spec-workflow/sdd --project {repo_path} <group>/<script>.py …`. |
| 2 — Inter-script Python subprocess | Workspace fan-outs, tests | `sdd_core.subprocess_dispatch.run_dispatched(<script>, *args, project_path=…)`. Tests use the `tests/_helpers/sdd_shim.run_sdd` thin wrapper. The four invariants (dispatcher entry, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH` injection, `--project` placement) live in this single helper. |
| 3 — Direct fallback | Per-directory bootstrap chain only | `python3 $SKILLS/sdd-common/scripts/<group>/<script>.py [args…]` — the per-directory `_bootstrap.py` makes the import path resolve without `PYTHONPATH` setup. Anti-pattern unless the shim is unavailable. |

See [`tool-patterns.md` § Invocation](tool-patterns.md#invocation) for the
canonical agent-facing rule.

## Two Layer Bootstrap Layout

| Layer | File | Role |
|-------|------|------|
| Sub-directory shim | `{approval,review,spec,util,workspace,prd,impl,discovery}/_bootstrap.py` and `internal_lints/_bootstrap.py` | Imported as `_bootstrap` by every directly-invoked script's first line; sets `sys.dont_write_bytecode = True` locally, prepends `scripts/` to `sys.path`, and imports the root helper. |
| Root helper | `$SKILLS/sdd-common/scripts/_sdd_bootstrap.py` | Idempotent process-wide setup — flips `sys.dont_write_bytecode`, guards against double path-insert, makes `sdd_core` / `review_quality` importable. |

**Why two layers with distinct names?** When a script is invoked
directly (`python3 spec/check-status.py`), Python inserts the script's
directory at `sys.path[0]`. If the root helper were *also* named
`_bootstrap.py`, the sub-directory shim would register first under that
module name and the subsequent `import _bootstrap` inside the shim
would return the partially-loaded same module — the root helper would
never execute and `sys.dont_write_bytecode` would never flip. Naming
the root helper `_sdd_bootstrap.py` removes the collision.

**Belt-and-braces rule.** Every shim sets
`sys.dont_write_bytecode = True` as its first executable statement so
the flag applies even if the subsequent root-helper import fails
(corrupted file, permissions, etc.). This is the "solve, don't punt"
rule from Anthropic's [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#advanced-skills-with-executable-code):
handle the failure mode at its source rather than leaving stray
`__pycache__` directories for callers to discover.

## External Tooling Invocation

IDE language servers (Pyright, Pylance) and ad-hoc `python3` runs
outside the bootstrap chain MUST set `PYTHONDONTWRITEBYTECODE=1` in
their environment. Recovery shim: `bash scripts/clean-pycache.sh`
purges any caches that leaked through. Pin `export
PYTHONDONTWRITEBYTECODE=1` in your shell rc-file to make it default-on
locally.

## Mirror contract

`.claude/skills/sdd-common/**` is a generated mirror of
`.cursor/skills/sdd-common/**`. Never hand-edit the `.claude` copy;
run `bash scripts/update-skills.sh` after every change under
`.cursor/skills/**`. CI gates the mirror via
`scripts/check-skills-mirror.sh --strict`.
