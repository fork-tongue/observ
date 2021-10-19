"""
observe converts plain datastructures (dict, list, set) to
proxied versions of those datastructures to make them reactive.
"""
from functools import wraps
import sys
from weakref import WeakSet

from .dep import Dep


class ProxyDb:
    """
    Collection of proxies, tracked by the id of the object that they wrap.
    Each time a Proxy is instantiated, it will register itself for the
    wrapped object. And when a Proxy is deleted, then it will unregister.
    When the last proxy that wraps an object is removed, it is uncertain
    what happens to the wrapped object, so in that case the object id is
    removed from the collection.
    """

    def __init__(self):
        self.db = {}

    def reference(self, proxy):
        """
        Adds a reference to the collection for the wrapped object's id
        """
        obj_id = id(proxy.target)
        attrs = (
            {"dep": Dep(), "keydep": {key: Dep() for key in dict.keys(proxy.target)}}
            if isinstance(proxy.target, dict)
            else {"dep": Dep()}
        )
        if obj_id not in self.db:
            self.db[obj_id] = {
                "ref": 0,  # ref counter
                "attrs": attrs,  # dep, keydep
                "proxies": {
                    # readonly
                    True: {
                        # shallow
                        True: WeakSet(),
                        False: WeakSet(),
                    },
                    False: {
                        True: WeakSet(),
                        False: WeakSet(),
                    },
                },
            }
        self.db[obj_id]["proxies"][proxy.readonly][proxy.shallow].add(proxy)
        self.db[obj_id]["ref"] += 1

    def dereference(self, proxy):
        """
        Removes the reference of the proxy for the wrapped object's id
        """
        obj_id = id(proxy.target)
        self.db[obj_id]["ref"] -= 1
        self.db[obj_id]["proxies"][proxy.readonly][proxy.shallow].remove(proxy)
        if self.db[obj_id]["ref"] == 0:
            del self.db[obj_id]
        elif self.db[obj_id]["ref"] < 0:
            raise RuntimeError("ye olde 'this should never happen'  ¯\\_(ツ)_/¯")

    def attrs(self, proxy):
        return self.db[id(proxy.target)]["attrs"]

    def get_proxy(self, target, readonly=False, shallow=False):
        """
        Returns a proxy from the collection for the given object and configuration.
        Will return None if there is no proxy for the object's id.
        """
        if id(target) not in self.db:
            return None
        return next(iter(self.db[id(target)]["proxies"][readonly][shallow]), None)


# Create a global proxy collection
proxy_db = ProxyDb()


class Proxy:
    """
    Proxy for an object.
    Instantiating a Proxy will add a reference to the global proxy_db and
    destroying a Proxy will remove that reference.
    """

    def __init__(self, target, readonly=False, shallow=False):
        self.target = target
        self.readonly = readonly
        self.shallow = shallow
        proxy_db.reference(self)

    def __del__(self):
        proxy_db.dereference(self)


def proxy(target, readonly=False, shallow=False):
    """
    Returns a Proxy for the given object. If a proxy for the given
    configuration already exists, it will return that instead of
    creating a new one.

    Please be aware: this only works on plain data types!
    """
    # We can only wrap the following datatypes
    if not isinstance(target, (dict, list, tuple, set)):
        return target
    # The object may be a proxy already
    # (exception is when we want a readonly proxy on a writable proxy)
    # FIXME: Could be that we also have to check for shallow??
    # https://github.com/vuejs/vue-next/blob/master/packages/reactivity/src/reactive.ts#L195
    # target[ReactiveFlags.RAW] && !(isReadonly && target[ReactiveFlags.IS_REACTIVE])
    # We could also just use:
    #   if isinstance()
    if isinstance(target, Proxy) and not (readonly and not target.readonly):
        return target
    # There may already be a proxy for this object
    if (
        existing_proxy := proxy_db.get_proxy(target, readonly=readonly, shallow=shallow)
    ) is not None:
        return existing_proxy
    # Otherwise, create a new proxy
    proxy_type = None
    if isinstance(target, dict):
        proxy_type = DictProxy if not readonly else ReadonlyDictProxy
    elif isinstance(target, list):
        proxy_type = ListProxy if not readonly else ReadonlyListProxy
    elif isinstance(target, set):
        proxy_type = SetProxy if not readonly else ReadonlySetProxy
    elif isinstance(target, tuple):
        # FIXME: think of what needs to be done for tuple
        proxy_type = Proxy
    return proxy_type(target, readonly=readonly, shallow=shallow)


def reactive(target):
    return proxy(target)


def readonly(target):
    return proxy(target, readonly=True)


def shallow_reactive(target):
    return proxy(target, shallow=True)


def shallow_readonly(target):
    return proxy(target, shallow=True, readonly=True)


def read_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self, *args, **kwargs):
        # If we are tracking changes
        if Dep.stack:
            # Mark as a dependency
            proxy_db.attrs(self)["dep"].depend()
        value = fn(self.target, *args, **kwargs)
        if self.shallow:
            return value
        return proxy(value, readonly=self.readonly)

    return trap


def read_key_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def inner(self, *args, **kwargs):
        # If we are tracking changes
        if Dep.stack:
            # Mark as a dependency
            key = args[0]
            proxy_db.attrs(self)["keydep"][key].depend()
        return fn(self.target, *args, **kwargs)

    return inner


def write_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def inner(self, *args, **kwargs):
        args = tuple(observe(a) for a in args)
        kwargs = {k: observe(v) for k, v in kwargs.items()}
        retval = fn(self.target, *args, **kwargs)
        # TODO: prevent firing if value hasn't actually changed?
        proxy_db.attrs(self)["dep"].notify()
        return retval

    return inner


def write_key_trap(method, obj_cls):
    fn = getattr(obj_cls, method)
    getitem_fn = getattr(obj_cls, "__getitem__")

    @wraps(fn)
    def inner(self, *args, **kwargs):
        key = args[0]
        is_new = key not in proxy_db.attrs(self)["keydep"]
        old_value = getitem_fn(self.target, key) if not is_new else None
        args = [key] + [observe(a) for a in args[1:]]
        kwargs = {k: observe(v) for k, v in kwargs.items()}
        retval = fn(self.target, *args, **kwargs)
        new_value = getitem_fn(self.target, key)
        if is_new:
            proxy_db.attrs(self)["keydep"][key] = Dep()
        if old_value != new_value:
            proxy_db.attrs(self)["keydep"][key].notify()
            proxy_db.attrs(self)["dep"].notify()
        return retval

    return inner


def delete_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def inner(self, *args, **kwargs):
        retval = fn(self.target, *args, **kwargs)
        proxy_db.attrs(self)["dep"].notify()
        for key in self._orphaned_keydeps():
            proxy_db.attrs(self)["keydep"][key].notify()
            del proxy_db.attrs(self)["keydep"][key]
        return retval

    return inner


def delete_key_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def inner(self, *args, **kwargs):
        retval = fn(self.target, *args, **kwargs)
        key = args[0]
        proxy_db.attrs(self)["dep"].notify()
        proxy_db.attrs(self)["keydep"][key].notify()
        del proxy_db.attrs(self)["keydep"][key]
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
            # trap = trap_map[trap_type](method, proxy_cls, obj_cls)
            trap = trap_map[trap_type](method, obj_cls)
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
    },
    "KEYREADERS": {
        "get",
        "__contains__",
        "__getitem__",
    },
    "WRITERS": {
        "update",
    },
    "KEYWRITERS": {
        "setdefault",
        "__setitem__",
    },
    "DELETERS": {
        "clear",
        "popitem",
    },
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


class DictProxyBase(Proxy):
    def __init__(self, target, readonly=False, shallow=False):
        super().__init__(target, readonly=readonly, shallow=shallow)

    def _orphaned_keydeps(self):
        return set(proxy_db.attrs(self)["keydep"].keys()) - set(self.target.keys())


class DictProxy(DictProxyBase):
    pass


class ReadonlyDictProxy(DictProxyBase):
    def __init__(self, target, shallow=False, **kwargs):
        super().__init__(target, shallow=shallow, **{**kwargs, "readonly": True})


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
    },
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
    },
}


class ListProxyBase(Proxy):
    def __init__(self, target, readonly=False, shallow=False):
        super().__init__(target, readonly=readonly, shallow=shallow)


class ListProxy(ListProxyBase):
    pass


class ReadonlyListProxy(ListProxyBase):
    def __init__(self, target, shallow=False, **kwargs):
        super().__init__(target, shallow=shallow, **{**kwargs, "readonly": True})


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
    },
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
    },
}


class SetProxyBase(Proxy):
    def __init__(self, target, readonly=False, shallow=False):
        super().__init__(target, readonly=readonly, shallow=shallow)


class SetProxy(SetProxyBase):
    pass


class ReadonlySetProxy(SetProxyBase):
    def __init__(self, target, shallow=False, **kwargs):
        super().__init__(target, shallow=shallow, **{**kwargs, "readonly": True})


make_observable(SetProxy, set, set_traps, trap_map)
make_observable(ReadonlySetProxy, set, set_traps, trap_map_readonly)


def observe(target, deep=True):
    return reactive(target=target)
