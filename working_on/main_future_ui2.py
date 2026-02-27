# -*- coding: utf-8 -*-
from htag import Tag
import json
import html


class ui_App(Tag.App):
    """
    Base class for UI applications via Tailwind CSS.
    """
    statics = [
        # Design System (Tailwind CSS CDN)
        Tag.script(_src="https://cdn.tailwindcss.com"),
        Tag.script("tailwind.config = { darkMode: 'class' }"),
        # FontAwesome for icons
        Tag.link(_rel="stylesheet", _href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # We handle layout on the root element
        self.add_class("flex justify-center items-center h-screen bg-slate-100 dark:bg-slate-900 text-slate-900 dark:text-slate-100 transition-colors m-0")

class ui_Title(Tag.h1):
    def init(self, text, **kwargs):
        super().init(text, **kwargs)
        self.add_class("text-2xl font-bold m-0")

class ui_Text(Tag.div):
    def init(self, text, **kwargs):
        super().init(text, **kwargs)
        self.add_class("text-base m-0 text-slate-600 dark:text-slate-400")

class ui_Icon(Tag.span):
    def init(self, name, **kwargs):
        super().init(**kwargs)
        fa_name = "cog" if name == "gear" else "info-circle"
        self <= Tag.i(_class=f"fa-solid fa-{fa_name}")

class ui_IconButton(Tag.button):
    def init(self, name, **kwargs):
        super().init(**kwargs)
        self.add_class("p-2 rounded-full hover:bg-slate-200 dark:hover:bg-slate-700 flex items-center justify-center transition-colors text-slate-500 dark:text-slate-400")
        self <= ui_Icon(name)

class ui_Badge(Tag.span):
    def init(self, text, variant="primary", **kwargs):
        super().init(text, **kwargs)
        self.base_classes = "px-2 py-1 text-xs font-semibold rounded-full"
        self._variant = variant

    @property
    def _variant(self):
        return getattr(self, "__variant", "primary")

    @_variant.setter
    def _variant(self, v):
        self.__variant = v
        classes = self.base_classes
        if v == "primary": classes += " bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300"
        elif v == "success": classes += " bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300"
        elif v == "neutral": classes += " bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-300"
        
        # Keep user classes
        user_classes = [c for c in (getattr(self, "_class", "") or "").split() if c not in classes]
        self._class = classes + (" " + " ".join(user_classes) if user_classes else "")

    # Patch for .text property used in main_future_ui.py
    @property
    def text(self): return "".join([str(c) for c in self.childs if isinstance(c, str)])
    
    @text.setter
    def text(self, val):
        self.clear()
        self <= val

class ui_Button(Tag.button):
    def init(self, text, **kwargs):
        self._variant = kwargs.pop("_variant", "default")
        super().init(text, **kwargs)
        self.add_class("px-4 py-2 rounded font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 dark:focus:ring-offset-slate-900")
        if self._variant == "primary": 
            self.add_class("bg-blue-600 hover:bg-blue-700 text-white focus:ring-blue-500")
        elif self._variant == "success": 
            self.add_class("bg-green-600 hover:bg-green-700 text-white focus:ring-green-500")
        else:
            self.add_class("bg-slate-200 hover:bg-slate-300 text-slate-800 dark:bg-slate-700 dark:hover:bg-slate-600 dark:text-slate-200 focus:ring-slate-400")

class ui_Checkbox(Tag.label):
    def init(self, text, **kwargs):
        onchange = kwargs.pop("_onchange", None)
        super().init(**kwargs)
        self.add_class("flex items-center space-x-2 cursor-pointer")
        self.input = Tag.input(_type="checkbox", _class="w-4 h-4 text-blue-600 bg-slate-100 border-slate-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-slate-800 focus:ring-2 dark:bg-slate-700 dark:border-slate-600")
        if onchange:
            self.input.onchange = self._internal_change
            self._user_onchange = onchange
        self <= self.input
        self <= Tag.span(text, _class="text-slate-700 dark:text-slate-300 select-none font-medium text-sm")

    def _internal_change(self, event):
        if hasattr(self, "_user_onchange"):
            self._user_onchange(event)

class ui_Dialog(Tag.div):
    def init(self, title, **kwargs):
        self._label = title
        super().init(**kwargs)
        self.add_class("fixed inset-0 z-50 flex items-center justify-center hidden")
        self.bg = Tag.div(_class="absolute inset-0 bg-slate-900/50 backdrop-blur-sm", _onclick=lambda e: self.hide())
        self.content = Tag.div(_class="relative bg-white dark:bg-slate-800 rounded-lg shadow-xl w-full max-w-md mx-4 flex flex-col overflow-hidden")
        
        with self:
            self.bg
            with self.content:
                with Tag.div(_class="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"):
                    ui_Title(title, _class="text-lg")
                    self.close_btn = Tag.button("×", _class="text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 text-2xl leading-none focus:outline-none", _onclick=lambda e: self.hide())
                self.inner = Tag.div(_class="p-4")
            
        self.add = self.inner.add

    def show(self):
        cls = getattr(self, "_class", "") or ""
        self._class = cls.replace(" hidden", "").replace("hidden", "")
    def hide(self):
        cls = getattr(self, "_class", "") or ""
        if "hidden" not in cls:
            self.add_class("hidden")

class ui_Drawer(Tag.div):
    def init(self, title, **kwargs):
        self._label = title
        super().init(**kwargs)
        self.add_class("fixed inset-0 z-50 flex justify-end hidden")
        self.bg = Tag.div(_class="absolute inset-0 bg-slate-900/50 backdrop-blur-sm transition-opacity", _onclick=lambda e: self.hide())
        self.content = Tag.div(_class="relative bg-white dark:bg-slate-800 shadow-2xl w-full max-w-sm h-full flex flex-col transform transition-transform")
        
        with self:
            self.bg
            with self.content:
                with Tag.div(_class="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"):
                    ui_Title(title, _class="text-lg")
                    self.close_btn = Tag.button("×", _class="text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 text-2xl leading-none focus:outline-none", _onclick=lambda e: self.hide())
                self.inner = Tag.div(_class="p-4 flex-1 overflow-y-auto")
            
        self.add = self.inner.add

    def show(self):
        cls = getattr(self, "_class", "") or ""
        self._class = cls.replace(" hidden", "").replace("hidden", "")
    def hide(self):
        cls = getattr(self, "_class", "") or ""
        if "hidden" not in cls:
            self.add_class("hidden")

class ui_Spinner(Tag.div):
    def init(self, **kwargs):
        super().init(**kwargs)
        self.add_class("inline-block animate-spin rounded-full border-4 border-solid border-current border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite] text-blue-600 dark:text-blue-400")
        self._style = getattr(self, "_style", "") + " width: 3rem; height: 3rem;"

def ui_Toast(caller: Tag, text: str, variant: str = "primary", duration: int = 3000):
    bg_color = "bg-blue-600 text-white" if variant == "primary" else "bg-slate-800 text-white"
    if variant == "success": bg_color = "bg-green-600 text-white"
    elif variant == "danger": bg_color = "bg-red-600 text-white"
    elif variant == "warning": bg_color = "bg-amber-500 text-white"
    
    js = f"""
    const toast = document.createElement('div');
    toast.className = 'fixed bottom-5 right-5 z-[9999] px-4 py-3 rounded shadow-lg flex items-center space-x-3 transition-opacity duration-300 opacity-0 translate-y-4 {bg_color}';
    toast.innerHTML = `<span class="font-medium">` + {json.dumps(html.escape(text))} + `</span><button class="ml-2 font-bold hover:text-slate-200 focus:outline-none">&times;</button>`;
    document.body.appendChild(toast);
    
    // Animate in
    requestAnimationFrame(() => {{
        toast.classList.remove('opacity-0', 'translate-y-4');
        toast.classList.add('opacity-100', 'translate-y-0', 'transition-all');
    }});
    
    toast.querySelector('button').addEventListener('click', () => {{
        toast.classList.add('opacity-0');
        setTimeout(() => toast.remove(), 300);
    }});
    setTimeout(() => {{
        toast.classList.add('opacity-0');
        setTimeout(() => toast.remove(), 300);
    }}, {duration});
    """
    caller.call_js(js)

class ui_SplitPanel(Tag.div):
    def init(self, **kwargs):
        super().init(**kwargs)
        self.add_class("flex w-full h-full overflow-hidden")
        self.start = Tag.div(_class="flex-1 min-w-[30%] overflow-y-auto border-r border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800")
        self.end = Tag.div(_class="flex-[2] overflow-y-auto bg-slate-50 dark:bg-slate-900")
        with self:
            self.start
            self.end

class ui_Card(Tag.div):
    def init(self, title=None, footer=None, **kwargs):
        super().init(**kwargs)
        self.add_class("bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden w-full max-w-[400px]")
        
        if title:
            with self:
                with Tag.div(_class="px-4 py-3 border-b border-slate-200 dark:border-slate-700 flex justify-between items-center bg-slate-50 dark:bg-slate-800"):
                    Tag.h3(title, _class="font-semibold text-slate-800 dark:text-slate-100 m-0")
                    self.header_actions = Tag.div(_class="flex items-center space-x-1")
                    
        self.content = Tag.div(_class="p-4")
        with self:
            self.content
        
        self.add = self.content.add

        if footer:
            with self:
                Tag.div(footer, _class="px-4 py-3 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 flex items-center justify-between w-full")

class ui_Tab(Tag.li):
    def init(self, text, panel: str, active=False, **kwargs):
        self.panel_id = panel
        super().init(**kwargs)
        self.add_class("-mb-px mr-1")
        self.a = Tag.a(text, _class="inline-block py-2 px-4 font-semibold cursor-pointer border-b-2 hover:text-blue-600 transition-colors duration-200", _onclick=self._activate)
        if active:
            self.a.add_class("border-blue-500 text-blue-600")
        else:
            self.a.add_class("border-transparent text-slate-500 dark:text-slate-400")
        self <= self.a
        
    def _activate(self, ev):
        if hasattr(self.parent.parent, "_select_tab"):
            self.parent.parent._select_tab(self.panel_id)

class ui_Tabs(Tag.div):
    def init(self, **kwargs):
        super().init(**kwargs)
        self.add_class("flex flex-col h-full w-full")
        self.tabs_nav = Tag.ul(_class="flex border-b border-slate-200 dark:border-slate-700 pl-4 pt-2 bg-white dark:bg-slate-800 m-0 p-0 list-none")
        self.panels_container = Tag.div(_class="flex-1 overflow-auto bg-slate-50 dark:bg-slate-900 border-none")
        
        self.current_tab = None
        
        # We need to manually append these internal structure blocks
        super().add(self.tabs_nav)
        super().add(self.panels_container)
            
    def add(self, item):
        if isinstance(item, ui_Tab):
            self.tabs_nav.add(item)
            cls = getattr(item.a, "_class", "") or ""
            if not self.current_tab and "border-blue-500" in cls:
                self.current_tab = item.panel_id
            elif not self.current_tab:
                self.current_tab = item.panel_id
                item.a.add_class("border-blue-500 text-blue-600")
                item.a._class = cls.replace("border-transparent", "").replace("text-slate-500", "").replace("dark:text-slate-400", "")
        elif isinstance(item, ui_TabPanel):
            self.panels_container.add(item)
            style = getattr(item, "_style", "") or ""
            item._style = style + (" display: block;" if item._name == self.current_tab else " display: none;")
            item.add_class("h-full")
            
    def _select_tab(self, panel_id):
        self.current_tab = panel_id
        for tab in self.tabs_nav.childs:
            if isinstance(tab, ui_Tab):
                is_active = tab.panel_id == panel_id
                cls = getattr(tab.a, "_class", "") or ""
                cls = cls.replace("border-blue-500", "").replace("text-blue-600", "").replace("border-transparent", "").replace("text-slate-500", "").replace("dark:text-slate-400", "").replace("  ", " ").strip()
                tab.a._class = cls
                if is_active:
                    tab.a.add_class("border-blue-500 text-blue-600")
                else:
                    tab.a.add_class("border-transparent text-slate-500 dark:text-slate-400")
            
        for panel in self.panels_container.childs:
            if isinstance(panel, ui_TabPanel):
                style = getattr(panel, "_style", "") or ""
                if panel._name == panel_id:
                    panel._style = style.replace("display: none;", "display: block;")
                else:
                    panel._style = style.replace("display: block;", "display: none;")

class ui_TabPanel(Tag.div):
    def init(self, name: str, **kwargs):
        self._name = name
        super().init(**kwargs)

class MyApp(ui_App):
    def init(self):
        self.count = 0

        # Overlays
        self.dialog = ui_Dialog("Settings")
        with self.dialog:
            ui_Text("Settings panel content.")
            with Tag.div(_class="mt-6 flex justify-end"):
                ui_Button("Close", _onclick=lambda e: self.dialog.hide())

        self.drawer = ui_Drawer("System Info")
        with self.drawer:
            ui_Text("Drawer content.")

        # Root Layout: Split Panel
        with ui_SplitPanel(_class="shadow-xl rounded-xl overflow-hidden border border-slate-200 dark:border-slate-700", _style="width: 800px; height: 500px;") as sp:
            # Left Side (Start Slot)
            with sp.start:
                with Tag.div(_class="flex flex-col items-center justify-center p-6 h-full w-full"):
                    with ui_Card(title="Core Controls") as self.card:
                        with self.card.header_actions:
                            ui_IconButton("gear", _onclick=lambda e: self.dialog.show())
                        
                        ui_Text("Status Dashboard")
                        with Tag.div(_style="margin-top: 1rem; display: flex; align-items: center; gap: 0.5rem;"):
                            self.badge = ui_Badge("Standby", variant="neutral")
                        
                        with Tag.div(_slot="footer", _class="flex gap-2 w-full justify-between items-center"):
                            with Tag.div(_class="flex gap-2 items-center"):
                                ui_Button("Increment", _variant="primary", _onclick=self.inc)
                                ui_Button("Info", _onclick=lambda e: self.drawer.show())
                            with Tag.div(_class="ml-auto"):
                                ui_Checkbox("Dark Mode", _onchange=self.toggle_dark_mode)

            # Right Side (End Slot)
            with sp.end:
                with ui_Tabs(_class="fill-height"):
                    ui_Tab("General", panel="general", active=True)
                    ui_Tab("Advanced", panel="advanced")
                    
                    with ui_TabPanel(name="general"):
                        with Tag.div(_class="flex flex-col items-center justify-center h-full w-full gap-4 p-8"):
                            ui_Spinner()
                            ui_Text("System Processing...")
                            ui_Button("Notify User", _variant="success", _onclick=self.notify)
                            
                    with ui_TabPanel(name="advanced"):
                        with Tag.div(_class="p-6"):
                            ui_Text("Advanced settings would go here.")

    def inc(self, event):
        self.count += 1
        self.badge.text = f"Activity: {self.count}"
        self.badge._variant = "primary" if self.count < 5 else "success"

    def notify(self, event):
        ui_Toast(self, f"Broadcast: New event recorded ({self.count})", variant="success")

    def toggle_dark_mode(self, event):
        try:
            is_dark = bool(getattr(event.target, "_value", False))
        except Exception:
            is_dark = False

        if is_dark:
            self.call_js("document.documentElement.classList.add('dark');")
        else:
            self.call_js("document.documentElement.classList.remove('dark');")

if __name__ == "__main__":
    from htag import ChromeApp
    ChromeApp(MyApp).run(port=8002)
