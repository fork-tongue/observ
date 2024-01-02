from .proxy import TYPE_LOOKUP, Proxy
from .traps import construct_methods_traps_dict, trap_map, trap_map_readonly

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


class ListProxyBase(Proxy[list]):
    pass


def readonly_list_proxy_init(self, target, shallow=False, **kwargs):
    super(ReadonlyListProxy, self).__init__(
        target, shallow=shallow, **{**kwargs, "readonly": True}
    )


ListProxy = type(
    "ListProxy",
    (ListProxyBase,),
    construct_methods_traps_dict(list, list_traps, trap_map),
)
ReadonlyListProxy = type(
    "ReadonlyListProxy",
    (ListProxyBase,),
    {
        "__init__": readonly_list_proxy_init,
        **construct_methods_traps_dict(list, list_traps, trap_map_readonly),
    },
)


def type_test(target):
    return isinstance(target, list)


TYPE_LOOKUP[type_test] = (ListProxy, ReadonlyListProxy)
