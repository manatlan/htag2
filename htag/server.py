import asyncio
import json
import os
import threading
import uuid
import inspect
import logging
from typing import Any, Dict, Optional, Union, List, Callable, Type, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response, Cookie
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
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
var ws;
var use_fallback = false;
var sse;
window._htag_callbacks = {}; // Store promise resolvers

function init_ws() {
    ws = new WebSocket("ws://" + window.location.host + "/ws");
    
    ws.onopen = function() {
        console.log("htag: websocket connected");
    };

    ws.onmessage = function(event) {
        var data = JSON.parse(event.data);
        handle_payload(data);
    };

    ws.onerror = function(err) {
        console.warn("htag: websocket error, switching to HTTP fallback (SSE)", err);
        fallback();
    };

    ws.onclose = function(event) {
        // If it closes abnormally or very quickly, trigger fallback
        if (event.code !== 1000 && event.code !== 1001) {
             console.warn("htag: websocket closed unexpectedly, switching to HTTP fallback (SSE)", event);
             fallback();
        }
    };
}

function handle_payload(data) {
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
}

function fallback() {
    if (use_fallback) return; 
    use_fallback = true;
    if(ws) ws.close(); // Ensure ws is torn down
    
    sse = new window.EventSource("/stream");
    sse.onmessage = function(event) {
        handle_payload(JSON.parse(event.data));
    };
    sse.onerror = function(err) {
        console.error("htag: SSE error", err);
    };
}

// Start with WebSockets
init_ws();

// Function called by HTML 'on{event}' attributes to send interactions back to Python
// Returns a Promise that resolves with the server's return value.
function htag_event(id, event_name, event) {
    var callback_id = Math.random().toString(36).substring(2);
    
    // Determine the value to send (handle checkboxes specifically)
    var val = null;
    if (event.target) {
        if (event.target.type === 'checkbox') {
            val = event.target.checked;
        } else {
            val = event.target.value;
        }
    }
    
    var data = {
        value: val,
        key: event.key,
        pageX: event.pageX,
        pageY: event.pageY,
        callback_id: callback_id
    };
    var payload = {id: id, event: event_name, data: data};
    
    if(!use_fallback && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(payload));
    } else {
        // Use HTTP POST Fallback
        // (Fastest trigger even if SSE is still initializing)
        if (!use_fallback) fallback();
        fetch("/event", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        }).catch(err => console.error("htag event POST error:", err));
    }

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
        @self.app.get("/logo.jpg")
        async def favicon():
            # Try to find the logo with different common extensions
            for ext in ["png", "jpg", "jpeg", "ico"]:
                logo_path = os.path.join(os.getcwd(), f"docs/assets/logo.{ext}")
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

        @self.app.get("/stream")
        async def stream_endpoint(request: Request, htag_sid: Optional[str] = Cookie(None)):
            if not htag_sid:
                return Response(status_code=400, content="No session cookie")
                
            instance = self._get_instance(htag_sid)
            return StreamingResponse(instance._handle_sse(request), media_type="text/event-stream")

        @self.app.post("/event")
        async def event_endpoint(request: Request, htag_sid: Optional[str] = Cookie(None)):
            if not htag_sid:
                return Response(status_code=400, content="No session cookie")
                
            instance = self._get_instance(htag_sid)
            try:
                msg = await request.json()
                # Run the event in the background to not block the HTTP response
                # Broadcast will trigger async queues anyway
                asyncio.create_task(instance.handle_event(msg, None))
                return {"status": "ok"}
            except Exception as e:
                logger.error("POST event error: %s", e)
                return Response(status_code=500, content=str(e))

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
        self.sse_queues: Set[asyncio.Queue] = set() # Queues for active SSE connections
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
                <link rel="icon" href="/logo.png">
                <script>{CLIENT_JS}</script>
                {statics_html}
            </head>
            {self.render_initial()}
        </html>
        """
        return html_content


    async def _handle_sse(self, request: Request):
        queue = asyncio.Queue()
        self.sse_queues.add(queue)
        logger.info("New SSE connection (Total clients: %d)", len(self.sse_queues))
        
        # Send initial state
        try:
            updates = {self.id: self.render_initial()}
            js = []
            self.collect_updates(self, {}, js)
            
            payload = json.dumps({
                "action": "update",
                "updates": updates,
                "js": js
            })
            # EventSource requires 'data: {payload}\n\n'
            yield f"data: {payload}\n\n"
        except Exception as e:
            logger.error("Failed to send initial SSE state: %s", e)

        try:
            while True:
                # Wait for next broadcast payload or client disconnect
                message = await queue.get()
                yield f"data: {message}\n\n"
        except asyncio.CancelledError: # Raised when client disconnects
            pass
        except Exception as e:
            logger.error("SSE stream error: %s", e)
        finally:
            self.sse_queues.discard(queue)
            logger.info("SSE disconnected (Total clients: %d)", len(self.sse_queues))
            asyncio.create_task(self._handle_disconnect())

    async def _handle_websocket(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.websockets.add(websocket)
        logger.info("New WebSocket connection (Total WS clients: %d)", len(self.websockets))
        
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
            logger.info("WebSocket disconnected (Total WS clients: %d)", len(self.websockets))
            asyncio.create_task(self._handle_disconnect())

    async def _handle_disconnect(self) -> None:
        """Centralized disconnect handler to manage graceful shutdown across WS and SSE"""
        if self.websockets or self.sse_queues:
            return # Still active clients (WS or SSE)

        # Exit when last browser window is closed, IF enabled
        if self.exit_on_disconnect:
            # Give it a small delay in case of F5 / Page Refresh
            await asyncio.sleep(0.5)
            
            # Check again if a client reconnects during the delay
            if self.websockets or self.sse_queues:
                logger.info("Client reconnected quickly, aborting exit (likely F5)")
                return
                
            # Session-aware exit: only exit if NO other session has active connections
            other_active = False
            if hasattr(self, "_webserver") and len(self._webserver.instances) > 1:
                webserver = getattr(self, "_webserver")
                for sid, inst in webserver.instances.items():
                    if inst is not self and (inst.websockets or inst.sse_queues):
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
        with tag._GTag__lock:
            if getattr(tag, "_GTag__dirty", False):
                # This tag or one of its attributes changed, we re-render it entirely
                updates[tag.id] = self.render_tag(tag)
            
            # ALWAYS check children for JS calls (or deep updates if parent wasn't dirty)
            for child in tag.childs:
                if isinstance(child, GTag):
                    # If the tag was already added to updates, we don't need its partial HTML,
                    # but we ALWAYS need its JS calls.
                    self.collect_updates(child, updates, js_calls)
            # Extract and clear JS calls
            if getattr(tag, "_GTag__js_calls", []):
                js_calls.extend(tag._GTag__js_calls)
                tag._GTag__js_calls = []

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
        
        for child in tag.childs:
            if isinstance(child, GTag):
                self.collect_statics(child, result)

    async def handle_event(self, msg: Dict[str, Any], ws: Optional[WebSocket]) -> None:
        tag_id = msg.get("id")
        event_name = msg.get("event")
        
        if not isinstance(tag_id, str):
            return

        target_tag = self.find_tag(self, tag_id)
        if target_tag:
            callback_id = msg.get("data", {}).get("callback_id")
            # Auto-sync value from client (bypass __setattr__ to avoid re-rendering the input while typing)
            if "value" in msg.get("data", {}):
                with target_tag._GTag__lock:
                    target_tag._GTag__attrs["value"] = msg["data"]["value"]

            if event_name in target_tag._GTag__events:
                logger.info("Event '%s' on tag %s (id: %s)", event_name, target_tag.tag, target_tag.id)
                callback = target_tag._GTag__events[event_name]
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
                    error_msg = f"Error in {event_name} callback: {str(e)}\n{traceback.format_exc()}"
                    logger.error(error_msg)
                    # Use broadcast-like update for error reporting
                    err_payload = json.dumps({
                        "action": "update",
                        "updates": {},
                        "js": [f"console.error({repr(error_msg)})"],
                        "callback_id": callback_id,
                        "result": None
                    })
                    
                    if ws:
                        try:
                            await ws.send_text(err_payload)
                        except Exception:
                            pass
                    else:
                        # Fallback Mode: Trigger error broadcast through SSE
                        for queue in self.sse_queues:
                            queue.put_nowait(err_payload)
                            
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
            
            # Send to websocket clients
            dead_ws: List[WebSocket] = []
            for client in list(self.websockets):
                try:
                    await client.send_text(payload)
                except Exception:
                    dead_ws.append(client)
            for client in dead_ws:
                self.websockets.discard(client)
                
            # Send to SSE clients
            for queue in self.sse_queues:
                queue.put_nowait(payload)

    def render_tag(self, tag: GTag) -> str:
        """
        Renders a GTag to its HTML string representation.
        Before rendering, it injects 'htag_event' calls into HTML event attributes,
        enabling the bridge between DOM events and Python callbacks.
        """
        def process(t: GTag) -> None:
            if isinstance(t, GTag):
                with t._GTag__lock:
                    # Auto-inject oninput for inputs if not already there, to support auto-binding
                    if t.tag in ["input", "textarea", "select"] and "input" not in t._GTag__events:
                        t._GTag__attrs["oninput"] = f"htag_event('{t.id}', 'input', event)"
                    # Only clear dirty flag for objects that have it
                    if hasattr(t, "_GTag__dirty"):
                        t._GTag__dirty = False # Clear dirty flag after rendering
                    for child in t.childs:
                        if isinstance(child, GTag):
                            process(child)
        
        process(tag)
        return str(tag)

    def find_tag(self, root: GTag, tag_id: str) -> Optional[GTag]:
        if root.id == tag_id:
            return root
        for child in root.childs:
            if isinstance(child, GTag):
                found = self.find_tag(child, tag_id)
                if found: return found
        return None


from .core import Tag
Tag._registry["App"] = App

