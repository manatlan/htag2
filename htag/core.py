from __future__ import annotations

import html
import logging
import threading
import weakref
from typing import Any, Callable


class _HtagLocal(threading.local):
    stack: list[GTag]
    current_eval: GTag | None  # Track which GTag is evaluating a reactive lambda

    def __init__(self) -> None:
        super().__init__()
        self.stack = []
        self.current_eval = None


_ctx = _HtagLocal()

logger = logging.getLogger("htag")


class State:
    def __init__(self, value: Any):
        self._value = value
        self._observers: weakref.WeakSet["GTag"] = weakref.WeakSet()

    @property
    def value(self) -> Any:
        # If a GTag is currently evaluating a reactive function, it records itself as an observer
        if _ctx.current_eval is not None:
            self._observers.add(_ctx.current_eval)
        return self._value

    @value.setter
    def value(self, new_value: Any) -> None:
        if self._value != new_value:
            self._value = new_value
            self._notify_observers()

    def set(self, value: Any) -> Any:
        self.value = value
        return value

    def notify(self) -> None:
        """Force notification after in-place mutation of mutable values (lists, dicts)."""
        self._notify_observers()

    def _notify_observers(self) -> None:
        for observer in self._observers:
            observer._GTag__dirty = True


VOID_ELEMENTS: set[str] = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class GTag:  # aka "Generic Tag"
    tag: str | None = None
    id: str

    def _render_attrs(self) -> str:
        """
        Renders the HTML attributes and events of the tag.
        Handles boolean attributes (True -> key only, False -> omit).
        """
        attrs_list: list[str] = []
        for k, v in self.__attrs.items():
            attr_name = k.replace("_", "-")
            val = self._eval_child(v, stringify=False)

            if val is True:
                attrs_list.append(attr_name)
            elif val is False or val is None:
                continue
            else:
                attrs_list.append(f'{attr_name}="{html.escape(str(val))}"')

        for name, callback in self.__events.items():
            if isinstance(callback, str):
                attrs_list.append(f'on{name}="{html.escape(callback)}"')
            else:
                js = f"htag_event('{self.id}', '{name}', event)"
                if getattr(callback, "_htag_prevent", False):
                    js = f"event.preventDefault(); {js}"
                if getattr(callback, "_htag_stop", False):
                    js = f"event.stopPropagation(); {js}"
                attrs_list.append(f'on{name}="{js}"')

        attrs = " ".join(attrs_list)
        if attrs:
            attrs = " " + attrs
        attrs += f' id="{self.id}"'
        return attrs

    def __enter__(self) -> GTag:
        _ctx.stack.append(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        _ctx.stack.pop()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initializes a GTag.
        - args: Child elements (strings or other GTags). The first arg is the tag name if self.tag is None.
        - kwargs: HTML attributes (prefixed with '_') or events (prefixed with 'on').
        """
        self.__lock = threading.RLock()
        self.__attrs: dict[str, Any] = {}
        self.__events: dict[str, Callable | str] = {}
        self.__dirty = False
        self.__js_calls: list[str] = []
        self.__rendered_callables: dict[Callable, list[GTag]] = {}

        # Public properties for tree traversal
        self.childs: list[str | GTag | Callable] = []
        self.parent: GTag | None = None
        self.id: str = ""  # placeholder

        # If tag is not set by subclass (class attribute), take it from first arg
        if getattr(self, "tag", None) is None:
            if args:
                self.tag = args[0].replace("_", "-")
                args = args[1:]
            else:
                self.tag = "div"  # fallback

        self.id = f"{self.tag}-{id(self)}"
        logger.debug("Created Tag: %s (id: %s)", self.tag, self.id)

        left_kwargs: dict[str, Any] = {}
        for k, v in kwargs.items():
            if k.startswith("_on"):
                # Events like _onclick=my_callback -> saved in self.__events
                self.__events[k[3:]] = v
            elif k.startswith("_"):
                # Attributes like _class="foo" -> class="foo"
                self.__attrs[k[1:]] = v
            else:
                left_kwargs[k] = v

        _ctx.stack.append(self)
        try:
            self.init(*args, **left_kwargs)
        finally:
            _ctx.stack.pop()

        if _ctx.stack:
            _ctx.stack[-1].add(self)

    def init(self, *args: Any, **kwargs: Any) -> None:
        """Called automatically at the end of GTag initialization."""
        for arg in args:
            self.add(arg)

    def on_mount(self) -> None:
        """Called when this tag (and its descendants) is attached to the App root."""
        pass

    def on_unmount(self) -> None:
        """Called when this tag (and its descendants) is detached from the App root."""
        pass

    def _trigger_mount(self) -> None:
        self.on_mount()
        for child in self.childs:
            if isinstance(child, GTag):
                child._trigger_mount()
        for tag_list in self.__rendered_callables.values():
            for t in tag_list:
                t._trigger_mount()

    def _trigger_unmount(self) -> None:
        self.on_unmount()
        for child in self.childs:
            if isinstance(child, GTag):
                child._trigger_unmount()
        for tag_list in self.__rendered_callables.values():
            for t in tag_list:
                t._trigger_unmount()

    def add(self, *content: Any) -> "GTag":
        for item in content:
            if item is None:
                continue
            if isinstance(item, (list, tuple)):
                self.add(*item)
            else:
                if isinstance(item, GTag):
                    if item.parent is not None and item.parent is not self:
                        item.remove_self()

                with self.__lock:
                    if isinstance(item, GTag):
                        if item in self.childs:
                            self.childs.remove(item)
                        item.parent = self
                        if self.root is not None:
                            item._trigger_mount()
                    elif callable(item):
                        # Reactive function (lambda), will be evaluated on render
                        pass

                    self.childs.append(item)
                    self.__dirty = True
        return self

    def __iadd__(self, other: Any) -> "GTag":
        return self.add(other)

    def __le__(self, other: Any) -> "GTag":
        return self.add(other)

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Magic attribute handling:
        - Internal attributes are set normally.
        - Attributes starting with '_' are treated as HTML attributes.
        - Attributes starting with 'on' are treated as event callbacks.
        - Setting an HTML attribute or event marks the tag as 'dirty' for client-side update.
        """
        if name.startswith("_GTag__") or name in ("childs", "parent", "tag", "id"):
            super().__setattr__(name, value)
        elif name.startswith("_on") and (callable(value) or isinstance(value, str)):
            # Event (e.g., self._onclick = my_callback or self._onclick = "alert(1)")
            with self.__lock:
                self.__events[name[3:]] = value
                self.__dirty = True
        elif name.startswith("_"):
            # HTML attribute (e.g., self._class = "foo")
            attr_name = name[1:]
            with self.__lock:
                self.__attrs[attr_name] = value
                self.__dirty = True
        else:
            # Regular Python attribute
            super().__setattr__(name, value)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_") and name[1:] in self.__attrs:
            return self.__attrs[name[1:]]
        return super().__getattribute__(name)

    def __add__(self, other: Any) -> list[Any]:
        if isinstance(other, list):
            return [self] + other
        return [self, other]

    def __radd__(self, other: Any) -> list[Any]:
        if isinstance(other, list):
            return other + [self]
        return [other, self]

    def remove(self, item: str | GTag | Callable) -> GTag:
        with self.__lock:
            if item in self.childs:
                if isinstance(item, GTag):
                    if self.root is not None:
                        item._trigger_unmount()
                self.childs.remove(item)
                if isinstance(item, GTag):
                    item.parent = None
                self.__dirty = True
        return self

    def remove_self(self) -> "GTag":
        if self.parent:
            self.parent.remove(self)
        return self

    @property
    def root(self) -> GTag | None:
        current: GTag | None = self
        while current is not None:
            if isinstance(current, Tag.App):
                return current
            current = current.parent
        return None

    @property
    def text(self) -> str:
        """Returns all string children concatenated."""
        return "".join(c for c in self.childs if isinstance(c, str))

    @text.setter
    def text(self, value: Any) -> None:
        """Clears all children and sets the text content."""
        self.clear()
        self.add(str(value))

    def clear(self) -> "GTag":
        with self.__lock:
            for child in self.childs:
                if isinstance(child, GTag):
                    if self.root is not None:
                        child._trigger_unmount()
                    child.parent = None
            self.childs = []
            self.__rendered_callables.clear()
            self.__dirty = True
        return self

    def add_class(self, name: str) -> "GTag":
        with self.__lock:
            classes = self.__attrs.get("class", "").split()
            if name not in classes:
                classes.append(name)
                self.__attrs["class"] = " ".join(classes)
                self.__dirty = True
        return self

    def remove_class(self, name: str) -> "GTag":
        with self.__lock:
            classes = self.__attrs.get("class", "").split()
            if name in classes:
                classes.remove(name)
                self.__attrs["class"] = " ".join(classes)
                self.__dirty = True
        return self

    def call_js(self, script: str) -> "GTag":
        self.__js_calls.append(script)
        return self

    # --- Public API for server-side access (avoids name-mangled access) ---

    @property
    def is_dirty(self) -> bool:
        """Whether this tag has pending changes that need re-rendering."""
        return self.__dirty

    def _reset_dirty(self) -> None:
        """Clear the dirty flag after rendering."""
        self.__dirty = False

    def _get_rendered_callables(self) -> dict[Callable, list["GTag"]]:
        """Return the dict of callable -> rendered GTag children."""
        return self.__rendered_callables

    def _consume_js_calls(self) -> list[str]:
        """Return and clear pending JS calls."""
        calls = list(self.__js_calls)
        self.__js_calls.clear()
        return calls

    def _get_events(self) -> dict[str, Callable | str]:
        """Return the events dict."""
        return self.__events

    def _get_attrs(self) -> dict[str, Any]:
        """Return the attributes dict."""
        return self.__attrs

    def _set_attr_direct(self, name: str, value: Any) -> None:
        """Set an attribute directly without triggering dirty flag (for input sync)."""
        with self.__lock:
            self.__attrs[name] = value

    def _eval_child(self, child: Any, stringify: bool = True) -> Any:
        """Evaluates a child for rendering. If it's a callable, evaluate it recursively and track observers."""
        if callable(child):
            old_eval = _ctx.current_eval
            _ctx.current_eval = self
            try:
                res = child()
            finally:
                _ctx.current_eval = old_eval

            # Track GTag objects generated by this callable for event dispatching
            tags: list[GTag] = []

            def collect(item: Any) -> None:
                if isinstance(item, GTag):
                    item.parent = self
                    tags.append(item)
                elif isinstance(item, (list, tuple)):
                    for i in item:
                        collect(i)

            collect(res)
            self.__rendered_callables[child] = tags

            return self._eval_child(
                res, stringify
            )  # Recursive call to handle list/tags returned

        if isinstance(child, (list, tuple)):
            return "".join(str(self._eval_child(i)) for i in child)

        if child is None:
            return "" if stringify else None
        return str(child) if stringify else child

    def __str__(self) -> str:
        """Renders the tag and its children to an HTML string."""
        with self.__lock:
            attrs = self._render_attrs()
            content = "".join(str(self._eval_child(c)) for c in self.childs)

            if self.tag in VOID_ELEMENTS:
                return f"<{self.tag}{attrs}/>"

            if self.tag:
                return f"<{self.tag}{attrs}>{content}</{self.tag}>"
            else:
                return content


def prevent(func: Callable) -> Callable:
    """Decorator to mark an event handler as needing preventDefault()"""
    setattr(func, "_htag_prevent", True)
    return func


def stop(func: Callable) -> Callable:
    """Decorator to mark an event handler as needing stopPropagation()"""
    setattr(func, "_htag_stop", True)
    return func


class TagCreator:
    def __init__(self) -> None:
        self._registry: dict[str, type[GTag]] = {}

    def __getattr__(self, name: str) -> type[GTag]:
        """
        Dynamically creates GTag subclasses on the fly.
        Allows using 'Tag.Div(...)', 'Tag.Button(...)', etc.
        """
        if name in self._registry:
            return self._registry[name]

        # Create a dynamic subclass of GTag
        tag_name = name.lower().replace("_", "-")
        # We cache it in registry for performance and consistency
        new_class = type(name, (GTag,), {"tag": tag_name})
        self._registry[name] = new_class
        return new_class


Tag = TagCreator()  # Singleton instance
