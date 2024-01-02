from .proxy import TYPE_LOOKUP, Proxy
from .proxy_db import proxy_db
from .traps import construct_methods_traps_dict, trap_map, trap_map_readonly

######################
# UNTRAPPED ATTRIBUTES
######################

# CREATION HOOKS:
# '__init__',
# '__init_subclass__',
# '__new__',

# PICKLE HOOKS:
# '__reduce__',
# '__reduce_ex__',
# '__getstate__',

# WEAKREF STORAGE:
# '__weakref__',

# FORMATTING HOOKS:
# '__format__',

# INTERNALS:
# '__dict__',

###########
# QUESTIONS
###########
# I don't think we can maintain per-key reactivity
# like we do with dicts. For starters we can't
# query the initial state since there is no .keys()

# There are many _optional_ magic methods, such as __iter__
# How do we support those without overcomplicating the traps?



object_traps = {
    "READERS": {
        '__class__',
        '__dir__',
        '__doc__',
        '__eq__',
        '__ge__',
        '__gt__',
        '__hash__',
        '__le__',
        '__lt__',
        '__module__',
        '__ne__',
        '__repr__',
        '__sizeof__',
        '__str__',
        '__subclasshook__',
        # also fires for method access :/
        '__getattribute__',
    },
    "WRITERS": {
        '__setattr__',
        "__delattr__",
    },
}


class ObjectProxyBase(Proxy[object]):
    def _orphaned_keydeps(self):
        return set(proxy_db.attrs(self)["keydep"].keys()) - set(vars(self.target).keys())


def readonly_object_proxy_init(self, target, shallow=False, **kwargs):
    super(ReadonlyObjectProxy, self).__init__(
        target, shallow=shallow, **{**kwargs, "readonly": True}
    )


ObjectProxy = type(
    "ObjectProxy",
    (ObjectProxyBase,),
    construct_methods_traps_dict(object, object_traps, trap_map),
)
ReadonlyObjectProxy = type(
    "ReadonlyObjectProxy",
    (ObjectProxyBase,),
    {
        "__init__": readonly_object_proxy_init,
        **construct_methods_traps_dict(object, object_traps, trap_map_readonly),
    },
)


def type_test(target):
    # exclude builtin objects
    return isinstance(target, object) and target.__module__ != object.__module__


TYPE_LOOKUP[type_test] = (ObjectProxy, ReadonlyObjectProxy)
