from operator import xor

from .dep import Dep
from .object_utils import get_object_attrs
from .proxy import TYPE_LOOKUP, Proxy, proxy
from .proxy_db import proxy_db
from .traps import ReadonlyError


class ObjectProxyBase(Proxy):
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
                return retval

        new_value = getattr(target, name, None)
        if is_new_keydep:
            attrs["keydep"][name] = Dep()
        if xor(old_value is None, new_value is None) or old_value != new_value:
            attrs["keydep"][name].notify()
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

        if is_target_attr and is_keydep:
            attrs["keydep"][name].notify()
            del attrs["keydep"][name]

        return retval


def passthrough(method):
    def trap(self, *args, **kwargs):
        fn = getattr(self.__target__, method, None)
        if fn is None:
            # we don't cache this
            # since it is possible a class is dynamically modified later
            # invalidating the cached result...
            raise TypeError(f"object of type '{type(self)}' has no {method}")
        return fn(*args, **kwargs)

    return trap


# TODO: how to verify this is the correct and complete set of magic methods?
# scraped from https://docs.python.org/3/reference/datamodel.html
# as of py3.12
magic_methods = [
    "__abs__",
    "__add__",
    "__aenter__",
    "__aexit__",
    "__aiter__",
    "__and__",
    "__anext__",
    "__annotations__",
    "__await__",
    "__bases__",
    "__bool__",
    "__buffer__",
    "__bytes__",
    "__call__",
    "__ceil__",
    "__class__",
    "__class_getitem__",
    # '__classcell__',
    "__closure__",
    "__code__",
    "__complex__",
    "__contains__",
    "__defaults__",
    # '__del__',
    # '__delattr__',
    "__delete__",
    "__delitem__",
    "__dict__",
    "__dir__",
    "__divmod__",
    "__doc__",
    "__enter__",
    "__eq__",
    "__exit__",
    "__file__",
    "__float__",
    "__floor__",
    "__floordiv__",
    "__format__",
    "__func__",
    "__future__",
    "__ge__",
    "__get__",
    # "__getattr__",
    # '__getattribute__',
    "__getitem__",
    "__globals__",
    "__gt__",
    "__hash__",
    "__iadd__",
    "__iand__",
    "__ifloordiv__",
    "__ilshift__",
    "__imatmul__",
    "__imod__",
    "__import__",
    "__imul__",
    "__index__",
    # '__init__',
    "__init_subclass__",
    "__instancecheck__",
    "__int__",
    "__invert__",
    "__ior__",
    "__ipow__",
    "__irshift__",
    "__isub__",
    "__iter__",
    "__itruediv__",
    "__ixor__",
    "__kwdefaults__",
    "__le__",
    "__len__",
    "__length_hint__",
    "__lshift__",
    "__lt__",
    "__match_args__",
    "__matmul__",
    "__missing__",
    "__mod__",
    "__module__",
    "__mro__",
    "__mro_entries__",
    "__mul__",
    "__name__",
    "__ne__",
    "__neg__",
    # '__new__',
    "__next__",
    "__objclass__",
    "__or__",
    "__pos__",
    "__pow__",
    "__prepare__",
    # '__qualname__',
    "__radd__",
    "__rand__",
    "__rdivmod__",
    "__release_buffer__",
    "__repr__",
    "__reversed__",
    "__rfloordiv__",
    "__rlshift__",
    "__rmatmul__",
    "__rmod__",
    "__rmul__",
    "__ror__",
    "__round__",
    "__rpow__",
    "__rrshift__",
    "__rshift__",
    "__rsub__",
    "__rtruediv__",
    "__rxor__",
    "__self__",
    "__set__",
    "__set_name__",
    # '__setattr__',
    "__setitem__",
    # '__slots__',
    "__str__",
    "__sub__",
    "__subclasscheck__",
    "__traceback__",
    "__truediv__",
    "__trunc__",
    "__type_params__",
    "__weakref__",
    "__xor__",
]


ObjectProxy = type(
    "ObjectProxy",
    (ObjectProxyBase,),
    {method: passthrough(method) for method in magic_methods},
)


class ReadonlyObjectProxy(ObjectProxy):
    def __init__(self, target, shallow=False, **kwargs):
        super().__init__(target, shallow=shallow, **{**kwargs, "readonly": True})


def type_test(target):
    # exclude builtin objects
    # exclude objects for which we have better proxies available
    # exclude ndarrays
    return not isinstance(target, (list, set, dict, tuple)) and type(
        target
    ).__module__ not in (object.__module__, "numpy")


TYPE_LOOKUP[type_test] = (ObjectProxy, ReadonlyObjectProxy)
