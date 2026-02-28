from .core import Tag, prevent, stop, State, current_request
from .server import WebApp
from .runner import ChromeApp
import logging

# Library best practice: attach NullHandler so apps that don't configure
# logging won't see "No handler found" warnings.
logging.getLogger("htag").addHandler(logging.NullHandler())

__all__ = ["Tag", "ChromeApp", "prevent", "stop", "State", "WebApp"]
