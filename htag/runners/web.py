import time
import threading
import logging
import webbrowser
import uvicorn
import inspect
from typing import Union, Type, TYPE_CHECKING
from .base import BaseRunner

if TYPE_CHECKING:
    from ..server import App

logger = logging.getLogger("htag2")

class WebApp(BaseRunner):
    """
    Executes an App in the system default browser (new tab).
    Does not exit by default when the tab is closed.
    """
    def __init__(self, app: Union[Type["App"], "App"]):
        super().__init__(app)
        # By default, WebApp doesn't exit on disconnect
        if not inspect.isclass(self.app):
            # If it's an instance, we can set the attribute directly
            self.app.exit_on_disconnect = False
        else:
            # If it's a class, the exit_on_disconnect is set in App.statics (class level) 
            # or we can rely on WebServer's on_instance to set it per instance.
            # For simplicity, we assume the user might want to customize it in their App class.
            pass

    def run(self, host: str = "127.0.0.1", port: int = 8000, open_browser: bool = False) -> None:
        if open_browser:
            def launch() -> None:
                time.sleep(1)
                url = f"http://{host}:{port}"
                webbrowser.open(url)
                logger.info("Opened default browser at %s", url)

            threading.Thread(target=launch, daemon=True).start()
        
        from ..server import WebServer
        
        # Ensure instances created for this runner don't exit on disconnect
        def on_inst(inst: "App") -> None:
            inst.exit_on_disconnect = False

        ws = WebServer(self.app, on_instance=on_inst)
        uvicorn.run(ws.app, host=host, port=port)
