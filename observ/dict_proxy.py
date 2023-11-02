from .proxy import Proxy, TYPE_LOOKUP
from .traps import construct_methods_traps_dict, trap_map, trap_map_readonly


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
        "__or__",
        "__ror__",
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
        "__reversed__",
    },
    "WRITERS": {
        "update",
        "__ior__",
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


class DictProxyBase(Proxy):
    def _orphaned_keydeps(self):
        return set(self.proxy_db.attrs(self)["keydep"].keys()) - set(self.target.keys())


def readonly_dict_proxy_init(self, target, shallow=False, **kwargs):
    super(ReadonlyDictProxy, self).__init__(
        target, shallow=shallow, **{**kwargs, "readonly": True}
    )


DictProxy = type(
    "DictProxy",
    (DictProxyBase,),
    construct_methods_traps_dict(dict, dict_traps, trap_map),
)
ReadonlyDictProxy = type(
    "ReadonlyDictProxy",
    (DictProxyBase,),
    {
        "__init__": readonly_dict_proxy_init,
        **construct_methods_traps_dict(dict, dict_traps, trap_map_readonly),
    },
)

TYPE_LOOKUP[dict] = (DictProxy, ReadonlyDictProxy)
