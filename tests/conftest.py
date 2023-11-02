import gc

import pytest

from observ import scheduler
from observ.proxy import proxy_db


def noop():
    pass


@pytest.fixture
def noop_request_flush():
    old_callback = scheduler.request_flush
    scheduler.register_request_flush(noop)
    try:
        yield
    finally:
        scheduler.register_request_flush(old_callback)


@pytest.fixture(autouse=True)
def clear():
    try:
        yield
    finally:
        scheduler.clear()


@pytest.fixture(autouse=True)
def clear_proxy_db():
    # Would be nice to do this at the end of runs, but
    # it seems that pytest keeps some references to some objects
    # so we're not able to guarentee that the db can be
    # cleared properly afterwards.
    gc.collect()
    # Running gc at the beginning should clear the proxy_db,
    # but this apparently only works when tests are not failing,
    # so the db needs to be cleared like this.
    proxy_db.db = {}
