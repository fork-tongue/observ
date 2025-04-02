from __future__ import annotations

from functools import partial
from typing import Generic, Literal, TypedDict, TypeVar, cast

from .proxy_db import proxy_db

T = TypeVar("T")


class Proxy(Generic[T]):
    """
    Proxy for an object/target.

    Instantiating a Proxy will add a reference to the global proxy_db and
    destroying a Proxy will remove that reference.

    Please use the `proxy` method to get a proxy for a certain object instead
    of directly creating one yourself. The `proxy` method will either create
    or return an existing proxy and makes sure that the db stays consistent.
    """

    __hash__ = None
    # the slots have to be very unique since we also proxy objects
    # which may define the attributes with the same names
    __slots__ = ("__readonly__", "__shallow__", "__target__", "__weakref__")

    def __init__(self, target: T, readonly=False, shallow=False):
        self.__target__ = target
        self.__readonly__ = readonly
        self.__shallow__ = shallow
        proxy_db.reference(self)

    def __del__(self):
        proxy_db.dereference(self)


# Lookup dict for mapping a type (dict, list, set) to a method
# that will convert an object of that type to a proxied version
TYPE_LOOKUP = {}


def proxy(target: T, readonly=False, shallow=False) -> T:
    """
    Returns a Proxy for the given object. If a proxy for the given
    configuration already exists, it will return that instead of
    creating a new one.

    Please be aware: this only works on plain data types: dict, list,
    set and tuple!
    """
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
            target = target.__target__

    # Note that at this point, target is always a non-proxy object
    # Check the proxy_db to see if there's already a proxy for the target object
    existing_proxy = proxy_db.get_proxy(target, readonly=readonly, shallow=shallow)
    if existing_proxy is not None:
        return existing_proxy

    # Create a new proxy
    for type_test, (writable_proxy_type, readonly_proxy_type) in TYPE_LOOKUP.items():
        if type_test(target):
            proxy_type = readonly_proxy_type if readonly else writable_proxy_type
            return proxy_type(target, readonly=readonly, shallow=shallow)

    if isinstance(target, tuple):
        return cast(
            T, tuple(proxy(x, readonly=readonly, shallow=shallow) for x in target)
        )

    # We can't proxy a plain value
    return cast(T, target)


try:
    # for Python >= 3.11
    class Ref(TypedDict, Generic[T]):
        value: T

    def ref(target: T) -> Ref[T]:
        return proxy(Ref(value=target))

except TypeError:
    # before python 3.11 a TypedDict cannot inherit from a non-TypedDict class
    def ref(target: T) -> dict[Literal["value"], T]:
        return proxy({"value": target})


reactive = proxy
readonly = partial(proxy, readonly=True)
shallow_reactive = partial(proxy, shallow=True)
shallow_readonly = partial(proxy, shallow=True, readonly=True)


def to_raw(target: Proxy[T] | T) -> T:
    """
    Returns a raw object from which any trace of proxy has been replaced
    with its wrapped target value.
    """
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
