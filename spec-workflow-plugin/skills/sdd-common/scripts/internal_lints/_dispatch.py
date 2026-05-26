"""Single-row registry of every internal lint.

Adding a new lint is one :data:`DISPATCH` row plus one
``baselines.json::rules`` entry — no other registry edits. Both
``review/check-template-compliance.py`` (the aggregator) and
``baseline-refresh.py`` import from this module. See
``references/internal-lints-inventory.md`` for the rendered Group A /
Group B inventory.

Each row carries:

* ``rule_id_attr`` — the argparse ``dest=`` name (Group A only; Group
  B rules are routed via ``--skill-md`` and do not need a dest).
* ``module_path`` — dotted module path (must resolve under
  ``internal_lints.*``).
* ``rule_label`` — kebab-case identifier emitted in JSON envelopes
  and used as the ``baselines.json::rules`` key.
* ``hint_text`` — message surfaced when the rule reports drift.
* ``group`` — ``"A"`` for Python source-quality lints,
  ``"B"`` for SKILL.md content lints.
"""
from __future__ import annotations

from typing import Literal, NamedTuple

__all__ = ["DispatchRow", "DISPATCH", "rule_id_for"]


class DispatchRow(NamedTuple):
    rule_id_attr: str
    module_path: str
    rule_label: str
    hint_text: str
    group: Literal["A", "B"]
    argparse_help: str = ""


DISPATCH: tuple[DispatchRow, ...] = (
    DispatchRow(
        "approve_ceremony_wired",
        "internal_lints.approve_ceremony_wired",
        "approve-ceremony-wired",
        (
            "Wire human-approval-ceremony.md into the SKILL body, "
            "or refresh the baseline if the finding is expected."
        ),
        "A",
        (
            "Run the SKILL.md ceremony lint that requires every approve "
            "invocation to reference human-approval-ceremony.md and that "
            "rejects render_prompt_for_harness mentions in SKILL bodies."
        ),
    ),
    DispatchRow(
        "name_type_wired",
        "internal_lints.name_type_wired",
        "name-type-wired",
        (
            "Wire ``type=cli.name_type(<kind>)`` on the flag, or "
            "refresh the baseline if the finding is expected."
        ),
        "A",
        (
            "Run the ``name_type`` AST lint that requires every identifier "
            "flag to declare ``type=cli.name_type(...)``."
        ),
    ),
    DispatchRow(
        "no_bare_subprocess_dispatch",
        "internal_lints.no_bare_subprocess_dispatch",
        "no-bare-subprocess-dispatch",
        (
            "Replace [sys.executable, str(<script>.py), …] with "
            "sdd_core.subprocess_dispatch.run_dispatched(...) "
            "(production) or tests/_helpers/sdd_shim.run_sdd(...) "
            "(tests). See references/script-conventions.md "
            "§ Bootstrap Pattern."
        ),
        "A",
        (
            "Run the AST lint that forbids bare "
            "[sys.executable, str(<script>.py), …] subprocess calls — "
            "every spawn must ride sdd_core.subprocess_dispatch.run_dispatched."
        ),
    ),
    DispatchRow(
        "no_shell_true",
        "internal_lints.no_shell_true",
        "no-shell-true",
        (
            "Replace subprocess(..., shell=True) with "
            "sdd_core.security.subprocess_safe.safe_run_test, or "
            "refresh the baseline if the finding is expected."
        ),
        "A",
        (
            "Run the ``shell=True`` AST lint across .cursor/skills/ and "
            "diff observed findings against the committed-empty baseline."
        ),
    ),
    DispatchRow(
        "security_concrete_import",
        "internal_lints.security_concrete_import",
        "security-concrete-import",
        (
            "Replace concrete imports of "
            "sdd_core.security.{state,subprocess_safe} with the seam "
            "accessor (locked_store / default_allowlist), or refresh "
            "the baseline if the finding is expected."
        ),
        "A",
        (
            "Run the security-concrete-import AST lint that flags direct "
            "imports of ``sdd_core.security.{state,subprocess_safe}`` from "
            "outside the package — callers must consume the seam accessors."
        ),
    ),
    DispatchRow(
        "no_dataclass_slots",
        "internal_lints.no_dataclass_slots",
        "no-dataclass-slots",
        (
            "Drop ``slots=True`` (and any other 3.10+-only construct) "
            "so the codebase keeps running on Python 3.9, or refresh "
            "the baseline if the finding is expected."
        ),
        "A",
        (
            "Run the AST lint that forbids @dataclass(slots=True) and "
            "other 3.10+-only constructs (match/case, typing.Self, "
            "asyncio.TaskGroup, ExceptionGroup)."
        ),
    ),
    DispatchRow(
        "result_class_exit",
        "internal_lints.result_class_exit",
        "result-class-exit",
        (
            "Replace ``output.error(... exit_code=1)`` on result-class "
            "outcomes with ``output.miss`` / ``output.partial`` / "
            "``output.preflight_required``, or refresh the baseline if "
            "the finding is expected."
        ),
        "A",
        (
            "Run the AST lint that flags output.error on result-class "
            "outcomes (search miss / partial coverage / preflight gate)."
        ),
    ),
    DispatchRow(
        "error_envelopes",
        "internal_lints.error_envelopes",
        "error-envelopes",
        (
            "Add ``next_action_command=`` (preferred) or annotate with "
            "``# noqa: solve-dont-punt — <reason>``."
        ),
        "A",
        "Run the `solve, don't punt` lint across executable scripts",
    ),
    DispatchRow(
        "no_validate_for_lint",
        "internal_lints.no_validate_for_lint",
        "no-validate-for-lint",
        (
            "Rename to `lint-*.py` (per-doc) or `check-*.py` (cross-doc). "
            "`validate` is reserved for schema checks on structured artifacts."
        ),
        "A",
        (
            "Run the AST + filename lint that forbids reintroducing the "
            "legacy `validate-{requirements,tasks,traceability,spec}.py` "
            "shim shapes (W5)."
        ),
    ),
    DispatchRow(
        "no_harness_name_collision",
        "internal_lints.no_harness_name_collision",
        "no-harness-name-collision",
        (
            "Rename the advisory copy so its `code` / `message` does not "
            "substring-match a registered harness name (e.g. cursor, "
            "claude-code-standard). See references/internal-lints-inventory.md."
        ),
        "A",
        (
            "Run the AST lint that flags advisory dict literals whose "
            "code or message collide with a harness name."
        ),
    ),
    DispatchRow(
        "cli_argument_conventions",
        "internal_lints.cli_argument_conventions",
        "cli-argument-conventions",
        (
            "Use `cli.target_argument(parser, family=...)` to register the "
            "canonical `--target` flag instead of declaring `--feature` / "
            "`--repo-id` / `--spec-name` / `--workspace` directly (W7)."
        ),
        "A",
        (
            "Run the AST lint that flags direct `parser.add_argument` "
            "calls for the legacy workflow flags."
        ),
    ),
    DispatchRow(
        "import_paths_resolve",
        "internal_lints.import_paths_resolve",
        "import-paths-resolve",
        (
            "Dotted module paths in steering/spec docs must resolve "
            "against the project's package list."
        ),
        "A",
        "Run the dotted-module-path lint across steering/spec docs.",
    ),
    DispatchRow(
        "emitted_commands_parse",
        "internal_lints.emitted_commands_parse",
        "emitted-commands-parse",
        (
            "An emitter in sdd_core.command_templates rendered a literal "
            "that argparse cannot parse. Common cause: a parent-parser "
            "flag (--target / --workspace) emitted after the "
            "subcommand token. Route it through "
            "build_shim_command(parent_flags={...}) instead."
        ),
        "A",
        (
            "Run the parse-gate lint that renders every build_* emitter "
            "against its fixture and asserts argparse-friendly token "
            "ordering — regression gate for the rerun's E-1."
        ),
    ),
    DispatchRow(
        "no_inline_state_dir_literal",
        "internal_lints.no_inline_state_dir_literal",
        "no-inline-state-dir-literal",
        (
            "Replace the inline `.sdd-state` literal with "
            "sdd_core.paths.STATE_DIR_NAME or "
            "sdd_core.paths.workflow_state_path()/state_dir() — the "
            "constant owns one source of truth."
        ),
        "A",
        (
            "Run the AST lint that forbids `.sdd-state` string literals "
            "outside sdd_core/paths.py."
        ),
    ),
    DispatchRow(
        "review_skill_no_string_default",
        "internal_lints.review_skill_no_string_default",
        "review-skill-no-string-default",
        (
            "Replace ``cached.get('review_skill', <string default>)`` "
            "with ``cached.get('review_skill') or "
            "ReviewSkill.for_category(category)``. The fallback-string "
            "pattern poisons spec/PRD review-skill selection — use the "
            "category-aware resolver instead."
        ),
        "A",
        (
            "Run the AST lint that forbids "
            "``dict.get('review_skill', <non-None default>)``."
        ),
    ),
    DispatchRow(
        "advisory_phase_placement",
        "internal_lints.advisory_phase_placement",
        "advisory-phase-placement",
        (
            "An advisory return-dict's ``status`` does not match the "
            "graph-declared ``severity_when_phase_mismatch`` for that "
            "advisory name. Update workflow-graph.json or the advisory "
            "body so the two agree — the graph is the source of truth "
            "for advisory placement."
        ),
        "A",
        (
            "Run the AST lint that cross-checks every advisory dict "
            "against ``workflow-graph.json::advisories`` placement."
        ),
    ),
    DispatchRow(
        "with_context_coverage",
        "internal_lints.with_context_coverage",
        "with-context-coverage",
        (
            "Add ``__sdd_context_needs__ = (\"target\", ...)`` at module "
            "scope mirroring the workflow graph's ``context_needs`` for "
            "the phase the shim serves, then call "
            "``cli.resolve_context(args, needs=...)`` after parse_args. "
            "Refresh the baseline only when introducing a non-shim helper."
        ),
        "A",
        (
            "Run the AST lint that asserts every workspace shim "
            "(``workspace/*.py`` with a ``def main()``) declares the "
            "``__sdd_context_needs__`` constant for V-7 resolver coverage."
        ),
    ),
    DispatchRow(
        "workflow_graph_cross_refs",
        "internal_lints.workflow_graph_cross_refs",
        "workflow-graph-cross-refs",
        (
            "Every gate_prompt_id / handoff_id / validations id in "
            "sdd_core/data/workflow-graph.json must resolve. Fix the "
            "missing reference (or remove the orphan from the graph) "
            "rather than refreshing the baseline."
        ),
        "A",
        (
            "Run the cross-reference lint that checks every "
            "workflow-graph.json reference resolves into "
            "prompt-registry.json, handoff-registry.json, and the "
            "registered Validator set."
        ),
    ),
    DispatchRow(
        "workspace_state_layout",
        "internal_lints.workspace_state_layout",
        "workspace-state-layout",
        (
            "Replace the inline `.spec-workflow/.sdd-state` literal with "
            "sdd_core.workspace_state_loader.state_path() or "
            "resolve_state_dir() — the loader owns the per-spec / "
            "workspace / standalone tier policy in one place."
        ),
        "A",
        (
            "Run the AST lint that forbids the legacy single-tier "
            "`.spec-workflow/.sdd-state` literal."
        ),
    ),
    DispatchRow(
        "flag_envelope_consistency",
        "internal_lints.flag_envelope_consistency",
        "flag-envelope-consistency",
        (
            "An action's option_strings group did not yield every alias "
            "from did_you_mean, or a sibling-flag registry entry was "
            "silently dropped. Restore the alias-expansion in "
            "sdd_core.cli._expand_alias_groups or refresh the baseline "
            "if the finding is expected."
        ),
        "A",
        (
            "Run the alias-grouping + sibling-registry parity lint for "
            "``_emit_unknown_flag_warn``."
        ),
    ),
    DispatchRow(
        "tracker_update_doc_code_parity",
        "internal_lints.tracker_update_doc_code_parity",
        "tracker-update-doc-code-parity",
        (
            "phase-loop.md prose claims an auto-update path that the "
            "in-tree ``check-spec-shape.py`` no longer honours. Restore "
            "the resolver wiring in workspace/check-spec-shape.py "
            "(_resolve_tracker_root_with_fallback) or refresh the "
            "baseline if the finding is expected."
        ),
        "A",
        (
            "Run the doc/code parity lint for the phase-loop tracker "
            "auto-update claim."
        ),
    ),
    DispatchRow(
        "prose_invocation_via_emitter",
        "internal_lints.prose_invocation_via_emitter",
        "prose-invocation-via-emitter",
        (
            "Skill prose taught a CLI invocation that the script-side "
            "argparse rejects. Replace the snippet with the emitter-"
            "produced literal from `sdd_core.command_templates.build_*` "
            "or refresh the baseline if the finding is expected."
        ),
        "B",
    ),
    DispatchRow(
        "orphan_sdd_core_modules",
        "internal_lints.orphan_sdd_core_modules",
        "orphan-sdd-core-modules",
        (
            "An ``sdd_core/`` module has no production consumer outside "
            "its own file. Wire it into a caller, delete the orphan, or "
            "refresh the baseline if the finding is expected."
        ),
        "A",
        (
            "Run the project-level lint that flags ``sdd_core/`` modules "
            "with no production consumer (manifest + tests do not count)."
        ),
    ),
    DispatchRow(
        "required_tool_calls_schema",
        "internal_lints.required_tool_calls_schema",
        "required-tool-calls-schema",
        (
            "Construct ``required_tool_calls`` payloads via "
            "``sdd_core.required_tool_calls.RequiredToolCallsPayload``. "
            "Legacy fields (``tool``, ``args.todos``) and missing "
            "``consumer`` rows are structurally absent from the dataclass."
        ),
        "A",
        (
            "Run the AST lint that asserts every ``required_tool_calls`` "
            "dict round-trips through "
            "``sdd_core.required_tool_calls.RequiredToolCallsPayload``."
        ),
    ),
    DispatchRow(
        "no_plan_trace_in_references",
        "internal_lints.no_plan_trace_in_references",
        "no-plan-trace-in-references",
        (
            "A SKILL.md or references/ line carries plan-trace lineage "
            "(workstream / rollout-cycle ids, lineage references, "
            "commit pointers — see the lint module for the full pattern "
            "list). Rewrite as a present-tense contract or move it "
            "under a ``## Maintainer notes`` heading."
        ),
        "B",
    ),
    DispatchRow(
        "skill_md_legacy_flags",
        "internal_lints.skill_md_legacy_flags",
        "skill-md-legacy-flags",
        (
            "Replace renamed legacy flags (`--feature`, `--repo-id`, "
            "`--target-name`, `--target-repo`, `--project-path`) in skill "
            "docs with the canonical `--target` / `--workspace` "
            "selectors. Allowlisted carve-outs live in "
            "`internal_lints/skill_md_legacy_flags.py::_ALLOWLIST_PHRASES`."
        ),
        "B",
    ),
    DispatchRow(
        "skill_md_handoff_table",
        "internal_lints.skill_md_handoff_table",
        "skill-md-handoff-table",
        (
            "Run `internal_lints/skill_md_handoff_table.py --rewrite` to "
            "regenerate the `## Handoffs` section from "
            "`scripts/handoff-registry.json`. Hand-edits drift; the "
            "registry is the single source of truth (V-6)."
        ),
        "B",
    ),
    DispatchRow(
        "skill_md_size_and_disclosure",
        "internal_lints.skill_md_size_and_disclosure",
        "skill-md-size-and-disclosure",
        (
            "Trim SKILL.md prose to the 500-line budget; move detail "
            "into references/."
        ),
        "B",
    ),
    DispatchRow(
        "skill_md_abs_paths",
        "internal_lints.skill_md_abs_paths",
        "skill-md-abs-paths",
        "Use $SKILLS-rooted paths instead of absolute paths.",
        "B",
    ),
    DispatchRow(
        "skill_md_toc",
        "internal_lints.skill_md_toc",
        "skill-md-toc",
        "Every H2 needs a TOC entry; titles must follow Title Case.",
        "B",
    ),
    DispatchRow(
        "skill_md_prompt_refs",
        "internal_lints.skill_md_prompt_refs",
        "skill-md-prompt-refs",
        "Every prompt id mention must carry its invocation verb nearby.",
        "B",
    ),
    DispatchRow(
        "skill_md_pair_key_literals",
        "internal_lints.skill_md_pair_key_literals",
        "skill-md-pair-key-literals",
        "Pair-key literals must match the canonical registry.",
        "B",
    ),
    DispatchRow(
        "skill_md_hand_rendered_options",
        "internal_lints.skill_md_hand_rendered_options",
        "skill-md-hand-rendered-options",
        (
            "Render option blocks via the canonical builder rather than "
            "hand-listing options."
        ),
        "B",
    ),
    DispatchRow(
        "skill_md_assessment_staging_literals",
        "internal_lints.skill_md_assessment_staging_literals",
        "skill-md-assessment-staging-literals",
        (
            "Replace assessment / staging literals with the canonical "
            "phrase emitter."
        ),
        "B",
    ),
    DispatchRow(
        "skill_md_dependency_order",
        "internal_lints.skill_md_dependency_order",
        "skill-md-dependency-order",
        "Dependencies tables must list every read row before any run row.",
        "B",
    ),
    DispatchRow(
        "skill_md_batch_hygiene",
        "internal_lints.skill_md_batch_hygiene",
        "skill-md-batch-hygiene",
        (
            "Compound discovery probes / parallel batches must follow "
            "the rules in parallel-batch-hygiene.md."
        ),
        "B",
    ),
    DispatchRow(
        "update_quality_command_uses_builder",
        "internal_lints.update_quality_command_uses_builder",
        "update-quality-command-uses-builder",
        (
            "Replace bare ``review/update-quality.py`` literals with "
            "``sdd_core.command_templates.build_update_quality_command(...)`` "
            "or ``build_review_update_quality_command(...)``."
        ),
        "A",
        (
            "Run the AST substring lint that forbids bare "
            "``review/update-quality.py`` literals outside the canonical "
            "command-template builder."
        ),
    ),
    DispatchRow(
        "review_quality_reader_uses_schema_api",
        "internal_lints.review_quality_reader_uses_schema_api",
        "review-quality-reader-uses-schema-api",
        (
            "Route review-quality artifact reads through "
            "``sdd_core.review_quality_schema`` accessors rather than "
            "indexing the envelope directly."
        ),
        "A",
        (
            "Run the AST lint that flags raw ``data['active']``/"
            "``data.get('issues')`` reads outside the schema module."
        ),
    ),
    DispatchRow(
        "review_input_keys_single_source",
        "internal_lints.review_input_keys_single_source",
        "review-input-keys-single-source",
        (
            "Reference the canonical sub-agent input keys from "
            "``sdd_core.review_input.INPUT_TOP_LEVEL_KEYS`` rather than "
            "duplicating the literals."
        ),
        "A",
        (
            "Run the AST lint that ensures the five canonical sub-agent "
            "input keys appear only in their single owning module."
        ),
    ),
)


def rule_id_for(module_name: str, module_file: "str | None" = None) -> str:
    """Return the kebab-case rule label for a per-lint module.

    Used by every lint module to derive its public ``RULE_ID`` from the
    registry rather than re-declaring the literal. Resolution order:

    1. Full dotted path (``internal_lints.<leaf>``) — production import.
    2. Leaf segment of *module_name* (with optional ``_lint`` suffix
       stripped) — covers test loaders that pass synthetic names.
    3. Basename of *module_file* (with ``.py`` stripped) — covers
       ``runpy.run_path`` / ``python3 script.py`` invocations where
       ``__name__`` is ``"__main__"``.

    Raises ``KeyError`` when no row matches.
    """
    for row in DISPATCH:
        if row.module_path == module_name:
            return row.rule_label
    leaf = module_name.rsplit(".", 1)[-1]
    leaf_clean = leaf[:-5] if leaf.endswith("_lint") else leaf
    for row in DISPATCH:
        row_leaf = row.module_path.rsplit(".", 1)[-1]
        if row_leaf == leaf or row_leaf == leaf_clean:
            return row.rule_label
    if module_file:
        import os as _os
        file_leaf = _os.path.splitext(_os.path.basename(module_file))[0]
        for row in DISPATCH:
            if row.module_path.rsplit(".", 1)[-1] == file_leaf:
                return row.rule_label
    raise KeyError(
        f"No DISPATCH row for module {module_name!r} "
        f"(file={module_file!r}). "
        f"Add an entry in internal_lints/_dispatch.py::DISPATCH."
    )
