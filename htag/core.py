import html
import uuid
import json
import threading
import logging
from typing import Any, List, Dict, Optional, Union, Callable, Set, Type

logger = logging.getLogger("htagravity")

VOID_ELEMENTS: Set[str] = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr"
}

class GTag: # aka "Generic Tag"
    tag: Optional[str] = None
    id: str

    def _render_attrs(self) -> str:
        """
        Renders the HTML attributes and events of the tag.
        Converts python-style underscores to hyphens (e.g., data_id becomes data-id).
        Always ensures an ID is present for client-side syncing.
        """
        attrs_list: List[str] = []
        for k, v in self.__attrs.items():
            # Convert python-style attributes (data_id -> data-id)
            attr_name = k.replace("_", "-")
            attrs_list.append(f'{attr_name}="{html.escape(str(v))}"')
        
        for name, callback in self.__events.items():
            if isinstance(callback, str):
                # Literal JS string
                attrs_list.append(f'on{name}="{html.escape(callback)}"')
            else:
                # Python callback (wrapped in htag_event)
                # We check for decorators like @prevent or @stop
                js = f"htag_event('{self.id}', '{name}', event)"
                if getattr(callback, "_htag_prevent", False):
                    js = f"event.preventDefault(); {js}"
                if getattr(callback, "_htag_stop", False):
                    js = f"event.stopPropagation(); {js}"
                attrs_list.append(f'on{name}="{js}"')

        attrs = " ".join(attrs_list)
        if attrs: attrs = " " + attrs
        attrs += f' id="{self.id}"'
        return attrs

    def __init__(self, *args: Any, **kwargs: Any):
        """
        Initializes a GTag.
        - args: Child elements (strings or other GTags). The first arg is the tag name if self.tag is None.
        - kwargs: HTML attributes (prefixed with '_') or events (prefixed with 'on').
        """
        self.__lock = threading.RLock()
        self.childs: List[Union[str, 'GTag']] = []
        self.parent: Optional['GTag'] = None
        self.__attrs: Dict[str, Any] = {}
        self.__events: Dict[str, Callable] = {}
        self.__dirty = False
        self.__js_calls: List[str] = []

        # If tag is not set by subclass (class attribute), take it from first arg
        if getattr(self, "tag", None) is None:
            if args:
                self.tag = args[0]
                args = args[1:]
            else:
                self.tag = "div" # fallback

        self.id = f"{self.tag}-{id(self)}"
        logger.debug("Created Tag: %s (id: %s)", self.tag, self.id)

        for arg in args:
            self.add(arg)

        for k, v in kwargs.items():
            if k.startswith("_on"):
                # Events like _onclick=my_callback -> saved in self.__events
                self.__events[k[3:]] = v
            elif k.startswith("_"):
                # Attributes like _class="foo" -> class="foo"
                self.__attrs[k[1:]] = v

    def add(self, *content: Any) -> 'GTag':
        with self.__lock:
            for item in content:
                if item is None: continue
                if isinstance(item, (list, tuple)):
                    self.add(*item)
                else:
                    self.childs.append(item)
                    if isinstance(item, GTag):
                        item.parent = self
            self.__dirty = True
        return self

    def __iadd__(self, other: Any) -> 'GTag':
        return self.add(other)

    def __le__(self, other: Any) -> 'GTag':
        return self.add(other)

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Magic attribute handling:
        - Internal attributes are set normally.
        - Attributes starting with '_' are treated as HTML attributes.
        - Attributes starting with 'on' are treated as event callbacks.
        - Setting an HTML attribute or event marks the tag as 'dirty' for client-side update.
        """
        if name in ["_GTag__lock", "childs", "_GTag__attrs", "_GTag__events", "_GTag__dirty", "_GTag__js_calls", "parent", "tag", "id"]:
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

    def __add__(self, other: Any) -> List[Any]:
        if isinstance(other, list):
            return [self] + other
        return [self, other]

    def __radd__(self, other: Any) -> List[Any]:
        if isinstance(other, list):
            return other + [self]
        return [other, self]

    def remove(self, item: Union[str, 'GTag']) -> 'GTag':
        with self.__lock:
            if item in self.childs:
                self.childs.remove(item)
                if isinstance(item, GTag):
                    item.parent = None
                self.__dirty = True
        return self

    def remove_self(self) -> 'GTag':
        if self.parent:
            self.parent.remove(self)
        return self

    @property
    def root(self) -> Optional['GTag']:
        current = self
        while current is not None:
            if isinstance(current, Tag.App):
                return current
            current = current.parent
        return None

    def clear(self) -> 'GTag':
        with self.__lock:
            self.childs = []
            self.__dirty = True
        return self

    def add_class(self, name: str) -> 'GTag':
        with self.__lock:
            classes = self.__attrs.get("class", "").split()
            if name not in classes:
                classes.append(name)
                self.__attrs["class"] = " ".join(classes)
                self.__dirty = True
        return self

    def remove_class(self, name: str) -> 'GTag':
        with self.__lock:
            classes = self.__attrs.get("class", "").split()
            if name in classes:
                classes.remove(name)
                self.__attrs["class"] = " ".join(classes)
                self.__dirty = True
        return self

    def call_js(self, script: str) -> 'GTag':
        self.__js_calls.append(script)
        return self

    def __str__(self) -> str:
        attrs = self._render_attrs()
        
        if self.tag in VOID_ELEMENTS:
            return f"<{self.tag}{attrs}/>"
            
        inner = "".join([str(child) for child in self.childs])
        
        if self.tag:
            return f"<{self.tag}{attrs}>{inner}</{self.tag}>"
        else:
            return inner

def prevent(func: Callable) -> Callable:
    """Decorator to mark an event handler as needing preventDefault()"""
    setattr(func, "_htag_prevent", True)
    return func

def stop(func: Callable) -> Callable:
    """Decorator to mark an event handler as needing stopPropagation()"""
    setattr(func, "_htag_stop", True)
    return func

class TagCreator:
    def __init__(self):
        self._registry: Dict[str, Type[GTag]] = {}

    def __getattr__(self, name: str) -> Type[GTag]:
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

