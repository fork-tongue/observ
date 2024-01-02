from dataclasses import dataclass

from observ.object_proxy import ObjectProxy
from observ.proxy import proxy
from observ.traps import ReadonlyError


@dataclass
class Foo:
    bar: int


def test_dataclass_proxy():
    data = Foo(bar=5)
    proxied = proxy(data)
    assert isinstance(proxied, ObjectProxy)
