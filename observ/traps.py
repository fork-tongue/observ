from __future__ import annotations

from functools import partial, wraps
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

# Performance notes that apply to all trap factories below. Traps are
# the per-read/per-write entry points of observ, so their call overhead
# is felt in every interaction with a proxy:
# - The Dep.stack list (a ClassVar that is only ever mutated, never
#   reassigned) is bound to a closure variable, which is cheaper to
#   load than a global plus an attribute
# - Dep.depend() is inlined as dep_stack[-1].add_dep(dep), which saves
#   a method call plus a second check of the stack per tracked read
# - proxy() is called with positional arguments; keyword arguments
#   make a call measurably slower
# - Trap signatures only take **kwargs when a wrapped method actually
#   accepts keyword arguments (only list.sort does; dict.update is
#   handled explicitly), because **kwargs allocates a dict on every
#   call. The wrapped plain containers raise TypeError for unexpected
#   keyword arguments, and so do the traps


class ReadonlyError(Exception):
    """
    Raised when a readonly proxy is modified.
    """

    pass


def read_trap(method: str, obj_cls: type) -> Trap:
    fn = getattr(obj_cls, method)
    dep_stack = Dep.stack

    @wraps(fn)
    def trap(self: Proxy[Any], *args: Any) -> Any:
        if dep_stack:
            dep_stack[-1].add_dep(self.__dep__)
        value = fn(self.__target__, *args)
        if self.__shallow__:
            return value
        return proxy(value, self.__readonly__)

    return trap


# The proxy function with the readonly flag pre-bound, for both flag
# values, so that iterate_trap doesn't construct a partial per call
_PROXY_PARTIAL = partial(proxy, readonly=False)
_PROXY_PARTIAL_READONLY = partial(proxy, readonly=True)


def iterate_trap(method: str, obj_cls: type) -> Trap:
    fn = getattr(obj_cls, method)
    # Hoist the method check out of the trap
    is_items = method == "items"
    dep_stack = Dep.stack

    # The wrapped iterator methods (items, values, keys, __iter__,
    # __reversed__) take no arguments at all
    @wraps(fn)
    def trap(self: Proxy[Any]) -> Any:
        if dep_stack:
            dep_stack[-1].add_dep(self.__dep__)
        iterator = fn(self.__target__)
        if self.__shallow__:
            return iterator
        readonly = self.__readonly__
        if is_items:
            return ((key, proxy(value, readonly)) for key, value in iterator)
        else:
            proxied = _PROXY_PARTIAL_READONLY if readonly else _PROXY_PARTIAL
            return map(proxied, iterator)

    return trap


def read_key_trap(method: str, obj_cls: type) -> Trap:
    fn = getattr(obj_cls, method)
    dep_stack = Dep.stack

    @wraps(fn)
    def trap(self: Proxy[Any], key: Any, *args: Any) -> Any:
        if dep_stack:
            dep_stack[-1].add_dep(self.__dep__.keydep(key))
        value = fn(self.__target__, key, *args)
        if self.__shallow__:
            return value
        return proxy(value, self.__readonly__)

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

    # The signature mirrors dict.update: at most one positional-only
    # argument (a mapping or an iterable of key/value pairs), plus
    # arbitrary keyword arguments
    @wraps(fn)
    def trap(self: Proxy[Any], positional: Any = _MISSING, /, **kwargs: Any) -> Any:
        target = self.__target__
        target_get = target.get
        # Normalize the arguments into a single dict, so that only the
        # incoming keys have to be diffed for changes. This also makes
        # sure that an iterable argument is not consumed twice
        if positional is not _MISSING:
            incoming = dict(positional)
            if kwargs:
                incoming.update(kwargs)
        else:
            incoming = kwargs
        old_values = {key: target_get(key, _MISSING) for key in incoming}
        retval = fn(target, incoming)
        dep = self.__dep__
        keydeps = dep.keydeps if dep.keydeps is not None else _NO_KEYDEPS
        change_detected = False
        for key, old_value in old_values.items():
            if old_value is not target_get(key, _MISSING):
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
    def trap(self: Proxy[Any], *args: Any) -> Any:
        target = self.__target__
        old_len = len(target)
        retval = fn(target, *args)
        if len(target) != old_len:
            self.__dep__.notify()
        return retval

    return trap


def write_copy_compare_trap(method: str, obj_cls: type) -> Trap:
    fn = getattr(obj_cls, method)

    # list.sort takes keyword arguments (key and reverse), so this is
    # the one write trap that must accept **kwargs
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
    def trap(self: Proxy[Any], key: Any, *args: Any) -> Any:
        target = self.__target__
        old_value = getitem_fn(target, key, _MISSING)
        retval = fn(target, key, *args)
        if is_setdefault and not self.__shallow__:
            # This method is only available when readonly is false
            retval = proxy(retval)

        new_value = getitem_fn(target, key)
        # The equality check runs only when neither value is _MISSING
        # or None: some types raise TypeError when compared to None
        # (e.g. PySide6's ItemFlags), see test_use_weird_types_as_value
        if old_value is not new_value and (
            old_value is _MISSING
            or (old_value is None) != (new_value is None)
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

    # The wrapped deleter methods (clear, popitem) take no arguments
    @wraps(fn)
    def trap(self: DictProxyBase) -> Any:
        retval = fn(self.__target__)
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
    def trap(self: Proxy[Any], key: Any, *args: Any) -> Any:
        key_existed = key in self.__target__
        retval = fn(self.__target__, key, *args)
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
