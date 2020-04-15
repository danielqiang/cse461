from typing import Callable, Union
from threading import Lock, RLock
from functools import wraps

__all__ = ['synchronized']


def synchronized(method: Callable, lock: Union[Lock, RLock]):
    """
    Method wrapper that acquires `lock` prior to executing `method` and
    releases it upon completion or if an exception occurs.

    :param method: Callable to synchronize.
    :param lock: Lock to acquire and release.
    """

    @wraps(method)
    def wrapped(*args, **kwargs):
        with lock:
            return method(*args, **kwargs)

    return wrapped
