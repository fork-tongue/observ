__version__ = "0.3.0"


from collections.abc import Container
from functools import wraps
from itertools import count
import sys
from typing import Any
from weakref import WeakSet


class Dep:
    stack = []

    def __init__(self) -> None:
        self._subs = WeakSet()

    def add_sub(self, sub: "Watcher") -> None:
        self._subs.add(sub)

    def remove_sub(self, sub: "Watcher") -> None:
        self._subs.remove(sub)

    def depend(self) -> None:
        if self.stack:
            self.stack[-1].add_dep(self)

    def notify(self) -> None:
        for sub in sorted(self._subs, key=lambda s: s.id):
            sub.update()


def traverse(obj):
    _traverse(obj, set())


def _traverse(obj, seen):
    seen.add(id(obj))
    if isinstance(obj, dict):
        val_iter = iter(obj.values())
    elif isinstance(obj, (list, tuple, set)):
        val_iter = iter(obj)
    else:
        val_iter = iter(())
    for v in val_iter:
        if isinstance(v, Container) and id(v) not in seen:
            _traverse(v, seen)


_ids = count()


class Watcher:
    def __init__(self, fn, lazy=True, deep=False, callback=None) -> None:
        self.id = next(_ids)
        self.fn = fn
        self._deps, self._new_deps = WeakSet(), WeakSet()

        self.callback = callback
        self.deep = deep
        self.lazy = lazy
        self.dirty = self.lazy
        self.value = None if self.lazy else self.get()

    def update(self) -> None:
        self.dirty = True
        if not self.lazy:
            self.evaluate()

    def evaluate(self) -> None:
        if self.dirty:
            old_value = self.value
            self.value = self.get()
            self.dirty = False
            if self.callback:
                self.callback(old_value, self.value)

    def get(self) -> Any:
        Dep.stack.append(self)
        try:
            value = self.fn()
        finally:
            if self.deep:
                traverse(value)
            Dep.stack.pop()
            self.cleanup_deps()
        return value

    def add_dep(self, dep: Dep) -> None:
        if dep not in self._new_deps:
            self._new_deps.add(dep)
            if dep not in self._deps:
                dep.add_sub(self)

    def cleanup_deps(self) -> None:
        for dep in self._deps:
            if dep not in self._new_deps:
                dep.remove_sub(self)
        self._deps, self._new_deps = self._new_deps, self._deps
        self._new_deps.clear()

    def depend(self) -> None:
        """This function is used by other watchers to depend on everything
        this watcher depends on."""
        if Dep.stack:
            for dep in self._deps:
                dep.depend()

    def teardown(self) -> None:
        for dep in self._deps:
            dep.remove_sub(self)

    def __del__(self) -> None:
        self.teardown()


def make_observable(cls):
    def read(fn):
        @wraps(fn)
        def inner(self, *args, **kwargs):
            if Dep.stack:
                self.__dep__.depend()
            return fn(self, *args, **kwargs)

        return inner

    def read_key(fn):
        @wraps(fn)
        def inner(self, *args, **kwargs):
            if Dep.stack:
                key = args[0]
                self.__keydeps__[key].depend()
            return fn(self, *args, **kwargs)

        return inner

    def write(fn):
        @wraps(fn)
        def inner(self, *args, **kwargs):
            args = tuple(observe(a) for a in args)
            kwargs = {k: observe(v) for k, v in kwargs.items()}
            retval = fn(self, *args, **kwargs)
            self.__dep__.notify()
            return retval

        return inner

    def write_key(fn):
        @wraps(fn)
        def inner(self, *args, **kwargs):
            key = args[0]
            is_new = key not in self.__keydeps__
            old_value = cls.__getitem__(self, key) if not is_new else None
            args = [key] + [observe(a) for a in args[1:]]
            kwargs = {k: observe(v) for k, v in kwargs.items()}
            retval = fn(self, *args, **kwargs)
            new_value = cls.__getitem__(self, key)
            if is_new:
                self.__keydeps__[key] = Dep()
            if old_value != new_value:
                self.__keydeps__[key].notify()
                self.__dep__.notify()
            return retval

        return inner

    def delete(fn):
        @wraps(fn)
        def inner(self, *args, **kwargs):
            retval = fn(self, *args, **kwargs)
            self.__dep__.notify()
            for key in self._orphaned_keydeps():
                self.__keydeps__[key].notify()
                del self.__keydeps__[key]
            return retval

        return inner

    def delete_key(fn):
        @wraps(fn)
        def inner(self, *args, **kwargs):
            retval = fn(self, *args, **kwargs)
            # TODO prevent firing if value hasn't actually changed?
            key = args[0]
            self.__dep__.notify()
            self.__keydeps__[key].notify()
            del self.__keydeps__[key]
            return retval

        return inner

    todo = [
        ("_READERS", read),
        ("_KEYREADERS", read_key),
        ("_WRITERS", write),
        ("_KEYWRITERS", write_key),
        ("_DELETERS", delete),
        ("_KEYDELETERS", delete_key),
    ]

    for category, decorate in todo:
        for name in getattr(cls, category, set()):
            fn = getattr(cls, name)
            setattr(cls, name, decorate(fn))

    return cls


class ObservableDict(dict):
    _READERS = {
        "values",
        "copy",
        "items",
        "keys",
        "__eq__",
        "__format__",
        "__ge__",
        "__gt__",
        "__iter__",
        "__le__",
        "__len__",
        "__lt__",
        "__ne__",
        "__repr__",
        "__sizeof__",
        "__str__",
    }
    _KEYREADERS = {
        "get",
        "__contains__",
        "__getitem__",
    }
    _WRITERS = {
        "update",
    }
    _KEYWRITERS = {
        "setdefault",
        "__setitem__",
    }
    _DELETERS = {
        "clear",
        "popitem",
    }
    _KEYDELETERS = {
        "pop",
        "__delitem__",
    }

    @wraps(dict.__init__)
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.__dep__ = Dep()
        self.__keydeps__ = {key: Dep() for key in dict.keys(self)}

    def _orphaned_keydeps(self):
        return set(self.__keydeps__.keys()) - set(dict.keys(self))


if sys.version_info >= (3, 8, 0):
    ObservableDict._READERS.add("__reversed__")
if sys.version_info >= (3, 9, 0):
    ObservableDict._READERS.add("__or__")
    ObservableDict._READERS.add("__ror__")
    ObservableDict._WRITERS.add("__ior__")
ObservableDict = make_observable(ObservableDict)


@make_observable
class ObservableList(list):
    _READERS = {
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
        "__iter__",
        "__len__",
        "__repr__",
        "__str__",
        "__format__",
        "__reversed__",
        "__sizeof__",
    }
    _WRITERS = {
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
    }

    @wraps(list.__init__)
    def __init__(self, *args, **kwargs):
        list.__init__(self, *args, **kwargs)
        self.__dep__ = Dep()


@make_observable
class ObservableSet(set):
    _READERS = {
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
        "__iter__",
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
    }
    _WRITERS = {
        "add",
        "clear",
        "difference_update",
        "intersection_update",
        "discard",
        "pop",
        "remove",
        "symmetric_difference_update",
        "update",
    }

    @wraps(set.__init__)
    def __init__(self, *args, **kwargs):
        set.__init__(self, *args, **kwargs)
        self.__dep__ = Dep()


def observe(obj, deep=True):
    if not isinstance(obj, (dict, list, tuple, set)):
        return obj  # common case first
    elif isinstance(obj, dict):
        if not isinstance(obj, ObservableDict):
            reactive = ObservableDict(obj)
        else:
            reactive = obj
        if deep:
            for k, v in reactive.items():
                reactive[k] = observe(v)
        return reactive
    elif isinstance(obj, list):
        if not isinstance(obj, ObservableList):
            reactive = ObservableList(obj)
        else:
            reactive = obj
        if deep:
            for i, v in enumerate(reactive):
                reactive[i] = observe(v)
        return reactive
    elif isinstance(obj, tuple):
        reactive = obj  # tuples are immutable
        if deep:
            reactive = tuple(observe(v) for v in reactive)
        return reactive
    elif isinstance(obj, set):
        if deep:
            return ObservableSet(observe(v) for v in obj)
        else:
            if not isinstance(obj, ObservableSet):
                reactive = ObservableSet(obj)
            else:
                reactive = obj
            return reactive


def computed(fn):
    watcher = Watcher(fn)

    @wraps(fn)
    def getter():
        if watcher.dirty:
            watcher.evaluate()
        if Dep.stack:
            watcher.depend()
        return watcher.value

    getter.__watcher__ = watcher
    return getter


def watch(fn, callback, deep=False, immediate=False):
    watcher = Watcher(fn, lazy=False, deep=deep, callback=callback)
    if immediate:
        watcher.dirty = True
        watcher.evaluate()
    return watcher
