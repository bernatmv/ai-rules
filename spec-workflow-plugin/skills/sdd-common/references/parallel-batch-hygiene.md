# Parallel-Batch Hygiene

Single-authority rules for composing parallel tool batches in SDD skills.
Cited by every review SKILL.md Dependencies table at Step 1.

## Contents

- [Cascade-Cancel Principle](#cascade-cancel-principle)
- [Rule 1 — Read-Before-Run](#rule-1--read-before-run)
- [Rule 2 — Harden Bash Probes](#rule-2--harden-bash-probes)
- [Rule 3 — Split Risky From Safe](#rule-3--split-risky-from-safe)
- [Rule 4 — Prefer Read Over Cat](#rule-4--prefer-read-over-cat)
- [Rule 5 — Compound Discovery Probes Must Mask Their Exit Code](#rule-5--compound-discovery-probes-must-mask-their-exit-code)
- [Rule 6 — Probe-vs-Required Mixing](#rule-6--probe-vs-required-mixing)
- [Sibling Cancel](#sibling-cancel)

## Cascade-Cancel Principle

When any tool in a parallel batch errors, the harness cancels every
sibling — even safe ``Read`` calls. This makes a risky ``Bash`` in a
mixed batch a blast radius for adjacent reads. Compose batches to
minimise cascade risk.

Observed cancel sources include any environment-dependent ``Bash``
probe (``init-project.py`` that fails on an existing dir, ``ls`` on an
unborn folder). Anti-pattern from the wild — running an
``init-project.py`` that errors alongside a ``ls`` cancels the read
sibling. Correct shape: run the read in a later turn, or as an
independent batch once the probe is known-healthy.

**Multi-target alternative.** When the same validator must run
against several targets (workspace contexts: coordinator + each
target repo), prefer a single multi-target invocation over parallel
sibling calls. ``spec/check-traceability.py --targets <a> <b>`` and
``spec/lint-tasks.py --targets <a> <b>`` accept the canonical
repeatable form and emit per-target sub-results under
``data.targets[]``. The literal is rendered by
``command_templates.build_check_traceability_command(spec_names=[…])``
and ``build_lint_tasks_command(spec_names=[…])`` so emitter and prose
share one shape. One Bash call → no cascade-cancel risk.

## Rule 1 — Read-Before-Run

If a ``Bash`` call's invocation contract lives in a reference doc,
issue the ``Read`` in an **earlier** turn. The two MUST NOT share a
parallel batch. Enforced mechanically by the
``dependency_table_read_before_run`` lint (see
`$SKILLS/sdd-common/references/tool-patterns.md` § Dependencies Table
Schema).

## Rule 2 — Harden Bash Probes

`;`-chained existence probes exit with the **last** command's
status, so any `test -f MISSING` at the tail fails the whole call.
For fixed-path existence checks, prefer a list-style probe that
never relies on the chain's exit status:

```bash
ls -la A B C 2>/dev/null
```

Reach for the brace-group + `|| true` shape only when an
existing chain cannot be rewritten.

## Rule 3 — Split Risky From Safe

In a single parallel batch, never mix:

- a ``Bash`` call whose success is conditional on environment state; with
- a ``Read`` call whose only cost is cheap filesystem I/O.

The cascade rule makes the cheap call pay for the expensive call's
failure. Split into two turns.

## Rule 4 — Prefer Read Over Cat

The ``Bash`` tool description forbids ``cat`` / ``head`` / ``tail`` /
``sed`` / ``awk`` / ``echo`` for file I/O. For fixed-path reads,
always use ``Read`` — parallelisable, auditable, and cheaper than
shelling out. See also `$SKILLS/sdd-common/references/tool-patterns.md`
§ Tool Choice for Common Needs.

## Rule 5 — Compound Discovery Probes Must Mask Their Exit Code

`;`-chained discovery probes whose exit code is the OR of their
sub-commands hide individual misses behind a uniform `0`. Use a
list-style probe so the shell expansion enumerates the candidates
and the call exits 0 cleanly:

```bash
ls /opt/homebrew/bin/python3.{10,11,12,13} /usr/local/bin/python3.{10,11,12,13} 2>/dev/null || true
```

`sdd_core.command_templates.build_compound_discovery_command`
emits this exact shape; every operator that surfaces a compound
discovery probe composes through it.

## Rule 6 — Probe-vs-Required Mixing

Never include a "probe-for-existence" call (whose miss is *expected*
on a fresh feature) as a sibling of "must-succeed" reads in the same
parallel batch. The probe's exit-1 cancels every sibling under the
[Cascade-Cancel Principle](#cascade-cancel-principle), so the cheap
required reads pay for the probe's miss.

Two anti-pattern shapes from the wild:

```bash
ls .spec-workflow/specs/<not-yet-created-feature>/
```

paired in the same batch with `Read` calls on canonical references —
the `ls` exits 1, every `Read` cancels.

```bash
ls A 2>/dev/null && echo --- && ls B 2>/dev/null
```

paired with required `Read`s — when `A` is missing the `&&` short-
circuits and the chain exits non-zero. Even with `2>/dev/null` the
chain's exit code propagates and cancels siblings.

**Remedies:**

- Mask the probe's exit code with `|| true` (acceptable when no
  downstream call inspects exit status):

  ```bash
  ls .spec-workflow/specs/<feature>/ 2>/dev/null || true
  ```

- Or split the probe into its own turn so the required reads run
  unconditionally next turn.
- Or replace the existence probe with a `Read` of a known-existing
  index file (the `Read` tool returns content or a structured "not
  found" — neither cancels siblings).

## Sibling Cancel

See [Cascade-Cancel Principle](#cascade-cancel-principle) — sibling
cancellation is the same surface; the rule and remediation live there.
