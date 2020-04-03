import threading
import random
import pytest
import time

from cse461.project1 import Client, Server


@pytest.fixture(autouse=True)
def setup_server(request):
    server = Server()
    server.start()
    request.addfinalizer(server.stop)


def spawn_concurrent_clients(count: int):
    threads = [threading.Thread(target=test_single_client) for _ in range(count)]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def test_single_client():
    client = Client(student_id=random.randint(100, 999))
    secrets = client.run()
    assert set(secrets.keys()) == {"a", "b", "c", "d"}
    assert all(isinstance(i, int) and i > 0 for i in secrets.values())


def test_concurrent_clients_small():
    spawn_concurrent_clients(5)


def test_concurrent_clients_large():
    spawn_concurrent_clients(100)


@pytest.mark.xfail(reason="Server timeout currently doesn't kill thread")
def test_server_timeout_single_client():
    client = Client(student_id=random.randint(100, 999))
    client.run()
    # Server should time out after 3 seconds;
    # sleep for 5 to be safe
    time.sleep(5)
    assert threading.active_count() == 1
