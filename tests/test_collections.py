from unittest.mock import Mock

from observ import Dep, ObservableDict, ObservableList, ObservableSet


COLLECTIONS = {
    ObservableList,
    ObservableSet,
    ObservableDict,
}

WRAPATTRS = {
    "_READERS",
    "_KEYREADERS",
    "_WRITERS",
    "_KEYWRITERS",
}

# we don't wrap these
EXCLUDED = {
    "__weakref__",
    "__class__",
    "__delattr__",
    "__setattr__",
    "__getattr__",
    "__getattribute__",
    "__dir__",
    "__dict__",
    "__doc__",
    "__init__",
    "__init_subclass__",
    "__new__",
    "__module__",
    "__subclasshook__",
    "fromkeys",
    "__reduce__",
    "__reduce_ex__",
    "__hash__",
} | WRAPATTRS


def test_wrapping_complete():
    for coll in COLLECTIONS:
        # ensure we're not wrapping anything more than once
        wrap_list = []
        for attr in WRAPATTRS:
            wrap_list += list(getattr(coll, attr, set()))
        assert len(wrap_list) == len(set(wrap_list))

        # ensure we're wrapping everything
        to_wrap = set(dir(coll)) - EXCLUDED
        wrapped = set(wrap_list)
        assert to_wrap == wrapped


def test_list_notify():
    args = {
        "append": (5,),
        "extend": ([5],),
        "clear": (),
        "extend": ([5],),
        "insert": (0, 5),
        "pop": (),
        "remove": (2,),
        "reverse": (),
        "sort": (),
        "__setitem__": (0, 5,),
        "__delitem__": (0,),
        "__iadd__": ([5],),
        "__imul__": (5,),
    }
    for name in ObservableList._WRITERS:
        coll = ObservableList([2])
        mock = Mock()
        coll.__dep__.notify = mock
        getattr(coll, name)(*args[name])
        mock.assert_called_once()


def test_list_depend():
    args = {
        "count": (2,),
        "index": (2,),
        "copy": (),
        "__add__": ([5],),
        "__getitem__": (0,),
        "__contains__": (2,),
        "__eq__": ([],),
        "__ge__": ([],),
        "__gt__": ([],),
        "__le__": ([],),
        "__lt__": ([],),
        "__mul__": (5,),
        "__ne__": ([],),
        "__rmul__": (5,),
        "__iter__": (),
        "__len__": (),
        "__repr__": (),
        "__str__": (),
        "__format__": ("",),
        "__reversed__": (),
        "__sizeof__": (),
    }
    for name in ObservableList._READERS:
        Dep.stack.append(None)
        try:
            coll = ObservableList([2])
            mock = Mock()
            coll.__dep__.depend = mock
            getattr(coll, name)(*args[name])
            mock.assert_called()
        finally:
            Dep.stack.pop()


def test_set_notify():
    args = {
        "add": (3,),
        "clear": (),
        "difference_update": ({3},),
        "intersection_update": ({3},),
        "discard": (2,),
        "pop": (),
        "remove": (2,),
        "symmetric_difference_update": ({3},),
        "update": ({3},),
    }
    for name in ObservableSet._WRITERS:
        coll = ObservableSet({2})
        mock = Mock()
        coll.__dep__.notify = mock
        getattr(coll, name)(*args[name])
        mock.assert_called_once()


def test_set_depend():
    args = {
        "copy": (),
        "difference": ({3},),
        "intersection": ({3},),
        "isdisjoint": ({3},),
        "issubset": ({3},),
        "issuperset": ({3},),
        "symmetric_difference": ({3},),
        "union": ({3},),
        "__and__": ({3},),
        "__contains__": (2,),
        "__eq__": ({3},),
        "__format__": ("",),
        "__ge__": ({3},),
        "__gt__": ({3},),
        "__iand__": ({3},),
        "__ior__": ({3},),
        "__isub__": ({3},),
        "__iter__": (),
        "__ixor__": ({3},),
        "__le__": ({3},),
        "__len__": (),
        "__lt__": ({3},),
        "__ne__": ({3},),
        "__or__": ({3},),
        "__rand__": ({3},),
        "__repr__": (),
        "__ror__": ({3},),
        "__rsub__": ({3},),
        "__rxor__": ({3},),
        "__sizeof__": (),
        "__str__": (),
        "__sub__": ({3},),
        "__xor__": ({3},),
    }
    for name in ObservableSet._READERS:
        Dep.stack.append(None)
        try:
            coll = ObservableSet({2})
            mock = Mock()
            coll.__dep__.depend = mock
            getattr(coll, name)(*args[name])
            mock.assert_called()
        finally:
            Dep.stack.pop()

