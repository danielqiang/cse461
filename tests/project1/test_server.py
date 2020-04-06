from typing import Callable
import threading
import random
import pytest
import time

from cse461.project1 import Client, Server


@pytest.fixture(autouse=True)
def server(request):
    server = Server()
    server.start()
    request.addfinalizer(server.stop)


def spawn_concurrent_clients(count: int, target: Callable, args=()):
    threads = [threading.Thread(target=target, args=args) for _ in range(count)]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def _test_basic_single():
    with Client(student_id=random.randint(100, 999)) as client:
        secrets = client.start()
    assert set(secrets.keys()) == {"a", "b", "c", "d"}
    assert all(isinstance(i, int) and i > 0 for i in secrets.values())


def test_basic_single():
    _test_basic_single()


def test_basic_concurrent_small():
    spawn_concurrent_clients(5, target=_test_basic_single)


def test_basic_concurrent_large():
    spawn_concurrent_clients(100, target=_test_basic_single)


def _test_timeout_single():
    with Client(student_id=random.randint(100, 999)) as client:
        resp = client.stage_a()
        resp = client.stage_b(resp)
        # Servers should time out after 3 seconds;
        # sleep for 4 to be safe
        time.sleep(4)
        # The server timed out, so attempting to send data should raise
        # a ConnectionRefusedError
        pytest.raises(ConnectionRefusedError, client.stage_c, resp)

        assert threading.active_count() == 1


def test_timeout_single():
    _test_timeout_single()


def test_timeout_concurrent_small():
    spawn_concurrent_clients(5, target=_test_timeout_single)


def test_timeout_concurrent_large():
    spawn_concurrent_clients(100, target=_test_timeout_single)
