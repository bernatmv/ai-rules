"""Prompt registry loader and renderer for SDD skills.

Loads prompt definitions from prompt-registry.json, validates parameters,
and renders prompts in JSON (AskQuestion) or markdown format.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from dataclasses import dataclass, replace
from typing import Any, Callable

__all__ = [
    "load_registry", "list_prompts", "render_prompt",
    "render_prompt_for_harness",
    "render_prompt_for_envelope",
    "registry_entry_sha256",
    "PromptParamError",
    "MAX_PROMPT_OPTIONS",
    "MIN_PROMPT_OPTIONS",
    "render_pipeline_instruction",
    "PIPELINE_INSTRUCTION_PENDING", "PIPELINE_INSTRUCTION_CLEAR",
    "require_fix_decision", "is_contradictory_feedback", "AFFIRM_WORDS",
    "SUB_AGENT_ECHO_INSTRUCTION", "SUB_AGENT_ECHO_INSTRUCTION_VERSION",
    "build_sub_agent_echo_instruction",
    "substitute_sub_agent_echo_placeholders",
    "sub_agent_echo_instruction_sha256",
    "SUB_AGENT_TWO_STATUS_CONTRACT",
    "SUB_AGENT_ONE_STATUS_CONTRACT",
    "status_contract_for_scope",
    "PROMPT_TYPE_REDIRECTS",
    "prompt_type_redirect",
]


# Canonical bounds for ``PromptSpec.options`` — the Claude Code
# AskUserQuestion schema rejects >4 options. The Cursor AskQuestion
# tool imposes a softer limit but identical UX collapses past 4.
# Single literal, single source of truth.
MAX_PROMPT_OPTIONS = 4
MIN_PROMPT_OPTIONS = 2

# Registry-entry / payload-envelope keys. Module-level constants so the
# renderer and the adapter share one vocabulary.
FORMAT_KEY = "format"
FORCE_MARKDOWN_KEY = "force_markdown"
ADAPTER_FORMAT_MARKDOWN = "markdown"


# Registered prompt-registry keys for the two pipeline-instruction
# entries. Exported so phase modules reference the registry by
# symbolic name rather than string-duplicating the key at every call
# site — the single source of truth for the key names sits here.
PIPELINE_INSTRUCTION_PENDING = "pipeline-instruction-pending"
PIPELINE_INSTRUCTION_CLEAR = "pipeline-instruction-clear"


# Sub-agent echo directive. ``build_sub_agent_echo_instruction``
# appends a ``reference_read_sha256`` line per ``required_reference_reads``
# entry; callers without reads receive the bare prompt-hash directive.
SUB_AGENT_TWO_STATUS_CONTRACT = (
    "Return two distinct status fields in your reply:\n"
    "- Reviewed-docs status (drives fix-loop routing): PASS / NEEDS_WORK / "
    "FAIL computed over the docs you examined in this gate.\n"
    "- Artifact completeness (informational): INCOMPLETE when any expected "
    "doc is missing; PASS once every expected doc exists. This never "
    "drives fix-loop routing — the score on reviewed docs wins."
)

# Per-document scope variant — drops the artifact-completeness line
# entirely. In a per-document review, the workspace tracker explicitly
# names the docs in scope; future-doc absence is by-design (those docs
# have their own per-document gates) so the line is pure noise.
SUB_AGENT_ONE_STATUS_CONTRACT = (
    "Return a single status field in your reply:\n"
    "- Reviewed-docs status (drives fix-loop routing): PASS / NEEDS_WORK / "
    "FAIL computed over the docs you examined in this gate."
)


def status_contract_for_scope(scope: str | None) -> str:
    """Return the sub-agent status contract for a given review *scope*.

    ``per-document`` scopes drop the ``Artifact completeness`` line so the
    sub-agent narrative does not lead with ``INCOMPLETE`` for docs that
    are explicitly out of this gate's scope. ``final`` scopes (the
    default) keep the dual line — completeness is meaningful at the
    final gate because every doc must exist. Callers must pass a
    validated scope (one of
    :data:`review_quality.constants.REVIEW_SCOPES`).
    """
    # Deferred import keeps the package-layer rule intact: ``sdd_core``
    # owns no permanent dependency on ``review_quality``.
    from review_quality.constants import SCOPE_PER_DOCUMENT
    if scope == SCOPE_PER_DOCUMENT:
        return SUB_AGENT_ONE_STATUS_CONTRACT
    return SUB_AGENT_TWO_STATUS_CONTRACT


SUB_AGENT_ECHO_INSTRUCTION_VERSION = "v2"
SUB_AGENT_ECHO_INSTRUCTION = (
    "When you reply, include the line "
    "`sub_agent_prompt_sha256: <hex>` where `<hex>` is the value emitted "
    "by --phase launch. This lets --phase post-review verify that the "
    "verbatim prompt was delivered. The hash is checked byte-for-byte "
    "after per-line whitespace normalisation."
)


_REFERENCE_READ_ECHO_DIRECTIVE = (
    "Additionally, when the launch envelope includes `required_reference_reads`, "
    "echo one line per entry: `reference_read_sha256: <name> <hex>` where "
    "<name> matches the `name` field and <hex> matches the `sha256` field for "
    "that entry. This lets --phase post-review verify that the reference files "
    "were read unchanged."
)


def build_sub_agent_echo_instruction(
    reference_reads: "list[dict] | None" = None,
) -> str:
    """Return the echo directive tailored to the current launch envelope.

    When ``reference_reads`` is non-empty we append a second directive
    asking the sub-agent to echo one ``reference_read_sha256`` line per
    entry. Callers without reads receive the bare prompt-hash directive.
    """
    base = SUB_AGENT_ECHO_INSTRUCTION
    names = [
        r.get("name", "") for r in (reference_reads or [])
        if isinstance(r, dict) and r.get("name")
    ]
    if not names:
        return base
    name_list = ", ".join(names)
    return (
        f"{base}\n\n{_REFERENCE_READ_ECHO_DIRECTIVE} "
        f"Expected names: {name_list}."
    )


def sub_agent_echo_instruction_sha256(
    reference_reads: "list[dict] | None" = None,
) -> str:
    """Content hash of the echo instruction — useful for audit artefacts."""
    return hashlib.sha256(
        build_sub_agent_echo_instruction(reference_reads).encode("utf-8"),
    ).hexdigest()


def substitute_sub_agent_echo_placeholders(
    prompt: str,
    *,
    prompt_sha256: str,
    reference_reads: "list[dict] | None" = None,
) -> str:
    """Return *prompt* with `<hex>` and `<name>` placeholders pre-substituted.

    Placeholders are resolved here so the launch envelope can be passed
    to sub-agents byte-for-byte and echoed back verbatim.

    Substitutions:
      * ``sub_agent_prompt_sha256: <hex>`` → the actual digest.
      * ``<hex>`` on the explanatory clause → the digest.
      * ``reference_read_sha256: <name> <hex>`` expands to one concrete
        line per entry; the directive paragraph is preserved.
    """
    if not prompt_sha256:
        return prompt
    # Replace the primary prompt hash marker — a single unambiguous
    # line so sub-agents can locate it without regex.
    updated = prompt.replace(
        "sub_agent_prompt_sha256: <hex>",
        f"sub_agent_prompt_sha256: {prompt_sha256}",
    )
    # Replace the explanatory `<hex>` tokens on the same paragraph so
    # the "this is the value emitted by --phase launch" sentence reads
    # correctly — no remaining `<hex>` literal in the agent-visible
    # prose.
    updated = updated.replace(
        "`<hex>` is the value emitted by",
        f"`{prompt_sha256}` is the value emitted by",
    )

    concrete_lines = []
    for entry in reference_reads or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        sha = entry.get("sha256")
        if not name or not sha:
            continue
        concrete_lines.append(f"reference_read_sha256: {name} {sha}")
    if concrete_lines:
        concrete_block = (
            "Expected echoes (copy these verbatim, one per line):\n"
            + "\n".join(concrete_lines)
            + "\n"
        )
        updated = f"{updated}\n\n{concrete_block}"
    return updated


from .command_templates import build_render_task_prompts_command as _build_render_task_prompts_command  # noqa: E402


_RENDER_TASK_PROMPTS_REDIRECT = {
    "command": _build_render_task_prompts_command(spec_name="{spec_name}"),
    "hint": (
        "The canonical task-prompt scaffolding is not a registry prompt. "
        "Run util/render-task-prompts.py --spec-name {spec_name} to print the "
        "prefix+suffix verbatim, or util/resolve-template.py --type tasks "
        "--spec-name {spec_name} --content to draft tasks.md from scratch."
    ),
}

PROMPT_TYPE_REDIRECTS: dict[str, dict[str, str]] = {
    "task-prompt-suffix": _RENDER_TASK_PROMPTS_REDIRECT,
    "task-prompt-prefix": _RENDER_TASK_PROMPTS_REDIRECT,
    "task-lifecycle-suffix": _RENDER_TASK_PROMPTS_REDIRECT,
}


def prompt_type_redirect(prompt_type: str) -> dict[str, str] | None:
    """Return the redirect hint for a well-known non-registry prompt type.

    Callers use this to surface a literal recovery command when an
    agent guesses at registry keys that are actually owned by a helper
    script (e.g. ``util/render-task-prompts.py``).
    """
    return PROMPT_TYPE_REDIRECTS.get(prompt_type)


class PromptParamError(ValueError):
    """Raised when prompt params are invalid — carries full diagnostic context."""

    def __init__(
        self,
        prompt_type: str,
        missing: list[str],
        unexpected: list[str],
        required: list[str],
    ):
        self.prompt_type = prompt_type
        self.missing = missing
        self.unexpected = unexpected
        self.required = required
        parts = [f"Missing required params for '{prompt_type}': {', '.join(missing)}"]
        if unexpected:
            parts.append(f"Unknown params provided: {', '.join(unexpected)}")
        parts.append(f"Required: {', '.join(required)}")
        super().__init__(". ".join(parts))


from .paths import PROMPT_REGISTRY_FILENAME

_REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", PROMPT_REGISTRY_FILENAME
)

_registry_cache: dict | None = None


def load_registry(path: str | None = None) -> dict:
    """Load and cache the prompt registry."""
    global _registry_cache
    if _registry_cache is not None and path is None:
        return _registry_cache
    target = path or _REGISTRY_PATH
    from sdd_core.output import safe_read_json
    data = safe_read_json(target, default=None)
    if data is None:
        raise FileNotFoundError(f"Prompt registry not found at {target}")
    if path is None:
        _registry_cache = data
    return data


def registry_entry_sha256(
    prompt_type: str, *, registry: dict | None = None,
) -> str:
    """Return a stable SHA-256 of the registry entry for *prompt_type*.

    Hashes the canonical-JSON serialisation of the entry so a downstream
    consumer can detect drift without copying the full structure into
    its envelope. Raises :class:`KeyError` when the type is unknown.
    """
    reg = registry or load_registry()
    prompts = reg.get("prompts", {})
    if prompt_type not in prompts:
        raise KeyError(prompt_type)
    canonical = json.dumps(
        prompts[prompt_type], sort_keys=True, separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def list_prompts(registry: dict | None = None) -> list[dict[str, str]]:
    """Return a list of {type, category, description} for each prompt."""
    reg = registry or load_registry()
    result = []
    for prompt_type, defn in reg["prompts"].items():
        result.append({
            "type": prompt_type,
            "category": defn.get("category", ""),
            "description": defn.get("description", ""),
            "params": defn.get("params", []),
            "optional_params": defn.get("optional_params", []),
        })
    return sorted(result, key=lambda x: (x["category"], x["type"]))


def _substitute(text: str, params: dict[str, str],
                optional_keys: list[str] | None = None) -> str:
    """Replace {key} placeholders. Remove lines with only unfilled optional placeholders."""
    optional_set = set(optional_keys or [])

    def replacer(match):
        key = match.group(1)
        if key in params:
            return params[key]
        if key in optional_set:
            return ""
        return match.group(0)

    result = re.sub(r"\{(\w+)\}", replacer, text)
    if optional_set:
        result = "\n".join(line for line in result.split("\n") if line.strip())
    return result


def _validate_prompt_params(
    prompt_type: str, params: dict[str, str], defn: dict,
) -> None:
    """Raise PromptParamError if required params are missing or unknown params supplied."""
    required_params = defn.get("params", [])
    optional_params_list = defn.get("optional_params", [])
    all_known = set(required_params) | set(optional_params_list)
    missing = [p for p in required_params if p not in params]
    unexpected = [p for p in params if p not in all_known]
    if missing or unexpected:
        raise PromptParamError(prompt_type, missing, unexpected, required_params)


def _prepare_rendered_questions(
    prompt_type: str,
    params: dict[str, str] | None,
    *,
    options: list[dict[str, str]] | None,
    registry: dict | None,
    exclude_options: list[str] | None,
) -> tuple[dict, list[dict]]:
    """Resolve, deep-copy, and render the registry entry.

    Returns ``(defn, questions)`` where ``defn`` is the full registry
    entry (callers that need ``title`` / ``header`` / etc read it) and
    ``questions`` is the post-substitution list. Raises ``KeyError``
    on unknown prompt types and ``PromptParamError`` on missing
    required params — the same contract as the public renderers.
    """
    reg = registry or load_registry()
    prompts = reg.get("prompts", {})
    if prompt_type not in prompts:
        available = ", ".join(sorted(prompts.keys()))
        redirect = prompt_type_redirect(prompt_type)
        if redirect:
            raise KeyError(
                f"'{prompt_type}' is not a registry prompt. {redirect['hint']}"
            )
        raise KeyError(
            f"Unknown prompt type '{prompt_type}'. Available: {available}"
        )
    defn = copy.deepcopy(prompts[prompt_type])
    params = params or {}
    _validate_prompt_params(prompt_type, params, defn)
    optional_params_list = defn.get("optional_params", [])

    questions = defn["questions"]
    for q in questions:
        q["prompt"] = _substitute(q["prompt"], params, optional_params_list)
        if options is not None:
            q["options"] = options
        else:
            for opt in q.get("options", []):
                opt["label"] = _substitute(
                    opt["label"], params, optional_params_list,
                )
        if exclude_options:
            q["options"] = [
                o for o in q.get("options", [])
                if o["id"] not in exclude_options
            ]
    return defn, questions


def render_prompt(
    prompt_type: str,
    params: dict[str, str] | None = None,
    fmt: str = "json",
    options: list[dict[str, str]] | None = None,
    registry: dict | None = None,
    exclude_options: list[str] | None = None,
) -> str:
    """Render a prompt by type ID.

    Args:
        prompt_type: The prompt type ID from the registry.
        params: Key-value pairs to substitute into template placeholders.
        fmt: Output format — "json" (AskQuestion) or "markdown".
        options: Dynamic options list to replace the static options.
        registry: Pre-loaded registry dict (optional).
        exclude_options: Option IDs to filter out (e.g. ["accept"] when docs are stale).

    Returns:
        Formatted prompt string.

    Raises:
        KeyError: If prompt_type is not in the registry.
        PromptParamError: If required params are missing (subclass of ValueError).
        ValueError: If format is invalid.
    """
    if fmt not in ("json", "markdown"):
        raise ValueError(f"Invalid format '{fmt}'. Must be 'json' or 'markdown'.")
    _, questions = _prepare_rendered_questions(
        prompt_type, params,
        options=options, registry=registry, exclude_options=exclude_options,
    )
    if fmt == "json":
        return json.dumps({"questions": questions}, indent=2)
    return _render_markdown(questions)


def render_pipeline_instruction(
    prompt_type: str,
    scenario: str,
    *,
    forward_key: str = "",
    registry: dict | None = None,
) -> str:
    """Render one of the two pipeline-instruction registry entries.

    The two entries (``pipeline-instruction-pending`` and
    ``pipeline-instruction-clear``) carry a ``scenarios`` dict keyed by
    the decision-branch name used by post-review / post-fix
    (``zero_findings``, ``findings``, ``post_fix``).

    ``forward_key`` is substituted into ``{forward_key}`` placeholders
    when present. Scenarios that don't parameterise on forward_key
    (the two zero_findings / findings "clear" strings are fully
    materialised because their next-phase identity is already
    embedded) ignore the argument by virtue of having no placeholder.

    Raises
    ------
    KeyError
        When ``prompt_type`` is not one of the two registered entries,
        or when ``scenario`` is not listed under that entry.
    """
    reg = registry or load_registry()
    prompts = reg.get("prompts", {})
    if prompt_type not in prompts:
        available = ", ".join(sorted(prompts.keys()))
        raise KeyError(
            f"Unknown prompt type '{prompt_type}'. Available: {available}"
        )
    defn = prompts[prompt_type]
    scenarios = defn.get("scenarios") or {}
    if scenario not in scenarios:
        raise KeyError(
            f"Unknown scenario '{scenario}' for '{prompt_type}'. "
            f"Available: {', '.join(sorted(scenarios.keys()))}"
        )
    template = scenarios[scenario]
    return _substitute(template, {"forward_key": forward_key or ""})


_MAX_LETTER_OPTIONS = 26


def _derive_header(entry: dict, prompt_type: str) -> str:
    """Return the 12-char-capped header for harness rendering.

    Uses ``entry["header"]`` when the registry authored one; otherwise
    derives a sensible default from the prompt category (e.g.
    ``approval`` → ``"Approval"``). Callers can override via the
    registry without touching code; the derivation keeps the default
    adapter-safe when the registry hasn't been migrated yet.
    """
    explicit = str(entry.get("header") or "").strip()
    if explicit:
        return explicit[:12]
    category = str(entry.get("category") or "").strip()
    if category:
        title = category.replace("-", " ").replace("_", " ").title()
        return title[:12]
    return prompt_type.replace("-", " ").title()[:12]


def _derive_option_description(option: dict) -> str:
    """Return the ``description`` for an option under harness rendering.

    Prefers the authored ``description`` when the registry carries one;
    otherwise falls back to the label. Fallback exists so prompts
    migrate incrementally without blocking the Claude Code
    ``AskUserQuestion`` schema.
    """
    explicit = str(option.get("description") or "").strip()
    if explicit:
        return explicit
    return str(option.get("label") or "").strip()


def _build_prompt_spec(
    prompt_type: str, defn: dict, questions: list[dict],
):
    """Materialise the registry entry's first question as a ``PromptSpec``.

    Returns ``None`` when the entry forces markdown rendering or when
    the question shape isn't eligible for structured rendering (multi-
    question, option count outside the ``MIN_PROMPT_OPTIONS`` /
    ``MAX_PROMPT_OPTIONS`` band). Shared by
    :func:`render_prompt_for_harness` and :func:`render_prompt_for_envelope`.
    """
    from sdd_core.harness.adapter import PromptOption, PromptSpec

    if defn.get(FORCE_MARKDOWN_KEY) is True:
        return None
    if not _is_ask_user_question_eligible(questions):
        return None

    question = questions[0]
    opts = tuple(
        PromptOption(
            id=str(o.get("id", "")),
            label=str(o.get("label", "")),
            description=_derive_option_description(o),
        )
        for o in question.get("options", [])
    )
    spec = PromptSpec(
        id=str(question.get("id") or prompt_type),
        prompt=str(question.get("prompt") or ""),
        options=opts,
        title=str(defn.get("title") or ""),
        header=_derive_header(defn, prompt_type),
        multi_select=bool(defn.get("multi_select") or False),
    )
    return _enforce_option_bounds(spec)


def render_prompt_for_harness(
    prompt_type: str,
    params: dict[str, str] | None = None,
    *,
    harness_name: str | None = None,
    options: list[dict[str, str]] | None = None,
    registry: dict | None = None,
    exclude_options: list[str] | None = None,
) -> dict:
    """Render a prompt shaped for the active harness adapter.

    Routes through :func:`_build_prompt_spec`; falls back to a Markdown
    payload when the question shape isn't eligible. Keeps one source
    of truth (the prompt registry) and one adapter interface.
    """
    defn, questions = _prepare_rendered_questions(
        prompt_type, params,
        options=options, registry=registry, exclude_options=exclude_options,
    )

    from sdd_core.harness import get_adapter, load_adapter

    adapter = (
        get_adapter(harness_name) if harness_name else load_adapter()
    )

    spec = _build_prompt_spec(prompt_type, defn, questions)
    if spec is None:
        return _markdown_payload(prompt_type, defn, questions)
    return adapter.build_prompt_payload(spec)


def render_prompt_for_envelope(
    prompt_type: str,
    params: dict[str, str] | None = None,
    *,
    options: list[dict[str, str]] | None = None,
    registry: dict | None = None,
    exclude_options: list[str] | None = None,
):
    """Return an un-rendered :class:`PromptSpec` for the given prompt entry.

    Returns ``None`` when the registry entry's question shape isn't
    eligible for structured rendering (force-markdown, multi-question,
    or option count outside the ``MIN_PROMPT_OPTIONS`` /
    ``MAX_PROMPT_OPTIONS`` band).
    """
    defn, questions = _prepare_rendered_questions(
        prompt_type, params,
        options=options, registry=registry, exclude_options=exclude_options,
    )
    return _build_prompt_spec(prompt_type, defn, questions)


def _is_ask_user_question_eligible(questions: list[dict]) -> bool:
    """True when the harness's structured-prompt slot can render *questions*.

    The Claude Code AskUserQuestion schema accepts one question with
    1–``MAX_PROMPT_OPTIONS`` options. Anything else routes through the
    markdown payload so options are never silently truncated.
    """
    if len(questions) != 1:
        return False
    options = questions[0].get("options") or []
    return MIN_PROMPT_OPTIONS <= len(options) <= MAX_PROMPT_OPTIONS


def _markdown_payload(prompt_type: str, defn: dict, questions: list[dict]) -> dict:
    """Wrap a Markdown-rendered prompt in the adapter-shape envelope.

    The renderer routes through this path when the entry sets
    ``force_markdown: true`` or when the rendered question shape does
    not satisfy ``_is_ask_user_question_eligible``.
    """
    body = _render_markdown(questions)
    return {
        FORMAT_KEY: ADAPTER_FORMAT_MARKDOWN,
        "prompt_type": prompt_type,
        "title": str(defn.get("title") or ""),
        "header": _derive_header(defn, prompt_type),
        "body": body,
    }


# Single literal pointing at the author-facing recovery section — both
# option-bound rules cite this so future reference-path rewrites are a
# one-edit affair.
_OPTION_CAP_ADVISORY_POINTER = (
    "$SKILLS/sdd-common/references/prompt-conventions.md \u00a7 Option Cap"
)


@dataclass(frozen=True)
class _OptionBoundRule:
    """One option-sanity rule applied at render time.

    ``applies`` inspects the current spec; ``message`` builds the
    stderr advisory; ``transform`` returns the fixed-up spec. All
    three callables are pure — the orchestrator owns the single side
    effect (``output.info``).
    """

    name: str
    applies: Callable[["PromptSpec"], bool]
    message: Callable[["PromptSpec"], str]
    transform: Callable[["PromptSpec"], "PromptSpec"]


def _overflow_applies(spec: "PromptSpec") -> bool:
    return len(spec.options) > MAX_PROMPT_OPTIONS


def _overflow_message(spec: "PromptSpec") -> str:
    n = len(spec.options)
    dropped = ", ".join(o.id for o in spec.options[MAX_PROMPT_OPTIONS:])
    return (
        f"Prompt {spec.id!r} had {n} options; trimmed to "
        f"{MAX_PROMPT_OPTIONS}. Dropped: {dropped}. "
        f"Edit the registry to fix. See {_OPTION_CAP_ADVISORY_POINTER}."
    )


def _overflow_transform(spec: "PromptSpec") -> "PromptSpec":
    return replace(spec, options=spec.options[:MAX_PROMPT_OPTIONS])


def _underflow_applies(spec: "PromptSpec") -> bool:
    return len(spec.options) < MIN_PROMPT_OPTIONS


def _underflow_message(spec: "PromptSpec") -> str:
    return (
        f"Prompt {spec.id!r} has {len(spec.options)} options; minimum "
        f"is {MIN_PROMPT_OPTIONS}. Edit the registry to fix. "
        f"See {_OPTION_CAP_ADVISORY_POINTER}."
    )


# Order is significant: the first applicable rule wins. Overflow runs
# before underflow because the overflow transform can never produce an
# underflow result (MAX >= MIN, enforced by constants). Extension
# point — add a rule by appending an ``_OptionBoundRule`` entry.
_OPTION_BOUND_RULES: tuple[_OptionBoundRule, ...] = (
    _OptionBoundRule(
        name="overflow",
        applies=_overflow_applies,
        message=_overflow_message,
        transform=_overflow_transform,
    ),
    _OptionBoundRule(
        name="underflow",
        applies=_underflow_applies,
        message=_underflow_message,
        transform=lambda spec: spec,
    ),
)


def _enforce_option_bounds(spec: "PromptSpec") -> "PromptSpec":
    """Apply the first applicable option-sanity rule and return the
    (possibly transformed) spec.

    Never raises; the companion pre-flight check
    ``check_prompt_registry_option_bounds`` surfaces the same drift at
    session start.
    """
    from sdd_core import output

    for rule in _OPTION_BOUND_RULES:
        if rule.applies(spec):
            output.info(rule.message(spec))
            return rule.transform(spec)
    return spec


def _render_markdown(questions: list[dict[str, Any]]) -> str:
    """Render questions as lettered markdown prompt."""
    parts = []
    for q in questions:
        parts.append(f"**Prompt:** {q['prompt']}")
        opts = q.get("options", [])
        use_letters = len(opts) <= _MAX_LETTER_OPTIONS
        for i, opt in enumerate(opts):
            label = chr(ord("a") + i) if use_letters else str(i + 1)
            parts.append(f"> - ({label}) {opt['label']}")
        parts.append("")
    return "\n".join(parts).rstrip()


from .governance import (  # noqa: E402, F401
    require_fix_decision,
    is_contradictory_feedback,
    AFFIRM_WORDS,
)
