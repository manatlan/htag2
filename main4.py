import os
import sys
import html
from pathlib import Path
from htag import Tag, ChromeApp, GTag

class Explorer(Tag.div):
    """Component responsible for listing files and folders."""
    statics = [
        Tag.style("""
            .explorer {
                flex: 1;
                overflow-y: auto;
                padding: 24px;
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
                gap: 12px;
                align-content: start;
                border-right: 1px solid rgba(255,255,255,0.05);
            }
            .item {
                display: flex;
                align-items: center;
                padding: 12px 16px;
                background: var(--surface);
                border-radius: 10px;
                cursor: pointer;
                transition: all 0.2s;
                border: 1px solid rgba(255,255,255,0.05);
            }
            .item:hover {
                background: var(--hover);
                border-color: var(--primary);
            }
            .item.selected {
                background: rgba(129, 193, 223, 0.2);
                border-color: var(--primary);
                box-shadow: 0 0 10px rgba(129, 193, 223, 0.2);
            }
            .icon {
                width: 32px;
                height: 32px;
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-right: 12px;
                font-size: 1.2rem;
                background: rgba(0,0,0,0.2);
            }
            .item.folder .icon { color: var(--accent); }
            .item.file .icon { color: var(--primary); }
            .item .info { flex: 1; min-width: 0; }
            .item .name { display: block; font-weight: 500; font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .item .details { display: block; font-size: 0.7rem; color: var(--text-dim); }
        """)
    ]

    def init(self, path, selected_file, select_callback):
        self._class="explorer"
        self.path = path
        self.selected_file = selected_file
        self.select_callback = select_callback
        self.render()

    def render(self):
        self.clear()
        try:
            entries = list(self.path.iterdir())
            entries.sort(key=lambda p: (not p.is_dir(), p.name.lower()))
            
            for item in entries:
                is_dir = item.is_dir()
                cls = "folder" if is_dir else "file"
                is_selected = self.selected_file == item
                
                div = Tag.div(_class=f"item {cls} {'selected' if is_selected else ''}", 
                            _onclick=lambda e, p=item: self.select_callback(p))
                
                div += Tag.div("📁" if is_dir else "📄", _class="icon")
                
                info = Tag.div(_class="info")
                info += Tag.span(item.name, _class="name")
                
                if not is_dir:
                    try:
                        size = item.stat().st_size
                        info += Tag.span(self.format_size(size), _class="details")
                    except Exception: pass
                else:
                    info += Tag.span("Folder", _class="details")
                
                div += info
                self += div
        except Exception as e:
            self += Tag.div(f"Error: {e}", _style="color: #ff6b6b; padding: 20px")

    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024: return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

class Viewer(Tag.div):
    """Component responsible for previewing file content."""
    statics = [
        Tag.style("""
            .preview-panel {
                width: 450px;
                background: var(--surface);
                display: flex;
                flex-direction: column;
                border-left: 1px solid rgba(129,193,223,0.2);
                animation: slideIn 0.3s ease-out;
                height: 100%;
            }
            @keyframes slideIn {
                from { transform: translateX(100%); }
                to { transform: translateX(0); }
            }
            .preview-header {
                padding: 16px 24px;
                background: var(--surface-light);
                display: flex;
                align-items: center;
                justify-content: space-between;
                border-bottom: 1px solid rgba(255,255,255,0.1);
            }
            .preview-title {
                font-weight: 600;
                font-size: 0.9rem;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .preview-content {
                flex: 1;
                overflow: auto;
                padding: 20px;
                font-family: 'Fira Code', monospace;
                font-size: 0.85rem;
                line-height: 1.5;
                white-space: pre;
                background: #1e2832;
                color: #d1d9e1;
            }
            .close-btn {
                background: none;
                border: none;
                color: var(--text-dim);
                font-size: 1.2rem;
                cursor: pointer;
                padding: 4px;
                border-radius: 4px;
            }
            .close-btn:hover {
                background: rgba(255,255,255,0.1);
                color: var(--text);
            }
        """)
    ]

    def init(self, file_path, close_callback):
        self._class="preview-panel"
        self.file_path = file_path
        self.close_callback = close_callback
        self.render()

    def render(self):
        self.clear()
        if not self.file_path or not self.file_path.is_file():
            return
            
        header = Tag.div(_class="preview-header")
        header += Tag.span(self.file_path.name, _class="preview-title")
        header += Tag.button("✕", _class="close-btn", _onclick=lambda e: self.close_callback())
        self += header
        
        content = Tag.div(_class="preview-content")
        if self.is_text_file(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                    all_text = f.read(50000)
                    lines = all_text.splitlines()[:1000]
                    text = "\n".join(lines)
                    if len(all_text) > 50000 or len(all_text.splitlines()) > 1000:
                        text += "\n... (truncated)"
                    content += html.escape(text)
            except Exception as e:
                content += f"Error reading file: {e}"
        else:
            content += "Preview not available for this file type."
        
        self += content

    def is_text_file(self, path):
        text_extensions = {
            '.py', '.md', '.txt', '.json', '.yml', '.yaml', 
            '.css', '.html', '.js', '.toml', '.xml', '.sh', 
            '.bat', '.log', '.ini', '.cfg', '.sql', '.svg'
        }
        return path.suffix.lower() in text_extensions

class FileNavigator(Tag.App):
    statics = [
        Tag.style("""
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap');
            @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&display=swap');
            :root {
                --bg: #1a242c;
                --surface: #24313d;
                --surface-light: #2d3d4d;
                --primary: #81C1DF;
                --accent: #F1CF6A;
                --text: #CFDDE5;
                --text-dim: #8ba2b1;
                --hover: rgba(129, 193, 223, 0.1);
            }
            body {
                background: var(--bg);
                color: var(--text);
                font-family: 'Outfit', sans-serif;
                margin: 0;
                padding: 0;
                display: flex;
                flex-direction: column;
                height: 100vh;
                overflow: hidden;
            }
            .main-container {
                flex: 1;
                display: flex;
                flex-direction: column;
                height: 100vh;
                overflow: hidden;
            }
            .navbar {
                padding: 16px 32px;
                background: var(--surface);
                display: flex;
                align-items: center;
                gap: 20px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                z-index: 10;
                border-bottom: 1px solid rgba(129, 193, 223, 0.2);
            }
            .navbar h1 {
                margin: 0;
                font-weight: 600;
                font-size: 1.2rem;
                background: linear-gradient(135deg, var(--primary), var(--accent));
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                letter-spacing: -0.5px;
            }
            .breadcrumb-bar {
                padding: 8px 32px;
                background: rgba(0,0,0,0.2);
                font-size: 0.8rem;
                color: var(--text-dim);
                display: flex;
                align-items: center;
                gap: 8px;
                white-space: nowrap;
                overflow-x: auto;
                scrollbar-width: none;
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }
            .split-view {
                flex: 1;
                display: flex;
                overflow: hidden;
            }
            .btn {
                background: rgba(129, 193, 223, 0.1);
                color: var(--primary);
                border: 1px solid var(--primary);
                padding: 8px 16px;
                border-radius: 6px;
                cursor: pointer;
                font-weight: 600;
                font-size: 0.8rem;
                transition: all 0.2s;
            }
            .btn:hover:not(:disabled) {
                background: var(--primary);
                color: var(--bg);
            }
            ::-webkit-scrollbar { width: 6px; height: 6px; }
            ::-webkit-scrollbar-track { background: transparent; }
            ::-webkit-scrollbar-thumb {
                background: rgba(129, 193, 223, 0.2);
                border-radius: 3px;
            }
            ::-webkit-scrollbar-thumb:hover { background: rgba(129, 193, 223, 0.4); }
        """)
    ]

    def __init__(self):
        super().__init__()
        self.main = Tag.div(_class="main-container")
        self += self.main
        self.current_path = Path(os.getcwd()).resolve()
        self.selected_file = None
        self.render_all()

    def render_all(self):
        self.main.clear()
        
        # Navigation Bar
        nav = Tag.div(_class="navbar")
        can_go_up = self.current_path.parent != self.current_path
        btn_props = {"_class": "btn", "_onclick": self.go_up}
        if not can_go_up: btn_props["disabled"] = True
        nav += Tag.button("↑ Up", **btn_props)
        nav += Tag.h1("HTAGravity Explorer")
        self.main += nav

        # Breadcrumbs
        self.main += Tag.div(str(self.current_path), _class="breadcrumb-bar")

        # Split View
        split = Tag.div(_class="split-view")
        
        # Explorer (Left)
        split += Explorer(self.current_path, self.selected_file, self.on_item_click)
        
        # Viewer (Right)
        if self.selected_file:
            split += Viewer(self.selected_file, self.on_close_viewer)
            
        self.main += split

    def on_item_click(self, item):
        if item.is_dir():
            self.current_path = item
            self.selected_file = None
            self.render_all()
        else:
            self.selected_file = item
            self.render_all()

    def go_up(self, e):
        if self.current_path.parent != self.current_path:
            self.current_path = self.current_path.parent
            self.selected_file = None
            self.render_all()

    def on_close_viewer(self):
        self.selected_file = None
        self.render_all()

if __name__ == "__main__":
    ChromeApp(FileNavigator, width=1200, height=800).run()
