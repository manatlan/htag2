class BaseRunner:
    """Base class for all runners that execute an App."""
    def __init__(self, app: "App"):
        self.app = app

    def run(self, host="127.0.0.1", port=8000):
        """Must be implemented by subclasses to start the server/UI."""
        raise NotImplementedError()
