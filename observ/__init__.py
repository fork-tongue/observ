__version__ = "0.1.0"


from itertools import count
from typing import Union, Any
from collections.abc import Container
from weakref import WeakSet
from functools import wraps


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
                key = args[0]  # TODO: test key
                self.__keydeps__[key].depend()
                # self.__dep__.depend()  # TODO: is this needed? doesn't appear to be
            return fn(self, *args, **kwargs)

        return inner

    def write(fn):
        @wraps(fn)
        def inner(self, *args, **kwargs):
            retval = fn(self, *args, **kwargs)
            self.__dep__.notify()
            return retval

        return inner

    def write_key(fn):
        @wraps(fn)
        def inner(self, *args, **kwargs):
            retval = fn(self, *args, **kwargs)
            # TODO prevent firing if value hasn't actually changed?
            key = args[0]  # TODO: test key
            if key not in self.__keydeps__:
                self.__keydeps__[key] = Dep()
            self.__keydeps__[key].notify()
            self.__dep__.notify()
            return retval

        return inner

    todo = [
        ("_READERS", read),
        ("_KEYREADERS", read_key),
        ("_WRITERS", write),
        ("_KEYWRITERS", write_key),
    ]

    for category, decorate in todo:
        for name in getattr(cls, category, set()):
            fn = getattr(cls, name)
            setattr(cls, name, decorate(fn))

    return cls


@make_observable
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
        "__hash__",
        "__iter__",
        "__le__",
        "__len__",
        "__lt__",
        "__ne__",
        "__reduce__",
        "__reduce_ex__",
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
        "clear",
        "update",
        "popitem",
    }
    _KEYWRITERS = {
        "pop",
        "setdefault",
        "__delitem__",
        "__setitem__",
    }

    @wraps(dict.__init__)
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.__keydeps__ = {key: Dep() for key in dict.keys(self)}
        self.__dep__ = Dep()


@make_observable
class ObservableList(list):
    _READERS = {
        "count",
        "index",
        "count",
        "index",
        "copy",
        "__add__",
        "__getitem__",
        "__hash__",
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
    }
    _WRITERS = {
        "append",
        "extend",
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
        "__dir__",
        "__eq__",
        "__format__",
        "__ge__",
        "__gt__",
        "__hash__",
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
        "__reduce__",
        "__reduce_ex__",
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
    if isinstance(obj, dict):
        reactive = ObservableDict(obj)
        if deep:
            for k, v in reactive.items():
                reactive[k] = observe(v)
        return reactive
    elif isinstance(obj, list):
        reactive = ObservableList(obj)
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
        return (
            ObservableSet(obj) if not deep else ObservableSet(observe(v) for v in obj)
        )
    elif not isinstance(obj, Container):
        return obj
    else:
        raise NotImplementedError(f"Don't know how to make {type(obj)} reactive")


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
        watcher.evaluate()
    return watcher
