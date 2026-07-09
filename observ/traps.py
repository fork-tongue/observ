from __future__ import annotations

from functools import partial, wraps
from operator import xor
from typing import TYPE_CHECKING, Any

from .dep import Dep
from .proxy import Proxy, proxy

if TYPE_CHECKING:
    from collections.abc import Callable

    from .dict_proxy import DictProxyBase

    # A trap wraps a method of a container type (dict, list or set)
    # with dependency tracking and/or change notification
    Trap = Callable[..., Any]
    # A trap factory builds a trap for the given method of the
    # given container type
    TrapFactory = Callable[[str, type], Trap]


class ReadonlyError(Exception):
    """
    Raised when a readonly proxy is modified.
    """

    pass


def read_trap(method: str, obj_cls: type) -> Trap:
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self: Proxy[Any], *args: Any, **kwargs: Any) -> Any:
        if Dep.stack:
            self.__dep__.depend()
        value = fn(self.__target__, *args, **kwargs)
        if self.__shallow__:
            return value
        return proxy(value, readonly=self.__readonly__)

    return trap


def iterate_trap(method: str, obj_cls: type) -> Trap:
    fn = getattr(obj_cls, method)
    # Hoist the method check out of the trap
    is_items = method == "items"

    @wraps(fn)
    def trap(self: Proxy[Any], *args: Any, **kwargs: Any) -> Any:
        if Dep.stack:
            self.__dep__.depend()
        iterator = fn(self.__target__, *args, **kwargs)
        if self.__shallow__:
            return iterator
        if is_items:
            return (
                (key, proxy(value, readonly=self.__readonly__))
                for key, value in iterator
            )
        else:
            proxied = partial(proxy, readonly=self.__readonly__)
            return map(proxied, iterator)

    return trap


def read_key_trap(method: str, obj_cls: type) -> Trap:
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self: Proxy[Any], *args: Any, **kwargs: Any) -> Any:
        if Dep.stack:
            self.__dep__.keydep(args[0]).depend()
        value = fn(self.__target__, *args, **kwargs)
        if self.__shallow__:
            return value
        return proxy(value, readonly=self.__readonly__)

    return trap


# Sentinel to distinguish 'key not present' from 'value is None'
_MISSING = object()

# Stand-in for TargetDep.keydeps when it hasn't been materialized
# (never written to, only used for lookups)
_NO_KEYDEPS = {}


def write_trap(method: str, obj_cls: type) -> Trap:
    """
    Returns a trap with the cheapest change detection strategy that
    is correct for the given method, so that writes don't need a copy
    of the whole container to detect changes.
    """
    if obj_cls is dict:
        # update and __ior__: only the incoming keys can change
        return write_dict_trap(method, obj_cls)
    if method in ("sort", "reverse", "symmetric_difference_update"):
        # These methods can change the container without changing its
        # length, so fall back to copy-and-compare. The cost of the
        # copy is proportional to the operation itself
        return write_copy_compare_trap(method, obj_cls)
    if method == "__setitem__":
        # list only: compare just the affected index or slice
        return write_setitem_trap(method, obj_cls)
    # The remaining list and set methods can only change the container
    # by changing its length
    return write_len_compare_trap(method, obj_cls)


def write_dict_trap(method: str, obj_cls: type) -> Trap:
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self: Proxy[Any], *args: Any, **kwargs: Any) -> Any:
        target = self.__target__
        # Normalize the arguments (an optional mapping or iterable of
        # key/value pairs, plus optional keyword arguments) into a
        # single dict, so that only the incoming keys have to be
        # diffed for changes. This also makes sure that an iterable
        # argument is not consumed twice
        if args:
            incoming = dict(args[0])
            if kwargs:
                incoming.update(kwargs)
        else:
            incoming = kwargs
        old_values = {key: target.get(key, _MISSING) for key in incoming}
        retval = fn(target, incoming)
        dep = self.__dep__
        keydeps = dep.keydeps if dep.keydeps is not None else _NO_KEYDEPS
        change_detected = False
        for key, old_value in old_values.items():
            if old_value is not target.get(key, _MISSING):
                keydep = keydeps.get(key)
                if keydep is not None:
                    keydep.notify()
                change_detected = True
        if change_detected:
            dep.notify()
        return retval

    return trap


def write_len_compare_trap(method: str, obj_cls: type) -> Trap:
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self: Proxy[Any], *args: Any, **kwargs: Any) -> Any:
        target = self.__target__
        old_len = len(target)
        retval = fn(target, *args, **kwargs)
        if len(target) != old_len:
            self.__dep__.notify()
        return retval

    return trap


def write_copy_compare_trap(method: str, obj_cls: type) -> Trap:
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self: Proxy[Any], *args: Any, **kwargs: Any) -> Any:
        target = self.__target__
        old = target.copy()
        retval = fn(target, *args, **kwargs)
        if target != old:
            self.__dep__.notify()
        return retval

    return trap


def write_setitem_trap(method: str, obj_cls: type) -> Trap:
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self: Proxy[Any], key: Any, value: Any) -> Any:
        target = self.__target__
        try:
            old_value = target[key]
        except (IndexError, TypeError):
            # Let the actual operation raise the appropriate error
            return fn(target, key, value)
        if type(key) is slice:
            # Slice assignment can change the length as well as
            # replace a same-length stretch of items
            old_len = len(target)
            retval = fn(target, key, value)
            changed = len(target) != old_len or target[key] != old_value
        else:
            retval = fn(target, key, value)
            new_value = target[key]
            changed = new_value is not old_value and new_value != old_value
        if changed:
            self.__dep__.notify()
        return retval

    return trap


def write_key_trap(method: str, obj_cls: type) -> Trap:
    fn = getattr(obj_cls, method)
    getitem_fn = getattr(obj_cls, "get")
    # Hoist the method check out of the trap
    is_setdefault = method == "setdefault"

    @wraps(fn)
    def trap(self: Proxy[Any], *args: Any, **kwargs: Any) -> Any:
        target = self.__target__
        key = args[0]
        old_value = getitem_fn(target, key, _MISSING)
        retval = fn(target, *args, **kwargs)
        if is_setdefault and not self.__shallow__:
            # This method is only available when readonly is false
            retval = proxy(retval)

        new_value = getitem_fn(target, key)
        # The equality check runs only when neither value is _MISSING
        # or None: some types raise TypeError when compared to None
        # (e.g. PySide6's ItemFlags), see test_use_weird_types_as_value
        if old_value is not new_value and (
            old_value is _MISSING
            or xor(old_value is None, new_value is None)
            or old_value != new_value
        ):
            dep = self.__dep__
            keydeps = dep.keydeps
            if keydeps is not None:
                keydep = keydeps.get(key)
                if keydep is not None:
                    keydep.notify()
            dep.notify()
        return retval

    return trap


def delete_trap(method: str, obj_cls: type) -> Trap:
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self: DictProxyBase, *args: Any, **kwargs: Any) -> Any:
        retval = fn(self.__target__, *args, **kwargs)
        dep = self.__dep__
        dep.notify()
        keydeps = dep.keydeps if dep.keydeps is not None else _NO_KEYDEPS
        for key in self._orphaned_keydeps():
            # A (sync) subscriber of the main dep may have released
            # a keydep already, so guard against dead entries
            keydep = keydeps.get(key)
            if keydep is not None:
                keydep.notify()
        return retval

    return trap


def delete_key_trap(method: str, obj_cls: type) -> Trap:
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self: Proxy[Any], *args: Any, **kwargs: Any) -> Any:
        key = args[0]
        key_existed = key in self.__target__
        retval = fn(self.__target__, *args, **kwargs)
        if key_existed:
            dep = self.__dep__
            dep.notify()
            keydeps = dep.keydeps
            if keydeps is not None:
                keydep = keydeps.get(key)
                if keydep is not None:
                    keydep.notify()
        return retval

    return trap


trap_map: dict[str, TrapFactory] = {
    "READERS": read_trap,
    "KEYREADERS": read_key_trap,
    "ITERATORS": iterate_trap,
    "WRITERS": write_trap,
    "KEYWRITERS": write_key_trap,
    "DELETERS": delete_trap,
    "KEYDELETERS": delete_key_trap,
}


def readonly_trap(method: str, obj_cls: type) -> Trap:
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self: Proxy[Any], *args: Any, **kwargs: Any) -> Any:
        raise ReadonlyError()

    return trap


trap_map_readonly: dict[str, TrapFactory] = {
    "READERS": read_trap,
    "KEYREADERS": read_key_trap,
    "ITERATORS": iterate_trap,
    "WRITERS": readonly_trap,
    "KEYWRITERS": readonly_trap,
    "DELETERS": readonly_trap,
    "KEYDELETERS": readonly_trap,
}


def construct_methods_traps_dict(
    obj_cls: type, traps: dict[str, set[str]], trap_map: dict[str, TrapFactory]
) -> dict[str, Trap]:
    return {
        method: trap_map[trap_type](method, obj_cls)
        for trap_type, methods in traps.items()
        for method in methods
    }
