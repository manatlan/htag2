from htag import Tag, WebApp
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
import uvicorn

# Create htag app
class MyApp(Tag.App):
    def init(self):
        self._style = "font-family: sans-serif; padding: 20px; border: 2px solid #646cff; border-radius: 8px; max-width: 400px; margin: 20px auto; text-align: center;"
        self <= Tag.h2("htag2 App")
        self <= Tag.p("I am mounted at /app")
        self <= Tag.button("Click me", _onclick=lambda e: self.add(Tag.p("Action from /app !")))
        
        def on_bug(e):
            raise Exception("bug")
        self <= Tag.button("Bug", _onclick=on_bug)
        self <= Tag.div(Tag.a("Back to HTML home", _href="/"), _style="margin-top:10px")

# Main Starlette application creation
app = Starlette()

@app.route("/")
async def home(request):
    return HTMLResponse("""
        <html>
            <body style="font-family: sans-serif; padding: 50px; text-align:center;">
                <h1>Starlette Home (Simple HTML)</h1>
                <p>This is a standard Starlette route without htag2.</p>
                <hr>
                <a href="/app" style="font-size: 1.5em; color: #646cff;">Launch htag2 App (/app)</a>
            </body>
        </html>
    """)

# mount htag app (Multi-Session mode)
# By passing the CLASS 'MyApp', WebApp will create one instance per session.
app.mount("/app", WebApp(MyApp).app) 

if __name__ == "__main__":
    print("🚀 Server started at http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
