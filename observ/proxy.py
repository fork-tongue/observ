from __future__ import annotations

from copy import copy, deepcopy
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

from .proxy_db import proxy_db

if TYPE_CHECKING:
    from typing import TypedDict

    from .proxy_db import TargetDep

T = TypeVar("T")


class Proxy(Generic[T]):
    """
    Proxy for an object/target.

    All proxies that wrap the same target share a single TargetDep
    (stored as `__dep__`), which holds the reactive state for the
    target. The proxy's strong reference to it keeps that state (and
    the registry entry for the target) alive; once the last proxy and
    the last subscribed watcher are gone, it is cleaned up through
    regular reference counting.

    Please use the `proxy` method to get a proxy for a certain object instead
    of directly creating one yourself. The `proxy` method will either create
    or return an existing proxy and makes sure that the db stays consistent.
    """

    __hash__ = None  # type: ignore[assignment]
    # the slots have to be very unique since we also proxy objects
    # which may define the attributes with the same names.
    # NB: deliberately not annotated in the class body (the slot types
    # are inferred from __init__): class-level annotations would add an
    # __annotations__ attribute to the class, which would leak through
    # to the container proxies (see test_wrapping_complete)
    __slots__ = ("__dep__", "__readonly__", "__shallow__", "__target__", "__weakref__")

    def __init__(self, target: T, readonly: bool = False, shallow: bool = False):
        self.__target__ = target
        self.__readonly__ = readonly
        self.__shallow__ = shallow
        dep: TargetDep = proxy_db.target_dep(target)
        dep.register_proxy((readonly, shallow), self)
        self.__dep__ = dep

    def __copy__(self) -> T:
        return copy(self.__target__)

    def __deepcopy__(self, memo: dict[int, Any]) -> T:
        return deepcopy(self.__target__, memo)


# Lookup dict for mapping a type (dict, list, set) to a tuple
# of proxy types (writable, readonly) for that type. Keyed on the
# exact type, so subclasses are (deliberately) not proxied
TYPE_LOOKUP: dict[type, tuple[type[Proxy[Any]], type[Proxy[Any]]]] = {}

# Types of values that can't be proxied. Note the exact type is
# checked (no subclasses) so that these can be ruled out with a
# single set containment check
PLAIN_TYPES: frozenset[type] = frozenset({type(None), bool, int, float, str, bytes})


def proxy(target: T, readonly: bool = False, shallow: bool = False) -> T:
    """
    Returns a Proxy for the given object. If a proxy for the given
    configuration already exists, it will return that instead of
    creating a new one.

    Please be aware: this only works on plain data types: dict, list,
    set and tuple!
    """
    # Note on the typing in this function: a proxy behaves exactly like
    # its target (all methods are delegated to it), but the type system
    # cannot express that relationship, so proxy-creating functions are
    # typed as returning the target's own type (see also the discussion
    # in https://github.com/fork-tongue/observ/pull/111). Since this is
    # the hottest code path in observ, Any-typed locals are used instead
    # of typing.cast, which would incur a function call at runtime

    # Plain values can't be proxied, so return them as-is. This is the
    # most common case since this function is called on the result of
    # every read from a proxied container, so it is checked first
    if type(target) in PLAIN_TYPES:
        return target

    # The object may be a proxy already, so check if it matches the
    # given configuration (readonly and shallow)
    if isinstance(target, Proxy):
        if readonly == target.__readonly__ and shallow == target.__shallow__:
            return target
        else:
            # If the configuration does not match,
            # unwrap the target from the proxy so that the right
            # kind of proxy can be returned in the next part of
            # this function
            unwrapped: Any = target.__target__
            target = unwrapped

    # Note that at this point, target is always a non-proxy object
    # Check the proxy_db to see if there's already a proxy for the target object
    existing_proxy: Any = proxy_db.get_proxy(target, readonly=readonly, shallow=shallow)
    if existing_proxy is not None:
        return existing_proxy

    # Create a new proxy
    proxy_types = TYPE_LOOKUP.get(type(target))
    if proxy_types is not None:
        proxy_type = proxy_types[1] if readonly else proxy_types[0]
        new_proxy: Any = proxy_type(target, readonly=readonly, shallow=shallow)
        return new_proxy

    if isinstance(target, tuple):
        return cast(
            T, tuple(proxy(x, readonly=readonly, shallow=shallow) for x in target)
        )

    # We can't proxy a plain value
    return target


if TYPE_CHECKING:
    # Only used for typing: at runtime a Ref is a plain (proxied) dict.
    # Defined here (instead of unconditionally) because a generic
    # TypedDict requires Python 3.11
    class Ref(TypedDict, Generic[T]):
        value: T


def ref(target: T) -> Ref[T]:
    """
    Returns a reactive dict with a single 'value' key, set to the
    given target. Useful for making a single (plain) value reactive.
    """
    return proxy(cast("Ref[T]", {"value": target}))


reactive = proxy


def readonly(target: T) -> T:
    """
    Returns a readonly proxy for the given target: reads are tracked,
    but any write raises a ReadonlyError.
    """
    return proxy(target, readonly=True)


def shallow_reactive(target: T) -> T:
    """
    Returns a shallow proxy for the given target: only the first level
    of the target is made reactive, nested values are returned raw.
    """
    return proxy(target, shallow=True)


def shallow_readonly(target: T) -> T:
    """
    Combination of `shallow_reactive` and `readonly`.
    """
    return proxy(target, readonly=True, shallow=True)


def trigger_ref(target: Proxy[T] | T) -> None:
    """
    Force-notify the watchers that depend on the given proxy, as if
    its first level was written to. This is typically used together
    with a shallow proxy (`shallow_reactive`, `shallow_readonly`),
    after making deep mutations to a value nested inside it — those
    mutations bypass the proxy, so observ cannot see them by itself.

    Note that the parameter is annotated `Proxy[T] | T` (like
    `to_raw`) rather than just `Proxy[T]`: proxies are typed as their
    target's own type, so requiring `Proxy` would reject every
    correctly-typed call site. A proxy is still required at runtime.
    """
    if not isinstance(target, Proxy):
        raise TypeError(
            "trigger_ref() expects a proxy "
            "(e.g. the result of ref, reactive or shallow_reactive)"
        )
    dep = target.__dep__
    keydeps = dep.keydeps
    if keydeps is not None:
        # Notifying may run sync watchers, which can release keydeps
        # and thereby mutate the (weak) mapping, so iterate a snapshot
        for keydep in list(keydeps.values()):
            keydep.notify()
    dep.notify()


def to_raw(target: Proxy[T] | T) -> T:
    """
    Returns a raw object from which any trace of proxy has been replaced
    with its wrapped target value.
    """
    # The casts below are needed because the type system cannot know
    # that rebuilding a container from its (recursively unproxied)
    # items yields a value of the same type as the original target
    if isinstance(target, Proxy):
        return to_raw(target.__target__)

    if isinstance(target, list):
        return cast(T, [to_raw(t) for t in target])

    if isinstance(target, dict):
        return cast(T, {key: to_raw(value) for key, value in target.items()})

    if isinstance(target, tuple):
        return cast(T, tuple(to_raw(t) for t in target))

    if isinstance(target, set):
        return cast(T, {to_raw(t) for t in target})

    return target
