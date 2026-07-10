from __future__ import annotations

from typing import cast

from .proxy import TYPE_LOOKUP, Proxy
from .traps import construct_methods_traps_dict, trap_map, trap_map_readonly

set_traps: dict[str, set[str]] = {
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
    __slots__ = ()


def readonly_set_proxy_init(
    self: SetProxyBase, target: set, readonly: bool = True, shallow: bool = False
) -> None:
    # The signature lines up with Proxy.__init__ so that proxy() can
    # construct any proxy type positionally; the readonly argument is
    # ignored, a ReadonlySetProxy is always readonly
    super(ReadonlySetProxy, self).__init__(target, True, shallow)


# The proxy classes are assembled dynamically from the trap functions,
# which the type system cannot see; cast them to their actual shape
SetProxy = cast(
    "type[SetProxyBase]",
    type(
        "SetProxy",
        (SetProxyBase,),
        {"__slots__": (), **construct_methods_traps_dict(set, set_traps, trap_map)},
    ),
)
ReadonlySetProxy = cast(
    "type[SetProxyBase]",
    type(
        "ReadonlysetProxy",
        (SetProxyBase,),
        {
            "__slots__": (),
            "__init__": readonly_set_proxy_init,
            **construct_methods_traps_dict(set, set_traps, trap_map_readonly),
        },
    ),
)


TYPE_LOOKUP[set] = (SetProxy, ReadonlySetProxy)
