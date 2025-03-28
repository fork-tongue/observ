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

    @wraps(fn)
    def trap(self, *args, **kwargs):
        if Dep.stack:
            proxy_db.attrs(self)["dep"].depend()
        iterator = fn(self.__target__, *args, **kwargs)
        if self.__shallow__:
            return iterator
        if method == "items":
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


def write_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self, *args, **kwargs):
        old = self.__target__.copy()
        retval = fn(self.__target__, *args, **kwargs)
        attrs = proxy_db.attrs(self)
        if obj_cls is dict:
            change_detected = False
            keydeps = attrs["keydep"]
            for key, val in self.__target__.items():
                if old.get(key) is not val:
                    if key in keydeps:
                        keydeps[key].notify()
                    else:
                        keydeps[key] = Dep()
                    change_detected = True
            if change_detected:
                attrs["dep"].notify()
        else:  # list and set
            if self.__target__ != old:
                attrs["dep"].notify()

        return retval

    return trap


def write_key_trap(method, obj_cls):
    fn = getattr(obj_cls, method)
    getitem_fn = getattr(obj_cls, "get")

    @wraps(fn)
    def trap(self, *args, **kwargs):
        key = args[0]
        attrs = proxy_db.attrs(self)
        is_new = key not in attrs["keydep"]
        old_value = getitem_fn(self.__target__, key) if not is_new else None
        retval = fn(self.__target__, *args, **kwargs)
        if method == "setdefault" and not self.__shallow__:
            # This method is only available when readonly is false
            retval = proxy(retval)

        new_value = getitem_fn(self.__target__, key)
        if is_new:
            attrs["keydep"][key] = Dep()
        if xor(old_value is None, new_value is None) or old_value != new_value:
            attrs["keydep"][key].notify()
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
            del attrs["keydep"][key]
        return retval

    return trap


def delete_key_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self, *args, **kwargs):
        retval = fn(self.__target__, *args, **kwargs)
        key = args[0]
        attrs = proxy_db.attrs(self)
        attrs["dep"].notify()
        attrs["keydep"][key].notify()
        del attrs["keydep"][key]
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
