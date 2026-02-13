# htag Documentation

`htag` is a modern, state-of-the-art Python library for building interactive web applications using a declarative, component-based approach. It bridges the gap between Python and the browser by synchronizing state and events over WebSockets.

[View on GitHub](https://github.com/manatlan/HTAGravity)

## Features

- **Component-Based**: Build complex UIs using reusable `GTag` components.
- **Pythonic**: All UI logic and state management are written in pure Python.
- **Real-time**: Automatic synchronization of UI changes via WebSockets.
- **Responsive**: Built-in support for multiple runners (Browser, Chrome App).
- **Type-Safe**: Comprehensive type hints for a great developer experience.
- **Modern HTML**: Native support for HTML5 void elements.

## Quick Start

Creating a basic `htag` app is simple:

```python
from htag import Tag, WebApp, App

class HelloApp(App):
    def __init__(self):
        super().__init__()
        self += Tag.h1("Hello htag!")
        self += Tag.button("Click Me", onclick=lambda e: self.add(Tag.p("Clicked!")))

if __name__ == "__main__":
    WebApp(HelloApp).run()
```

### Installation

`htag` requires Python 3.7+ and standard networking dependencies (FastAPI, Uvicorn).

```bash
pip install htagravity
```

### Core Concepts

1.  **GTag**: The base class for all UI components.
2.  **Tag**: A helper to dynamically create HTML elements (e.g., `Tag.div()`, `Tag.input()`).
3.  **App**: A specialized `GTag` that acts as the root of your application and manages the server lifecycle.
4.  **Runners**: Classes like `WebApp` or `ChromeApp` that host and launch your application.

---

[Next: Components →](components.md)
