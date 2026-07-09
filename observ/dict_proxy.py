from __future__ import annotations

from typing import Any, cast

from .proxy import TYPE_LOOKUP, Proxy
from .traps import construct_methods_traps_dict, trap_map, trap_map_readonly

dict_traps: dict[str, set[str]] = {
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


class DictProxyBase(Proxy[dict]):
    __slots__ = ()

    def _orphaned_keydeps(self) -> set[Any]:
        keydeps = self.__dep__.keydeps
        if keydeps is None:
            return set()
        return set(keydeps.keys()) - set(self.__target__.keys())


def readonly_dict_proxy_init(
    self: DictProxyBase, target: dict, shallow: bool = False, **kwargs: Any
) -> None:
    super(ReadonlyDictProxy, self).__init__(
        target, shallow=shallow, **{**kwargs, "readonly": True}
    )


# The proxy classes are assembled dynamically from the trap functions,
# which the type system cannot see; cast them to their actual shape
DictProxy = cast(
    "type[DictProxyBase]",
    type(
        "DictProxy",
        (DictProxyBase,),
        {
            "__slots__": (),
            **construct_methods_traps_dict(dict, dict_traps, trap_map),
        },
    ),
)
ReadonlyDictProxy = cast(
    "type[DictProxyBase]",
    type(
        "ReadonlyDictProxy",
        (DictProxyBase,),
        {
            "__slots__": (),
            "__init__": readonly_dict_proxy_init,
            **construct_methods_traps_dict(dict, dict_traps, trap_map_readonly),
        },
    ),
)


TYPE_LOOKUP[dict] = (DictProxy, ReadonlyDictProxy)
