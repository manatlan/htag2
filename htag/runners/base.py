import os
import sys
import time
import subprocess
import threading
from typing import TYPE_CHECKING, Union, Type, List, Any

if TYPE_CHECKING:
    from ..server import App

class BaseRunner:
    """Base class for all runners that execute an App."""
    def __init__(self, app: Union[Type["App"], "App"]):
        self.app = app

    def run(self, host: str = "127.0.0.1", port: int = 8000, reload: bool = False, **kwargs: Any) -> None:
        """Must be implemented by subclasses to start the server/UI."""
        raise NotImplementedError()

    def _run_with_reloader(self, host: str = "127.0.0.1", port: int = 8000) -> None:
        """
        Runs the normal runner in a subprocess and watches for file changes.
        If a .py file changes, it restarts the subprocess.
        """
        import stat

        def get_mtimes() -> dict:
            mtimes = {}
            for root, _, files in os.walk("."):
                for file in files:
                    if file.endswith(".py"):
                        path = os.path.join(root, file)
                        try:
                            mtimes[path] = os.stat(path)[stat.ST_MTIME]
                        except OSError:
                            continue
            return mtimes

        import logging
        logger = logging.getLogger("htag2")

        # Copy environment and add flags
        env = os.environ.copy()
        env["HTAG_RELOADER"] = "1"
        
        # Determine the command to restart the current script
        cmd = [sys.executable] + sys.argv

        while True:
            # Start the child worker
            logger.info("Starting worker process...")
            process = subprocess.Popen(cmd, env=env)
            
            # Record mtimes
            last_mtimes = get_mtimes()

            # Watch loop
            try:
                while process.poll() is None:
                    time.sleep(0.5)
                    current_mtimes = get_mtimes()
                    changed = False
                    for path, mtime in current_mtimes.items():
                        if path not in last_mtimes or mtime > last_mtimes[path]:
                            logger.warning(f"** Code changed ({path}), restarting server... **")
                            changed = True
                            break
                    
                    if changed:
                        process.terminate()
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            process.kill()
                        break
            except KeyboardInterrupt:
                logger.info("KeyboardInterrupt, exiting...")
                if process.poll() is None:
                    process.terminate()
                break

            # If the process exited cleanly (not due to a file change), we also exit
            # On Windows returncode might be positive, on Unix it might be negative signal (e.g. -15 for SIGTERM)
            import signal
            if process.returncode is not None and process.returncode not in (0, signal.SIGTERM, -signal.SIGTERM):
                # Process exited abnormally, but maybe we want to keep watching?
                # For now let's just break
                break
            elif process.returncode == 0:
                # Normal exit (browser closed)
                break
