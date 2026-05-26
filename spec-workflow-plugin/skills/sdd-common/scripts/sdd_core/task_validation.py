"""Task validation rules with error/warning severity classification."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .matchers import WordMatcher
from .tasks import TASK_LINE_RE, COMPLETED_STATUS, is_header
from .task_prompts import TASK_PROMPT_PREFIX_FORMAT
from .validation_helpers import Severity

__all__ = [
    "TASK_LINE_RE",
    "validate",
    "validate_single_prompt",
    "validate_prompt_format",
    "validate_lifecycle_ordering",
    "detect_contradictions",
]

REQUIRED_SECTIONS = ["role:", "task:", "restrictions:", "success:"]
# Drop the ``{spec_name}`` token and lower-case to match the normalised
# prompt-text used by the lifecycle check below.
REQUIRED_PREFIX = TASK_PROMPT_PREFIX_FORMAT.split("{spec_name}")[0].lower().strip()

_LOG_SEARCH_PHRASES = WordMatcher(("implementation logs", "existing logs"))
_IN_PROGRESS_PHRASES = WordMatcher(("in-progress",))
_COMPLETE_PHRASES = WordMatcher(("mark the task complete",))
_CONTRADICTION_PHRASES = WordMatcher(("in-progress", "before starting"))

_LIFECYCLE_STEP1_RE = _IN_PROGRESS_PHRASES.compose(
    extra_alternatives=(r"\[-\]",),
)
_LIFECYCLE_STEP2_RE = _LOG_SEARCH_PHRASES.compose()
_LIFECYCLE_STEP3_RE = re.compile(r"log-implementation", re.IGNORECASE)
_LIFECYCLE_STEP4_RE = _COMPLETE_PHRASES.compose(
    extra_alternatives=(r"\[x\]", r"mark\s+(?:\w+\s+){0,3}complete"),
)

LIFECYCLE_KEYWORDS: list[tuple[re.Pattern, str]] = [
    (_LIFECYCLE_STEP1_RE, "Step 1 — mark in-progress"),
    (_LIFECYCLE_STEP2_RE, "Step 2 — search Implementation Logs"),
    (_LIFECYCLE_STEP3_RE, "Step 3 — call log-implementation"),
    (_LIFECYCLE_STEP4_RE, "Step 4 — mark complete"),
]

CONTRADICTION_RE = _CONTRADICTION_PHRASES.compose(
    prefix=r"after implement\S* .{0,80}",
)
PROMPT_RE = re.compile(r"_Prompt:\s*(.*)")


@dataclass(frozen=True)
class RuleResult:
    """Uniform output from a single rule check.

    ``severity`` is the shared :class:`~sdd_core.validation_helpers.Severity`
    enum; its ``str`` mixin emits the wire-level values (``"error"`` /
    ``"warning"``) directly on JSON serialisation.
    """
    rule: str
    severity: Severity
    message: str


def _normalize(text: str) -> str:
    """Collapse whitespace and lower-case for pattern matching."""
    return re.sub(r"\s+", " ", text.lower())


def _check_lifecycle_order(normalized: str) -> tuple[str, str] | None:
    """Check lifecycle keyword ordering in normalized prompt text.

    Returns ``(rule, label)`` on first violation, or ``None`` if all OK.
    ``rule`` is either ``"missing"`` or ``"misordered"``.
    """
    prev_pos = -1
    for pattern, label in LIFECYCLE_KEYWORDS:
        m = pattern.search(normalized)
        if not m:
            return ("missing", label)
        if prev_pos >= 0 and m.start() <= prev_pos:
            return ("misordered", label)
        prev_pos = m.start()
    return None


def _check_contradiction(normalized: str) -> bool:
    """Return True if a lifecycle contradiction is detected."""
    return bool(CONTRADICTION_RE.search(normalized))


def _run_rules(prompt: str, task_id: str = "") -> list[RuleResult]:
    """Execute all prompt-level rules and return uniform results."""
    normalized = _normalize(prompt)
    results: list[RuleResult] = []

    tag = f"Task {task_id}: " if task_id else ""

    for section in REQUIRED_SECTIONS:
        if section not in normalized:
            results.append(RuleResult(
                rule="prompt-section-missing",
                severity=Severity.ERROR,
                message=f"{tag}missing section '{section}'",
            ))

    if REQUIRED_PREFIX not in normalized:
        results.append(RuleResult(
            rule="prompt-prefix",
            severity=Severity.WARNING,
            message=f"{tag}missing prefix 'Implement the task for spec...'",
        ))

    violation = _check_lifecycle_order(normalized)
    if violation:
        rule_kind, label = violation
        if rule_kind == "missing":
            results.append(RuleResult(
                rule="lifecycle-missing",
                severity=Severity.WARNING,
                message=f"{tag}MISSING — {label}",
            ))
        else:
            results.append(RuleResult(
                rule="lifecycle-order",
                severity=Severity.WARNING,
                message=f"{tag}MISORDERED — {label} appears before previous step",
            ))

    if _check_contradiction(normalized):
        results.append(RuleResult(
            rule="contradiction",
            severity=Severity.WARNING,
            message=f"{tag}CONTRADICTION detected",
        ))

    return results


def validate(tasks: list[dict], content: str) -> dict[str, list[dict]]:
    """Validate parsed tasks against the canonical rule set.

    Returns ``{"errors": [...], "warnings": [...]}`` with per-rule dicts.
    """
    errors: list[dict] = []
    warnings: list[dict] = []

    _validate_checkbox_format(content, errors)

    for task in tasks:
        task_id = task.get("id", "?")
        if is_header(task):
            continue
        prompt_text = _extract_prompt(task)

        if not prompt_text and task.get("status") != COMPLETED_STATUS:
            errors.append({"rule": "prompt-missing", "task": task_id, "message": f"Task {task_id}: no _Prompt field found", "severity": "error"})
            continue

        if prompt_text:
            for r in _run_rules(prompt_text, task_id):
                entry = {"rule": r.rule, "task": task_id, "message": r.message, "severity": r.severity}
                if r.severity == "error":
                    errors.append(entry)
                else:
                    warnings.append(entry)

    return {"errors": errors, "warnings": warnings}


def validate_single_prompt(prompt_text: str) -> list[str]:
    """Validate a single _Prompt field, returning a flat list of human-readable issue strings."""
    return [r.message for r in _run_rules(prompt_text)]


def validate_prompt_format(prompt: str) -> list[dict]:
    """Check that all required sections are present in the prompt."""
    return [
        {"rule": r.rule, "message": r.message}
        for r in _run_rules(prompt) if r.rule == "prompt-section-missing"
    ]


def _filter_task_rules(tasks: list[dict], rule_names: set[str]) -> list[dict]:
    """Collect issues from _run_rules across all tasks, filtered by rule name.

    Each issue dict carries the originating ``rule`` so callers can
    distinguish between the variants that share a filter set
    (e.g. ``lifecycle-missing`` vs ``lifecycle-order``).
    """
    issues: list[dict] = []
    for task in tasks:
        prompt = task.get("metadata", {}).get("Prompt", "")
        if not prompt:
            continue
        for r in _run_rules(prompt, task["id"]):
            if r.rule in rule_names:
                issues.append({"task": task["id"], "rule": r.rule, "message": r.message})
    return issues


def validate_lifecycle_ordering(tasks: list[dict]) -> list[dict]:
    """Check lifecycle keyword ordering across all tasks' prompts."""
    return _filter_task_rules(tasks, {"lifecycle-missing", "lifecycle-order"})


def detect_contradictions(tasks: list[dict]) -> list[dict]:
    """Detect lifecycle contradictions in task prompts."""
    return _filter_task_rules(tasks, {"contradiction"})


def _validate_checkbox_format(content: str, errors: list[dict]) -> None:
    for line in content.splitlines():
        if re.match(r"^\s*\*\s*\[.\]", line):
            errors.append({"rule": "checkbox-format", "message": f"Asterisk checkbox not allowed (use dash): {line.strip()}", "severity": "error"})


def _extract_prompt(task: dict) -> str:
    """Return the task's `_Prompt:` text, preferring the parsed ``lines`` source.

    Resolution order:
      1. Scan ``task["lines"]`` for the ``_Prompt:`` marker and concatenate
         continuation lines until the next ``- _<key>:`` marker. This handles
         multi-line prompts that the ``parse_tasks`` step left embedded in raw
         markdown rather than collapsing into ``metadata``.
      2. Fall back to the pre-collapsed ``metadata.Prompt`` value when the
         lines source does not contain a marker (e.g. callers that build
         tasks programmatically with only ``metadata`` populated).
    """
    for i, line in enumerate(task.get("lines", [])):
        pm = PROMPT_RE.search(line)
        if pm:
            parts = [pm.group(1)]
            for cont in task.get("lines", [])[i + 1:]:
                if re.match(r"^\s*-\s*_\w+:", cont):
                    break
                parts.append(cont.strip())
            return " ".join(parts)
    return task.get("metadata", {}).get("Prompt", "")
