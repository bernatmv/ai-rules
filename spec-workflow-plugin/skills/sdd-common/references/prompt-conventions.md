# Prompt Conventions

> **Related protocols:** Called from SKILL.md Dependencies tables (never via chain).
> Used by: all creation and review skills for prompt generation.
> See also: `approval-flow.md` (audit-aware prompts), `review-approval-pipeline.md` (pipeline integration).

Shared conventions for user-facing prompts and workflow formatting across all SDD skills.

## Contents
- [Triage Tiers](#triage-tiers)
- [Mandatory Prompt Convention](#mandatory-prompt-convention)
- [Structured Prompt Format](#structured-prompt-format)
  - [Prompt Generation](#prompt-generation)
  - [Params Quoting](#params-quoting)
  - [Integration Pattern](#integration-pattern)
- [Option Cap](#option-cap)
  - [When You See The Advisory](#when-you-see-the-advisory)
- [Single-Select Default](#single-select-default)
- [Dismissed Prompts](#dismissed-prompts)
- [Free-Text Collection](#free-text-collection)
- [Audit-Aware Prompt Format](#audit-aware-prompt-format)
- [Review and Approval Pipeline](#review-and-approval-pipeline)
- [Inline Hand-off Convention](#inline-hand-off-convention)
  - [Canonical Hand-off Messages](#canonical-hand-off-messages)
- [Workflow Formatting Convention](#workflow-formatting-convention)

## Triage Tiers

Three tiers define when and how many clarifying questions to ask based on task ambiguity:

| Tier | When | Max Questions | Example Skills |
|------|------|---------------|----------------|
| **T0: Zero questions** | Intent is unambiguous from invocation | 0 | `sdd implement X`, `sdd archive X`, `sdd review spec X` |
| **T1: One scope question** | Need to narrow target/scope | 1 (multi-select OK) | `sdd update steering` → which docs?, `sdd approve spec` → which approvals + action |
| **T2: Multi-step triage** | Complex context gathering needed | 2–3 questions | `sdd create spec` (bug fix) → severity + reproduction |

### Tier Assignment Table

| Skill | Invocation | Tier | Questions |
|-------|-----------|------|-----------|
| sdd-create-spec | `sdd create spec X` (standard) | T0 | None |
| sdd-create-spec | `sdd bug fix ...` | T2 | `bug-severity` → if ambiguous, reproduction info (free-text) |
| sdd-create-spec | `sdd update spec X requirements` | T0 | None (target doc is in invocation) |
| sdd-create-spec | `sdd update spec X` (no doc specified) | T1 | Which doc? (free-text or context) |
| sdd-create-steering | `sdd create steering` | T0 | None |
| sdd-create-steering | `sdd update steering` (no doc specified) | T1 | `steering-scope` prompt |
| sdd-create-steering | `sdd update steering tech.md` | T0 | None (target in invocation) |
| sdd-review-spec-docs | `sdd review spec X` | T0 | None |
| sdd-review-steering-docs | `sdd review steering` | T0 | None |
| sdd-manage-status | `sdd approve spec X` | T0 | None (action in invocation) |
| sdd-manage-status | `sdd list pending` | T0 | None |
| sdd-implement-spec | `sdd implement X` | T0 | None |
| sdd-archive-spec | `sdd archive X` | T0 | None |
| sdd-archive-spec | `sdd archive all` | T1 | `batch-archive` prompt |
| sdd-create-prd | `sdd create prd {name}` | T0 | None |
| sdd-create-prd | `sdd resume prd {name}` | T0 | None |
| sdd-create-prd | `sdd update prd {name}` | T0 | None |
| sdd-review-prd | `sdd review prd {name}` | T0 | None |
| sdd-manage-template | `sdd list templates` | T0 | None |
| sdd-manage-template | `sdd show template X` | T0 | None |
| sdd-manage-template | `sdd customize template X` | T0 | None |
| sdd-manage-template | `sdd validate template X` | T0 | None |
| sdd-manage-template | `sdd validate templates` | T0 | None |
| sdd-manage-template | `sdd reset template X` | T1 | Confirmation prompt |
| sdd-manage-template | `sdd diff template X` | T0 | None |
| sdd-manage-template | `sdd sync templates` | T0 | None |

## Mandatory Prompt Convention

When a workflow step presents a choice with a "skip" option, the **prompt
itself is always mandatory**. The agent MUST present the prompt and MUST NOT
autonomously select the skip option. Only the user can choose to skip.

Step headings should NOT include "(optional)" when the prompt is mandatory.
Use "(optional)" only when the entire step — including the prompt — can be
bypassed by the agent (e.g., gated by a prior condition that wasn't met).

### Dismissed Prompts

If the system returns "Questions skipped by the user", treat this as the
skip option for review-offer and fix-loop-continue prompts. For approval
prompts (which require explicit user action), re-present once with:
"The approval prompt was dismissed. Please select an option."

## Structured Prompt Format

Convert all decision points with finite options to structured multiple-choice format. Keep free-text only for genuinely open-ended inputs.

**Standard format:**

```markdown
**Prompt:**
> {Context message}
> - (a) {Option 1}
> - (b) {Option 2}
> - (c) {Option 3}
```

### Prompt Generation

All structured prompts are defined in `$SCRIPTS/prompt-registry.json`. Agents
MUST NOT read this file directly — use `generate-prompt.py` which resolves the
path internally.

Run:

```
.spec-workflow/sdd util/generate-prompt.py --type {type} --params key=value
```

The active harness adapter selects the output format via
`prompt_default_format()` (Cursor → `AskQuestion`-shaped JSON; Claude
Code → lettered markdown). Callers MUST NOT pass `--format` unless
overriding the adapter default.

Skills reference prompts by type ID instead of embedding JSON. If no suitable type exists, add a new entry to `$SCRIPTS/prompt-registry.json` following the existing entry format — do not hand-craft options inline.

### Params Quoting

Use `--params key=value` (one token per pair, repeat the flag for
additional keys):

```
.spec-workflow/sdd util/generate-prompt.py --type {type} --params doc=product.md --params scope=Requirements
```

The argparse parser (`KeyValueAppend.__doc__` in `sdd_core.cli`)
rejects ambiguous bundled tokens with a recovery hint pointing back
at this canonical form. Two bundle shapes are rejected:
whitespace-bundled (`'a=1 b=2'`) and comma-bundled (`'a=1,b=2,c=3'`).
Use the repeatable `--params key=value` form (one token per pair).

### Integration Pattern

At every decision point that references a prompt type:

1. Run `.spec-workflow/sdd util/generate-prompt.py --type {type} --params key=value`.
2. If the type is missing from the registry, add a new entry to `$SCRIPTS/prompt-registry.json` — do not fabricate options.
3. Consume the adapter-shaped output: on Cursor, parse the JSON `questions` array and pass it to **AskQuestion**; on Claude Code, present the rendered lettered markdown and accept the user's letter or full-text response.
4. Map the user's selected option (`option.id` on Cursor, letter label on Claude Code) to the workflow branch.

Skills MUST NOT hand-craft option lists. If no suitable prompt type exists,
add a new entry to `$SCRIPTS/prompt-registry.json`.

## Option Cap

A single prompt carries between 2 and 4 options. Registry drift is
surfaced at two non-blocking layers:

- **Pre-flight** — `workspace/ensure-healthy.py` emits the
  `prompt_registry_option_bounds` advisory once per session, listing
  every out-of-bounds entry. Grep that literal to locate the check
  (`sdd_core.workspace_health_checks.check_prompt_registry_option_bounds`).
- **Render time** — `render_prompt_for_harness` auto-trims to
  `MAX_PROMPT_OPTIONS` and writes one `info` stderr line per render
  (`sdd_core.prompts._enforce_option_bounds`). The returned payload
  is always valid.

### When You See The Advisory

Examples:

- Render-time stderr: `Prompt 'update-intent' had 5 options; trimmed to 4. Dropped: targeted_edit. Edit the registry to fix.`
- Pre-flight tail: `— advisories: prompt_registry_option_bounds`.

Recovery: edit the registry entry in the same session — merge
overlapping options or split into a follow-up prompt. Never raise
`MAX_PROMPT_OPTIONS`; never hand-trim inside an `AskUserQuestion` /
`AskQuestion` call.

CI coverage: `util/generate-prompt.py --validate-registry` walks
every entry through every adapter and surfaces the same info lines.

## Single-Select Default

When the typical answer is exactly one option, omit `multi_select` from
the prompt-registry entry. The default is `false` which mirrors
`PromptSpec.multi_select`. Only set `multi_select: true` when the
answer is genuinely a set (e.g. selecting which docs to revise). This
avoids the radio-vs-checkbox UX mismatch where Cursor renders
checkboxes for a question the user reads as single-select.

**MUST NOT hand-craft lettered options inline.** When a decision point has a
fixed set of options, either (a) use or add a prompt-registry type and present
via the adapter-selected output, or (b) use pure free-text per § Free-Text
Collection — never a markdown-rendered bullet list of pseudo-options. Audit
note #F1 of `docs/sdd-update-steering-execution-audit.md` records the failure
mode this rule exists to prevent: an agent shortcut that splices
registry-ready options into free-text prose because no matching prompt type
existed.

## Free-Text Collection

Structured prompts support only multiple-choice. When open-ended user input is needed (approval comments, rejection reasons, custom descriptions):

1. Prompt conversationally: "Please enter your comment/reason:"
2. Read the user's next chat message as the input
3. Do NOT manufacture multiple-choice options for genuinely open-ended inputs

## Audit-Aware Prompt Format

Approval prompts with audit logging are handled by `approval-flow.md`. The `approval-formal` and `approval-inline` prompt types in the registry embed default comments into option labels. See `approval-flow.md` § Audit Logging for details.

## Review and Approval Pipeline

See `review-approval-pipeline.md` for the shared pipeline
(Validate → Review Gate → Approve) used at every approval point in creation
workflows. Supports `per-document` and `final` scopes.

## Inline Hand-off Convention

All skill completion messages use a brief inline text suggestion. Rules:

1. **One sentence, one suggestion.** No multi-option menus.
2. **Include the exact command** the user would type to invoke the next skill.
3. **Use "Consider" phrasing** — suggestion, not instruction.
4. **No structured prompt** at completion. Reserve structured prompts for genuine in-workflow decisions.

### Canonical Hand-off Messages

| Completing Skill | Inline Suggestion |
|------------------|-------------------|
| sdd-create-steering | "Steering docs complete. Consider running `sdd create spec {name}` to create feature specs." |
| sdd-create-spec | "Spec `{name}` complete. Consider running `sdd implement {name}` to begin implementation." |
| sdd-review-spec-docs | "Spec review complete. To approve, run `sdd approve spec {name}`. To request revision, run `sdd request revision {name}`." |
| sdd-review-steering-docs | "Steering review complete. To approve, run `sdd approve steering`. To request revision, ask for changes." |
| sdd-manage-status (approve) | "Approval complete. To start implementation, run `sdd implement {name}`." |
| sdd-implement-spec | "Implementation complete. The next step is typically `sdd-review-code` for a code-quality review; archival is optional via `sdd archive {spec-name}` once the spec is fully complete." |
| sdd-review-code | "Code review complete. Next step depends on what shipped: open or land the PR and address any non-blocking advisories. Once the spec is fully complete, archival is optional via `sdd archive {spec-name}`." |
| sdd-archive-spec | "Spec archived." |
| sdd-manage-template (customize) | "Template customized. Consider running `sdd create spec {name}` to use your new template." |
| sdd-manage-template (sync) | "Templates synced. Default templates in `.spec-workflow/templates/` are now up to date." |
| sdd-manage-template (reset) | "User template removed. The default template will now be used." |
| sdd-create-prd | "PRD `{feature-name}` complete. Consider running `sdd create spec {feature-name}` to begin spec creation with the PRD as context." |
| sdd-review-prd | "PRD review complete. To approve, run `sdd approve prd {feature-name}`. To request revision, ask for changes." |
| sdd-workspace-create-spec (complete) | "Workspace `{feature}` specs complete. To implement, run `sdd implement {subSpecName}` in each target repo." |

## Workflow Formatting Convention

| Element | SKILL.md (primary) | Workflow reference (detailed) |
|---------|-------------------|-------------------------------|
| Step headings | `### Step N: Title` | `## Phase N: Title` |
| Progress checklist | Plain markdown `- [ ] Step N: Title` | Not needed (SKILL.md owns the checklist) |
| Decision points | Tables with `Situation \| Action` columns | Mermaid flowcharts + tables |
| Approval loops | Delegate to `approval-flow.md` | Delegate to `approval-flow.md` |
