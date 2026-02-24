---
name: htagravity-development
description: Guidelines and best practices for building modern, state-of-the-art web applications using the htagravity framework.
---

# htagravity Developer Skill

Use this skill to design, implement, and refine web applications using the **htagravity** framework.

## Core Architecture

### 1. Components (`Tag`)
Every UI element in htagravity is a component created via `Tag`.
- Use the `Tag` factory for standard HTML elements (e.g., `Tag.div`, `Tag.button`).
- Create custom components by subclassing any `Tag.*` class.
- Add children using `+=` or the `<=` operator (e.g., `self += Tag.p("hello")` or `self <= Tag.p("hello")`).
- Use the `.root` property to get a reference to the main `Tag.App` instance (useful for triggering app-level events or modals).
- Use `.parent` to access the parent component, and `.childs` to access the list of child components.

```python
from htag import Tag

class MyComponent(Tag.div):
    def __init__(self, name):
        super().__init__()
        self += Tag.h1(f"Hello {name}")
```

### 2. Component Lifecycle
htagravity provides three lifecycle hooks to override on custom components:
- `init(self)`: Replaces `__init__` to safely initialize variables without `super()` boilerplate.
- `on_mount(self)`: Fired when the component is firmly attached to the main `App` tree (`self.root` is ready).
- `on_unmount(self)`: Fired when the component is removed, ideal for cleaning up tasks, caches, or event listeners.

### 3. Composite Components
When creating complex UI components (like a Card or a Window), you should override the `add(self, o)` method so that when users do `my_card += content`, the content goes into the correct inner container, not the root tag.

```python
class Card(Tag.div):
    def __init__(self, title):
        super().__init__(_class="card")
        self += Tag.h2(title)
        self.body = Tag.div(_class="card-body")
        # Use Tag.div.add to bypass the overridden add method during init
        Tag.div.add(self, self.body)

    def add(self, o):
        # Redirect append operations (+-) to the body container
        self.body += o
```

### 3. State & Reactivity
htagravity uses a "dirty-marking" system for UI updates.
- **HTML Attributes**: MUST start with `_` to be rendered as HTML attributes.
  - Correct: `_class="btn"`, `_src="image.png"`, `_type="checkbox"`
  - Incorrect: `class="btn"`, `src="image.png"`
- **Events**: Properties starting with `_on` are mapped to Python callbacks.

### 4. Forms & Inputs
htagravity automatically binds input events to Python.
- For text/number inputs, the current value is accessed safely via event handlers: `val = event.value`
- For checkboxes/toggles, the framework synchronizes the boolean state. Access it safely using `getattr(self.checkbox, "_value", False)`. Do not use `.value` directly on a checkbox component as it will raise an `AttributeError`.

### 5. Resiliency & Fallback
The `htag/server.py` implementation is fully robust against network irregularities:
- **WebSocket to HTTP Fallback**: If a WebSocket drops or fails to connect, the Javascript bridge automatically falls back to utilizing standard HTTP POST requests (`/event`) and Server-Sent Events (`/stream`).
- **Graceful Reconnections**: A user pressing F5 will not kill the server thread. The server only exits when the browser tab is explicitly closed or navigates away cleanly without returning within the 1-second reconnect window.

## Best Practices

### Layout & Styling
- Define CSS/JS dependencies in the `statics` class attribute on your main `App` class.
- Use modern, curated color palettes and typography.
- Prefer `Tag.style` and `Tag.script`. Remember to use `_src` for script/image URLs.

```python
class App(Tag.App):
    statics = [
        Tag.script(_src="https://cdn.tailwindcss.com"),
        Tag.style("body { background-color: #f8fafc; }")
    ]
```

### Event Control
Use decorators to control event behavior:
- `@prevent`: Calls `event.preventDefault()` on the client side.
- `@stop`: Calls `event.stopPropagation()` on the client side.

## Runner Choice
- **`ChromeApp`**: Primary choice. Attempts to launch a clean desktop-like Kiosk window via Chromium/Chrome binaries. If none are found, it falls back to opening the default system browser via `webbrowser.open`.
- **`WebApp`**: For shared web access. Opens in the default browser in a new tab.

## Multi-Session Deployment
To ensure each user has their own isolated session/state:
- **ALWAYS** pass the `Tag.App` class to the runner, NOT an instance.

```python
if __name__ == "__main__":
    from htag import ChromeApp
    ChromeApp(MyApp).run() # Correct: unique instance per user
```
