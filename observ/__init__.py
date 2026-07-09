from importlib.metadata import version

__version__ = version("observ")


# Importing the proxy modules registers their types in TYPE_LOOKUP
from . import dict_proxy, list_proxy, set_proxy
from .init import init, loop_factory
from .proxy import (
    reactive,
    readonly,
    ref,
    shallow_reactive,
    shallow_readonly,
    to_raw,
    trigger_ref,
)
from .scheduler import scheduler
from .watcher import Watcher, computed, watch, watch_effect
