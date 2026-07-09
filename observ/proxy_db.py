"""
Registry of the reactive state that observ keeps for each wrapped
target object.

For every target that is wrapped by one or more proxies there is a
single TargetDep: the Dep for the container as a whole, which also
owns everything else observ needs to know about the target (the
per-key deps and the proxies that wrap it).

Lifetimes are managed purely by reference counting:

- Every Proxy holds a strong reference to the TargetDep of its
  target (Proxy.__dep__).
- Every Watcher that depends on a target holds a strong reference
  to its TargetDep, or to one of its KeyDeps which in turn hold
  their TargetDep, for as long as the dependency lasts.
- The registry itself only holds weak references, so as soon as the
  last proxy and the last interested watcher are gone, the TargetDep
  (and with it observ's reference to the target) is destroyed and
  its entry is removed from the registry by a weakref callback.

The registry is keyed on id(target), because the plain containers
(dict, list, set) do not support weak references and are not
(reliably) hashable. This is safe against id reuse, because a
TargetDep keeps its target alive: an id can only be recycled after
the TargetDep for its previous target has already been destroyed
and has removed itself from the registry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from weakref import WeakValueDictionary, ref

from .dep import Dep

if TYPE_CHECKING:
    from .proxy import Proxy

    # A proxy configuration: the (readonly, shallow) flags
    ProxyConfig = tuple[bool, bool]


class TargetDep(Dep):
    """
    The Dep for a target container as a whole. There is at most one
    TargetDep per wrapped target, shared by all proxies that wrap it,
    so that watchers and mutations always meet on the same Dep no
    matter which proxy they go through.
    """

    __slots__ = ("keydeps", "proxies", "target")

    keydeps: WeakValueDictionary[Any, KeyDep] | None
    proxies: dict[ProxyConfig, ref[Proxy[Any]]]

    def __init__(self, target: Any) -> None:
        super().__init__()
        self.target = target
        # Per-key deps (dict targets only). Starts out as None and is
        # only materialized (as a WeakValueDictionary) when a key is
        # read with dependency tracking active, since constructing a
        # WeakValueDictionary is relatively expensive. The values are
        # kept alive by the watchers that depend on them: a keydep
        # without subscribers has nobody to notify, so it can be
        # recreated freely whenever the key is read again
        self.keydeps = None
        # Weakrefs to the proxies that wrap the target,
        # keyed on (readonly, shallow)
        self.proxies = {}

    def keydep(self, key: Any) -> KeyDep:
        """
        Returns the dep for the given key, creating it if needed.
        Note that the keydeps mapping is weak: the returned dep stays
        registered only for as long as the caller (or a subscribed
        watcher) holds a reference to it.
        """
        keydeps = self.keydeps
        if keydeps is None:
            keydeps = self.keydeps = WeakValueDictionary()
        else:
            keydep = keydeps.get(key)
            if keydep is not None:
                return keydep
        keydep = KeyDep(self)
        keydeps[key] = keydep
        return keydep

    def register_proxy(self, config: ProxyConfig, proxy: Proxy[Any]) -> None:
        """
        Registers the proxy as the proxy that wraps the target with
        the given (readonly, shallow) configuration. There can be only
        one proxy per configuration.
        """
        proxies = self.proxies
        existing = proxies.get(config)
        if existing is not None and existing() is not None:
            raise RuntimeError("Proxy with existing configuration already in db")

        def remove(
            weak_proxy: ref[Proxy[Any]],
            proxies: dict[ProxyConfig, ref[Proxy[Any]]] = proxies,
            config: ProxyConfig = config,
        ) -> None:
            if proxies.get(config) is weak_proxy:
                del proxies[config]

        proxies[config] = ref(proxy, remove)

    def get_proxy(self, config: ProxyConfig) -> Proxy[Any] | None:
        """
        Returns the proxy that wraps the target with the given
        (readonly, shallow) configuration, or None if there is none.
        """
        weak_proxy = self.proxies.get(config)
        if weak_proxy is None:
            return None
        return weak_proxy()


class KeyDep(Dep):
    """
    The Dep for a single key of a target. It holds a strong reference
    to the TargetDep that owns it, so that a watcher that depends on
    just a key still keeps the target's registry entry (and thereby
    the identity of its deps) alive.
    """

    __slots__ = ("owner",)

    def __init__(self, owner: TargetDep) -> None:
        super().__init__()
        self.owner = owner


class ProxyDb:
    """
    Weak registry of TargetDeps, keyed on the id of the target object
    that they describe. Entries remove themselves when their TargetDep
    is destroyed.
    """

    __slots__ = ("db",)

    def __init__(self) -> None:
        # id(target) -> weakref to the TargetDep for that target
        self.db: dict[int, ref[TargetDep]] = {}

    def target_dep(self, target: Any) -> TargetDep:
        """
        Returns the TargetDep for the given target, creating it (and
        registering it) if there is none yet.
        """
        db = self.db
        obj_id = id(target)
        weak_dep = db.get(obj_id)
        if weak_dep is not None:
            dep = weak_dep()
            if dep is not None:
                return dep

        dep = TargetDep(target)

        def remove(
            weak_dep: ref[TargetDep],
            db: dict[int, ref[TargetDep]] = db,
            obj_id: int = obj_id,
        ) -> None:
            # Guard against the entry having been replaced in the
            # meantime, so a stale callback can't remove a live entry
            if db.get(obj_id) is weak_dep:
                del db[obj_id]

        db[obj_id] = ref(dep, remove)
        return dep

    def get_proxy(
        self, target: Any, readonly: bool = False, shallow: bool = False
    ) -> Proxy[Any] | None:
        """
        Returns the proxy with the given configuration for the given
        target. Will return None if there is no such proxy.
        """
        weak_dep = self.db.get(id(target))
        if weak_dep is None:
            return None
        dep = weak_dep()
        if dep is None:
            return None
        return dep.get_proxy((readonly, shallow))


# Create a global proxy collection
proxy_db = ProxyDb()
