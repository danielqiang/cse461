from .client import Client
from .server import Server
from .consts import *
from .packet import *
import logging


# Log all messages as white text
WHITE = "\033[1m"
logging.basicConfig(level=logging.INFO,
                    format=WHITE + "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                    datefmt='%Y-%m-%d %H:%M:%S')
