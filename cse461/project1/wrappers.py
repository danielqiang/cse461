from typing import Callable
from threading import Lock

__all__ = ['synchronized']


def synchronized(method: Callable, lock: Lock):
    """
    Method wrapper that acquires `lock` prior to executing `method` and
    releases it upon completion or if an exception occurs.

    :param method: Callable to synchronize.
    :param lock: Lock to acquire and release.
    """
    from functools import wraps

    @wraps(method)
    def wrapped(*args, **kwargs):
        with lock:
            return method(*args, **kwargs)

    return wrapped
