from .client import Client
from .server import Server
from .consts import *
from .packet import Packet
from .wrappers import synchronized
import logging

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s.%(msecs)03d [%(name)s] "
                           "%(levelname)s: %(message)s",
                    datefmt='%Y-%m-%d %H:%M:%S')
