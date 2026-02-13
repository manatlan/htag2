from htag import Tag, prevent
import logging

# logging.basicConfig(level=logging.INFO)

class App(Tag.App):
    def __init__(self):
        super().__init__()
        b = Tag.button("add", onclick=self.onclick, oncontextmenu=self.onmenu, _style="color:green")
        b.a_var=42
        self += b

    def onclick(self, event):
        self += Tag.div(f"hello {event.target.a_var} {event}")

        yield

        event.target.a_var += 1
        event.target._style = "color:red"
        event.target += Tag.span("added")
        event.target.call_js("console.log('Button clicked!')")

    @prevent
    def onmenu(self, event):
        event.target += Tag.span("menu")

if __name__ == "__main__":
    from htag import ChromeApp
    p = App()
    ChromeApp(p).run()
