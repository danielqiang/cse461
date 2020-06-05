import logging
from .proxy import Proxy
from .http import *

# Log all messages as white text
WHITE = "\033[1m"
logging.basicConfig(level=logging.INFO,
                    format=WHITE + "%(asctime)s - %(message)s",
                    datefmt='%Y-%m-%d %H:%M:%S')
