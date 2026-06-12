Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

You are a DeepSeek audit subagent reviewing top-level Python/package boundaries.

Known top-level code-ish folders/files:
vibecomfy, ready_templates, recipes, agentic, scripts, tools, tests, vendor,
workflow_corpus, _regen_templates.py, _fix_t6.py, _debug_*.py.

Question:
- Which folders are importable/runtime package surfaces?
- Which are CLI/dev tooling?
- Which are data/corpus/template sources?
- Which root scripts should become tools or scripts?
- What moves are likely to break imports, pyproject config, tests, or CLI entrypoints?

Return under 450 words:
1. Boundary map.
2. Safe moves at top level.
3. Risky moves that should wait.
4. Specific files/config references to check before changing.
