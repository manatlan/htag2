# Advanced Features

Take your `htag` applications to the next level with these powerful features.

## Multi-Session Support

`htag` allows you to host unique application instances for different users using session cookies.

### How to use Multi-Session
To enable multi-session isolation, you must pass the **App class** (not an instance) to your runner:

```python
from htag import WebApp, Tag

class MyMultiUserApp(Tag.App):
    def init(self) -> None:
        pass

if __name__ == "__main__":
    # Passing the CLASS enables session isolation
    WebApp(MyMultiUserApp).run()
```

When a user visits the site, `htag` generates a unique session ID and creates a private instance of `MyMultiUserApp` for them.

You can bundle CSS and JavaScript with your components using the `statics` attribute.

> [!TIP]
> For component-specific CSS, the [Scoped Styles](components.md#scoped-styles) feature is usually preferred as it automatically handles CSS isolation.

```python
class StyledComponent(Tag.div):
    statics = [
        Tag.style(" .my-btn { color: lime; } "),
        Tag.link(_rel="stylesheet", _href="https://cdn.example.com/styles.css"),
        Tag.script(_src="https://cdn.example.com/lib.js")
    ]
```

`htag` ensures that statics are:

- Collected recursively from all active tags, including those created dynamically via reactive lambdas.
- Sent to the client only once per session.
- Injected into the `<head>` dynamically if they are added after the initial load.

## Performance Best Practices

1.  **Partial Updates**: `htag` only sends the HTML of "dirty" tags over the wire. Keep your components granular to minimize payload size.
2.  **State Management**: Use instance attributes on your components for local state. `htag` will automatically detect changes and queue re-renders.
3.  **Thread Safety**: `htag` components are thread-safe. You can modify the UI tree from background threads or async tasks safely.

## Troubleshooting

- **Logs**: Check the console logs. `htag` provides detailed INFO and DEBUG logs about sessions, WebSocket status, and event dispatching.
- **WebSocket connection**: Ensure your environment allows WebSocket connections (check firewalls/proxies). `htag` requires a constant WS link to function.

---

[← Runners](runners.md)
