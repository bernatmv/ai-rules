"""Structured output formatting for all scripts."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Literal, NoReturn, TypedDict, Union

__all__ = [
    "StdoutResponse",
    "SuccessResponse",
    "ResultResponse",
    "PreflightResponse",
    "ErrorResponse",
    "ResponseEnvelope",
    "VALID_STDOUT_STATUSES",
    "VALID_STDERR_STATUSES",
    "VALID_OUTPUT_STATUSES",
    "STDOUT_REQUIRED_FIELDS",
    "STDERR_REQUIRED_FIELDS",
    "success",
    "error",
    "result",
    "miss",
    "partial",
    "preflight_required",
    "recoverable_miss",
    "warn",
    "advisory",
    "info",
    "envelope_status_for",
    "OUTCOME_TO_STATUS",
    "atomic_write_json",
    "append_jsonl",
    "safe_read_json",
    "safe_open",
    "_dry_run_active",
]


class StdoutResponse(TypedDict):
    """Shared shape for both "ok" and "result" envelopes on stdout.

    "ok" is for completed operations (always exit 0).
    "result" carries structured data that may accompany any exit code
    (e.g. a "skipped" result at exit 0, or partial data at exit 1).

    Use :class:`SuccessResponse` or :class:`ResultResponse` in type
    annotations when the specific status is required for narrowing.
    """
    status: str
    data: dict[str, Any]
    message: str


class SuccessResponse(StdoutResponse):
    """Envelope returned by :func:`success` — ``status`` is always ``"ok"``."""
    status: Literal["ok"]


class ResultResponse(StdoutResponse):
    """Envelope returned by :func:`result` — ``status`` is always ``"result"``."""
    status: Literal["result"]


class PreflightResponse(ResultResponse, total=False):
    """Envelope returned by :func:`preflight_required`."""
    next_action_command: str
    next_action_command_note: str
    error: str
    hint: str


class ErrorResponse(TypedDict, total=False):
    status: Literal["error"]
    error: str
    hint: str
    context: str
    next_action_command: str
    # Structured recovery hints for argparse / validation failures.
    # ``kind`` classifies the error; ``did_you_mean`` ranks alternatives;
    # ``available_flags`` enumerates every option the failing parser
    # accepts so the agent can self-correct without consulting --help.
    kind: str
    did_you_mean: list
    available_flags: list


ResponseEnvelope = Union[StdoutResponse, PreflightResponse, ErrorResponse]

OUTCOME_TO_STATUS: dict[str, str] = {
    "ok": "ok",
    "miss": "result",
    "partial": "result",
    "preflight_required": "result",
    "blocked": "result",
}


def envelope_status_for(outcome: str) -> str:
    """Map ``data.outcome`` → top-level envelope ``status``.

    Single source of truth so a partial outcome can never appear under
    a top-level "ok" envelope. Unknown outcomes default to "result" so
    callers do not falsely succeed on undeclared values.
    """
    return OUTCOME_TO_STATUS.get(outcome, "result")


VALID_STDOUT_STATUSES: frozenset[str] = frozenset({"ok", "result"})
VALID_STDERR_STATUSES: frozenset[str] = frozenset({"error"})
VALID_OUTPUT_STATUSES: frozenset[str] = VALID_STDOUT_STATUSES | VALID_STDERR_STATUSES

STDOUT_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "ok": ("data", "message"),
    "result": ("data", "message"),
}
STDERR_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "error": ("error",),
}


def _emit_stdout(
    status: str,
    payload: dict,
    message: str,
    exit_code: int,
    *,
    extras: "dict[str, Any] | None" = None,
) -> NoReturn:
    """Print a JSON stdout envelope and exit.

    ``extras`` carries optional fields (``handoffs``, ``ctx``,
    ``resolved_from``) that ride alongside the canonical
    ``status`` / ``data`` / ``message`` envelope. Each extra is only
    emitted when populated so existing parsers see a byte-identical
    payload.
    """
    response: dict[str, Any] = {
        "status": status,
        "data": payload,
        "message": message,
    }
    if extras:
        response.update(extras)
    print(json.dumps(response, indent=2))
    sys.exit(exit_code)


def _envelope_extras(
    *,
    handoffs: "list[dict] | None",
    ctx: "Any | None",
    resolved_from: "dict[str, str] | None",
) -> "dict[str, Any]":
    """Collect optional envelope fields, omitting empty ones.

    ``ctx`` accepts a dict or any object exposing ``to_dict()`` —
    unknown shapes raise :class:`TypeError` so callers cannot smuggle
    arbitrary state into the envelope.
    """
    extras: dict[str, Any] = {}
    if handoffs:
        extras["handoffs"] = list(handoffs)
    if ctx is not None:
        if hasattr(ctx, "to_dict"):
            extras["ctx"] = ctx.to_dict()
        elif isinstance(ctx, dict):
            extras["ctx"] = dict(ctx)
        else:
            raise TypeError(
                f"ctx must be a dict or expose to_dict(); got {type(ctx).__name__}"
            )
    if resolved_from:
        extras["resolved_from"] = dict(resolved_from)
    return extras


def success(
    payload: dict,
    message: str = "",
    *,
    handoffs: "list[dict] | None" = None,
    ctx: "Any | None" = None,
    resolved_from: "dict[str, str] | None" = None,
) -> NoReturn:
    """Print JSON envelope to stdout and exit 0.

    ``handoffs`` lists next-action commands the agent should run after
    the success. ``ctx`` carries the resolved
    :class:`sdd_core.context.WorkflowContext`. ``resolved_from`` maps
    each context field to the resolver layer that produced it.
    """
    _emit_stdout(
        "ok", payload, message, 0,
        extras=_envelope_extras(
            handoffs=handoffs, ctx=ctx, resolved_from=resolved_from,
        ),
    )


def result(payload: dict, message: str = "", *, exit_code: int = 0) -> NoReturn:
    """Print JSON result envelope to stdout and exit with given code.

    Unlike ``success()`` (always status "ok", always exit 0), this function
    lets callers embed structured data at any exit code.
    """
    _emit_stdout("result", payload, message, exit_code)


def miss(
    payload: dict,
    message: str = "",
    *,
    next_action_command: str = "",
    hint: str = "",
) -> NoReturn:
    """Search returned zero rows — exit 0 with ``data.outcome="miss"``.

    Use whenever a query/listing comes back empty: the call succeeded,
    there were just no results. Keeps callers out of the parallel-batch
    cancel cascade that exit-1 would trigger.

    ``next_action_command`` and ``hint`` ride at the top level of the
    envelope so the agent finds the recovery shim in the same slot the
    other recoverable-class envelopes use.
    """
    payload = dict(payload)
    payload.setdefault("outcome", "miss")
    response: dict[str, Any] = {
        "status": "result",
        "data": payload,
        "message": message,
    }
    if next_action_command:
        response["next_action_command"] = next_action_command
    if hint:
        response["hint"] = hint
    print(json.dumps(response, indent=2))
    sys.exit(0)


def partial(payload: dict, message: str = "") -> NoReturn:
    """Checker found N>0 issues — exit 0 with ``data.outcome="partial"``.

    Rating / counts travel inside ``payload``. Reserve ``error`` for
    user-fatal outcomes; partial coverage is structured data, not a
    failure.
    """
    payload = dict(payload)
    payload.setdefault("outcome", "partial")
    _emit_stdout("result", payload, message, 0)


def preflight_required(
    payload: dict,
    message: str = "",
    *,
    next_action_command: str,
    hint: str = "",
    error: str = "",
    next_action_command_note: str = "",
    handoffs: "list[dict] | None" = None,
    ctx: "Any | None" = None,
    resolved_from: "dict[str, str] | None" = None,
) -> NoReturn:
    """H1-style preflight gate — exit 0 with the retry shim in-band.

    Preserves the top-level ``error`` / ``hint`` / ``next_action_command``
    keys that existing readers (agent harnesses, retry envelopes) expect,
    while flipping the exit code to 0 so the gate stops cancelling
    parallel-batch siblings.

    ``next_action_command_note`` documents inline what the named command
    actually does — the agent does not have to peek at the script's
    docstring to learn that one command performs two side effects.

    Optional ``handoffs`` / ``ctx`` / ``resolved_from`` mirror the
    :func:`success` envelope so retry shims can carry next-action
    handoff suggestions and resolved-context provenance alongside the
    preflight payload.
    """
    payload = dict(payload)
    payload.setdefault("outcome", "preflight_required")
    response: dict[str, Any] = {
        "status": "result",
        "data": payload,
        "message": message,
        "next_action_command": next_action_command,
    }
    if next_action_command_note:
        response["next_action_command_note"] = next_action_command_note
    if hint:
        response["hint"] = hint
    if error:
        response["error"] = error
    response.update(
        _envelope_extras(
            handoffs=handoffs, ctx=ctx, resolved_from=resolved_from,
        )
    )
    print(json.dumps(response, indent=2))
    sys.exit(0)


def recoverable_miss(
    payload: "dict | None" = None,
    message: str = "",
    *,
    next_action_command_sequence: str,
    problems: "list[str] | None" = None,
    hint: str = "",
    handoffs: "list[dict] | None" = None,
    ctx: "Any | None" = None,
    resolved_from: "dict[str, str] | None" = None,
) -> NoReturn:
    """The single constructor for the *recoverable miss* artifact role.

    Use whenever a phase produces a recoverable failure carrying a
    literal recovery command sequence — argparse-style validation
    misses, missing-precondition gates, etc. The contract is that any
    envelope carrying ``next_action_command_sequence`` must be
    ``result``-class (exit 0, status="result"), so the agent treats
    the failure as recoverable and runs the sequence rather than
    surfacing a Python traceback.

    Maps to top-level ``status="result"`` with ``data.outcome=
    "preflight_required"`` (existing readers) and adds the recovery
    sequence both at the top-level (``next_action_command`` slot) and
    inside ``data.next_action_command_sequence`` so new readers find
    the canonical chain in one place.
    """
    if not next_action_command_sequence:
        raise TypeError(
            "recoverable_miss requires a non-empty next_action_command_sequence"
        )
    payload_dict: dict[str, Any] = dict(payload or {})
    payload_dict["next_action_command_sequence"] = next_action_command_sequence
    if problems:
        payload_dict["problems"] = list(problems)
    preflight_required(
        payload_dict,
        message,
        next_action_command=next_action_command_sequence,
        hint=hint or _default_recovery_hint(problems),
        handoffs=handoffs,
        ctx=ctx,
        resolved_from=resolved_from,
    )


def _default_recovery_hint(problems: "list[str] | None") -> str:
    """Build the operator-facing hint for a recoverable miss.

    Promotes the first entry of *problems* into the hint so log-only
    viewers see the actionable signal without expanding ``data.context``.
    Falls back to the generic instruction when no problems are
    supplied.
    """
    instruction = "Execute next_action_command_sequence, then retry."
    if problems:
        first = str(problems[0]).strip()
        if first:
            return f"{first} — execute next_action_command_sequence, then retry."
    return instruction


def error(
    message: str,
    hint: str = "",
    context: str = "",
    exit_code: int = 1,
    *,
    next_action_command: str = "",
    kind: str = "",
    did_you_mean: "list[str] | None" = None,
    available_flags: "list[str] | None" = None,
) -> NoReturn:
    """Print structured error envelope to stderr and exit with exit_code.

    ``next_action_command`` is the "solve, don't punt" field: when the
    caller knows the exact shim command to run for recovery, emit it
    verbatim so the agent doesn't reconstruct it from prose. Absent —
    the lint in ``internal_lints/error_envelopes.py`` flags the call
    unless a ``hint=`` or ``# noqa: solve-dont-punt`` suppression is
    present.

    Optional fields: ``kind`` classifies the error (``"unknown_flag"``,
    ``"missing_value"``, ``"invalid_value"``); ``did_you_mean`` is a
    ranked list of alternatives; ``available_flags`` enumerates the
    option strings the failing parser accepts.
    """
    response: ErrorResponse = {
        "status": "error", "error": message,
        "hint": hint, "context": context,
    }
    if next_action_command:
        response["next_action_command"] = next_action_command
    if kind:
        response["kind"] = kind
    if did_you_mean is not None:
        response["did_you_mean"] = list(did_you_mean)
    if available_flags is not None:
        response["available_flags"] = list(available_flags)
    print(json.dumps(response), file=sys.stderr)
    sys.exit(exit_code)


def warn(message: str) -> None:
    """Print warning to stderr without exiting."""
    print(f"WARNING: {message}", file=sys.stderr)


def advisory(message: str, *, level: str = "warn", code: str = "") -> dict:
    """Return an advisory entry the caller appends to ``data.advisories[]``.

    Use instead of :func:`warn` whenever the script is on its success
    path — keeps stderr empty so ``2>&1 | jq`` chaining stays
    parseable. ``level`` defaults to ``"warn"``; ``code`` is optional
    for machine-routing.
    """
    entry: dict = {"level": level, "message": message}
    if code:
        entry["code"] = code
    return entry


def info(message: str) -> None:
    """Print diagnostic message to stderr without exiting."""
    print(message, file=sys.stderr)


def _verify_json_key(path: str, key: str, expected: Any) -> None:
    """Read back a JSON file and verify a single key matches the expected value."""
    with open(path) as f:
        written = json.load(f)
    if written.get(key) != expected:
        raise IOError(
            f"Write verification failed for {path}: "
            f"expected {key}={expected!r}"
        )


#: Env-var gate honoured by every persistence helper in this module.
#: ``pipeline-tick.py --dry-run`` sets this in the subprocess
#: environment so phase handlers run their real compute path and emit
#: byte-identical envelopes without mutating disk state. Keeping the
#: gate at the write boundary — rather than threading a flag through
#: every handler — keeps the envelope as the one source of truth;
#: only the atomic-replace step differs between live and dry-run.
from sdd_core.security.constants import DRY_RUN_ENV as _DRY_RUN_ENV_VAR  # noqa: E402
from sdd_core.security.constants import TRUTHY_ENV_VALUES as _TRUTHY_ENV_VALUES  # noqa: E402


def _dry_run_active() -> bool:
    """Return True when the current process is in pipeline dry-run mode.

    Truthy values: ``1``, ``true`` (case-insensitive). Anything else —
    including the variable being unset — means writes proceed normally.
    """
    raw = os.environ.get(_DRY_RUN_ENV_VAR, "")
    return raw.strip().lower() in _TRUTHY_ENV_VALUES


def atomic_write_json(
    path: str, content: dict, verify_key: "str | None" = None,
) -> None:
    """Write JSON atomically with optional read-back verification.

    Public API preserved — delegates to
    :func:`sdd_core.security.state.atomic_write_text` so the single
    durable-write primitive owns unique temp files, ``fsync``, and
    orphan cleanup. Dry-run short-circuit is honoured inside
    :func:`atomic_write_text`; the post-write verification is skipped
    in dry-run because nothing was written.

    Raises :class:`IOError` on verification failure.
    """
    from sdd_core.security.state import atomic_write_text
    target = Path(path)
    atomic_write_text(target, json.dumps(content, indent=2) + "\n")
    if _dry_run_active():
        return
    if verify_key is not None:
        _verify_json_key(path, verify_key, content.get(verify_key))


def append_jsonl(path: str, entry: dict) -> None:
    """Append one JSON object line, honouring the global dry-run gate."""
    if _dry_run_active():
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def safe_read_json(path: str | Path, default: Any = None) -> Any:
    """Read and parse a JSON file. Return default if file is missing.

    Raises ValueError on malformed JSON (unlike missing file which returns default).
    """
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e


def safe_open(filepath: str, mode: str = "r"):
    """Open a file with consistent error handling for CLI scripts.

    Emits a structured ``output.error`` and exits on missing file or
    permission error, so callers don't need to catch these uniformly.
    """
    try:
        return open(filepath, mode)
    except FileNotFoundError:
        error(f"File not found: {filepath}")
    except PermissionError:
        error(f"Permission denied: {filepath}", exit_code=2)
