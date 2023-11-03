from functools import partial

from .dep import Dep
from .proxy_db import proxy_db


class Proxy:
    """
    Proxy for an object/target.

    Instantiating a Proxy will add a reference to the global proxy_db and
    destroying a Proxy will remove that reference.

    Please use the `proxy` method to get a proxy for a certain object instead
    of directly creating one yourself. The `proxy` method will either create
    or return an existing proxy and makes sure that the db stays consistent.
    """

    __hash__ = None
    __slots__ = ["target", "readonly", "shallow", "proxy_db", "Dep", "__weakref__"]

    def __init__(self, target, readonly=False, shallow=False):
        self.target = target
        self.readonly = readonly
        self.shallow = shallow
        self.proxy_db = proxy_db
        self.proxy_db.reference(self)
        self.Dep = Dep

    def __del__(self):
        self.proxy_db.dereference(self)


# Lookup dict for mapping a type (dict, list, set) to a method
# that will convert an object of that type to a proxied version
TYPE_LOOKUP = {}


def proxy(target, readonly=False, shallow=False):
    """
    Returns a Proxy for the given object. If a proxy for the given
    configuration already exists, it will return that instead of
    creating a new one.

    Please be aware: this only works on plain data types: dict, list,
    set and tuple!
    """
    # The object may be a proxy already, so check if it matches the
    # given configuration (readonly and shallow)
    if isinstance(target, Proxy):
        if readonly == target.readonly and shallow == target.shallow:
            return target
        else:
            # If the configuration does not match,
            # unwrap the target from the proxy so that the right
            # kind of proxy can be returned in the next part of
            # this function
            target = target.target

    # Note that at this point, target is always a non-proxy object
    # Check the proxy_db to see if there's already a proxy for the target object
    existing_proxy = proxy_db.get_proxy(target, readonly=readonly, shallow=shallow)
    if existing_proxy is not None:
        return existing_proxy

    # We can only wrap the following datatypes
    if not isinstance(target, (dict, list, tuple, set)):
        return target

    # Otherwise, create a new proxy
    proxy_type = None

    for target_type, (writable_proxy_type, readonly_proxy_type) in TYPE_LOOKUP.items():
        if isinstance(target, target_type):
            proxy_type = readonly_proxy_type if readonly else writable_proxy_type
            break
    else:
        if isinstance(target, tuple):
            return tuple(proxy(x, readonly=readonly, shallow=shallow) for x in target)

    return proxy_type(target, readonly=readonly, shallow=shallow)


reactive = proxy
readonly = partial(proxy, readonly=True)
shallow_reactive = partial(proxy, shallow=True)
shallow_readonly = partial(proxy, shallow=True, readonly=True)


def to_raw(target):
    """
    Returns a raw object from which any trace of proxy has been replaced
    with its wrapped target value.
    """
    if isinstance(target, Proxy):
        return to_raw(target.target)

    if isinstance(target, list):
        return [to_raw(t) for t in target]

    if isinstance(target, dict):
        return {key: to_raw(value) for key, value in target.items()}

    if isinstance(target, tuple):
        return tuple(to_raw(t) for t in target)

    if isinstance(target, set):
        return {to_raw(t) for t in target}

    return target
