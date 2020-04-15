from .client import Client
from .server import Server
from .consts import *
from .packet import Packet
from .wrappers import synchronized
import logging

# Log all messages as white text
WHITE = "\033[1m"
logging.basicConfig(level=logging.INFO,
                    format=WHITE + "%(asctime)s.%(msecs)03d [%(name)s] "
                                   "%(levelname)s: %(message)s",
                    datefmt='%Y-%m-%d %H:%M:%S')
