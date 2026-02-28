from htag import Tag
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
        self <= Tag.div(Tag.a("Back to HTML home", _href="/"), _style="margin-top:10px")

myapp = MyApp()

# Main Starlette application creation
app = Starlette(debug=True)

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

# mount htag app
app.mount("/app", myapp.app) 

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
