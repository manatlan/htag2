# Events and Reactivity

`htag` provides a seamless way to handle user interactions on the server side.

## Event Handlers

You can attach event handlers to any `Tag` component using the `_on{event}` syntax:

```python
def my_callback(e):
    print(f"Clicked on {e.target.id}")
    e.target.add(Tag.span("!"))

btn = Tag.button("Click me", _onclick=my_callback)
```

### The Event Object

The `e` argument passed to the callback is an `Event` object containing:

- `e.target`: The `Tag` instance that triggered the event.
- `e.name`: The name of the event (e.g., "click").
- Data attributes like `e.value` (for inputs), `e.x`, `e.y` (for mouse events), etc.

## Automatic Binding (Magic Bind)

`htag` automatically synchronizes the state of input elements without requiring explicit event handlers.

When you use an `<input>`, `<textarea>`, or `<select>`, `htag` injects an `_oninput` event that updates the component's `_value` attribute in real-time on the server.

```python
class MyForm(Tag.App):
    def init(self):
        # No '_oninput' needed, it's automatic!
        self.entry = Tag.input(_value="Initial")
        self += self.entry
        self += Tag.button("Show", _onclick=lambda e: self.add(f"Value is: {self.entry._value}"))
```

## Async Handlers

`htag` fully supports `asyncio`. You can define callbacks as `async def`:

```python
async def my_async_callback(e):
    await asyncio.sleep(1)
    e.target.add("Done!")
```

## UI Streaming (Generators)

For long-running tasks that need to update the UI multiple times, you can use generators:

```python
def my_generator(e):
    e.target.add("Starting...")
    yield # Triggers a UI update to the client
    
    import time
    time.sleep(2)
    e.target.add("Halfway...")
    yield
    
    time.sleep(2)
    e.target.add("Finished!")
```

## Event Decorators

- `@prevent`: Calls `event.preventDefault()` in the browser.
- `@stop`: Calls `event.stopPropagation()` in the browser.

```python
from htag import prevent, stop

@prevent
def handle_submit(e):
    # Form won't reload the page
    pass
```

## Client-side JavaScript

You can execute arbitrary JavaScript from the server using `call_js()`:

```python
class MyTag(Tag.div):
    def boom(self, e):
        self.call_js("alert('BOOM!')")
```

---

[← Components](components.md) | [Next: Runners →](runners.md)
