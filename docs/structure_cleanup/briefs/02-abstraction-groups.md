Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

You are a DeepSeek audit subagent reviewing top-level abstraction boundaries.

Question: what top-level folder groups should exist so the repo feels self-organizing?

Use the current observed root entries:
agentic, agents, artifacts, docs, ready_templates, recipes, scripts, tests, tools,
vendor, vibecomfy, workflow_corpus, plus root files including debug scripts,
plans, generated indexes, manifests, lockfiles, audit notes, env/log files.

Focus on:
- Which categories are real first-class concepts in this project?
- Which current entries are implementation details of another category?
- Which root files should be grouped under docs/, scripts/, tools/, artifacts/,
  out/, or another existing/new folder?
- Which names are confusing or overlapping, especially agentic vs agents vs .agents
  and artifacts vs out?

Return conclusions only, under 400 words:
1. Proposed root taxonomy.
2. Entries that violate it today.
3. Minimal migration path that avoids breaking imports/tests.
4. Any naming conflicts worth resolving later.
