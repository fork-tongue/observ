"""
observe converts plain datastructures (dict, list, set) to
proxied versions of those datastructures to make them reactive.
"""
from functools import wraps
import sys

from .dep import Dep


def observe(obj, deep=True, readonly=False):
    """Please be aware: this only works on plain data types!"""
    if not isinstance(obj, (dict, list, tuple, set)):
        return obj  # common case first
    elif isinstance(obj, dict):
        cls = ReadonlyDictProxy if readonly else DictProxy
        if not isinstance(obj, DictProxyBase):
            reactive = cls(obj)
        else:
            reactive = obj
        if deep:
            for k, v in reactive.items():
                reactive[k] = observe(v, deep=deep, readonly=readonly)
        return reactive
    elif isinstance(obj, list):
        cls = ReadonlyListProxy if readonly else ListProxy
        if not isinstance(obj, ListProxyBase):
            reactive = cls(obj)
        else:
            reactive = obj
        if deep:
            for i, v in enumerate(reactive):
                reactive[i] = observe(v, deep=deep, readonly=readonly)
        return reactive
    elif isinstance(obj, tuple):
        reactive = obj  # tuples are immutable
        if deep:
            reactive = tuple(observe(v, deep=deep, readonly=readonly) for v in reactive)
        return reactive
    elif isinstance(obj, set):
        cls = ReadonlySetProxy if readonly else SetProxy
        if deep:
            return cls({observe(v, deep=deep, readonly=readonly) for v in obj})
        else:
            if not isinstance(obj, SetProxyBase):
                reactive = cls(obj)
            else:
                reactive = obj
            return reactive


def read_trap(method, proxy_cls, obj_cls):
    fn = getattr(obj_cls, method)
    @wraps(fn)
    def inner(self, *args, **kwargs):
        if Dep.stack:
            self.__dep__.depend()
        return fn(self, *args, **kwargs)

    return inner


def read_key_trap(method, proxy_cls, obj_cls):
    fn = getattr(obj_cls, method)
    @wraps(fn)
    def inner(self, *args, **kwargs):
        if Dep.stack:
            key = args[0]
            self.__keydeps__[key].depend()
        return fn(self, *args, **kwargs)

    return inner


def write_trap(method, proxy_cls, obj_cls):
    fn = getattr(obj_cls, method)
    @wraps(fn)
    def inner(self, *args, **kwargs):
        args = tuple(observe(a) for a in args)
        kwargs = {k: observe(v) for k, v in kwargs.items()}
        retval = fn(self, *args, **kwargs)
        # TODO prevent firing if value hasn't actually changed?
        self.__dep__.notify()
        return retval

    return inner


def write_key_trap(method, proxy_cls, obj_cls):
    fn = getattr(obj_cls, method)
    getitem_fn = getattr(obj_cls, "__getitem__")
    @wraps(fn)
    def inner(self, *args, **kwargs):
        key = args[0]
        is_new = key not in self.__keydeps__
        old_value = getitem_fn(self, key) if not is_new else None
        args = [key] + [observe(a) for a in args[1:]]
        kwargs = {k: observe(v) for k, v in kwargs.items()}
        retval = fn(self, *args, **kwargs)
        new_value = getitem_fn(self, key)
        if is_new:
            self.__keydeps__[key] = Dep()
        if old_value != new_value:
            self.__keydeps__[key].notify()
            self.__dep__.notify()
        return retval

    return inner


def delete_trap(method, proxy_cls, obj_cls):
    fn = getattr(obj_cls, method)
    @wraps(fn)
    def inner(self, *args, **kwargs):
        retval = fn(self, *args, **kwargs)
        self.__dep__.notify()
        for key in self._orphaned_keydeps():
            self.__keydeps__[key].notify()
            del self.__keydeps__[key]
        return retval

    return inner


def delete_key_trap(method, proxy_cls, obj_cls):
    fn = getattr(obj_cls, method)
    @wraps(fn)
    def inner(self, *args, **kwargs):
        retval = fn(self, *args, **kwargs)
        key = args[0]
        self.__dep__.notify()
        self.__keydeps__[key].notify()
        del self.__keydeps__[key]
        return retval

    return inner


trap_map = {
    "READERS": read_trap,
    "KEYREADERS": read_key_trap,
    "WRITERS": write_trap,
    "KEYWRITERS": write_key_trap,
    "DELETERS": delete_trap,
    "KEYDELETERS": delete_key_trap,
}

class ReadonlyError(Exception):
    pass


def readonly_trap(method, proxy_cls, obj_cls):
    fn = getattr(obj_cls, method)
    @wraps(fn)
    def inner(self, *args, **kwargs):
        raise ReadonlyError()

    return inner

trap_map_readonly = {
    "READERS": read_trap,
    "KEYREADERS": read_key_trap,
    "WRITERS": readonly_trap,
    "KEYWRITERS": readonly_trap,
    "DELETERS": readonly_trap,
    "KEYDELETERS": readonly_trap,
}

def make_observable(proxy_cls, obj_cls, traps, trap_map):
    for trap_type, methods in traps.items():
        for method in methods:
            trap = trap_map[trap_type](method, proxy_cls, obj_cls)
            setattr(proxy_cls, method, trap)


dict_traps = {
    "READERS": {
        "values",
        "copy",
        "items",
        "keys",
        "__eq__",
        "__format__",
        "__ge__",
        "__gt__",
        "__iter__",
        "__le__",
        "__len__",
        "__lt__",
        "__ne__",
        "__repr__",
        "__sizeof__",
        "__str__",
    }
    "KEYREADERS": {
        "get",
        "__contains__",
        "__getitem__",
    }
    "WRITERS": {
        "update",
    }
    "KEYWRITERS": {
        "setdefault",
        "__setitem__",
    }
    "DELETERS": {
        "clear",
        "popitem",
    }
    "KEYDELETERS": {
        "pop",
        "__delitem__",
    },
}

if sys.version_info >= (3, 8, 0):
    dict_traps["READERS"].add("__reversed__")
if sys.version_info >= (3, 9, 0):
    dict_traps["READERS"].add("__or__")
    dict_traps["READERS"].add("__ror__")
    dict_traps["WRITERS"].add("__ior__")


class ProxyBase:
    def __init__(self, obj):
        self._obj = obj


class DictProxyBase(ProxyBase):
    def __init__(self, obj):
        super().__init__(obj)
        self.__dep__ = Dep()
        self.__keydeps__ = {key: Dep() for key in self._obj.keys()}

    def _orphaned_keydeps(self):
        return set(self.__keydeps__.keys()) - set(self._obj.keys())


class DictProxy(DictProxyBase):
    pass


class ReadonlyDictProxy(DictProxyBase):
    pass


make_observable(DictProxy, dict, dict_traps, trap_map)
make_observable(ReadonlyDictProxy, dict, dict_traps, trap_map_readonly)


list_traps = {
    "READERS": {
        "count",
        "index",
        "copy",
        "__add__",
        "__getitem__",
        "__contains__",
        "__eq__",
        "__ge__",
        "__gt__",
        "__le__",
        "__lt__",
        "__mul__",
        "__ne__",
        "__rmul__",
        "__iter__",
        "__len__",
        "__repr__",
        "__str__",
        "__format__",
        "__reversed__",
        "__sizeof__",
    }
    "WRITERS": {
        "append",
        "clear",
        "extend",
        "insert",
        "pop",
        "remove",
        "reverse",
        "sort",
        "__setitem__",
        "__delitem__",
        "__iadd__",
        "__imul__",
    }
}


class ListProxyBase(ProxyBase):
    def __init__(self, obj):
        super().__init__(obj)
        self.__dep__ = Dep()


class ListProxy(ListProxyBase):
    pass


class ReadonlyListProxy(ListProxyBase):
    pass


make_observable(ListProxy, list, list_traps, trap_map)
make_observable(ReadonlyListProxy, list, list_traps, trap_map_readonly)


set_traps = {
    "READERS": {
        "copy",
        "difference",
        "intersection",
        "isdisjoint",
        "issubset",
        "issuperset",
        "symmetric_difference",
        "union",
        "__and__",
        "__contains__",
        "__eq__",
        "__format__",
        "__ge__",
        "__gt__",
        "__iand__",
        "__ior__",
        "__isub__",
        "__iter__",
        "__ixor__",
        "__le__",
        "__len__",
        "__lt__",
        "__ne__",
        "__or__",
        "__rand__",
        "__repr__",
        "__ror__",
        "__rsub__",
        "__rxor__",
        "__sizeof__",
        "__str__",
        "__sub__",
        "__xor__",
    }
    "WRITERS": {
        "add",
        "clear",
        "difference_update",
        "intersection_update",
        "discard",
        "pop",
        "remove",
        "symmetric_difference_update",
        "update",
    }
}


class SetProxyBase(ProxyBase):
    def __init__(self, obj):
        super().__init__(obj)
        self.__dep__ = Dep()


class SetProxy(SetProxyBase):
    pass


class ReadonlySetProxy(SetProxyBase):
    pass


make_observable(SetProxy, set, set_traps, trap_map)
make_observable(ReadonlySetProxy, set, set_traps, trap_map_readonly)
