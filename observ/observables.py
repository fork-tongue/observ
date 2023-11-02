"""
observe converts plain datastructures (dict, list, set) to
proxied versions of those datastructures to make them reactive.
"""
from functools import partial, wraps
from operator import xor
import sys

from .dep import Dep
from .proxy_db import proxy_db


# TODO: separate file
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

    for target_type, (writable_proxy_type, readonly_proxy_type) in TYPE_LOOKUP.items():
        if isinstance(target, target_type):
            proxy_type = readonly_proxy_type if readonly else writable_proxy_type
            break
    else:
        if isinstance(target, tuple):
            return tuple(proxy(x, readonly=readonly, shallow=shallow) for x in target)

    return proxy_type(target, readonly=readonly, shallow=shallow)


reactive = proxy
readonly = partial(proxy, readonly=True)
shallow_reactive = partial(proxy, shallow=True)
shallow_readonly = partial(proxy, shallow=True, readonly=True)


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
            keydeps = proxy_db.attrs(self)["keydep"]
            if key not in keydeps:
                keydeps[key] = Dep()
            keydeps[key].depend()
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
        old = self.target.copy()
        retval = fn(self.target, *args, **kwargs)
        attrs = proxy_db.attrs(self)
        if obj_cls == dict:
            change_detected = False
            keydeps = attrs["keydep"]
            for key, val in self.target.items():
                if old.get(key) is not val:
                    if key in keydeps:
                        keydeps[key].notify()
                    else:
                        keydeps[key] = Dep()
                    change_detected = True
            if change_detected:
                attrs["dep"].notify()
        else:  # list and set
            if self.target != old:
                attrs["dep"].notify()

        return retval

    return inner


def write_key_trap(method, obj_cls):
    fn = getattr(obj_cls, method)
    getitem_fn = getattr(obj_cls, "get")

    @wraps(fn)
    def inner(self, *args, **kwargs):
        if Dep.stack:
            raise StateModifiedError()
        key = args[0]
        attrs = proxy_db.attrs(self)
        is_new = key not in attrs["keydep"]
        old_value = getitem_fn(self.target, key) if not is_new else None
        retval = fn(self.target, *args, **kwargs)
        if method == "setdefault" and not self.shallow:
            # This method is only available when readonly is false
            retval = reactive(retval)

        new_value = getitem_fn(self.target, key)
        if is_new:
            attrs["keydep"][key] = Dep()
        if xor(old_value is None, new_value is None) or old_value != new_value:
            attrs["keydep"][key].notify()
            attrs["dep"].notify()
        return retval

    return inner


def delete_trap(method, obj_cls):
    fn = getattr(obj_cls, method)

    @wraps(fn)
    def inner(self, *args, **kwargs):
        if Dep.stack:
            raise StateModifiedError()
        retval = fn(self.target, *args, **kwargs)
        attrs = proxy_db.attrs(self)
        attrs["dep"].notify()
        for key in self._orphaned_keydeps():
            attrs["keydep"][key].notify()
            del attrs["keydep"][key]
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
        attrs = proxy_db.attrs(self)
        attrs["dep"].notify()
        attrs["keydep"][key].notify()
        del attrs["keydep"][key]
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


def map_traps(obj_cls, traps, trap_map):
    return {
        method: trap_map[trap_type](method, obj_cls)
        for trap_type, methods in traps.items()
        for method in methods
    }


# TODO: separate files for dict, list, set classes

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


# class type(name, bases, dict, **kwds)


class DictProxyBase(Proxy):
    def __init__(self, target, readonly=False, shallow=False):
        super().__init__(target, readonly=readonly, shallow=shallow)

    def _orphaned_keydeps(self):
        return set(proxy_db.attrs(self)["keydep"].keys()) - set(self.target.keys())


def readonly_dict_proxy__init__(self, target, shallow=False, **kwargs):
    super(ReadonlyDictProxy, self).__init__(
        target, shallow=shallow, **{**kwargs, "readonly": True}
    )


DictProxy = type("DictProxy", (DictProxyBase,), map_traps(dict, dict_traps, trap_map))
ReadonlyDictProxy = type(
    "ReadonlyDictProxy",
    (DictProxyBase,),
    {
        "__init__": readonly_dict_proxy__init__,
        **map_traps(dict, dict_traps, trap_map_readonly),
    },
)


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


def readonly_list__init__(self, target, shallow=False, **kwargs):
    super(ReadonlyListProxy, self).__init__(
        target, shallow=shallow, **{**kwargs, "readonly": True}
    )


ListProxy = type("ListProxy", (ListProxyBase,), map_traps(list, list_traps, trap_map))
ReadonlyListProxy = type(
    "ReadonlyListProxy",
    (ListProxyBase,),
    {
        "__init__": readonly_list__init__,
        **map_traps(list, list_traps, trap_map_readonly),
    },
)


TYPE_LOOKUP = {
    dict: (DictProxy, ReadonlyDictProxy),
    list: (ListProxy, ReadonlyListProxy),
}


# TODO: pair with proxy function
def to_raw(target):
    """
    Returns a raw object from which any trace of proxy has been replaced
    with its wrapped target value.
    """
    if isinstance(target, Proxy):
        return to_raw(target.target)

    if isinstance(target, list):
        return [to_raw(t) for t in target]

    if isinstance(target, dict):
        return {key: to_raw(value) for key, value in target.items()}

    if isinstance(target, tuple):
        return tuple(to_raw(t) for t in target)

    if isinstance(target, set):
        return {to_raw(t) for t in target}

    return target
