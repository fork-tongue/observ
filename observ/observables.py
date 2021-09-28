"""
observe converts plain datastructures (dict, list, set) to
proxied versions of those datastructures to make them reactive.
"""
from functools import wraps
import weakref

from .dep import Dep


class ProxyDb:
    def __init__(self):
        self.db = {}

    def reference(self, proxy):
        obj_id = id(proxy.obj)
        if obj_id not in self.db:
            self.db[obj_id] = {
                "ref": 0,
                "attrs": {},
                "proxies": {
                    # readonly
                    True: {
                        # shallow
                        True: weakref.WeakSet(),
                        False: weakref.WeakSet(),
                    },
                    False: {
                        True: weakref.WeakSet(),
                        False: weakref.WeakSet(),
                    },
                },
            }
        self.db[obj_id]["proxies"][proxy.readonly][proxy.shallow].add(proxy)
        self.db[obj_id]["ref"] += 1

    def dereference(self, proxy):
        obj_id = id(proxy.obj)
        self.db[obj_id]["ref"] -= 1
        self.db[obj_id]["proxies"][proxy.readonly][proxy.shallow].remove(proxy)
        if self.db[obj_id]["ref"] == 0:
            del self.db[obj_id]
        elif self.db[obj_id]["ref"] < 0:
            raise RuntimeError("ye olde 'this should never happen'")

    def attrs(self, proxy):
        return self.db[id(proxy.obj)]["attrs"]

    def proxy(self, obj, readonly=False, shallow=False):
        return next(iter(self.db[id(obj)]["proxies"][readonly][shallow]), None)


proxy_db = ProxyDb()


class Proxy:
    def __init__(self, obj, readonly=False, shallow=False):
        self.obj = obj
        self.readonly = readonly
        self.shallow = shallow
        proxy_db.reference(self)

    def __del__(self):
        proxy_db.dereference(self)


def proxy(obj, readonly=False, shallow=False):
    """Please be aware: this only works on plain data types!"""
    # we can only wrap the following datatypes
    if not isinstance(obj, (dict, list, tuple, set)):
        return obj
    # the object may be a proxy already
    # (exception is when we want a readonly proxy on a writable proxy)
    if isinstance(obj, Proxy) and not (readonly and not obj.readonly):
        return obj
    # there may already be a proxy for this object
    if (existing_proxy := proxy_db.proxy(obj, readonly=readonly, shallow=shallow)) is not None:
        return existing_proxy
    # otherwise, create a new proxy
    return Proxy(obj, readonly=readonly, shallow=shallow)


def reactive(obj):
    return proxy(obj)


def readonly(obj):
    return proxy(obj, readonly=True)


def shallow_reactive(obj):
    return proxy(obj, shallow=True)


def shallow_readonly(obj):
    return proxy(obj, shallow=True, readonly=True)


def read_trap(method, obj_cls):
    fn = getattr(obj_cls, method)
    @wraps(fn)
    def trap(self, *args, **kwargs):
        if Dep.stack:
            proxy_db.attrs(self)["dep"].depend()
        value = fn(self.obj, *args, **kwargs)

    return trap


def read_key_trap(method, obj_cls):
    fn = getattr(obj_cls, method)
    @wraps(fn)
    def inner(self, *args, **kwargs):
        if Dep.stack:
            key = args[0]
            self.__keydeps__[key].depend()
        return fn(self, *args, **kwargs)

    return inner


def write_trap(method, obj_cls):
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


def write_key_trap(method, obj_cls):
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


def delete_trap(method, obj_cls):
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


def delete_key_trap(method, obj_cls):
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


def readonly_trap(method, obj_cls):
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
