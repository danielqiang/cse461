from cse461.project1 import Client, Server
import threading
import random

with Server() as server:
    server.start()


def _test_concurrent_clients(count: int):
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
    _test_concurrent_clients(5)


def test_concurrent_clients_large():
    _test_concurrent_clients(100)
