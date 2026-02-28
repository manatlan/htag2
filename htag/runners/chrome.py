import sys
import time
import subprocess
import threading
import logging
import uvicorn
import platform
import inspect
import os
from typing import Union, Type, TYPE_CHECKING, Optional, Callable, List, Any
from .base import BaseRunner

if TYPE_CHECKING:
    from ..server import App

logger = logging.getLogger("htag2")

class ChromeApp(BaseRunner):
    """
    Executes an App in a Chrome/Chromium kiosk window.
    Features auto-cleanup of temporary browser profiles.
    """
    def __init__(self, app: Union[Type["App"], "App"], kiosk: bool = True, width: int = 800, height: int = 600):
        super().__init__(app)
        self.kiosk = kiosk
        self.width = width
        self.height = height
        self._cleanup_func: Optional[Callable[[], None]] = None

    def run(self, host: str = "127.0.0.1", port: int = 8000, reload: bool = False, **kwargs: Any) -> None:
        if reload:
            # Tag the app so the frontend knows to auto-reconnect
            if inspect.isclass(self.app):
                self.app._reload = True
            else:
                setattr(self.app, "_reload", True)

        is_reloader_child = os.environ.get("HTAG_RELOADER", "") == "1"

        if self.kiosk and not (reload and is_reloader_child):
            # Only launch the browser if we are NOT the restarted child worker
            def launch() -> None:
                time.sleep(1)  # Give the server a second to start
                
                import tempfile
                import shutil
                import atexit
                tmp_dir = tempfile.mkdtemp(prefix="htag2_")
                
                def cleanup() -> None:
                    try:
                        shutil.rmtree(tmp_dir)
                        logger.info("Cleaned up temporary browser profile: %s", tmp_dir)
                    except Exception:
                        pass
                
                atexit.register(cleanup)
                # Cleanup logic will be attached to instances via on_instance callback
                self._cleanup_func = cleanup
                
                browsers: List[str] = []
                if platform.system() == "Windows":
                    # Windows-specific browser paths
                    possible_paths = [
                        os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "Google", "Chrome", "Application", "chrome.exe"),
                        os.path.join(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), "Google", "Chrome", "Application", "chrome.exe"),
                        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
                        os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "Microsoft", "Edge", "Application", "msedge.exe"),
                        os.path.join(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), "Microsoft", "Edge", "Application", "msedge.exe"),
                        os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
                        os.path.join(os.environ.get("LOCALAPPDATA", ""), "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
                    ]
                    browsers = [p for p in possible_paths if os.path.isfile(p)]
                else:
                    # Linux/macOS browser names
                    browsers = ["google-chrome-stable", "google-chrome", "chromium-browser", "chromium", "chrome", "microsoft-edge", "brave-browser"]
                
                found = False
                
                for browser in browsers:
                    try:
                        subprocess.Popen([
                            browser, 
                            f"--app=http://{host}:{port}", 
                            f"--window-size={self.width},{self.height}",
                            f"--user-data-dir={tmp_dir}",
                            "--no-first-run",
                            "--no-default-browser-check"
                        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        logger.info("Launched %s with window size %dx%d", browser, self.width, self.height)
                        found = True
                        break
                    except FileNotFoundError:
                        continue
                    except Exception as e:
                        logger.error("Error launching %s: %s", browser, e)
                        continue
                
                if not found:
                    logger.warning("Could not launch any Chromium-based browser (tried: %s)", ", ".join(browsers))
                    import webbrowser
                    if webbrowser.open(f"http://{host}:{port}"):
                        logger.info("Fallback: opened default browser")
                    else:
                        logger.error("Fatal: Could not open any browser at all")

            threading.Thread(target=launch, daemon=True).start()

        if reload and not is_reloader_child:
            # We are the master process. Start the reloader loop.
            self._run_with_reloader(host=host, port=port)
            return

        from ..server import WebServer
        
        def on_inst(inst: "App") -> None:
            inst.exit_on_disconnect = True
            if self._cleanup_func:
                setattr(inst, "_browser_cleanup", self._cleanup_func)
                
        if not inspect.isclass(self.app):
            self.app.exit_on_disconnect = True
            
        ws = WebServer(self.app, on_instance=on_inst)
        log_config = None if getattr(sys, 'frozen', False) else uvicorn.config.LOGGING_CONFIG
        uvicorn.run(ws.app, host=host, port=port, log_config=log_config)
        
