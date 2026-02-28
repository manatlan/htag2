# 🚀 htag2 Project Rules

> [!NOTE]
> **Project Type**: `uv` Python project (editable install)

## 📁 Project Structure

- **Framework Source**: [htag](file://./htag)
- **Developer Guidelines**: [htag2-development skill](file://.agent/skills/htag2-development/SKILL.md)

## 🛠️ Standard Commands

| Action | Command |
| :--- | :--- |
| **Run a script** | `uv run python_file.py` |
| **Add dependency** | `uv add <package>` |
| **Run tests** | `uv run pytest` |

## rules

- if you touch files in ./htag folder, ensure "uv run pytest" pass after your changes
- always ensure a minimal, but robust, type hints in folder ./htag
- if you add/change core feature, always update SKILL.md, README.md, and all relevant documentation
- ensure comments are in english
- when you add/edit examples (main*.py files), always use the skill best practices
- when I say "core", focus on all files in ./htag folder