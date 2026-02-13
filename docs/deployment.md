# Production Deployment

While runners are great for development and desktop apps, `htag` applications are fully compatible with production-grade web servers.

## FastAPI Integration

Every `App` in `htag` exposes an underlying **FastAPI** instance through its `.app` property. This allows you to deploy your application using standard tools like `uvicorn` or `gunicorn`.

### Basic Production Entrypoint

```python
# main.py
from htag import App, Tag

class MyApp(App):
    def __init__(self):
        super().__init__()
        self += Tag.h1("Production App")

# Create the FastAPI instance
app = MyApp().app
```

You can now run this with `uvicorn`:

```bash
uvicorn main:app --host 0.0.0.0 --port 80
```

## Embedding htag in existing FastAPI apps

Since `htag` uses a `WebServer` wrapper, you can also mount it as a sub-application or include its routes in a larger FastAPI project.

```python
from fastapi import FastAPI
from htag.server import WebServer
from my_htag_app import MyApp

main_app = FastAPI()

# Wrap your htag App in a WebServer
htag_server = WebServer(MyApp)

# Mount or include routes
main_app.mount("/htag", htag_server.app)

@main_app.get("/health")
def health():
    return {"status": "ok"}
```

## Performance & Scalability

- **WebSockets**: Ensure your production load balancer (like Nginx or Traefik) is configured to handle WebSocket connections properly.
- **Workers**: Since `htag` maintains session state in memory (by default), you should ideally use **sticky sessions** if you scale to multiple worker processes or containers.
- **Memory**: Each active session consumes a small amount of memory on the server. Monitor your memory usage if you expect thousands of concurrent users.

## Automatic Deployment (GitHub Pages)

You can automate the deployment of your documentation using GitHub Actions.

### Using GitHub Actions

Create a file at `.github/workflows/docs.yml` with the following content to build and deploy your docs on every push to `main`:

```yaml
name: docs
on:
  push:
    branches:
      - main
permissions:
  contents: write
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v5
      - name: Install dependencies
        run: uv sync --dev
      - name: Deploy to GitHub Pages
        run: uv run mkdocs gh-deploy --force
```

### Enable GitHub Pages in Repository Settings

1.  Go to your GitHub repository **Settings**.
2.  Navigate to **Pages** in the left sidebar.
3.  Under **Build and deployment**, ensure the source is set to **Deploy from a branch**.
4.  Choose the `gh-pages` branch (it will be created automatically by the workflow) and the `/ (root)` folder.
5.  Click **Save**.

Your documentation will then be available at `https://<username>.github.io/<repository-name>/`.

---

[← Runners](runners.md) | [Home](index.md)
