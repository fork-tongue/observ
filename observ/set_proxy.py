from .proxy import TYPE_LOOKUP, Proxy
from .traps import construct_methods_traps_dict, trap_map, trap_map_readonly

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


class SetProxyBase(Proxy[set]):
    pass


def readonly_set_proxy_init(self, target, shallow=False, **kwargs):
    super(ReadonlySetProxy, self).__init__(
        target, shallow=shallow, **{**kwargs, "readonly": True}
    )


SetProxy = type(
    "SetProxy", (SetProxyBase,), construct_methods_traps_dict(set, set_traps, trap_map)
)
ReadonlySetProxy = type(
    "ReadonlysetProxy",
    (SetProxyBase,),
    {
        "__init__": readonly_set_proxy_init,
        **construct_methods_traps_dict(set, set_traps, trap_map_readonly),
    },
)


def type_test(target):
    return isinstance(target, set)


TYPE_LOOKUP[type_test] = (SetProxy, ReadonlySetProxy)
