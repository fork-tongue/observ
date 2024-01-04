from observ.object_proxy import ObjectProxy


class Foo:
    __slots__ = ("bar",)

    def __init__(self, bar=5):
        self.bar = bar


def test_object_proxying():
    obj = Foo(bar=5)
    proxy = ObjectProxy(obj)
    assert proxy.bar == 5
    proxy.bar = 6
    assert proxy.bar == 6

