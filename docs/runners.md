# Runners

Runners are responsible for hosting your `App` and launching the interface.

## WebApp

`WebApp` is the standard runner for web-based applications. By default, it starts the server without automatically opening a browser tab.

```python
from htag import WebApp, Tag

class HelloApp(Tag.App):
    pass

if __name__ == "__main__":
    WebApp(HelloApp).run(host="0.0.0.0", port=8000)
```

- **Default behavior**: 
    - Does not exit the server when the browser tab is closed.
    - Does **not** open a browser tab automatically (can be enabled with `run(open_browser=True)`).
- **Usage**: Best for tools that should run continuously or be accessible by multiple users.

## ChromeApp

`ChromeApp` launches your application as a standalone kiosk window using Google Chrome or Chromium.

```python
from htag import ChromeApp, Tag

class MyApp(Tag.App):
    pass

if __name__ == "__main__":
    ChromeApp(MyApp, width=600, height=800).run()
```

- **Features**:

    - Clean UI without URL bars or browser tabs.
    - Automatic cleanup of temporary browser profiles.
    - **Smart Exit**: Automatically shuts down the Python server when the window is closed (highly recommended for desktop-like tools).

## Base Runner API

All runners accept the `App` class (or instance) and have a `run()` method with common parameters:

- `host`: The IP address to bind to (default: "127.0.0.1").
- `port`: The port to listen on (default: 8000).

---

[← Events](events.md) | [Next: Advanced →](advanced.md)
