import asyncio
from htag import Tag
from htag.runners import WebApp

class MyApp(Tag.App):
    def init(self):
        self <= Tag.div("Hello World")

if __name__ == "__main__":
    WebApp(MyApp).run(port=8080)
