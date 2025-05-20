- Use "source .venv/bin/activate" to activate the virtual environment before
  running any commands
- ONLY use non-interactive commands like cat, sed, apply_patch to do edits.
  Do NOT use interactive editors.
- Do NOT attempt to install packages.  Only the packages specified in
  pyproject.toml are available.  You cannot add new packages.  If you
  desperately want another package, make a note of it in the final PR
  description.
- Use conventional commits to format PR title
- There are no nested AGENTS.md files, this is the only agents file
- When using Playwright, ONLY use chromium browser.  This browser is already
  installed.
- Use "ruff check" to check lint, "ruff format" to autoformat files and
  "pyright" to typecheck.
- When writing the PR description, include the original prompt supplied by the
  user.
- When you add functionality to the server, add server tests to
  tests/test_server.py.  When you add features to the frontend, add frontend
  tests to tests/test_web.py
