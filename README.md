# htag2

<p align="center">
  <img src="docs/assets/logo.png" width="300" alt="htag2 logo">
</p>

<p align="center">
  <a href="https://github.com/manatlan/htag2/releases/tag/latest">
    <img src="https://img.shields.io/badge/Download-Latest_Build-blue?style=for-the-badge&logo=github" alt="Download Latest Build">
  </a>
</p>

Here is a full rewrite of [htag](https://github.com/manatlan/htag), using only antigravity and prompts.

It feels very good. It's not a replacement, it's just a POC.

It's completly crazy, but it works (ChromeApp & WebApp, on linux/windows).


## Get Started

Check the [Official Documentation](https://manatlan.github.io/htag2/) for more information.

## Install

```bash
git clone https://github.com/manatlan/htag2.git
cd htag2
uv run main3.py
```

currently, it's not available yet on pypi ... but the latest working wheel is available on the [latest release](https://github.com/manatlan/htag2/releases/tag/latest).

### Skill

With gemini-cli, claude-code, mistral-vibe (or others), you can use this [SKILL.md](.agent/skills/htag2-development/SKILL.md) to create a htag2 application.


## Antigravity resumes :

htag2 is a Python library for building web applications using HTML, CSS, and JavaScript.

### Key Resiliency Features Added
*   **F5/Reload Robustness**: Refreshing the browser no longer kills the Python backend; the session reconstructs cleanly.
*   **HTTP Fallback (SSE + POST)**: If WebSockets are blocked (e.g. strict proxies) or fail to connect, the client seamlessly falls back to HTTP POST for events and Server-Sent Events (SSE) for receiving UI updates.

### New API Features
*   **`.root`, `.parent`, and `.childs` properties**: Every `GTag` exposes its position in the component tree. `.root` references the main `Tag.App` instance, `.parent` references the direct parent component, and `.childs` is a list of its children. This allows components to easily navigate the DOM tree and trigger app-level actions.
*   **Declarative UI with Context Managers (`with`)**: You can now build component trees visually using `with` blocks (e.g., `with Tag.div(): Tag.h1("Hello")`), removing the need for `self <= ...` boilerplate.
*   **Reactive State Management (`State`)**: Introducing `State(value)` for automatic UI reactivity. Simply assign a `State` to a component using a lambda (e.g. `Tag.div(lambda: state.value)`), and the UI will auto-update whenever the state changes. Use `state.set(new_value)` for functional updates inside callbacks.
*   **Reactive & Boolean Attributes**: Attributes like `_class`, `_style`, or `_disabled` now support lambdas for dynamic updates. Boolean attributes (e.g. `_disabled=True`) are correctly rendered as key-only or omitted.
*   **Rapid Content Replacement (`.text`)**: Use the `.text` property on any tag to quickly replace its inner text content without needing to manually clear its children first.
*   **Recursive Statics & JS**: Components created dynamically (via lambdas) now have their `statics` (CSS) and `call_js` commands correctly collected and sent to the client.