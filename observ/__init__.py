__version__ = "0.8.0"


from .observables import (
    reactive,
    readonly,
    shallow_reactive,
    shallow_readonly,
    to_raw,
)
from .scheduler import scheduler
from .watcher import computed, watch
