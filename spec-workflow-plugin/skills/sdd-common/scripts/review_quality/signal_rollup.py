"""Advisory-signal rollup policy.

Advisory signals (``template_compliance``, ``size_check``,
``cross_validation.status``) previously appeared on the artifact but
did not contribute to ``overall_status``: a FAIL on a Tier 1 check
silently rolled up to ``PASS``. The rollup policy below is consulted
once by :func:`sdd_core.review_quality.scoring.derive_overall_status`
and declared *open for extension* (new signals add themselves via
:func:`register_signal`) and *closed for modification* (the rollup
function never branches on signal name).

Outputs:

- ``PASS`` — score PASS and no advisory signal adverse.
- ``PASS_WITH_ADVISORIES`` — score PASS but one or more advisory
  signals adverse (template_compliance FAIL, size_check WARNING,
  cross_validation.status NEEDS_WORK / FAIL).
- ``NEEDS_WORK`` — any score-band NEEDS_WORK or any ``blocking``
  signal adverse (no blocking signals today; reserved for future use).
- ``FAIL`` — reserved for score FAIL (rollup does not downgrade past
  the score band itself; advisory signals never upgrade a FAIL to PASS).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from sdd_core.review_input import INPUT_KEY_CROSS_VALIDATION

__all__ = [
    "AdvisorySignal",
    "SIGNALS",
    "register_signal",
    "worst_status",
    "is_advisory_adverse",
]


SignalSeverity = Literal["advisory", "blocking"]


@dataclass(frozen=True)
class AdvisorySignal:
    name: str
    severity: SignalSeverity
    extractor: Callable[[dict], bool]


SIGNALS: list[AdvisorySignal] = []


def register_signal(
    factory: Callable[[], AdvisorySignal],
) -> Callable[[], AdvisorySignal]:
    """Decorator: register the :class:`AdvisorySignal` returned by ``factory``.

    Mirrors :func:`sdd_core.harness.detectors.register_detector` so
    detection and rollup share one OCP idiom. Duplicate names raise
    ``ValueError`` at import time.
    """
    signal = factory()
    for existing in SIGNALS:
        if existing.name == signal.name:
            raise ValueError(
                f"Advisory signal {signal.name!r} already registered"
            )
    SIGNALS.append(signal)
    return factory


def _template_compliance_adverse(artifact: dict) -> bool:
    documents = artifact.get("documents") if isinstance(artifact, dict) else None
    if not isinstance(documents, dict):
        return False
    for doc in documents.values():
        if not isinstance(doc, dict):
            continue
        tc = doc.get("template_compliance")
        if isinstance(tc, str) and tc == "FAIL":
            return True
    return False


def _size_check_adverse(artifact: dict) -> bool:
    documents = artifact.get("documents") if isinstance(artifact, dict) else None
    if not isinstance(documents, dict):
        return False
    for doc in documents.values():
        if not isinstance(doc, dict):
            continue
        sc = doc.get("size_check")
        if isinstance(sc, str) and sc in {"FAIL", "WARNING"}:
            return True
    return False


def _cv_status_adverse(artifact: dict) -> bool:
    cv = artifact.get(INPUT_KEY_CROSS_VALIDATION) if isinstance(artifact, dict) else None
    if not isinstance(cv, dict):
        return False
    status = cv.get("status")
    return isinstance(status, str) and status in {"NEEDS_WORK", "FAIL"}


@register_signal
def template_compliance() -> AdvisorySignal:
    return AdvisorySignal(
        name="template_compliance",
        severity="advisory",
        extractor=_template_compliance_adverse,
    )


@register_signal
def size_check() -> AdvisorySignal:
    return AdvisorySignal(
        name="size_check",
        severity="advisory",
        extractor=_size_check_adverse,
    )


@register_signal
def cross_validation_status() -> AdvisorySignal:
    return AdvisorySignal(
        name="cross_validation_status",
        severity="advisory",
        extractor=_cv_status_adverse,
    )


def is_advisory_adverse(artifact: dict) -> bool:
    """Return True iff any registered advisory signal is adverse."""
    return any(
        sig.severity == "advisory" and _safe_extract(sig, artifact)
        for sig in SIGNALS
    )


def _is_blocking_adverse(artifact: dict) -> bool:
    return any(
        sig.severity == "blocking" and _safe_extract(sig, artifact)
        for sig in SIGNALS
    )


def _safe_extract(signal: AdvisorySignal, artifact: dict) -> bool:
    try:
        return bool(signal.extractor(artifact))
    except Exception:
        return False


def worst_status(artifact: dict, *, score_band: str = "PASS") -> str:
    """Return the rollup label given the score band and artifact signals.

    ``score_band`` is the band derived from the numeric score (PASS /
    NEEDS_WORK / FAIL / INCOMPLETE). The rollup uses it as the floor:

    - score band ``INCOMPLETE`` / ``FAIL`` → returned verbatim.
    - score band ``NEEDS_WORK`` → always ``NEEDS_WORK`` (blocking or
      advisory signals do not downgrade further today).
    - score band ``PASS`` + any blocking signal adverse → ``NEEDS_WORK``.
    - score band ``PASS`` + any advisory signal adverse →
      ``PASS_WITH_ADVISORIES``.
    - score band ``PASS`` with no adverse signals → ``PASS``.
    """
    if score_band in {"INCOMPLETE", "FAIL"}:
        return score_band
    if score_band == "NEEDS_WORK":
        return "NEEDS_WORK"
    if _is_blocking_adverse(artifact):
        return "NEEDS_WORK"
    if is_advisory_adverse(artifact):
        return "PASS_WITH_ADVISORIES"
    return "PASS"
