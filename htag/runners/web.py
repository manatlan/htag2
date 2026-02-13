import time
import threading
import logging
import webbrowser
import uvicorn
from .base import BaseRunner

logger = logging.getLogger("htagravity")

class WebApp(BaseRunner):
    """
    Executes an App in the system default browser (new tab).
    Does not exit by default when the tab is closed.
    """
    def __init__(self, app: "App"):
        super().__init__(app)
        # By default, WebApp doesn't exit on disconnect
        self.app.exit_on_disconnect = False

    def run(self, host="127.0.0.1", port=8000):
        def launch():
            time.sleep(1)
            url = f"http://{host}:{port}"
            webbrowser.open(url)
            logger.info("Opened default browser at %s", url)

        threading.Thread(target=launch, daemon=True).start()
        uvicorn.run(self.app.app, host=host, port=port)
