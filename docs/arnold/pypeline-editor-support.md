# `.pypeline` Editor Support

Megaplan treats `.pypeline` files as Python-like Arnold workflow source. The
editor setup path maps that extension to Python highlighting in the places that
can be configured reliably.

## Automatic Repo Setup

On normal Megaplan CLI startup, the repo-local setup runs best-effort and
idempotently:

- `.gitattributes` gets `*.pypeline linguist-language=Python` so GitHub
  Linguist classifies and highlights `.pypeline` as Python.
- `.vscode/settings.json` gets:

```json
{
  "files.associations": {
    "*.pypeline": "python"
  }
}
```

That covers VS Code, Cursor, Windsurf, and other VS Code-compatible editors
when the workspace settings file is respected.

Run it explicitly with:

```bash
python -m arnold_pipelines.megaplan setup --editors
```

## Optional User Editor Setup

Global editor preferences are not changed automatically on ordinary CLI
startup. To opt in:

```bash
python -m arnold_pipelines.megaplan setup --editors --user-editors
```

That command updates detected user-level config for:

- Sublime Text: adds `pypeline` to `Python.sublime-settings` extensions.
- Vim: writes `~/.vim/ftdetect/pypeline.vim` when `~/.vim` exists.
- Neovim: writes `~/.config/nvim/ftdetect/pypeline.vim` when Neovim config
  exists.
- Emacs: writes `~/.emacs.d/pypeline-mode.el` when `~/.emacs.d` exists.

JetBrains IDEs should be configured manually under `Editor | File Types` by
associating `*.pypeline` with Python. The setting is IDE/user-level and is not
safe to rewrite generically from a repo tool.

## Validated Mechanisms

- GitHub uses Linguist `.gitattributes` overrides, including
  `linguist-language`, for language detection and syntax highlighting.
- VS Code documents `files.associations` for mapping new file extensions to an
  existing language identifier.
- Sublime Text supports syntax associations through syntax-specific settings,
  including the `extensions` list.
- JetBrains IDEs expose file type associations through `Editor | File Types`.
