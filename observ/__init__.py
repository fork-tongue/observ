from importlib.metadata import version

__version__ = version("observ")


from .init import init, loop_factory
from .proxy import (
    reactive,
    readonly,
    ref,
    shallow_reactive,
    shallow_readonly,
    to_raw,
)
from .scheduler import scheduler
from .watcher import Watcher, computed, watch, watch_effect
