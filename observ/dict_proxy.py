import sys

from .observables import map_traps, Proxy, trap_map, trap_map_readonly, TYPE_LOOKUP
from .proxy_db import proxy_db

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

TYPE_LOOKUP[dict] = (DictProxy, ReadonlyDictProxy)
