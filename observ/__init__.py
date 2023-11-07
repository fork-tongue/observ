__version__ = "0.12.0"


from .proxy import (
    reactive,
    readonly,
    shallow_reactive,
    shallow_readonly,
    to_raw,
)
from .scheduler import scheduler
from .watcher import computed, watch, watch_effect
