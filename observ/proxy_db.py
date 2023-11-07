import gc
import sys
from weakref import WeakValueDictionary

from .dep import Dep


class ProxyDb:
    """
    Collection of proxies, tracked by the id of the object that they wrap.
    Each time a Proxy is instantiated, it will register itself for the
    wrapped object. And when a Proxy is deleted, then it will unregister.
    When the last proxy that wraps an object is removed, it is uncertain
    what happens to the wrapped object, so in that case the object id is
    removed from the collection.
    """

    __slots__ = ["db"]

    def __init__(self):
        self.db = {}
        gc.callbacks.append(self.cleanup)

    def cleanup(self, phase, info):
        """
        Callback for garbage collector to cleanup the db for targets
        that have no other references outside of the db
        """
        # TODO: maybe also run on start? Check performance
        if phase != "stop":
            return

        keys_to_delete = []
        for key, value in self.db.items():
            # Refs:
            # - sys.getrefcount
            # - ref in db item
            if sys.getrefcount(value["target"]) <= 2:
                # We are the last to hold a reference!
                keys_to_delete.append(key)

        for keys in keys_to_delete:
            del self.db[keys]

    def reference(self, proxy):
        """
        Adds a reference to the collection for the wrapped object's id
        """
        obj_id = id(proxy.target)

        if obj_id not in self.db:
            attrs = {
                "dep": Dep(),
            }
            if isinstance(proxy.target, dict):
                attrs["keydep"] = {key: Dep() for key in proxy.target.keys()}
            self.db[obj_id] = {
                "target": proxy.target,
                "attrs": attrs,  # dep, keydep
                # keyed on tuple(readonly, shallow)
                "proxies": WeakValueDictionary(),
            }

        # Use setdefault to put the proxy in the proxies dict. If there
        # was an existing value, it will return that instead. There shouldn't
        # be an existing value, so we can compare the objects to see if we
        # should raise an exception.
        # Seems to be a tiny bit faster than checking beforehand if
        # there is already an existing value in the proxies dict
        result = self.db[obj_id]["proxies"].setdefault(
            (proxy.readonly, proxy.shallow), proxy
        )
        if result is not proxy:
            raise RuntimeError("Proxy with existing configuration already in db")

    def dereference(self, proxy):
        """
        Removes a reference from the database for the given proxy
        """
        obj_id = id(proxy.target)
        if obj_id not in self.db:
            # When there are failing tests, it might happen that proxies
            # are garbage collected at a point where the proxy_db is already
            # cleared. That's why we need this check here.
            # See fixture [clear_proxy_db](/tests/conftest.py:clear_proxy_db)
            # for more info.
            return

        # The given proxy is the last proxy in the WeakValueDictionary,
        # so now is a good moment to see if can remove clean the deps
        # for the target object
        if len(self.db[obj_id]["proxies"]) == 1:
            ref_count = sys.getrefcount(self.db[obj_id]["target"])
            # Ref count is still 3 here because of the reference through proxy.target
            if ref_count <= 3:
                # We are the last to hold a reference!
                del self.db[obj_id]

    def attrs(self, proxy):
        return self.db[id(proxy.target)]["attrs"]

    def get_proxy(self, target, readonly=False, shallow=False):
        """
        Returns a proxy from the collection for the given object and configuration.
        Will return None if there is no proxy for the object's id.
        """
        if id(target) not in self.db:
            return None
        return self.db[id(target)]["proxies"].get((readonly, shallow))


# Create a global proxy collection
proxy_db = ProxyDb()
