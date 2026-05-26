"""Agent-facing health advisories.

``workspace/check-health.py`` reports check results with
``status: pass|warn|fail``. Advisories wrap the ``warn``-tier entries
into an agent-ergonomic shape that includes:

* a single-line, self-contained ``banner`` for verbatim echo,
* an ``action_required`` boolean the agent keys off,
* a ``next_action_command`` — the exact shim command when applicable.

Concise output: the banner is one line with no placeholder tokens so
the agent can echo it byte-for-byte without paraphrasing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal

__all__ = [
    "Advisory",
    "ROOT_CAUSE_KINDS",
    "RootCauseKind",
    "collect_warn",
    "make_banner",
    "diff_advisories",
    "auto_fix_command",
]


RootCauseKind = Literal["in_doc", "external_state", "cross_doc", "criteria_dispute"]
ROOT_CAUSE_KINDS: frozenset[str] = frozenset(
    {"in_doc", "external_state", "cross_doc", "criteria_dispute"}
)


@dataclass(frozen=True)
class Advisory:
    """One ``warn``-tier advisory.

    ``action_required`` is the literal boolean the agent reads to decide
    whether to surface the advisory to the user. ``banner`` is
    self-contained — no placeholder tokens, one line. ``cleared``
    indicates a prior advisory has been resolved by ``--auto-fix``;
    ``fix_error`` carries the reason when an automatic fix was
    attempted and failed — explicit fields prevent re-surfacing the
    same banner after auto-fix.

    ``user_echo_required`` is the explicit dataclass field the
    ``AdvisoryEchoPrecondition`` reads to decide whether the banner
    must be echoed verbatim to the user before the agent continues.
    Defaults to ``action_required`` — if the advisory expects the user
    to act, they need to see the banner.
    """

    name: str
    detail: str
    action_required: bool = False
    next_action_command: str | None = None
    cleared: bool = False
    fix_error: str | None = None
    user_echo_required: "bool | None" = None
    extra: dict = field(default_factory=dict)
    prerequisite_action_command: str | None = None
    prerequisite_required: bool = False
    session_id: str | None = None
    root_cause_kind: "RootCauseKind | None" = None

    def to_banner(self) -> str:
        if self.cleared:
            tag = "Cleared"
        elif self.fix_error:
            tag = "Fix failed"
        elif self.action_required:
            tag = "ACTION REQUIRED"
        else:
            tag = "Advisory"
        return f"[{tag}] {self.name}: {self.detail}"

    def to_payload(self) -> dict:
        payload: dict = {
            "name": self.name,
            "detail": self.detail,
            "action_required": self.action_required,
            "banner": self.to_banner(),
            "user_echo_required": self.requires_user_echo(),
        }
        if self.next_action_command:
            payload["next_action_command"] = self.next_action_command
        if self.cleared:
            payload["cleared"] = True
        if self.fix_error:
            payload["fix_error"] = self.fix_error
        if self.extra:
            payload["extra"] = self.extra
        if self.prerequisite_action_command:
            payload["prerequisite_action_command"] = self.prerequisite_action_command
        if self.prerequisite_required:
            payload["prerequisite_required"] = True
        if self.session_id:
            payload["session_id"] = self.session_id
        if self.root_cause_kind:
            payload["root_cause_kind"] = self.root_cause_kind
        return payload

    @classmethod
    def from_dict(cls, raw: "dict | None") -> "Advisory | None":
        """Reconstruct an :class:`Advisory` from a serialized payload.

        Tolerant of partial payloads — missing fields default per the
        dataclass. Returns ``None`` when ``raw`` is not a mapping or
        omits the required ``name`` field so callers can drop bad rows.
        """
        if not isinstance(raw, dict):
            return None
        name = raw.get("name")
        if not isinstance(name, str) or not name:
            return None
        extra = raw.get("extra")
        kind = raw.get("root_cause_kind")
        if isinstance(kind, str) and kind not in ROOT_CAUSE_KINDS:
            kind = None
        return cls(
            name=name,
            detail=str(raw.get("detail") or ""),
            action_required=bool(raw.get("action_required", False)),
            next_action_command=(
                str(raw["next_action_command"])
                if raw.get("next_action_command")
                else None
            ),
            cleared=bool(raw.get("cleared", False)),
            fix_error=(
                str(raw["fix_error"]) if raw.get("fix_error") else None
            ),
            user_echo_required=(
                bool(raw["user_echo_required"])
                if raw.get("user_echo_required") is not None
                else None
            ),
            extra=dict(extra) if isinstance(extra, dict) else {},
            prerequisite_action_command=(
                str(raw["prerequisite_action_command"])
                if raw.get("prerequisite_action_command")
                else None
            ),
            prerequisite_required=bool(raw.get("prerequisite_required", False)),
            session_id=(
                str(raw["session_id"]) if raw.get("session_id") else None
            ),
            root_cause_kind=kind if isinstance(kind, str) else None,
        )

    def requires_user_echo(self) -> bool:
        """Return whether the banner must be echoed verbatim to the user.

        Defaults to ``action_required`` when :attr:`user_echo_required`
        is ``None`` (the common case). Cleared / auto-fixed advisories
        never require echo.
        """
        if self.cleared:
            return False
        if self.user_echo_required is None:
            return self.action_required
        return bool(self.user_echo_required)


_FIXABLE_CHECK_NAMES: frozenset[str] = frozenset(
    {
        "sdd_shim_present",
        "runner_shim_version",
        "templates_present",
    }
)


def _is_fixable(name: str, detail: str) -> bool:
    """Decide whether an advisory advertises the auto-fix shim.

    Default list is additive — checks flagged as ``warn`` with names the
    workspace autofix loop knows how to repair get ``action_required``
    true. Anything else gets surfaced informationally.
    """
    if name in _FIXABLE_CHECK_NAMES:
        return True
    if "run with --auto-fix" in detail.lower():
        return True
    if "shim missing" in detail.lower():
        return True
    return False


def auto_fix_command() -> str:
    """Return the canonical auto-fix shim command."""
    return ".spec-workflow/sdd workspace/ensure-healthy.py --auto-fix --workspace ."


def collect_warn(checks: Iterable[dict]) -> list[Advisory]:
    """Return one :class:`Advisory` per ``warn``-tier check.

    Accepts either the ``checks`` list produced by ``check-health.py``
    (dicts with ``name`` / ``status`` / ``detail``) or the richer
    structures emitted by future sources — any dict with ``status:
    "warn"`` qualifies. When a check supplies its own
    ``next_action_command`` (e.g. the deferred-tool preload advisory),
    that literal wins over the default workspace auto-fix shim.

    Dedups on ``(name, next_action_command)`` so two checks that
    surface the same condition (e.g. deferred-tool preload and the
    dedicated harness-state consistency check) never double-print the
    banner on ``--detect-only``.
    """
    advisories: list[Advisory] = []
    seen_pairs: set[tuple[str, str | None]] = set()
    for check in checks or []:
        if not isinstance(check, dict):
            continue
        if check.get("status") != "warn":
            continue
        name = check.get("name", "unknown")
        detail = check.get("detail") or check.get("message") or ""
        explicit_cmd = check.get("next_action_command")
        if explicit_cmd:
            action_required = True
            next_cmd = str(explicit_cmd)
        else:
            action_required = _is_fixable(name, detail)
            next_cmd = auto_fix_command() if action_required else None
        key = (str(name), next_cmd)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        extra = check.get("extra")
        extra_payload = dict(extra) if isinstance(extra, dict) else {}
        prereq_cmd = check.get("prerequisite_action_command")
        prereq_required = bool(check.get("prerequisite_required", False))
        kind = check.get("root_cause_kind")
        if isinstance(kind, str) and kind not in ROOT_CAUSE_KINDS:
            kind = None
        advisories.append(
            Advisory(
                name=name,
                detail=str(detail) or "advisory",
                action_required=action_required,
                next_action_command=next_cmd,
                extra=extra_payload,
                prerequisite_action_command=(
                    str(prereq_cmd) if prereq_cmd else None
                ),
                prerequisite_required=prereq_required,
                root_cause_kind=kind if isinstance(kind, str) else None,
            )
        )
    return advisories


def make_banner(advisories: Iterable[Advisory]) -> str:
    """Collapse advisories into a single multi-line banner for verbatim echo."""
    return "\n".join(a.to_banner() for a in advisories)


def _index_checks(checks: Iterable[dict]) -> dict[str, dict]:
    return {c.get("name", ""): c for c in (checks or []) if isinstance(c, dict)}


def diff_advisories(
    previous: Iterable[dict],
    current: Iterable[dict],
) -> list[Advisory]:
    """Compute post-``--auto-fix`` advisories.

    ``previous`` is the pre-autofix ``checks`` list, ``current`` the
    post-autofix one. The returned list contains:

    * every current ``warn`` check (unchanged from :func:`collect_warn`),
    * plus one ``cleared=True`` advisory for each name that was ``warn``
      previously and is now ``pass`` (an auto-fix actually landed),
    * plus one ``fix_error=...`` advisory for each name that was ``warn``
      previously and remains ``warn`` or ``fail`` with a ``detail``
      that indicates a fix was attempted (``still_failing``/``repaired``
      context carried by :mod:`sdd_core.workspace_health_checks`).

    All returned advisories have ``action_required=False`` for the
    cleared/fix_error variants so the agent does not surface the banner
    as a repair prompt.
    """
    prev_index = _index_checks(previous)
    cur_index = _index_checks(current)

    advisories: list[Advisory] = list(collect_warn(current))

    for name, prev_check in prev_index.items():
        if prev_check.get("status") != "warn":
            continue
        cur = cur_index.get(name)
        if cur is None:
            continue
        if cur.get("status") == "pass":
            advisories.append(
                Advisory(
                    name=name,
                    detail=str(prev_check.get("detail") or "resolved"),
                    action_required=False,
                    cleared=True,
                )
            )
        elif cur.get("status") in ("warn", "fail"):
            # Heuristic: if the fix ran but didn't land, the current
            # check reports either ``still_failing`` entries (auto_fix
            # loop attempted repair) or its ``detail`` contains an
            # error message. Surface that literal to the agent.
            reason = cur.get("detail") or ""
            still_failing = cur.get("still_failing") or []
            if still_failing:
                try:
                    reason = str(still_failing[0].get("detail", ""))
                except (AttributeError, IndexError):
                    reason = "repair did not clear the advisory"
            if _is_fixable(name, prev_check.get("detail") or "") and reason:
                advisories.append(
                    Advisory(
                        name=name,
                        detail=str(prev_check.get("detail") or "fix attempted"),
                        action_required=False,
                        fix_error=str(reason),
                    )
                )
    return _dedup_by_name(advisories)


def _dedup_by_name(advisories: list[Advisory]) -> list[Advisory]:
    """Collapse duplicate names — prefer the resolved state per envelope.

    Preference order: ``cleared`` (auto-fix landed) > ``fix_error``
    (auto-fix attempted) > active ``action_required`` > anything else.
    Mirrors the agent-perception rule: each advisory name appears at
    most once per envelope, reflecting the final post-loop state.
    """
    def _rank(a: Advisory) -> int:
        if a.cleared:
            return 3
        if a.fix_error:
            return 2
        if a.action_required:
            return 1
        return 0

    by_name: dict[str, Advisory] = {}
    for adv in advisories:
        existing = by_name.get(adv.name)
        if existing is None or _rank(adv) > _rank(existing):
            by_name[adv.name] = adv
    seen: set[str] = set()
    out: list[Advisory] = []
    for adv in advisories:
        chosen = by_name[adv.name]
        if adv is not chosen or adv.name in seen:
            continue
        seen.add(adv.name)
        out.append(adv)
    return out
