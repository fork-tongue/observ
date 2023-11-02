from unittest.mock import Mock

from observ.dep import Dep
from observ.list_proxy import list_traps, ListProxy
from observ.observables import dict_traps
from observ.observables import DictProxy
from observ.observables import proxy_db
from observ.set_proxy import set_traps, SetProxy


COLLECTIONS = {
    ListProxy: list_traps,
    SetProxy: set_traps,
    DictProxy: dict_traps,
}

WRAPATTRS = {
    "READERS",
    "KEYREADERS",
    "ITERATORS",
    "WRITERS",
    "KEYWRITERS",
    "DELETERS",
    "KEYDELETERS",
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
    "_orphaned_keydeps",
    "__class_getitem__",
    # __del__ is custom method on Proxy
    "__del__",
    "__getstate__",
}


def test_wrapping_complete():
    for coll in COLLECTIONS:
        # ensure we're not wrapping anything more than once
        wrap_list = []
        for attr in WRAPATTRS:
            wrap_list += list(COLLECTIONS[coll].get(attr, set()))
        assert len(wrap_list) == len(set(wrap_list))

        # ensure we're wrapping everything
        to_wrap = set(dir(coll)) - EXCLUDED
        wrapped = set(wrap_list)
        assert to_wrap == wrapped, f"Failing for: {coll}"


def test_list_notify():
    args = {
        "append": (5,),
        "extend": ([5],),
        "clear": (),
        "insert": (0, 5),
        "pop": (),
        "remove": (2,),
        "reverse": (),
        "sort": (),
        "__setitem__": (
            0,
            5,
        ),
        "__delitem__": (0,),
        "__iadd__": ([5],),
        "__imul__": (5,),
    }
    for name in COLLECTIONS[ListProxy]["WRITERS"]:
        coll = ListProxy([3, 2])
        mock = Mock()
        proxy_db.attrs(coll)["dep"].notify = mock
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
    for name in COLLECTIONS[ListProxy]["READERS"]:
        Dep.stack.append(Mock())
        try:
            coll = ListProxy([2])
            mock = Mock()
            proxy_db.attrs(coll)["dep"].depend = mock
            getattr(coll, name)(*args[name])
            mock.assert_called()
        finally:
            Dep.stack.pop()


def test_set_notify():
    args = {
        "add": (3,),
        "clear": (),
        "difference_update": ({2, 3},),
        "intersection_update": ({3},),
        "discard": (2,),
        "pop": (),
        "remove": (2,),
        "symmetric_difference_update": ({3},),
        "update": ({3},),
    }
    for name in COLLECTIONS[SetProxy]["WRITERS"]:
        coll = SetProxy({2})
        mock = Mock()
        proxy_db.attrs(coll)["dep"].notify = mock
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
    for name in COLLECTIONS[SetProxy]["READERS"]:
        Dep.stack.append(Mock())
        try:
            coll = SetProxy({2})
            mock = Mock()
            proxy_db.attrs(coll)["dep"].depend = mock
            getattr(coll, name)(*args[name])
            mock.assert_called()
        finally:
            Dep.stack.pop()


def test_dict_notify():
    args = {
        "update": ({5: 6},),
        "__ior__": ({5: 6},),
    }
    for name in COLLECTIONS[DictProxy]["WRITERS"]:
        coll = DictProxy({2: 3})
        old_keys = set(coll.keys())
        proxy_db.attrs(coll)["dep"].notify = Mock()
        for key in proxy_db.attrs(coll)["keydep"].keys():
            proxy_db.attrs(coll)["keydep"][key].notify = Mock()
        getattr(coll, name)(*args[name])
        proxy_db.attrs(coll)["dep"].notify.assert_called_once()
        for key in old_keys:
            proxy_db.attrs(coll)["keydep"][key].notify.assert_not_called()


def test_dict_keynotify():
    args = {
        "setdefault": (3, 5),
        "__setitem__": (2, 4),
    }
    for name in COLLECTIONS[DictProxy]["KEYWRITERS"]:
        coll = DictProxy({2: 3})
        key = args[name][0]
        is_new_key = key not in proxy_db.attrs(coll)["keydep"]
        proxy_db.attrs(coll)["dep"].notify = Mock()
        for k in proxy_db.attrs(coll)["keydep"].keys():
            proxy_db.attrs(coll)["keydep"][k].notify = Mock()
        getattr(coll, name)(*args[name])
        proxy_db.attrs(coll)["dep"].notify.assert_called_once()
        if is_new_key:
            assert isinstance(proxy_db.attrs(coll)["keydep"][key], Dep)
        else:
            proxy_db.attrs(coll)["keydep"][key].notify.assert_called_once()


def test_dict_depend():
    args = {
        "values": (),
        "copy": (),
        "items": (),
        "keys": (),
        "__eq__": ({},),
        "__format__": ("",),
        "__ge__": ({},),
        "__gt__": ({},),
        "__iter__": (),
        "__le__": ({},),
        "__len__": (),
        "__lt__": ({},),
        "__ne__": ({},),
        "__repr__": (),
        "__sizeof__": (),
        "__str__": (),
        "__reversed__": (),
        "__ror__": ({},),
        "__or__": ({},),
        "__ior__": ({},),
    }
    for name in COLLECTIONS[DictProxy]["READERS"]:
        Dep.stack.append(Mock())
        try:
            coll = DictProxy({2: 3})
            proxy_db.attrs(coll)["dep"].depend = Mock()
            for k in proxy_db.attrs(coll)["keydep"].keys():
                proxy_db.attrs(coll)["keydep"][k].depend = Mock()
            getattr(coll, name)(*args[name])
            proxy_db.attrs(coll)["dep"].depend.assert_called()
        finally:
            Dep.stack.pop()


def test_dict_keydepend():
    args = {
        "get": (2,),
        "__contains__": (2,),
        "__getitem__": (2,),
    }
    for name in COLLECTIONS[DictProxy]["KEYREADERS"]:
        Dep.stack.append(None)
        try:
            coll = DictProxy({2: 3})
            proxy_db.attrs(coll)["dep"].depend = Mock()
            for k in proxy_db.attrs(coll)["keydep"].keys():
                proxy_db.attrs(coll)["keydep"][k].depend = Mock()
            getattr(coll, name)(*args[name])
            proxy_db.attrs(coll)["dep"].depend.assert_not_called()
            proxy_db.attrs(coll)["keydep"][args[name][0]].depend.assert_called_once()
        finally:
            Dep.stack.pop()


def test_dict_delete_notify():
    args = {
        "clear": (),
        "popitem": (),
    }
    for name in COLLECTIONS[DictProxy]["DELETERS"]:
        coll = DictProxy({2: 3})
        proxy_db.attrs(coll)["dep"].notify = Mock()
        for key in proxy_db.attrs(coll)["keydep"].keys():
            proxy_db.attrs(coll)["keydep"][key].notify = Mock()
        getattr(coll, name)(*args[name])
        proxy_db.attrs(coll)["dep"].notify.assert_called_once()
        assert len(proxy_db.attrs(coll)["keydep"]) == 0


def test_dict_delete_keynotify():
    args = {
        "pop": (2,),
        "__delitem__": (2,),
    }
    for name in COLLECTIONS[DictProxy]["KEYDELETERS"]:
        coll = DictProxy({2: 3})
        key = args[name][0]
        proxy_db.attrs(coll)["dep"].notify = Mock()
        keymock = Mock()
        proxy_db.attrs(coll)["keydep"][key] = keymock
        for k in proxy_db.attrs(coll)["keydep"].keys():
            proxy_db.attrs(coll)["keydep"][k].notify = Mock()
        getattr(coll, name)(*args[name])
        proxy_db.attrs(coll)["dep"].notify.assert_called_once()
        keymock.notify.assert_called_once()
        assert len(proxy_db.attrs(coll)["keydep"]) == 0
