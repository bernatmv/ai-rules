"""Line-level regex / word-matcher dispatch for the validator.

Iterates every non-fence, non-frontmatter line and dispatches via two
data tables — one for top-level ``match_strategy`` choices, one for
nested word-matcher buckets. Adding a strategy or bucket is a tuple
edit; the loop body never changes.
"""
from __future__ import annotations

from typing import Any, Callable

from ..matchers import WordMatcher
from ..text import iter_line_categories
from ..validation_helpers import Severity
from .messages import build_message
from .sections import build_section_map, collect_suppressions, resolve_severity
from .types import (
    Finding,
    NON_SUPPRESSIBLE_GROUPS,
    REPLACEMENT_PLACEHOLDERS,
    STRATEGY_REGEX,
    STRATEGY_WORD,
)


def _suppression_applies(group_name: str, severity: Severity) -> bool:
    """Return ``True`` when ``rq-ignore`` can silence this finding.

    Two structural guards live here so every emission site (regex group,
    word group, nested buckets) dispatches identically:

    * ``Severity.ERROR`` findings are always reported — ``rq-ignore`` is
      an escape hatch for warnings / info, not a hard-block override.
    * :data:`NON_SUPPRESSIBLE_GROUPS` entries can never be cleared —
      preserves the template ↔ reviewer agreement invariant.
    """
    if severity == Severity.ERROR:
        return False
    if group_name in NON_SUPPRESSIBLE_GROUPS:
        return False
    return True

__all__ = [
    "iter_line_findings",
    "STRATEGY_DISPATCH",
    "NESTED_BUCKET_DISPATCH",
]


def _emit_finding(
    *,
    findings: list[Finding],
    group_dict: dict[str, Any],
    group_name: str,
    rule_id: str,
    severity: Severity,
    line_idx: int,
    column: int,
    section: str,
    match_text: str,
    suggestion: "str | None",
    replacement_template: "str | None" = None,
) -> None:
    finding = Finding(
        severity=severity.value,
        group=group_name,
        rule=rule_id,
        line=line_idx + 1,
        column=column,
        section=section,
        match=match_text,
        message=build_message(
            group_dict, group_name=group_name, rule=rule_id, match=match_text,
        ),
        suggestion=suggestion,
    )
    # When the rule declares a ``replacement_template``, render it
    # against the matched literal and surface the result as
    # ``replacement_text`` so post-fix can present a mechanical
    # substitution. The substitution dict is keyed on
    # :data:`REPLACEMENT_PLACEHOLDERS` so the YAML schema validator and
    # the runtime renderer agree on the token vocabulary.
    if replacement_template:
        substitutions = {"match": match_text, "section": section}
        assert (  # noqa: S101 — import-time invariant
            set(substitutions) == REPLACEMENT_PLACEHOLDERS
        ), "REPLACEMENT_PLACEHOLDERS drifted from the runtime substitution dict"
        try:
            finding["replacement_text"] = replacement_template.format(
                **substitutions,
            )
        except (KeyError, IndexError):
            pass
    findings.append(finding)


def _run_regex_group(
    findings: list[Finding],
    group_name: str,
    group: dict[str, Any],
    raw: str,
    line_idx: int,
    section: str,
    mode: str,
    suppressed_groups: set[str],
) -> None:
    for rule in group["rules"]:
        for m in rule["regex"].finditer(raw):
            severity = resolve_severity(
                group, rule=rule, section=section, mode=mode,
            )
            if (
                group_name in suppressed_groups
                and _suppression_applies(group_name, severity)
            ):
                continue
            _emit_finding(
                findings=findings,
                group_dict=group,
                group_name=group_name,
                rule_id=rule["id"],
                severity=severity,
                line_idx=line_idx,
                column=m.start() + 1,
                section=section,
                match_text=m.group(0),
                suggestion=rule["suggestion"],
                replacement_template=rule.get("replacement_template"),
            )


def _run_word_group(
    findings: list[Finding],
    group_name: str,
    group: dict[str, Any],
    raw: str,
    line_idx: int,
    section: str,
    mode: str,
    suppressed_groups: set[str],
) -> None:
    matcher: "WordMatcher | None" = group.get("word_matcher")
    if not matcher:
        return
    for m in matcher.regex.finditer(raw):
        severity = resolve_severity(
            group, rule=None, section=section, mode=mode,
        )
        if (
            group_name in suppressed_groups
            and _suppression_applies(group_name, severity)
        ):
            continue
        _emit_finding(
            findings=findings,
            group_dict=group,
            group_name=group_name,
            rule_id=f"{group_name}-sentinel",
            severity=severity,
            line_idx=line_idx,
            column=m.start() + 1,
            section=section,
            match_text=m.group(0),
            suggestion=None,
        )


def _run_package_manager_bucket(
    findings: list[Finding],
    group_name: str,
    group: dict[str, Any],
    raw: str,
    line_idx: int,
    section: str,
    mode: str,
    suppressed_groups: set[str],
) -> None:
    pkg: WordMatcher = group["package_matcher"]
    co: WordMatcher = group["package_co_matcher"]
    # Gate: require a word-boundary match of install/package/dependency
    # on the same line. ``reinstalled`` / ``packaged`` do NOT trigger.
    if not co.regex.search(raw):
        return
    for m in pkg.regex.finditer(raw):
        severity = resolve_severity(
            group, rule=None, section=section, mode=mode,
        )
        if (
            group_name in suppressed_groups
            and _suppression_applies(group_name, severity)
        ):
            continue
        _emit_finding(
            findings=findings,
            group_dict=group,
            group_name=group_name,
            rule_id="tech-stack-package-manager",
            severity=severity,
            line_idx=line_idx,
            column=m.start() + 1,
            section=section,
            match_text=m.group(0),
            suggestion=None,
        )


def _run_env_var_bucket(
    findings: list[Finding],
    group_name: str,
    group: dict[str, Any],
    raw: str,
    line_idx: int,
    section: str,
    mode: str,
    suppressed_groups: set[str],
) -> None:
    env: WordMatcher = group["env_matcher"]
    for m in env.regex.finditer(raw):
        severity = resolve_severity(
            group, rule=None, section=section, mode=mode,
        )
        if (
            group_name in suppressed_groups
            and _suppression_applies(group_name, severity)
        ):
            continue
        _emit_finding(
            findings=findings,
            group_dict=group,
            group_name=group_name,
            rule_id="env-var-literal",
            severity=severity,
            line_idx=line_idx,
            column=m.start() + 1,
            section=section,
            match_text=m.group(0),
            suggestion=(
                "Configuration belongs in design.md; "
                "express the requirement as a user-visible constraint."
            ),
        )


# Top-level dispatch keyed by the compiled group's ``match_strategy``.
# Add a new strategy by appending one entry; ``iter_line_findings`` does
# not change.
STRATEGY_DISPATCH: dict[str, Callable[..., None]] = {
    STRATEGY_REGEX: _run_regex_group,
    STRATEGY_WORD: _run_word_group,
}


# Nested word-matcher buckets (gated by sibling matcher keys on the
# group). Each entry: ``(presence_key, co_presence_key_or_None, runner)``.
# A new bucket adds one row — see ``types.NESTED_WORD_BUCKETS`` for the
# parallel data-side declaration.
NESTED_BUCKET_DISPATCH: tuple[tuple[str, "str | None", Callable[..., None]], ...] = (
    ("package_matcher", "package_co_matcher", _run_package_manager_bucket),
    ("env_matcher", None, _run_env_var_bucket),
)


def iter_line_findings(
    content: str,
    ruleset: dict[str, Any],
    *,
    mode: str,
) -> list[Finding]:
    """Run regex and word-matcher rules over non-fence, non-frontmatter lines.

    Dispatch is driven by :data:`STRATEGY_DISPATCH` (top-level
    ``match_strategy``) and :data:`NESTED_BUCKET_DISPATCH` (gated nested
    buckets). Adding a new word-matcher / regex group in
    ``requirements_antipatterns.yaml`` does not require editing this
    function.
    """
    findings: list[Finding] = []
    section_map = build_section_map(content)
    suppressions = collect_suppressions(content)
    groups = ruleset["groups"]

    skipped_categories = {"frontmatter", "code_block", "html_comment"}
    for line_idx, raw, stripped, category in iter_line_categories(content):
        if category in skipped_categories or not stripped:
            continue
        section = section_map.get(line_idx, "")
        suppressed_groups = suppressions.get(line_idx, set())

        for group_name, group in groups.items():
            runner = STRATEGY_DISPATCH.get(group.get("match_strategy"))
            if runner is not None:
                runner(
                    findings, group_name, group, raw, line_idx, section,
                    mode, suppressed_groups,
                )

            for presence_key, co_key, bucket_runner in NESTED_BUCKET_DISPATCH:
                if not group.get(presence_key):
                    continue
                if co_key and not group.get(co_key):
                    continue
                bucket_runner(
                    findings, group_name, group, raw, line_idx, section,
                    mode, suppressed_groups,
                )

    return findings
