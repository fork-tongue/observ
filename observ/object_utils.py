from functools import cache
from itertools import chain


@cache
def get_class_slots(cls):
    """utility to collect all __slots__ entries for a given type and its supertypes"""
    # collect via iterables for performance
    # deduplicate via set
    return set(
        chain.from_iterable(getattr(cls, "__slots__", []) for cls in cls.__mro__)
    )


def get_object_attrs(obj):
    """utility to collect all stateful attributes of an object"""
    # __slots__ from full class ancestry
    attrs = list(get_class_slots(type(obj)))
    try:
        # all __dict__ entries
        attrs.extend(vars(obj).keys())
    except TypeError:
        pass
    return attrs
