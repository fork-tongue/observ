from observ import ObservableDict, ObservableList, ObservableSet


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
