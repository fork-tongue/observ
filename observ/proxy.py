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

    def __init__(self, target, readonly=False, shallow=False):
        self.target = target
        self.readonly = readonly
        self.shallow = shallow
        proxy_db.reference(self)

    def __del__(self):
        proxy_db.dereference(self)
