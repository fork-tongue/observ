import pytest

from observ import scheduler
from observ.observables import proxy_db


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
    proxy_db.db = {}
