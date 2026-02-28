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

- always ensure a minimal, but robust, type hints in folder ./htag
- ensure comments are in english
- when you add/edit examples (main*.py files), always use the skill best practices
- when I say "core", focus on all files in ./htag folder
- when I say "docs", focus on .agent/skills/htag2-development/SKILL.md, ./README.md, and alls files in ./docs folder
- when I say "examples", focus on all files in **/main*.py**
- if you add/change core feature, always update docs
