# Brief — Area 8: Deterministic external-profile import mechanics

Explore in `/Users/peteromalley/Documents/arnold-oracle` (worktree). Link `.oracle/agent_goal.md`, `.oracle/northstar.md`.

Context: R3 loads a repo-relative `path.py:Class` profile via importlib in `arnold_pipelines/megaplan/resident/cli.py`. Sol requires: deterministic, collision-resistant module identities; containment under the project root (reject absolute paths, `..`, escaping symlinks); no stale module state across tests; acceptable import side effects.

Questions:
1. Existing precedent: does the repo already load code by path/module dynamically (search `importlib`, `import_module`, `spec_from_file_location`, `SourceFileLoader` in `arnold_pipelines/megaplan/` and `agentbox/`)? Cite the best existing pattern (e.g. operation adapters `agentbox/adapters.py`, worker loading, `launch_subagent` machinery, cloud wrapper loading). What naming/caching conventions do they use?
2. For `spec_from_file_location`: what module-name scheme avoids sys.modules collisions across repeated loads and different repos (e.g. hash-based names, `__name__` mangling, `sys.modules` cleanup)? Check how existing code handles re-import/caching.
3. Symlink containment: how does the repo resolve+confine paths elsewhere (search `resolve()`, `is_relative_to`, `commonpath`, traversal guards, e.g. `agentbox/repos.py`, custody/redaction code)? What's the strongest reusable guard?
4. Import side effects: does any existing loader warn about or forbid side-effectful imports? Any test isolation precedent (monkeypatch, import lock)?

Report: verified facts with file:line, recommended mechanics (module identity scheme, containment guard, cache policy), unknowns/risks. Ranked findings, <300 words.
