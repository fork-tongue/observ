from operator import xor

from .dep import Dep
from .object_utils import get_object_attrs
from .proxy import TYPE_LOOKUP, Proxy, proxy
from .proxy_db import proxy_db
from .traps import ReadonlyError


class ObjectProxy(Proxy):
    def __getattribute__(self, name):
        if name in Proxy.__slots__:
            return super().__getattribute__(name)

        target = self.__target__
        target_attrs = get_object_attrs(target)
        if name not in target_attrs:
            return getattr(target, name)

        if Dep.stack:
            keydeps = proxy_db.attrs(self)["keydep"]
            if name not in keydeps:
                keydeps[name] = Dep()
            keydeps[name].depend()
        value = getattr(target, name)
        if self.__shallow__:
            return value
        return proxy(value, readonly=self.__readonly__)

    def __setattr__(self, name, value):
        if name in Proxy.__slots__:
            return super().__setattr__(name, value)

        if self.__readonly__:
            raise ReadonlyError()

        target = self.__target__
        target_attrs = get_object_attrs(target)
        attrs = proxy_db.attrs(self)
        is_new_keydep = name not in attrs["keydep"]
        is_new_target_attr = name not in target_attrs

        old_value = getattr(target, name, None) if not is_new_target_attr else None
        retval = setattr(target, name, value)

        if is_new_keydep:
            # we have not determined earlier that this attr
            # should be reactive, so let's determine it now
            target_attrs_new = get_object_attrs(target)
            if name not in target_attrs_new:
                # the set attr is not stateful (e.g. someone
                # is attaching a bound method)
                # so no need to track this modification
                # TODO: we could cache this maybe?
                return retval

        new_value = getattr(target, name, None)
        if is_new_keydep:
            attrs["keydep"][name] = Dep()
        if xor(old_value is None, new_value is None) or old_value != new_value:
            attrs["keydep"][name].notify()
            attrs["dep"].notify()
        return retval

    def __delattr__(self, name):
        if name in Proxy.__slots__:
            return super().__delattr__(name)

        if self.__readonly__:
            raise ReadonlyError()

        target = self.__target__
        target_attrs = get_object_attrs(target)
        attrs = proxy_db.attrs(self)
        is_keydep = name in attrs["keydep"]
        is_target_attr = name in target_attrs

        retval = delattr(target, name)

        if is_target_attr:
            attrs["dep"].notify()
            if is_keydep:
                attrs["keydep"][name].notify()
                del attrs["keydep"][name]

        return retval


class ReadonlyObjectProxy(ObjectProxy):
    def __init__(self, target, shallow=False, **kwargs):
        super().__init__(target, shallow=shallow, **{**kwargs, "readonly": True})


def type_test(target):
    # exclude builtin objects and objects for which we have better proxies available
    return (
        not isinstance(target, (list, set, dict, tuple))
        and type(target).__module__ != object.__module__
    )


TYPE_LOOKUP[type_test] = (ObjectProxy, ReadonlyObjectProxy)
