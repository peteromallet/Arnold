# Sprint 5 — Codebase research and code investigation

Bot can read and reason about public GitHub codebases. Adds GitHub REST API integration, codebase management, code investigation tools, and caching.

**Full spec is at `planning-bot-spec.md` in this repo root. Refer to Code Investigation, codebases table, code_artifacts table sections.**

## Supabase
- URL: https://yhwflvadmefhkshwbfnf.supabase.co
- Service key: <redacted; use SUPABASE_SERVICE_KEY env>

## Scope

- Tables: codebases (with group_name, verified_accessible_at), code_artifacts (unified: excerpts, summaries, cache)
- GitHub REST API integration (PAT-authenticated, 5000/hour) with rate limit monitoring
- Org populator script: one-time setup populates codebases from peteromallet and banodoco org listings; verifies each repo is fetchable
- Workspace grouping: initial groups configured; user adjustable via natural language
- Codebase management tools: add_codebase, remove_codebase, list_codebases
- Code investigation tools: get_codebase_tree, read_codebase_file, search_code, analyze_code
- Cross-codebase analyze_code with multiple codebase_ids
- Code artifact tools: save_code_excerpt, mark_code_in_body
- Codebase research checklist item (#6) workflow
- Cache management — hourly TTL on api_cache, scheduled cleanup

## Key Data Model

### codebases
id, owner (lowercase), name (lowercase), default_branch, scope (global|epic_specific), group_name, associated_epic_id, added_at, added_via, last_accessed_at, verified_accessible_at, notes
Unique: (owner, name)

### code_artifacts
id, codebase_id, epic_id, kind (excerpt|summary|api_cache), source (conversation|codebase), file_path, line_range, scope (file|directory|cross_codebase for summaries), content, content_summary, metadata (json), created_at, last_used_at, expires_at

## Acceptance Criteria

- Populator runs against peteromallet and banodoco orgs (mocked GitHub in tests) → codebases rows created with verified_accessible_at
- Inaccessible repos reported in output, not silently skipped
- Add a public GitHub repo via natural language → codebases row created, tree fetchable
- analyze_code with multiple codebase_ids → analysis covering all referenced codebases
- Same analyze_code within hour → served from code_artifacts cache (no GitHub API call)
- GitHub rate limit at 80% → log entry with level warn, category external_api
- 404 on deleted repo → bot reports failure, retains cached content

## Tests
- Unit: cache TTL logic; codebase scope filtering; file path parsing; group-name resolution
- Integration: full investigation chain (tree → search → read → save_excerpt → mark_in_body) against mocked GitHub; cross-codebase analysis
