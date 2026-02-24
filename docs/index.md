# htag Documentation

![htagravity logo](assets/logo.png)

`htag` is a modern, state-of-the-art Python library for building interactive web applications using a declarative, component-based approach. It bridges the gap between Python and the browser by synchronizing state and events over WebSockets.

[View on GitHub](https://github.com/manatlan/HTAGravity)

## Features

- **Component-Based**: Build complex UIs using reusable components via `Tag`.
- **Pythonic**: All UI logic and state management are written in pure Python.
- **Real-time**: Automatic synchronization of UI changes via WebSockets.
- **Responsive**: Built-in support for multiple runners (Browser, Chrome App).
- **Type-Safe**: Comprehensive type hints for a great developer experience.
- **Modern HTML**: Native support for HTML5 void elements.

## Quick Start

Creating a basic `htag` app is simple:

```python
from htag import Tag, WebApp

class HelloApp(Tag.App):
    def init(self):
        self += Tag.h1("Hello htag!")
        self <= Tag.button("Click Me", _onclick=lambda e: self.add(Tag.p("Clicked!")))

if __name__ == "__main__":
    WebApp(HelloApp).run()
```


### Core Concepts

1.  **Tag**: The helper class to dynamically create UI components (e.g., `Tag.div()`, `Tag.input()`).
2.  **App**: A specialized tag (accessed via `Tag.App`) that acts as the root of your application and manages the server lifecycle.
3.  **Runners**: Classes like `WebApp` or `ChromeApp` that host and launch your application.

---

[Next: Components →](components.md)
