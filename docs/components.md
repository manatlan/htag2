# Components

Components are the building blocks of an `htag` application. Every visual element is a `GTag` or a subclass of it.

## GTag

`GTag` is the core class. It handles HTML rendering, state management, and lifecycle.

### Creating a Component

You can create a custom component by subclassing `GTag`:

```python
from htag import GTag

class MyComponent(GTag):
    def __init__(self, name):
        super().__init__()
        self.tag = "div"  # Optional: default is "div"
        self._class = "my-class"
        self.add(f"Hello {name}!")
```

### Tree Manipulation

- `self.add(*content)`: Adds children (strings or other GTags).
- `self += content`: An elegant shorthand for `self.add(content)`.
- `self.remove(child)`: Removes a child.
- `self.clear()`: Removes all children.
- `self.remove_self()`: Removes the component from its parent.

```python
# Using the += operator
row = Tag.div()
row += Tag.span("Left")
row += Tag.span("Right")
```

## Attributes and Style

Attributes are managed using properties starting with an underscore. This mapping covers all standard and custom HTML attributes.

```python
# Mapping attributes
img = Tag.img(_src="logo.png", _alt="Logo")
img._width = "100"

# Custom data attributes
div = Tag.div(_data_user_id="123")
```

- `_class`: Maps to the `class` attribute.
- `_id`: Maps to the `id` attribute.
- `_style`: Maps to the `style` attribute.
- `_any_thing`: Maps to `any-thing` in the rendered HTML.

---

## The Tag Creator

The `Tag` singleton allows you to create standard HTML elements dynamically using a clean syntax:

```python
from htag import Tag

# Equivalent to <div class="foo">content</div>
d = Tag.div("content", _class="foo")

# Equivalent to <br/> (Void Element)
b = Tag.br()

# Equivalent to <input type="text" value="hello"/>
i = Tag.input(_type="text", _value="hello")
```

### Void Elements

`htag` automatically handles HTML void elements (self-closing tags) like `input`, `img`, `br`, `hr`, etc. You don't need to specify a closing tag for these.

---

[← Home](index.md) | [Next: Events →](events.md)
