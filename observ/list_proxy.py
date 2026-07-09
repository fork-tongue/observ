from __future__ import annotations

from typing import Any, cast

from .proxy import TYPE_LOOKUP, Proxy
from .traps import construct_methods_traps_dict, trap_map, trap_map_readonly

list_traps: dict[str, set[str]] = {
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
    __slots__ = ()


def readonly_list_proxy_init(
    self: ListProxyBase, target: list, shallow: bool = False, **kwargs: Any
) -> None:
    super(ReadonlyListProxy, self).__init__(
        target, shallow=shallow, **{**kwargs, "readonly": True}
    )


# The proxy classes are assembled dynamically from the trap functions,
# which the type system cannot see; cast them to their actual shape
ListProxy = cast(
    "type[ListProxyBase]",
    type(
        "ListProxy",
        (ListProxyBase,),
        {
            "__slots__": (),
            **construct_methods_traps_dict(list, list_traps, trap_map),
        },
    ),
)
ReadonlyListProxy = cast(
    "type[ListProxyBase]",
    type(
        "ReadonlyListProxy",
        (ListProxyBase,),
        {
            "__slots__": (),
            "__init__": readonly_list_proxy_init,
            **construct_methods_traps_dict(list, list_traps, trap_map_readonly),
        },
    ),
)


TYPE_LOOKUP[list] = (ListProxy, ReadonlyListProxy)
