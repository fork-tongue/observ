from .observables import map_traps, Proxy, trap_map, trap_map_readonly, TYPE_LOOKUP

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


TYPE_LOOKUP[list] = (ListProxy, ReadonlyListProxy)
