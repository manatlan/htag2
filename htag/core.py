
import html
import uuid
import json
import threading
import logging

logger = logging.getLogger("htagravity")

class GTag:
    def _render_attrs(self):
        """
        Renders the HTML attributes of the tag.
        Converts python-style underscores to hyphens (e.g., data_id becomes data-id).
        Always ensures an ID is present for client-side syncing.
        """
        attrs_list = []
        for k, v in self._attrs.items():
            # Convert python-style attributes (data_id -> data-id)
            attr_name = k.replace("_", "-")
            attrs_list.append(f'{attr_name}="{html.escape(str(v))}"')
        
        attrs = " ".join(attrs_list)
        if attrs: attrs = " " + attrs
        attrs += f' id="{self.id}"'
        return attrs

    def __init__(self, *args, **kwargs):
        """
        Initializes a GTag.
        - args: Child elements (strings or other GTags). The first arg is the tag name if self.tag is None.
        - kwargs: HTML attributes (prefixed with '_') or events (prefixed with 'on').
        """
        self._lock = threading.RLock()
        self._childs = []
        self._parent = None
        self._attrs = {}
        self._events = {}
        self._dirty = False
        self._js_calls = []

        # If tag is not set by subclass (class attribute), take it from first arg
        if getattr(self, "tag", None) is None:
            if args:
                self.tag = args[0]
                args = args[1:]
            else:
                self.tag = "div" # fallback

        self.id = str(uuid.uuid4())
        logger.debug("Created Tag: %s (id: %s)", self.tag, self.id)

        for arg in args:
            self.add(arg)

        for k, v in kwargs.items():
            if k.startswith("_"):
                # Attributes like _class="foo" -> class="foo"
                self._attrs[k[1:]] = v
            elif k.startswith("on"):
                # Events like onclick=my_callback -> saved in self._events
                self._events[k[2:]] = v

    def add(self, *content):
        with self._lock:
            for item in content:
                if item is None: continue
                if isinstance(item, (list, tuple)):
                    self.add(*item)
                else:
                    self._childs.append(item)
                    if isinstance(item, GTag):
                        item._parent = self
            self._dirty = True
        return self

    def __iadd__(self, other):
        return self.add(other)

    def __setattr__(self, name, value):
        """
        Magic attribute handling:
        - Internal attributes are set normally.
        - Attributes starting with '_' are treated as HTML attributes.
        - Attributes starting with 'on' are treated as event callbacks.
        - Setting an HTML attribute or event marks the tag as 'dirty' for client-side update.
        """
        if name in ["_lock", "_childs", "_attrs", "_events", "_dirty", "_js_calls", "_parent", "tag", "id"]:
            super().__setattr__(name, value)
        elif name.startswith("_"):
            # HTML attribute (e.g., self._class = "foo")
            attr_name = name[1:]
            with self._lock:
                self._attrs[attr_name] = value
                self._dirty = True
        elif name.startswith("on") and callable(value):
            # Event (e.g., self.onclick = my_callback)
            with self._lock:
                self._events[name[2:]] = value
                self._dirty = True
        else:
            # Regular Python attribute
            super().__setattr__(name, value)

    def __getattr__(self, name):
        if name.startswith("_") and name[1:] in self._attrs:
            return self._attrs[name[1:]]
        return super().__getattribute__(name)

    def __add__(self, other):
        if isinstance(other, list):
            return [self] + other
        return [self, other]

    def __radd__(self, other):
        if isinstance(other, list):
            return other + [self]
        return [other, self]

    def remove(self, item):
        with self._lock:
            if item in self._childs:
                self._childs.remove(item)
                item._parent = None
                self._dirty = True
        return self

    def remove_self(self):
        if self._parent:
            self._parent.remove(self)
        return self

    def clear(self):
        with self._lock:
            self._childs = []
            self._dirty = True
        return self

    def add_class(self, name):
        with self._lock:
            classes = self._attrs.get("class", "").split()
            if name not in classes:
                classes.append(name)
                self._attrs["class"] = " ".join(classes)
                self._dirty = True
        return self

    def call_js(self, script):
        self._js_calls.append(script)
        return self

    def __str__(self):
        attrs = self._render_attrs()
        inner = "".join([str(child) for child in self._childs])
        
        if self.tag:
            return f"<{self.tag}{attrs}>{inner}</{self.tag}>"
        else:
            return inner

class Input(GTag):
    def __init__(self, **kwargs):
        super().__init__("input", **kwargs)
    def __str__(self):
         return f"<input{self._render_attrs()}/>"

def prevent(func):
    """Decorator to mark an event handler as needing preventDefault()"""
    func._htag_prevent = True
    return func

def stop(func):
    """Decorator to mark an event handler as needing stopPropagation()"""
    func._htag_stop = True
    return func

class TagCreator:
    def __init__(self):
        self._registry = {}

    def __getattr__(self, name):
        """
        Dynamically creates GTag subclasses on the fly.
        Allows using 'Tag.Div(...)', 'Tag.Button(...)', etc.
        """
        if name in self._registry:
            return self._registry[name]
        
        # Create a dynamic subclass of GTag
        tag_name = name.lower()
        # We cache it in registry for performance and consistency
        new_class = type(name, (GTag,), {"tag": tag_name})
        self._registry[name] = new_class
        return new_class

Tag = TagCreator() # Singleton instance
Tag._registry["Input"] = Input

