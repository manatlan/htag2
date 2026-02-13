import asyncio
import json
import os
import threading
import uuid
import inspect
import logging
from typing import Any, Dict, Optional, Union, List, Callable, Type, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response, Cookie
from fastapi.responses import HTMLResponse, FileResponse
from .core import GTag

logger = logging.getLogger("htagravity")

class Event:
    """
    Simulates a DOM Event.
    Attributes are dynamically populated from the client message.
    """
    def __init__(self, target: GTag, msg: Dict[str, Any]):
        self.target = target
        self.id: str = msg.get("id", "")
        self.name: str = msg.get("event", "")
        # Flat access to msg['data'] (e.g., e.value, e.x, etc.)
        for k, v in msg.get("data", {}).items():
            setattr(self, k, v)
    
    def __getattr__(self, name: str) -> Any:
        return None

    def __repr__(self) -> str:
        return f"Event({self.name} on {self.target.tag})"

CLIENT_JS = """
// The client-side bridge that connects the browser to the Python server.
var ws = new WebSocket("ws://" + window.location.host + "/ws");
window._htag_callbacks = {}; // Store promise resolvers

ws.onmessage = function(event) {
    var data = JSON.parse(event.data);
    if(data.action == "update") {
        // Apply partial DOM updates received from the server
        for(var id in data.updates) {
            var el = document.getElementById(id);
            if(el) el.outerHTML = data.updates[id];
        }
        // Execute any JavaScript calls emitted by the Python tags
        if(data.js) {
            for(var i=0; i<data.js.length; i++) eval(data.js[i]);
        }
        // Inject new css/js statics if they haven't been loaded yet
        if(data.statics) {
            data.statics.forEach(s => {
                var div = document.createElement('div');
                div.innerHTML = s.trim();
                var node = div.firstChild;
                if (node && (node.tagName === "STYLE" || node.tagName === "LINK")) {
                    document.head.appendChild(node);
                }
            });
        }
        // Resolve promise if a result is returned for a callback
        if(data.callback_id && window._htag_callbacks[data.callback_id]) {
            window._htag_callbacks[data.callback_id](data.result);
            delete window._htag_callbacks[data.callback_id];
        }
    }
};
// Function called by HTML 'on{event}' attributes to send interactions back to Python
// Returns a Promise that resolves with the server's return value.
function htag_event(id, event_name, event) {
    var callback_id = Math.random().toString(36).substring(2);
    var data = {
        value: event.target ? event.target.value : null,
        key: event.key,
        pageX: event.pageX,
        pageY: event.pageY,
        callback_id: callback_id
    };
    ws.send(JSON.stringify({id: id, event: event_name, data: data}));
    return new Promise(resolve => {
        window._htag_callbacks[callback_id] = resolve;
    });
}
"""

# --- WebServer ---

class WebServer:
    """
    FastAPI implementation for hosting one or more App sessions.
    Handles the HTTP initial render and the WebSocket communication.
    """
    def __init__(self, tag_entity: Union[Type['App'], 'App'], on_instance: Optional[Callable[['App'], None]] = None):
        import threading
        self._lock = threading.Lock()
        self.tag_entity = tag_entity # Class or Instance
        self.on_instance = on_instance # Optional callback(instance)
        self.instances: Dict[str, 'App'] = {} # sid -> App instance
        self.app = FastAPI()
        self._setup_routes()

    def _get_instance(self, sid: str) -> 'App':
        if sid not in self.instances:
            with self._lock:
                if sid not in self.instances:
                    if inspect.isclass(self.tag_entity):
                        self.instances[sid] = self.tag_entity()
                        logger.info("Created new session instance for sid: %s", sid)
                    else:
                        # tag_entity is an App instance
                        self.instances[sid] = self.tag_entity # type: ignore
                        logger.info("Using shared instance for session sid: %s", sid)
                    
                    if self.on_instance:
                        self.on_instance(self.instances[sid])
                    
                    # Store a backlink to the webserver for session-aware logic
                    setattr(self.instances[sid], "_webserver", self)

        return self.instances[sid]

    def _setup_routes(self) -> None:
        @self.app.get("/")
        async def index(htag_sid: Optional[str] = Cookie(None)):
            if htag_sid is None:
                htag_sid = str(uuid.uuid4())
            
            instance = self._get_instance(htag_sid)
            res = HTMLResponse(instance._render_page())
            res.set_cookie("htag_sid", htag_sid)
            return res

        @self.app.get("/favicon.ico")
        @self.app.get("/logo.png")
        async def favicon():
            logo_path = os.path.join(os.getcwd(), "docs/assets/logo.png")
            if os.path.exists(logo_path):
                return FileResponse(logo_path)
            return Response(status_code=204)

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            htag_sid: Optional[str] = websocket.cookies.get("htag_sid")
            if htag_sid:
                instance = self._get_instance(htag_sid)
                await instance._handle_websocket(websocket)
            else:
                await websocket.close()

# --- App ---

class App(GTag):
    """
    The main application class for htagravity.
    Handles HTML rendering, event dispatching, and WebSocket communication.
    """
    statics: List[GTag] = []

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__("body", *args, **kwargs)
        self.exit_on_disconnect: bool = True # Default behavior
        self.websockets: Set[WebSocket] = set()
        self.sent_statics: Set[str] = set() # Track assets already in browser

    @property
    def app(self) -> FastAPI:
        """Property for backward compatibility: returns a FastAPI instance hosting this App."""
        if not hasattr(self, "_app_host"):
            self._app_host = WebServer(self)
        return self._app_host.app

    def _render_page(self) -> str:
        # Collect ALL statics from the whole tree on first load
        self.sent_statics.clear()
        all_statics: List[str] = []
        self.collect_statics(self, all_statics)
        self.sent_statics.update(all_statics)
        statics_html = "".join(all_statics)

        html_content = f"""
        <!DOCTYPE html>
        <html>
            <head>
                <title>{self.__class__.__name__}</title>
                <link rel="icon" type="image/png" href="/logo.png">
                <script>{CLIENT_JS}</script>
                {statics_html}
            </head>
            {self.render_initial()}
        </html>
        """
        return html_content


    async def _handle_websocket(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.websockets.add(websocket)
        logger.info("New WebSocket connection (Total clients: %d)", len(self.websockets))
        
        # Send initial state on connection/reconnection
        try:
            updates = {self.id: self.render_initial()}
            js = []
            self.collect_updates(self, {}, js) # We only want the JS calls here
            
            await websocket.send_text(json.dumps({
                "action": "update",
                "updates": updates,
                "js": js
            }))
            logger.debug("Sent initial state to client")
        except Exception as e:
            logger.error("Failed to send initial state: %s", e)

        try:
            while True:
                data = await websocket.receive_text()
                msg = json.loads(data)
                await self.handle_event(msg, websocket)
        except (WebSocketDisconnect, Exception):
            pass
        finally:
            if websocket in self.websockets:
                self.websockets.discard(websocket)
            logger.info("WebSocket disconnected (Total clients: %d)", len(self.websockets))
            
            if not self.websockets:
                # Exit when last browser window is closed, IF enabled
                if self.exit_on_disconnect:
                    # Session-aware exit: only exit if NO other session has active websockets
                    other_active = False
                    if hasattr(self, "_webserver") and len(self._webserver.instances) > 1:
                        webserver: WebServer = getattr(self, "_webserver")
                        for sid, inst in webserver.instances.items():
                            if inst is not self and inst.websockets:
                                other_active = True
                                break
                    
                    if not other_active:
                        logger.info("Last client of the last active session disconnected, exiting...")
                        if hasattr(self, "_browser_cleanup"):
                            self._browser_cleanup()
                        os._exit(0)
                    else:
                        logger.info("Session disconnected, but other sessions are still active.")
                else:
                    logger.info("Last client disconnected (server stays alive)")

    def render_initial(self) -> str:
        # Initial render of the page (body)
        return self.render_tag(self)

    def collect_updates(self, tag: GTag, updates: Dict[str, str], js_calls: List[str]) -> None:
        """
        Recursively traverses the tag tree to find 'dirty' tags that need re-rendering.
        Also collects pending JavaScript calls from tags.
        """
        with tag._lock:
            if tag._dirty:
                # This tag or one of its attributes changed, we re-render it entirely
                updates[tag.id] = self.render_tag(tag)
            
            # ALWAYS check children for JS calls (or deep updates if parent wasn't dirty)
            for child in tag._childs:
                if isinstance(child, GTag):
                    # If the tag was already added to updates, we don't need its partial HTML,
                    # but we ALWAYS need its JS calls.
                    self.collect_updates(child, updates, js_calls)
            
            if tag._js_calls:
                js_calls.extend(tag._js_calls)
                tag._js_calls = []

    def collect_statics(self, tag: GTag, result: List[str]) -> None:
        # Collect statics from class and instance
        s_instance = getattr(tag, "statics", [])
        s_class = getattr(tag.__class__, "statics", [])
        
        for s_list in [s_class, s_instance]:
            if not isinstance(s_list, (list, tuple)):
                s_list = [s_list]
            for s in s_list:
                s_str = str(s)
                if s_str not in result:
                    result.append(s_str)
        
        for child in tag._childs:
            if isinstance(child, GTag):
                self.collect_statics(child, result)

    async def handle_event(self, msg: Dict[str, Any], ws: WebSocket) -> None:
        tag_id = msg.get("id")
        event_name = msg.get("event")
        
        if not isinstance(tag_id, str):
            return

        target_tag = self.find_tag(self, tag_id)
        if target_tag:
            callback_id = msg.get("data", {}).get("callback_id")
            # Auto-sync value from client (bypass __setattr__ to avoid re-rendering the input while typing)
            if "value" in msg.get("data", {}):
                with target_tag._lock:
                    target_tag._attrs["value"] = msg["data"]["value"]

            if event_name in target_tag._events:
                logger.info("Event '%s' on tag %s (id: %s)", event_name, target_tag.tag, target_tag.id)
                callback = target_tag._events[event_name]
                event = Event(target_tag, msg)
                try:
                    if asyncio.iscoroutinefunction(callback):
                        res = await callback(event)
                    else:
                        res = callback(event)
                    
                    # Handle generators/async generators for intermediate rendering
                    if inspect.isasyncgen(res):
                        async for _ in res:
                            await self.broadcast_updates()
                        res = None # Async generators don't easily return a final value
                    elif inspect.isgenerator(res):
                        try:
                            while True:
                                next(res)
                                await self.broadcast_updates()
                        except StopIteration as e:
                            res = e.value # This is the return value of the generator
                except Exception as e:
                    import traceback
                    error_msg = f"Error in {event_name} callback: {str(e)}\\n{traceback.format_exc()}"
                    logger.error(error_msg)
                    # Use broadcast-like update for error reporting
                    await ws.send_text(json.dumps({
                        "action": "update",
                        "updates": {},
                        "js": [f"console.error({repr(error_msg)})"],
                        "callback_id": callback_id,
                        "result": None
                    }))
                    return
            else:
                res = None

            # Sanitize result: we don't want to send GTag instances (not JSON serializable)
            # This happens often with "self += Tag(...)" which returns self.
            if isinstance(res, GTag):
                res = True # Convert to a simple truthy value
            
            # Final broadcast after callback finishes, including the result if any
            await self.broadcast_updates(result=res, callback_id=callback_id)

    async def broadcast_updates(self, result: Any = None, callback_id: Optional[str] = None) -> None:
        """
        Collects all pending updates (tags, JS calls, statics) 
        and broadcasts them to all connected clients.
        Optional 'result' and 'callback_id' are used to resolve client-side Promises.
        """
        updates: Dict[str, str] = {}
        js_calls: List[str] = []
        self.collect_updates(self, updates, js_calls)
        
        all_statics: List[str] = []
        self.collect_statics(self, all_statics)
        new_statics = [s for s in all_statics if s not in self.sent_statics]
        
        if updates or js_calls or new_statics or callback_id:
            self.sent_statics.update(new_statics)
            
            data = {
                "action": "update",
                "updates": updates,
                "js": js_calls,
                "statics": new_statics
            }
            if callback_id:
                data["callback_id"] = callback_id
                data["result"] = result

            logger.debug("Broadcasting updates: %s (js calls: %d, result: %s)", 
                         list(updates.keys()), len(js_calls), result if callback_id else "n/a")
            
            payload = json.dumps(data)
            dead: List[WebSocket] = []
            for client in list(self.websockets):
                try:
                    await client.send_text(payload)
                except Exception:
                    dead.append(client)
            for client in dead:
                self.websockets.discard(client)

    def render_tag(self, tag: GTag) -> str:
        """
        Renders a GTag to its HTML string representation.
        Before rendering, it injects 'htag_event' calls into HTML event attributes,
        enabling the bridge between DOM events and Python callbacks.
        """
        def process(t: GTag) -> None:
            if isinstance(t, GTag):
                with t._lock:
                    # Auto-inject oninput for inputs if not already there, to support auto-binding
                    if t.tag in ["input", "textarea", "select"] and "input" not in t._events:
                        t._attrs["oninput"] = f"htag_event('{t.id}', 'input', event)"

                    # Convert registered python callbacks into htag_event(...) JS calls in HTML attributes
                    for event_name, callback in t._events.items():
                        js = f"htag_event('{t.id}', '{event_name}', event)"
                        
                        # Detect modifiers from decorators
                        prefix = ""
                        suffix = ""
                        if hasattr(callback, "_htag_prevent"):
                            prefix = "event.preventDefault();"
                            suffix = "; return false;"
                        if hasattr(callback, "_htag_stop"):
                            prefix += "event.stopPropagation();"
                            
                        # Overwrite or set the attribute
                        t._attrs[f"on{event_name}"] = f"{prefix}{js}{suffix}"
                    t._dirty = False # Clear dirty flag after rendering
                    for child in t._childs:
                        if isinstance(child, GTag):
                            process(child)
        
        process(tag)
        return str(tag)

    def find_tag(self, root: GTag, tag_id: str) -> Optional[GTag]:
        if root.id == tag_id:
            return root
        for child in root._childs:
            if isinstance(child, GTag):
                found = self.find_tag(child, tag_id)
                if found: return found
        return None


from .core import Tag
Tag._registry["App"] = App

