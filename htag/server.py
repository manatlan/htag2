import asyncio
import json
import os
import threading
import uuid
import inspect
import logging
from typing import Any, Dict, Optional, Union, List, Callable, Type, Set
from starlette.applications import Starlette
from starlette.websockets import WebSocket, WebSocketDisconnect
from starlette.requests import Request
from starlette.responses import (
    HTMLResponse,
    FileResponse,
    StreamingResponse,
    Response,
    JSONResponse,
)
from .core import GTag

logger = logging.getLogger("htag2")


class Event:
    """
    Simulates a DOM Event.
    Attributes are dynamically populated from the client message.
    """

    def __init__(self, target: GTag, msg: Dict[str, Any]) -> None:
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
var _base_path = window.location.pathname.endsWith("/") ? window.location.pathname : window.location.pathname + "/";
window._htag_callbacks = {}; // Store promise resolvers

// --- htag-error Web Component (Shadow DOM for style isolation) ---
class HtagError extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({mode: 'open'});
        this.shadowRoot.innerHTML = `
            <style>
                :host {
                    display: none;
                    position: fixed;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    width: 80%;
                    max-width: 600px;
                    background: #fee2e2;
                    border: 1px solid #ef4444;
                    border-left: 5px solid #ef4444;
                    color: #991b1b;
                    padding: 15px;
                    border-radius: 4px;
                    z-index: 2147483647;
                    font-family: system-ui, -apple-system, sans-serif;
                    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2);
                    max-height: 80vh;
                    overflow-y: auto;
                    text-align: left;
                }
                :host([show]) { display: block; }
                h3 { margin: 0 0 10px 0; font-size: 16px; }
                pre { background: #fef2f2; padding: 10px; border-radius: 4px; font-family: monospace; font-size: 12px; overflow-x: auto; margin:0; text-align: left; }
                .close { position: absolute; top: 10px; right: 15px; cursor: pointer; font-weight: bold; font-size: 18px; color: #ef4444; }
                .close:hover { color: #b91c1c; }
            </style>
            <div class="close" title="Close">×</div>
            <h3 id="title">Error</h3>
            <pre id="trace"></pre>
        `;
        this.shadowRoot.querySelector('.close').onclick = () => this.removeAttribute('show');
    }
    show(title, trace) {
        this.shadowRoot.getElementById('title').textContent = title;
        this.shadowRoot.getElementById('trace').textContent = trace || 'No traceback available.';
        this.setAttribute('show', '');
    }
}
customElements.define('htag-error', HtagError);

// Global references for UI overlays
var _error_overlay = document.createElement('htag-error');

document.addEventListener("DOMContentLoaded", () => {
    document.body.appendChild(_error_overlay);
});

window.onerror = function(message, source, lineno, colno, error) {
    if(_error_overlay && typeof _error_overlay.show === 'function') {
        _error_overlay.show("Client JavaScript Error", `${message}\\n${source}:${lineno}:${colno}\\n${error ? error.stack : ''}`);
    }
};
window.onunhandledrejection = function(event) {
    if(_error_overlay && typeof _error_overlay.show === 'function') {
        _error_overlay.show("Unhandled Promise Rejection", String(event.reason));
    }
};



function init_ws() {
    var ws_protocol = window.location.protocol === "https:" ? "wss://" : "ws://";
    ws = new WebSocket(ws_protocol + window.location.host + _base_path + "ws");
    
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
        
        // Ensure overlays are still in the DOM (in case the body was replaced)
        if(_error_overlay && _error_overlay.parentNode !== document.body) {
            document.body.appendChild(_error_overlay);
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
    } else if (data.action == "error") {
        if(_error_overlay && typeof _error_overlay.show === 'function') {
            _error_overlay.show("Server Error", data.traceback);
        } else {
            console.error("Server Error:", data.traceback);
        }
    }
}

function fallback() {
    if (use_fallback) return; 
    use_fallback = true;
    if(ws) ws.close(); // Ensure ws is torn down
    
    // Auto-reload mechanism
    if (window.HTAG_RELOAD) {
        console.log("htag: connection lost, starting auto-reload polling...");
        
        function poll_reload() {
            fetch("/").then(response => {
                if (response.ok) {
                    console.log("htag: server is back! Reloading page...");
                    window.location.reload();
                } else {
                    setTimeout(poll_reload, 500);
                }
            }).catch(err => {
                setTimeout(poll_reload, 500);
            });
        }
        
        setTimeout(poll_reload, 500);
        return; // Don't try SSE, we just want to reload the page when the server comes back
    }

    sse = new window.EventSource(_base_path + "stream");
    sse.onopen = () => console.log("htag: SSE connected");
    sse.onmessage = function(event) {
        handle_payload(JSON.parse(event.data));
    };
    sse.onerror = function(err) {
        console.error("htag: SSE error", err);
        if(_error_overlay && typeof _error_overlay.show === 'function') {
            _error_overlay.show("Connection Lost", "Server Sent Events connection failed.");
        }
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
        fetch(_base_path + "event", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        }).then(response => {
            if (!response.ok) {
                if(_error_overlay && typeof _error_overlay.show === 'function') {
                    _error_overlay.show("HTTP Error", `Server returned status: ${response.status}`);
                }
            }
        }).catch(err => {
            console.error("htag event POST error:", err);
            if(_error_overlay && typeof _error_overlay.show === 'function') {
                _error_overlay.show("Network Error", "Could not reach server to trigger event.");
            }
        });
    }

    return new Promise(resolve => {
        window._htag_callbacks[callback_id] = resolve;
    });
}
"""

# --- WebApp ---


class WebApp:
    """
    FastAPI implementation for hosting one or more App sessions.
    Handles the HTTP initial render and the WebSocket communication.
    """

    def __init__(
        self,
        tag_entity: Union[Type["App"], "App"],
        on_instance: Optional[Callable[["App"], None]] = None,
    ) -> None:
        self._lock = threading.Lock()
        self.tag_entity = tag_entity  # Class or Instance
        self.on_instance = on_instance  # Optional callback(instance)
        self.instances: Dict[str, "App"] = {}  # sid -> App instance
        self.app = Starlette()
        self._setup_routes()

    def _get_instance(self, sid: str) -> "App":
        if sid not in self.instances:
            with self._lock:
                if sid not in self.instances:
                    if inspect.isclass(self.tag_entity):
                        self.instances[sid] = self.tag_entity()
                        logger.info("Created new session instance for sid: %s", sid)
                    else:
                        # tag_entity is an App instance
                        self.instances[sid] = self.tag_entity  # type: ignore
                        logger.info("Using shared instance for session sid: %s", sid)

                    if self.on_instance:
                        self.on_instance(self.instances[sid])

                    # Store a backlink to the webserver for session-aware logic
                    setattr(self.instances[sid], "_webserver", self)

                    # Trigger lifecycle mount on the root App instance
                    self.instances[sid]._trigger_mount()

        return self.instances[sid]

    def _setup_routes(self) -> None:
        async def index(request: Request) -> HTMLResponse:
            htag_sid: Optional[str] = request.cookies.get("htag_sid")
            if htag_sid is None:
                htag_sid = str(uuid.uuid4())

            instance = self._get_instance(htag_sid)
            res = HTMLResponse(instance._render_page())
            res.set_cookie("htag_sid", htag_sid)
            return res

        async def favicon(request: Request) -> Response:
            # Try to find the logo with different common extensions
            for ext in ["png", "jpg", "jpeg", "ico"]:
                logo_path = os.path.join(os.getcwd(), f"docs/assets/logo.{ext}")
                if os.path.exists(logo_path):
                    return FileResponse(logo_path)
            return Response(status_code=204)

        async def websocket_endpoint(websocket: WebSocket) -> None:
            htag_sid: Optional[str] = websocket.cookies.get("htag_sid")
            if htag_sid:
                instance = self._get_instance(htag_sid)
                await instance._handle_websocket(websocket)
            else:
                await websocket.close()

        async def stream_endpoint(request: Request) -> Response:
            htag_sid: Optional[str] = request.cookies.get("htag_sid")
            if not htag_sid:
                return Response(status_code=400, content="No session cookie")

            instance = self._get_instance(htag_sid)
            return StreamingResponse(
                instance._handle_sse(request), media_type="text/event-stream"
            )

        async def event_endpoint(request: Request) -> Response:
            htag_sid: Optional[str] = request.cookies.get("htag_sid")
            if not htag_sid:
                return Response(status_code=400, content="No session cookie")

            instance = self._get_instance(htag_sid)
            try:
                msg = await request.json()
                # Run the event in the background to not block the HTTP response
                # Broadcast will trigger async queues anyway
                asyncio.create_task(instance.handle_event(msg, None))
                return JSONResponse({"status": "ok"})
            except Exception as e:
                logger.error("POST event error: %s", e)
                return Response(status_code=500, content=str(e))

        self.app.add_route("/", index)
        self.app.add_route("/favicon.ico", favicon)
        self.app.add_route("/logo.png", favicon)
        self.app.add_route("/logo.jpg", favicon)
        self.app.add_websocket_route("/ws", websocket_endpoint)
        self.app.add_route("/stream", stream_endpoint)
        self.app.add_route("/event", event_endpoint, methods=["POST"])


# --- App ---


class App(GTag):
    """
    The main application class for htag2.
    Handles HTML rendering, event dispatching, and WebSocket communication.
    """

    statics: List[GTag] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__("body", *args, **kwargs)
        self.exit_on_disconnect: bool = False  # Default behavior for Web/API apps
        self.debug: bool = True  # Local debug mode default
        self.websockets: Set[WebSocket] = set()
        self.sse_queues: Set[asyncio.Queue] = set()  # Queues for active SSE connections
        self.sent_statics: Set[str] = set()  # Track assets already in browser

    @property
    def app(self) -> Starlette:
        """Property for backward compatibility: returns a Starlette instance hosting this App."""
        if not hasattr(self, "_app_host"):
            self._app_host = WebApp(self)
        return self._app_host.app

    def _render_page(self) -> str:
        # 1. Render the initial body FIRST to populate __rendered_callables
        try:
            body_html = self.render_initial()
        except Exception as e:
            import traceback

            error_trace = traceback.format_exc()
            logger.error("Error during initial render: %s\n%s", e, error_trace)
            if self.debug:
                safe_trace = error_trace.replace("`", "\\`").replace("$", "\\$")
                body_html = f"<body><htag-error show='true'></htag-error><script>document.body.appendChild(document.createElement('htag-error')).show('Initial Render Error', `{safe_trace}`);</script></body>"
            else:
                body_html = "<body><h1>Internal Server Error</h1></body>"

        # 2. Collect ALL statics from the whole tree
        self.sent_statics.clear()
        all_statics: List[str] = []
        try:
            self.collect_statics(self, all_statics)
        except Exception:
            pass  # Fatal error already caught above
        self.sent_statics.update(all_statics)
        statics_html = "".join(all_statics)

        html_content = f"""
        <!DOCTYPE html>
        <html>
            <head>
                <title>{self.__class__.__name__}</title>
                <link rel="icon" href="/logo.png">
                <script>{CLIENT_JS}</script>
                <script>
                    window.HTAG_RELOAD = {"true" if getattr(self, "_reload", False) else "false"};
                </script>
                {statics_html}
            </head>
            {body_html}
        </html>
        """
        return html_content

    async def _handle_sse(self, request: Request):
        queue: asyncio.Queue = asyncio.Queue()
        self.sse_queues.add(queue)
        logger.info("New SSE connection (Total clients: %d)", len(self.sse_queues))

        # Send initial state
        try:
            updates = {self.id: self.render_initial()}
            js: List[str] = []
            self.collect_updates(self, {}, js)

            payload = json.dumps({"action": "update", "updates": updates, "js": js})
            # EventSource requires 'data: {payload}\n\n'
            yield f"data: {payload}\n\n"
        except Exception as e:
            logger.error("Failed to send initial SSE state: %s", e)

        try:
            while True:
                # Wait for next broadcast payload or client disconnect
                message = await queue.get()
                yield f"data: {message}\n\n"
        except asyncio.CancelledError:  # Raised when client disconnects
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
        logger.info(
            "New WebSocket connection (Total WS clients: %d)", len(self.websockets)
        )

        # Send initial state on connection/reconnection
        try:
            updates = {self.id: self.render_initial()}
            js: List[str] = []
            self.collect_updates(self, {}, js)  # We only want the JS calls here

            await websocket.send_text(
                json.dumps({"action": "update", "updates": updates, "js": js})
            )
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
            logger.info(
                "WebSocket disconnected (Total WS clients: %d)", len(self.websockets)
            )
            asyncio.create_task(self._handle_disconnect())

    async def _handle_disconnect(self) -> None:
        """Centralized disconnect handler to manage graceful shutdown across WS and SSE"""
        if self.websockets or self.sse_queues:
            return  # Still active clients (WS or SSE)

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
                logger.info(
                    "Last client of the last active session disconnected, exiting..."
                )
                if hasattr(self, "_browser_cleanup"):
                    self._browser_cleanup()
                os._exit(0)
            else:
                logger.info(
                    "Session disconnected, but other sessions are still active."
                )
        else:
            logger.info("Last client disconnected (server stays alive)")

    def render_initial(self) -> str:
        # Initial render of the page (body)
        return self.render_tag(self)

    def collect_updates(
        self, tag: GTag, updates: Dict[str, str], js_calls: List[str]
    ) -> None:
        """
        Recursively traverses the tag tree to find 'dirty' tags that need re-rendering.
        Also collects pending JavaScript calls from tags.
        """
        with tag._GTag__lock:
            if getattr(tag, "_GTag__dirty", False):
                # This tag or one of its attributes changed, we re-render it entirely
                updates[tag.id] = self.render_tag(tag)

            # 1. Check static children
            for child in tag.childs:
                if isinstance(child, GTag):
                    self.collect_updates(child, updates, js_calls)

            # 2. Check dynamic (rendered) children
            rendered = getattr(tag, "_GTag__rendered_callables", {})
            for tag_list in rendered.values():
                for t in tag_list:
                    self.collect_updates(t, updates, js_calls)

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

        # 1. Traverse static children
        for child in tag.childs:
            if isinstance(child, GTag):
                self.collect_statics(child, result)

        # 2. Traverse dynamic (rendered) children
        rendered = getattr(tag, "_GTag__rendered_callables", {})
        for tag_list in rendered.values():
            for t in tag_list:
                self.collect_statics(t, result)

    async def handle_event(self, msg: Dict[str, Any], ws: Optional[WebSocket]) -> None:
        tag_id: Optional[str] = msg.get("id")
        event_name: Optional[str] = msg.get("event")

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
                logger.info(
                    "Event '%s' on tag %s (id: %s)",
                    event_name,
                    target_tag.tag,
                    target_tag.id,
                )
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
                        res = None  # Async generators don't easily return a final value
                    elif inspect.isgenerator(res):
                        try:
                            while True:
                                next(res)
                                await self.broadcast_updates()
                        except StopIteration as e:
                            res = e.value  # This is the return value of the generator

                    # Sanitize result: we don't want to send GTag instances (not JSON serializable)
                    if isinstance(res, GTag):
                        res = True  # Convert to a simple truthy value

                    # Final broadcast after callback finishes, including the result if any
                    await self.broadcast_updates(result=res, callback_id=callback_id)
                except Exception as e:
                    import traceback

                    error_trace: str = traceback.format_exc()
                    error_msg: str = (
                        f"Error in {event_name} callback: {str(e)}\n{error_trace}"
                    )
                    logger.error(error_msg)
                    # Use broadcast-like update for error reporting
                    err_payload: str = json.dumps(
                        {
                            "action": "error",
                            "traceback": error_trace
                            if self.debug
                            else "Internal Server Error",
                            "callback_id": callback_id,
                            "result": None,
                        }
                    )

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
                await self.broadcast_updates(result=res, callback_id=callback_id)

    async def broadcast_updates(
        self, result: Any = None, callback_id: Optional[str] = None
    ) -> None:
        """
        Collects all pending updates (tags, JS calls, statics)
        and broadcasts them to all connected clients.
        Optional 'result' and 'callback_id' are used to resolve client-side Promises.
        """
        updates: Dict[str, str] = {}
        js_calls: List[str] = []

        try:
            self.collect_updates(self, updates, js_calls)
        except Exception as e:
            import traceback

            error_trace = traceback.format_exc()
            error_msg = (
                f"Error during render/update collection: {str(e)}\n{error_trace}"
            )
            logger.error(error_msg)

            err_payload = json.dumps(
                {
                    "action": "error",
                    "traceback": error_trace if self.debug else "Internal Server Error",
                    "callback_id": callback_id,
                    "result": None,
                }
            )

            # Send to websocket clients
            dead_ws: List[WebSocket] = []
            for client in list(self.websockets):
                try:
                    await client.send_text(err_payload)
                except Exception:
                    dead_ws.append(client)
            for client in dead_ws:
                self.websockets.discard(client)

            # Send to SSE clients
            for queue in self.sse_queues:
                queue.put_nowait(err_payload)

            return  # Abort sending normal updates

        all_statics: List[str] = []
        self.collect_statics(self, all_statics)
        new_statics = [s for s in all_statics if s not in self.sent_statics]

        if updates or js_calls or new_statics or callback_id:
            self.sent_statics.update(new_statics)

            data = {
                "action": "update",
                "updates": updates,
                "js": js_calls,
                "statics": new_statics,
            }
            if callback_id:
                data["callback_id"] = callback_id
                data["result"] = result

            logger.debug(
                "Broadcasting updates: %s (js calls: %d, result: %s)",
                list(updates.keys()),
                len(js_calls),
                result if callback_id else "n/a",
            )

            payload = json.dumps(data)

            # Send to websocket clients
            dead_ws_clients: List[WebSocket] = []
            for client in list(self.websockets):
                try:
                    await client.send_text(payload)
                except Exception:
                    dead_ws_clients.append(client)
            for client in dead_ws_clients:
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
                    if (
                        t.tag in ["input", "textarea", "select"]
                        and "input" not in t._GTag__events
                    ):
                        t._GTag__attrs["oninput"] = (
                            f"htag_event('{t.id}', 'input', event)"
                        )
                    # Only clear dirty flag for objects that have it
                    if hasattr(t, "_GTag__dirty"):
                        t._GTag__dirty = False  # Clear dirty flag after rendering
                    for child in t.childs:
                        if isinstance(child, GTag):
                            process(child)

        process(tag)
        return str(tag)

    def find_tag(self, root: GTag, tag_id: str) -> Optional[GTag]:
        """Recursively find a tag by its ID, searching both static and dynamic (reactive) children."""
        if root.id == tag_id:
            return root

        # 1. Search in static children
        for child in root.childs:
            if isinstance(child, GTag):
                found = self.find_tag(child, tag_id)
                if found:
                    return found

        # 2. Search in dynamic (rendered from callables) children
        rendered = getattr(root, "_GTag__rendered_callables", {})
        for tag_list in rendered.values():
            for t in tag_list:
                found = self.find_tag(t, tag_id)
                if found:
                    return found

        return None


from .core import Tag  # noqa: E402

Tag._registry["App"] = App
