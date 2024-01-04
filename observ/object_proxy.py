from operator import xor

from .dep import Dep
from .proxy import proxy
from .proxy_db import proxy_db

from .proxy import TYPE_LOOKUP, Proxy
from .proxy_db import proxy_db


class ObjectProxy(Proxy):
    def __getattribute__(self, name):
        if name in Proxy.__slots__:
            return super().__getattribute__(name)

        if Dep.stack:
            keydeps = proxy_db.attrs(self)["keydep"]
            if name not in keydeps:
                keydeps[name] = Dep()
            keydeps[name].depend()
        value = getattr(self.target, name)
        if self.shallow:
            return value
        return proxy(value, readonly=self.readonly)

    def __setattr__(self, name, value):
        if name in Proxy.__slots__:
            return super().__setattr__(name, value)

        attrs = proxy_db.attrs(self)
        is_new = name not in attrs["keydep"]
        old_value = getattr(self.target, name, None)  # if not is_new else None
        retval = setattr(self.target, name, value)
        new_value = getattr(self.target, name, None)
        if is_new:
            attrs["keydep"][name] = Dep()
        if xor(old_value is None, new_value is None) or old_value != new_value:
            attrs["keydep"][name].notify()
            attrs["dep"].notify()
        return retval

    def __delattr__(self, name):
        if name in Proxy.__slots__:
            return super().__delattr__(name)
        retval = delattr(self.target, name)
        attrs = proxy_db.attrs(self)
        attrs["dep"].notify()
        attrs["keydep"][name].notify()
        del attrs["keydep"][name]
        return retval


class ReadonlyObjectProxy(ObjectProxy):
    def __init__(self, target, shallow=False, **kwargs):
        super().__init__(
            target, shallow=shallow, **{**kwargs, "readonly": True}
        )


def type_test(target):
    # exclude builtin objects
    return isinstance(target, object) and type(target).__module__ != object.__module__


TYPE_LOOKUP[type_test] = (ObjectProxy, ReadonlyObjectProxy)
