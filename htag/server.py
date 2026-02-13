import asyncio
import json
import subprocess
import os
import threading
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn
import logging
import inspect
from .core import GTag

logger = logging.getLogger("htagravity")

class Event:
    def __init__(self, target, msg):
        self.target = target
        self.id = msg.get("id")
        self.name = msg.get("event")
        self.data = msg.get("data", {})
        # Flatten data for easy access
        for k, v in self.data.items():
            setattr(self, k, v)
    def __str__(self):
        return f"Event({self.name}, {self.data}, target={self.target})"

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

# --- Runners ---

class BaseRunner:
    """Base class for all runners that execute an App."""
    def __init__(self, app: "App"):
        self.app = app

    def run(self, host="127.0.0.1", port=8000):
        """Must be implemented by subclasses to start the server/UI."""
        raise NotImplementedError()

class ChromeApp(BaseRunner):
    """
    Executes an App in a Chrome/Chromium kiosk window.
    Features auto-cleanup of temporary browser profiles.
    """
    def __init__(self, app: "App", kiosk=True, width=800, height=600):
        super().__init__(app)
        self.kiosk = kiosk
        self.width = width
        self.height = height

    def run(self, host="127.0.0.1", port=8000):
        if self.kiosk:
            def launch():
                time.sleep(1)  # Give the server a second to start
                
                import tempfile
                import shutil
                import atexit
                tmp_dir = tempfile.mkdtemp(prefix="htagravity_")
                
                def cleanup():
                    try:
                        shutil.rmtree(tmp_dir)
                        logger.info("Cleaned up temporary browser profile: %s", tmp_dir)
                    except:
                        pass
                
                atexit.register(cleanup)
                # Store cleanup in app if needed (though runner handles it via atexit)
                self.app._browser_cleanup = cleanup
                
                browsers = ["google-chrome", "chromium-browser", "chromium", "chrome"]
                found = False
                
                for browser in browsers:
                    try:
                        subprocess.Popen([
                            browser, 
                            f"--app=http://{host}:{port}", 
                            f"--window-size={self.width},{self.height}",
                            f"--user-data-dir={tmp_dir}",
                            "--no-first-run",
                            "--no-default-browser-check"
                        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        logger.info("Launched %s with window size %dx%d", browser, self.width, self.height)
                        found = True
                        break
                    except FileNotFoundError:
                        continue
                    except Exception as e:
                        logger.error("Error launching %s: %s", browser, e)
                        continue
                
                if not found:
                    logger.warning("Could not launch any browser (tried: %s)", ", ".join(browsers))

            threading.Thread(target=launch, daemon=True).start()

        uvicorn.run(self.app.app, host=host, port=port)

class App(GTag):
    def __init__(self, *args, **kwargs):
        super().__init__("body", *args, **kwargs)
        self.app = FastAPI()
        self.websockets = set()
        self.sent_statics = set() # Track assets already in browser
        self.setup_routes()

    def setup_routes(self):
        @self.app.get("/", response_class=HTMLResponse)
        async def get():
            # Collect ALL statics from the whole tree on first load
            self.sent_statics.clear()
            all_statics = []
            self.collect_statics(self, all_statics)
            self.sent_statics.update(all_statics)
            statics_html = "".join(all_statics)

            html_content = f"""
            <!DOCTYPE html>
            <html>
                <head>
                    <title>htagravity</title>
                    <script>{CLIENT_JS}</script>
                    {statics_html}
                </head>
                {self.render_initial()}
            </html>
            """
            return html_content

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.websockets.add(websocket)
            logger.info("New WebSocket connection (Total clients: %d)", len(self.websockets))
            
            # Send initial state on connection/reconnection
            try:
                await websocket.send_text(json.dumps({
                    "action": "update",
                    "updates": {self.id: self.render_initial()}
                }))
                logger.debug("Sent initial state to client")
            except Exception as e:
                logger.error("Failed to send initial state: %s", e)

            try:
                while True:
                    data = await websocket.receive_text()
                    msg = json.loads(data)
                    await self.handle_event(msg, websocket)
            except WebSocketDisconnect:
                self.websockets.remove(websocket)
                logger.info("WebSocket disconnected (Total clients: %d)", len(self.websockets))
                if not self.websockets:
                    # Exit when last browser window is closed
                    logger.info("Last client disconnected, exiting...")
                    # Manual cleanup before os._exit(0) because it skips atexit handlers
                    if hasattr(self, "_browser_cleanup"):
                        self._browser_cleanup()
                    os._exit(0)

    def render_initial(self):
        # Initial render of the page (body)
        return self.render_tag(self)

    def collect_updates(self, tag, updates, js_calls):
        """
        Recursively traverses the tag tree to find 'dirty' tags that need re-rendering.
        Also collects pending JavaScript calls from tags.
        """
        with tag._lock:
            if tag._dirty:
                # This tag or one of its attributes changed, we re-render it entirely
                updates[tag.id] = self.render_tag(tag)
            else:
                # If not dirty, check children
                for child in tag._childs:
                    if isinstance(child, GTag):
                        self.collect_updates(child, updates, js_calls)
            
            if tag._js_calls:
                js_calls.extend(tag._js_calls)
                tag._js_calls = []

    def collect_statics(self, tag, result):
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

    async def handle_event(self, msg, ws):
        tag_id = msg.get("id")
        event_name = msg.get("event")
        
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

    async def broadcast_updates(self, result=None, callback_id=None):
        """
        Collects all pending updates (tags, JS calls, statics) 
        and broadcasts them to all connected clients.
        Optional 'result' and 'callback_id' are used to resolve client-side Promises.
        """
        updates = {}
        js_calls = []
        self.collect_updates(self, updates, js_calls)
        
        all_statics = []
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
            dead = []
            for client in self.websockets:
                try:
                    await client.send_text(payload)
                except:
                    dead.append(client)
            for client in dead:
                self.websockets.remove(client)

    def render_tag(self, tag):
        """
        Renders a GTag to its HTML string representation.
        Before rendering, it injects 'htag_event' calls into HTML event attributes,
        enabling the bridge between DOM events and Python callbacks.
        """
        def process(t):
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
                        process(child)
        
        process(tag)
        return str(tag)

    def find_tag(self, root, tag_id):
        if root.id == tag_id:
            return root
        for child in root._childs:
            if isinstance(child, GTag):
                found = self.find_tag(child, tag_id)
                if found: return found
        return None


from .core import Tag
Tag._registry["App"] = App

