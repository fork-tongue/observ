from functools import partial, wraps
from operator import xor

from .dep import Dep
from .proxy import proxy
from .proxy_db import proxy_db


class ReadonlyError(Exception):
    """
    Raised when a readonly proxy is modified.
    """

    pass


def read_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self, *args, **kwargs):
        if Dep.stack:
            proxy_db.attrs(self)["dep"].depend()
        value = fn(self.__target__, *args, **kwargs)
        if self.__shallow__:
            return value
        return proxy(value, readonly=self.__readonly__)

    return trap


def iterate_trap(method, obj_cls):
    fn = getattr(obj_cls, method)
    # Hoist the method check out of the trap
    is_items = method == "items"

    @wraps(fn)
    def trap(self, *args, **kwargs):
        if Dep.stack:
            proxy_db.attrs(self)["dep"].depend()
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


def read_key_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self, *args, **kwargs):
        if Dep.stack:
            key = args[0]
            keydeps = proxy_db.attrs(self)["keydep"]
            if key not in keydeps:
                keydeps[key] = Dep()
            keydeps[key].depend()
        value = fn(self.__target__, *args, **kwargs)
        if self.__shallow__:
            return value
        return proxy(value, readonly=self.__readonly__)

    return trap


# Sentinel to distinguish 'key not present' from 'value is None'
_MISSING = object()


def write_trap(method, obj_cls):
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


def write_dict_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self, *args, **kwargs):
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
        attrs = proxy_db.attrs(self)
        keydeps = attrs["keydep"]
        change_detected = False
        for key, old_value in old_values.items():
            if old_value is not target.get(key, _MISSING):
                if key in keydeps:
                    keydeps[key].notify()
                else:
                    keydeps[key] = Dep()
                change_detected = True
        if change_detected:
            attrs["dep"].notify()
        return retval

    return trap


def write_len_compare_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self, *args, **kwargs):
        target = self.__target__
        old_len = len(target)
        retval = fn(target, *args, **kwargs)
        if len(target) != old_len:
            proxy_db.attrs(self)["dep"].notify()
        return retval

    return trap


def write_copy_compare_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self, *args, **kwargs):
        target = self.__target__
        old = target.copy()
        retval = fn(target, *args, **kwargs)
        if target != old:
            proxy_db.attrs(self)["dep"].notify()
        return retval

    return trap


def write_setitem_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self, key, value):
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
            proxy_db.attrs(self)["dep"].notify()
        return retval

    return trap


def write_key_trap(method, obj_cls):
    fn = getattr(obj_cls, method)
    getitem_fn = getattr(obj_cls, "get")
    # Hoist the method check out of the trap
    is_setdefault = method == "setdefault"

    @wraps(fn)
    def trap(self, *args, **kwargs):
        target = self.__target__
        key = args[0]
        is_new = key not in target
        old_value = getitem_fn(target, key) if not is_new else None
        retval = fn(target, *args, **kwargs)
        if is_setdefault and not self.__shallow__:
            # This method is only available when readonly is false
            retval = proxy(retval)

        new_value = getitem_fn(target, key)
        if xor(old_value is None, new_value is None) or old_value != new_value:
            attrs = proxy_db.attrs(self)
            keydep = attrs["keydep"].get(key)
            if keydep is not None:
                keydep.notify()
            attrs["dep"].notify()
        return retval

    return trap


def delete_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self, *args, **kwargs):
        retval = fn(self.__target__, *args, **kwargs)
        attrs = proxy_db.attrs(self)
        attrs["dep"].notify()
        for key in self._orphaned_keydeps():
            attrs["keydep"][key].notify()
        return retval

    return trap


def delete_key_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self, *args, **kwargs):
        key = args[0]
        attrs = proxy_db.attrs(self)
        key_existed = key in self.__target__
        retval = fn(self.__target__, *args, **kwargs)
        if key_existed:
            attrs["dep"].notify()
            keydep = attrs["keydep"].get(key)
            if keydep is not None:
                keydep.notify()
        return retval

    return trap


trap_map = {
    "READERS": read_trap,
    "KEYREADERS": read_key_trap,
    "ITERATORS": iterate_trap,
    "WRITERS": write_trap,
    "KEYWRITERS": write_key_trap,
    "DELETERS": delete_trap,
    "KEYDELETERS": delete_key_trap,
}


def readonly_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self, *args, **kwargs):
        raise ReadonlyError()

    return trap


trap_map_readonly = {
    "READERS": read_trap,
    "KEYREADERS": read_key_trap,
    "ITERATORS": iterate_trap,
    "WRITERS": readonly_trap,
    "KEYWRITERS": readonly_trap,
    "DELETERS": readonly_trap,
    "KEYDELETERS": readonly_trap,
}


def construct_methods_traps_dict(obj_cls, traps, trap_map):
    return {
        method: trap_map[trap_type](method, obj_cls)
        for trap_type, methods in traps.items()
        for method in methods
    }
