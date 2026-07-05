Working directory: /Users/peteromalley/Documents/Arnold

Task: Inventory console scripts, CLIs, shell wrappers, aliases, and command examples that could remain direct agent launch surfaces.

Focus areas:
- pyproject.toml console_scripts
- arnold/**/cli*.py, arnold_pipelines/**/cli*.py
- scripts/**
- docs/**/*.md command examples
- Makefiles or shell files if present

Output:
- Table-like list: command/surface, path, current launch behavior, migration handling.
- Flag any command that should become an `agent ...` subcommand or delegate to facade.
- Keep under 900 words.
