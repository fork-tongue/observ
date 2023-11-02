from .observables import TYPE_LOOKUP
from .proxy import Proxy
from .traps import map_traps, trap_map, trap_map_readonly


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


def readonly_set__init__(self, target, shallow=False, **kwargs):
    super(ReadonlySetProxy, self).__init__(
        target, shallow=shallow, **{**kwargs, "readonly": True}
    )


SetProxy = type("SetProxy", (SetProxyBase,), map_traps(set, set_traps, trap_map))
ReadonlySetProxy = type(
    "ReadonlysetProxy",
    (SetProxyBase,),
    {
        "__init__": readonly_set__init__,
        **map_traps(set, set_traps, trap_map_readonly),
    },
)

TYPE_LOOKUP[set] = (SetProxy, ReadonlySetProxy)
