"""Shared seam helpers — Protocol + accessor + setter + reset.

Every pluggable primitive in :mod:`sdd_core.security` has the same
shape: a runtime-checkable Protocol with ``protocol_version: int``, a
bundled default, an accessor, a setter that validates conformance and
version, a reset. :class:`Seam` collapses that onto one helper for
*instance-shaped* primitives; :class:`FactorySeam` carries the same
contract for *factory-shaped* primitives (path → P).

Both seam variants self-register into the package-level registry; the
registry powers :func:`seal_security` (refuses post-seal mutation) and
:func:`dump_security_provenance` (audit-entry attribution).
"""
from __future__ import annotations

from typing import Any, Callable, Generic, Iterator, TypeVar

P = TypeVar("P")

_REGISTRY: list["BaseSeam[Any]"] = []
_sealed: bool = False


def _set_sealed(flag: bool) -> None:
    """Package-private toggle used by :mod:`sdd_core.security.seal`."""
    global _sealed
    _sealed = flag


def _get_sealed() -> bool:
    return _sealed


class BaseSeam(Generic[P]):
    """Common contract shared by :class:`Seam` and :class:`FactorySeam`.

    Concrete seams must declare ``name``, expose
    :attr:`protocol_version`, :attr:`active_provenance`, and honour the
    sealed-state guard on :meth:`set` / :meth:`reset`.
    """

    name: str

    @property
    def protocol_version(self) -> int:  # pragma: no cover - abstract
        raise NotImplementedError

    @property
    def active_provenance(self) -> dict[str, object]:  # pragma: no cover - abstract
        raise NotImplementedError


class Seam(BaseSeam[P]):
    """Generic accessor / setter / reset helper for a security primitive.

    Parameters
    ----------
    name:
        Human-readable name used in error messages and provenance.
    protocol:
        The runtime-checkable Protocol the value must satisfy.
    default:
        The bundled default instance (or factory; see ``default_factory``).
    protocol_version:
        Bundled Protocol version. Setters refuse implementations whose
        ``protocol_version`` is below this number so a future API
        extension cannot be silently downgraded.
    default_factory:
        Optional zero-arg factory used to rebuild the default on
        :meth:`reset` (e.g. ``EnvDryRunGate`` re-snapshots the env).
        When present, ``default`` may be ``None``.
    extra_validator:
        Optional ``Callable[[P], None]`` invoked after Protocol /
        version checks; raise :exc:`TypeError` to reject the value.
        Used by hash.py to require a non-empty ``algo``.
    """

    __slots__ = (
        "name",
        "_protocol",
        "_default",
        "_default_factory",
        "_active",
        "_version",
        "_extra_validator",
    )

    def __init__(
        self,
        *,
        name: str,
        protocol: type,
        default: "P | None" = None,
        protocol_version: int = 1,
        default_factory: "Callable[[], P] | None" = None,
        extra_validator: "Callable[[P], None] | None" = None,
    ) -> None:
        if default is None and default_factory is None:
            raise ValueError(
                f"Seam {name!r}: either default or default_factory required"
            )
        self.name = name
        self._protocol = protocol
        self._default = default
        self._default_factory = default_factory
        self._version = protocol_version
        self._extra_validator = extra_validator
        self._active: P = (
            default if default_factory is None else default_factory()
        )
        _REGISTRY.append(self)

    def get(self) -> P:
        return self._active

    def set(self, value: P) -> None:
        if _sealed:
            raise RuntimeError(
                f"security sealed — {self.name}.set is locked"
            )
        if not isinstance(value, self._protocol):
            raise TypeError(
                f"{type(value).__name__} does not satisfy {self.name}"
            )
        observed = getattr(value, "protocol_version", 0)
        if observed < self._version:
            raise TypeError(
                f"{self.name} version {observed} < required {self._version}"
            )
        if self._extra_validator is not None:
            self._extra_validator(value)
        self._active = value

    def reset(self) -> None:
        if _sealed:
            raise RuntimeError(
                f"security sealed — {self.name}.reset is locked"
            )
        if self._default_factory is not None:
            self._active = self._default_factory()
        else:
            self._active = self._default  # type: ignore[assignment]

    @property
    def protocol_version(self) -> int:
        return self._version

    @property
    def active_provenance(self) -> dict[str, object]:
        active = self._active
        return {
            "name": self.name,
            "protocol_version": getattr(active, "protocol_version", 0),
            "impl": type(active).__name__,
        }


class FactorySeam(BaseSeam[P]):
    """Seam whose pluggable value is a factory ``Callable[[Any], P]``.

    Validates a candidate factory by invoking it on a probe argument
    and checking the resulting object satisfies *protocol* with the
    bundled :attr:`protocol_version`. Provenance reports the factory's
    qualified name plus the version.
    """

    __slots__ = (
        "name",
        "_protocol",
        "_default_factory",
        "_active",
        "_version",
        "_probe_arg_factory",
        "_probe_cleanup",
    )

    def __init__(
        self,
        *,
        name: str,
        protocol: type,
        default_factory: Callable[[Any], P],
        protocol_version: int = 1,
        probe_arg_factory: Callable[[], Any],
        probe_cleanup: "Callable[[Any], None] | None" = None,
    ) -> None:
        self.name = name
        self._protocol = protocol
        self._default_factory = default_factory
        self._version = protocol_version
        self._probe_arg_factory = probe_arg_factory
        self._probe_cleanup = probe_cleanup
        self._active: Callable[[Any], P] = default_factory
        _REGISTRY.append(self)

    def get(self) -> Callable[[Any], P]:
        return self._active

    def set(self, factory: Callable[[Any], P]) -> None:
        if _sealed:
            raise RuntimeError(
                f"security sealed — {self.name}.set is locked"
            )
        self._validate(factory)
        self._active = factory

    def reset(self) -> None:
        if _sealed:
            raise RuntimeError(
                f"security sealed — {self.name}.reset is locked"
            )
        self._active = self._default_factory

    def _validate(self, factory: Callable[[Any], P]) -> None:
        probe_arg = self._probe_arg_factory()
        try:
            probe = factory(probe_arg)
        except TypeError as exc:
            raise TypeError(f"factory rejected probe arg: {exc}") from exc
        if not isinstance(probe, self._protocol):
            raise TypeError(
                f"{type(probe).__name__} does not satisfy {self.name}"
            )
        observed = getattr(probe, "protocol_version", 0)
        if observed < self._version:
            raise TypeError(
                f"{self.name} version {observed} < required {self._version}"
            )
        if self._probe_cleanup is not None:
            try:
                self._probe_cleanup(probe_arg)
            except OSError:
                pass

    @property
    def protocol_version(self) -> int:
        return self._version

    @property
    def active_provenance(self) -> dict[str, object]:
        factory = self._active
        impl = getattr(factory, "__qualname__", type(factory).__name__)
        return {
            "name": self.name,
            "protocol_version": self._version,
            "impl": impl,
        }


def iter_seams() -> Iterator["BaseSeam[Any]"]:
    """Walk every registered seam — used by seal + provenance."""
    return iter(_REGISTRY)


def dump_security_provenance() -> dict[str, dict[str, object]]:
    """Return ``{seam_name: {protocol_version, impl}}`` for every seam."""
    return {s.name: s.active_provenance for s in _REGISTRY}
