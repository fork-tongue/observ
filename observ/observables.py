"""
observe converts plain datastructures (dict, list, set) to
proxied versions of those datastructures to make them reactive.
"""
from copy import copy
from functools import partial, wraps
import gc
import sys
from weakref import WeakValueDictionary

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
        gc.callbacks.append(self.cleanup)

    def cleanup(self, phase, info):
        """
        Callback for garbage collector to cleanup the db for targets
        that have no other references outside of the db
        """
        # TODO: maybe also run on start? Check performance
        if phase != "stop":
            return

        keys_to_delete = []
        for key, value in self.db.items():
            # Refs:
            # - sys.getrefcount
            # - ref in db item
            if sys.getrefcount(value["target"]) <= 2:
                # We are the last to hold a reference!
                keys_to_delete.append(key)

        for keys in keys_to_delete:
            del self.db[keys]

    def reference(self, proxy):
        """
        Adds a reference to the collection for the wrapped object's id
        """
        obj_id = id(proxy.target)

        if obj_id not in self.db:
            attrs = {
                "dep": Dep(),
            }
            if isinstance(proxy.target, dict):
                attrs["keydep"] = {key: Dep() for key in proxy.target.keys()}
            self.db[obj_id] = {
                "target": proxy.target,
                "attrs": attrs,  # dep, keydep
                # keyed on tuple(readonly, shallow)
                "proxies": WeakValueDictionary(),
            }

        # Use setdefault to put the proxy in the proxies dict. If there
        # was an existing value, it will return that instead. There shouldn't
        # be an existing value, so we can compare the objects to see if we
        # should raise an exception.
        # Seems to be a tiny bit faster than checking beforehand if
        # there is already an existing value in the proxies dict
        result = self.db[obj_id]["proxies"].setdefault(
            (proxy.readonly, proxy.shallow), proxy
        )
        if result is not proxy:
            raise RuntimeError("Proxy with existing configuration already in db")

    def dereference(self, proxy):
        """
        Removes a reference from the database for the given proxy
        """
        obj_id = id(proxy.target)
        if obj_id not in self.db:
            # When there are failing tests, it might happen that proxies
            # are garbage collected at a point where the proxy_db is already
            # cleared. That's why we need this check here.
            # See fixture [clear_proxy_db](/tests/conftest.py:clear_proxy_db)
            # for more info.
            return

        # The given proxy is the last proxy in the WeakValueDictionary,
        # so now is a good moment to see if can remove clean the deps
        # for the target object
        if len(self.db[obj_id]["proxies"]) == 1:
            ref_count = sys.getrefcount(self.db[obj_id]["target"])
            # Ref count is still 3 here because of the reference through proxy.target
            if ref_count <= 3:
                # We are the last to hold a reference!
                del self.db[obj_id]

    def attrs(self, proxy):
        return self.db[id(proxy.target)]["attrs"]

    def get_proxy(self, target, readonly=False, shallow=False):
        """
        Returns a proxy from the collection for the given object and configuration.
        Will return None if there is no proxy for the object's id.
        """
        if id(target) not in self.db:
            return None
        return self.db[id(target)]["proxies"].get((readonly, shallow))


# Create a global proxy collection
proxy_db = ProxyDb()


class Proxy:
    """
    Proxy for an object/target.

    Instantiating a Proxy will add a reference to the global proxy_db and
    destroying a Proxy will remove that reference.

    Please use the `proxy` method to get a proxy for a certain object instead
    of directly creating one yourself. The `proxy` method will either create
    or return an existing proxy and makes sure that the db stays consistent.
    """

    __hash__ = None

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
    # The object may be a proxy already, so check if it matches the
    # given configuration (readonly and shallow)
    if isinstance(target, Proxy):
        if readonly == target.readonly and shallow == target.shallow:
            return target
        else:
            # If the configuration does not match,
            # unwrap the target from the proxy so that the right
            # kind of proxy can be returned in the next part of
            # this function
            target = target.target

    # Note that at this point, target is always a non-proxy object
    # Check the proxy_db to see if there's already a proxy for the target object
    existing_proxy = proxy_db.get_proxy(target, readonly=readonly, shallow=shallow)
    if existing_proxy is not None:
        return existing_proxy

    # We can only wrap the following datatypes
    if not isinstance(target, (dict, list, tuple, set)):
        return target

    # Otherwise, create a new proxy
    proxy_type = None
    if isinstance(target, dict):
        proxy_type = DictProxy if not readonly else ReadonlyDictProxy
    elif isinstance(target, list):
        proxy_type = ListProxy if not readonly else ReadonlyListProxy
    elif isinstance(target, set):
        proxy_type = SetProxy if not readonly else ReadonlySetProxy
    elif isinstance(target, tuple):
        return tuple(proxy(x, readonly=readonly, shallow=shallow) for x in target)
    return proxy_type(target, readonly=readonly, shallow=shallow)


class StateModifiedError(Exception):
    """
    Raised when a proxy is modified in a watched (or computed) expression.
    """

    pass


def read_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self, *args, **kwargs):
        if Dep.stack:
            proxy_db.attrs(self)["dep"].depend()
        value = fn(self.target, *args, **kwargs)
        if self.shallow:
            return value
        return proxy(value, readonly=self.readonly)

    return trap


def iterate_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def trap(self, *args, **kwargs):
        if Dep.stack:
            proxy_db.attrs(self)["dep"].depend()
        iterator = fn(self.target, *args, **kwargs)
        if self.shallow:
            return iterator
        if method == "items":
            return (
                (key, proxy(value, readonly=self.readonly)) for key, value in iterator
            )
        else:
            proxied = partial(proxy, readonly=self.readonly)
            return map(proxied, iterator)

    return trap


def read_key_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def inner(self, *args, **kwargs):
        if Dep.stack:
            key = args[0]
            proxy_db.attrs(self)["keydep"][key].depend()
        value = fn(self.target, *args, **kwargs)
        if self.shallow:
            return value
        return proxy(value, readonly=self.readonly)

    return inner


def write_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def inner(self, *args, **kwargs):
        if Dep.stack:
            raise StateModifiedError()
        args = tuple(proxy(a) for a in args)
        kwargs = {k: proxy(v) for k, v in kwargs.items()}
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
        if Dep.stack:
            raise StateModifiedError()
        key = args[0]
        is_new = key not in proxy_db.attrs(self)["keydep"]
        old_value = getitem_fn(self.target, key) if not is_new else None
        args = [key] + [proxy(a) for a in args[1:]]
        kwargs = {k: proxy(v) for k, v in kwargs.items()}
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
        if Dep.stack:
            raise StateModifiedError()
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
        if Dep.stack:
            raise StateModifiedError()
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
    "ITERATORS": iterate_trap,
    "WRITERS": write_trap,
    "KEYWRITERS": write_key_trap,
    "DELETERS": delete_trap,
    "KEYDELETERS": delete_key_trap,
}


class ReadonlyError(Exception):
    """
    Raised when a readonly proxy is modified.
    """

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
    "ITERATORS": iterate_trap,
    "WRITERS": readonly_trap,
    "KEYWRITERS": readonly_trap,
    "DELETERS": readonly_trap,
    "KEYDELETERS": readonly_trap,
}


def bind_traps(proxy_cls, obj_cls, traps, trap_map):
    for trap_type, methods in traps.items():
        for method in methods:
            trap = trap_map[trap_type](method, obj_cls)
            setattr(proxy_cls, method, trap)


dict_traps = {
    "READERS": {
        "copy",
        "__eq__",
        "__format__",
        "__ge__",
        "__gt__",
        "__le__",
        "__len__",
        "__lt__",
        "__ne__",
        "__repr__",
        "__sizeof__",
        "__str__",
        "keys",
    },
    "KEYREADERS": {
        "get",
        "__contains__",
        "__getitem__",
    },
    "ITERATORS": {
        "items",
        "values",
        "__iter__",
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
    dict_traps["ITERATORS"].add("__reversed__")
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


bind_traps(DictProxy, dict, dict_traps, trap_map)
bind_traps(ReadonlyDictProxy, dict, dict_traps, trap_map_readonly)


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
        "__len__",
        "__repr__",
        "__str__",
        "__format__",
        "__sizeof__",
    },
    "ITERATORS": {
        "__iter__",
        "__reversed__",
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


bind_traps(ListProxy, list, list_traps, trap_map)
bind_traps(ReadonlyListProxy, list, list_traps, trap_map_readonly)


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
    "ITERATORS": {
        "__iter__",
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


bind_traps(SetProxy, set, set_traps, trap_map)
bind_traps(ReadonlySetProxy, set, set_traps, trap_map_readonly)


def to_raw(target):
    """
    Returns a raw object from which any trace of proxy has been replaced
    with its wrapped target value.
    """
    if isinstance(target, Proxy):
        return to_raw(target.target)

    if isinstance(target, list):
        tcopy = copy(target)
        for idx, value in enumerate(tcopy):
            tcopy[idx] = to_raw(value)
        return tcopy

    if isinstance(target, dict):
        target = copy(target)
        for key, value in target.items():
            target[key] = to_raw(value)
        return target

    if isinstance(target, tuple):
        return tuple(map(to_raw, target))

    if isinstance(target, set):
        return target

    return target
