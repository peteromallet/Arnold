# Implementation Plan: Sprint 5 Codebase Research

## Overview
Arnold is a Python `agent_kit` project with decorator-registered tools, SQLite and Supabase store adapters, SQL migrations, and turn-loop tool loading in `agent_kit/loop.py`. Sprint 5 should extend the existing tool/store pattern rather than add a separate service: create codebase tables in both migration stacks, add a small GitHub REST client, add store methods for `codebases` and `code_artifacts`, register code investigation tools, and cover the behavior with mocked GitHub tests.

The critique does not show that the plan targeted the wrong code or root cause. The architecture is still right: GitHub fetching belongs behind a client/cache/tool layer. The missing issue is a required cross-cutting security invariant: any fetched code content must be redacted before it is returned to the model, persisted in `tool_calls.result`, logged, or cached/replayed from `code_artifacts`. This revision adds that invariant at the content boundary and backs it with secret-fixture tests.

The relevant spec anchors are `planning-bot-spec.md` Sprint 5, Code Investigation, `codebases`, `code_artifacts`, code tool sections, and the secret-redaction requirement for code investigation outputs. The implementation should keep GitHub read-only, require `GITHUB_PAT`, cache API responses and `analyze_code` results in `code_artifacts`, redact secret-like content before persistence or model exposure, and preserve cached content when a repo later returns 404.

## Phase 1: Schema And Store Foundation

### Step 1: Add database migrations (`supabase/migrations/`, `agent_kit/store/migrations/sqlite/`)
**Scope:** Medium
1. Create migration `008_codebase_research.sql` in both Supabase and SQLite migration directories.
2. Add `codebases` with lowercase `owner`/`name`, unique `(owner, name)`, `scope`, `group_name`, `associated_epic_id`, `default_branch`, access timestamps, and notes.
3. Add `code_artifacts` with `kind`, `source`, optional codebase/epic refs, `file_path`, `line_range`, `scope`, `content`, `content_summary`, JSON metadata, timestamps, and `expires_at`.
4. Add indexes from the spec, including cache cleanup support on `expires_at`.

### Step 2: Extend store adapters (`agent_kit/store/sqlite.py`, `agent_kit/store/supabase.py`, `agent_kit/ports.py`)
**Scope:** Large
1. Add store protocol methods for codebase CRUD, scoped listing, artifact CRUD, cache lookup/update, cache expiry cleanup, and `last_accessed_at`/`verified_accessible_at` updates.
2. Mirror behavior in SQLite and Supabase, following existing `_json`/normalization helpers.
3. Keep owner/name normalization server-side so `PeterOMallet/Repo` and `peteromallet/repo` converge.
4. Add focused unit tests around scope filtering, group filtering, uniqueness, artifact cache TTL, and expired cache cleanup.

## Phase 2: GitHub Integration And Redaction

### Step 3: Add code-content redaction (`agent_kit/code_redaction.py`, `agent_kit/logging.py`, `agent_kit/tools/code.py`)
**Scope:** Medium
1. Implement a small content scrubber for source text and JSON-like payloads before code content reaches model-facing tool results, `tool_calls.result`, `system_logs.details`, or `code_artifacts.content`.
2. Cover the spec-required patterns: OpenAI-style keys, GitHub tokens, AWS access keys/secrets, and high-entropy hex-like values.
3. Apply redaction in code investigation tools immediately after GitHub content is fetched and before cache writes or artifact saves.
4. Harden recursive log/result redaction for strings, not only sensitive dictionary keys, so fetched source values cannot bypass redaction through audit persistence.
5. Add tests with a source fixture containing representative secret-like strings and assert raw values do not appear in tool results, artifacts, tool-call rows, or logs.

### Step 4: Add a GitHub REST client (`agent_kit/github_client.py`)
**Scope:** Medium
1. Implement an `httpx`-based client using `GITHUB_PAT`, `Accept: application/vnd.github+json`, and `X-GitHub-Api-Version: 2022-11-28`.
2. Implement endpoints for repo metadata, org repo pagination, tree fetch, file content fetch, and code search.
3. Track `X-RateLimit-*` headers and log a redacted `warn` `external_api` system event when usage reaches 80% of the hourly limit.
4. Return structured errors for 404, 403/rate-limited, malformed paths, and unsupported file sizes rather than throwing opaque HTTP errors.

### Step 5: Add cache helpers (`agent_kit/code_cache.py`)
**Scope:** Medium
1. Define deterministic cache keys in `code_artifacts.metadata` for GitHub metadata/tree/file/search and `analyze_code` requests.
2. Use a one-hour TTL for `kind='api_cache'` and same-question `analyze_code` cache hits.
3. Keep durable summaries separate from transient API cache entries.
4. Store only redacted fetched content in cache rows; never cache raw source text that matched secret-like patterns.
5. On deleted repo 404, return a failure payload while leaving existing redacted artifacts untouched and available for future reads.

## Phase 3: Tools And Runtime Wiring

### Step 6: Register codebase management tools (`agent_kit/tools/code.py`)
**Scope:** Medium
1. Add `add_codebase(owner, name, scope, epic_id?, group_name?, notes?)`, verifying repo metadata before insert/update and setting `verified_accessible_at`.
2. Add `remove_codebase(codebase_id)` as a soft or hard delete according to existing repo conventions; prefer hard delete only if no retained artifacts depend on it.
3. Add `list_codebases(scope?, group?, epic_id?)`, including grouped global codebases and epic-specific rows.
4. Record `epic_events` for `codebase_added` where an epic is associated.

### Step 7: Register investigation tools (`agent_kit/tools/code.py`, `agent_kit/loop.py`)
**Scope:** Large
1. Add `get_codebase_tree(codebase_id, path?)` backed by GitHub tree API and hourly API cache.
2. Add `read_codebase_file(codebase_id, file_path, line_range?)`, with line range parsing, content truncation rules aligned to the 10k excerpt limit, and redaction before returning or persisting content.
3. Add `search_code(codebase_id, query, type?)`, mapping the four spec search types to GitHub search queries or local filtering over cached tree/file data where simpler; redact matched excerpts before returning them.
4. Add `analyze_code(codebase_ids, scope, question)`, accepting multiple codebase IDs, gathering relevant redacted tree/search/file snippets, returning per-codebase coverage, and caching identical requests for one hour.
5. Import `agent_kit.tools.code` in `agent_kit/loop.py` so the tools appear in model definitions.

### Step 8: Add code artifact tools (`agent_kit/tools/code.py`, `agent_kit/tools/editorial.py`)
**Scope:** Medium
1. Add `save_code_excerpt(epic_id, source, content, summary, codebase_id?, file_path?, line_range?)`, storing `kind='excerpt'`, `source`, `content_summary`, and artifact metadata after redacting the supplied content.
2. Add `mark_code_in_body(artifact_id)` to mark the artifact metadata/body flag and record an `epic_events` row with `event_type='code_referenced'`.
3. Keep actual body weaving through the existing `edit_epic` flow so `mark_code_in_body` remains a durable marker rather than a hidden body rewrite.

### Step 9: Update prompt/hot context behavior (`agent_kit/prompts.py`, `agent_kit/store/*`)
**Scope:** Medium
1. Include available codebases with `name`, `scope`, `group_name`, and notes in hot context, matching the spec’s “available codebases” prompt input.
2. Add guidance for checklist item #6: use code tools before designing changes when codebase research is applicable, save durable findings, and mark excerpts only when they belong in the deliverable.
3. Avoid loading large artifact content into hot context; include summaries and recent artifact metadata only.
4. Ensure any artifact snippets included in hot context are redacted and summary-sized.

## Phase 4: Populator And Maintenance

### Step 10: Add org populator (`scripts/populate_codebases.py`, `scripts/codebase_groups.yaml`)
**Scope:** Medium
1. Implement `python scripts/populate_codebases.py --orgs peteromallet,banodoco` against the GitHub client.
2. Paginate `GET /orgs/{org}/repos?type=public&per_page=100`, verify each repo with `GET /repos/{owner}/{name}`, lower-case owner/name, and upsert rows.
3. Print inaccessible repos explicitly with owner/name and error reason.
4. Add `--apply-groups` to read `scripts/codebase_groups.yaml` and update `group_name` idempotently.
5. Test the script with a mocked GitHub client, including inaccessible repos and group updates.

### Step 11: Add cache cleanup entry point (`scripts/cleanup_code_artifacts.py` or store helper)
**Scope:** Small
1. Add a callable/script that deletes expired `kind='api_cache'` rows where `expires_at < now()`.
2. Document that production should schedule it daily, matching the existing setup checklist style.
3. Unit test the deletion query against SQLite.

## Phase 5: Validation

### Step 12: Add targeted unit tests (`tests/test_codebase_store.py`, `tests/test_github_client.py`, `tests/test_code_redaction.py`, `tests/test_code_tools.py`)
**Scope:** Large
1. Test cache TTL hit/miss behavior and that identical `analyze_code` calls within an hour avoid GitHub calls.
2. Test codebase scope filtering, group-name resolution, and lower-case owner/name normalization.
3. Test file path and line range parsing.
4. Test GitHub rate limit accounting logs a warn at 80%.
5. Test 404 behavior returns a failure and retains existing cached artifacts.
6. Test secret redaction against fetched source content containing OpenAI keys, GitHub tokens, AWS keys/secrets, and high-entropy hex strings.

### Step 13: Add integration tests (`tests/test_code_investigation.py`)
**Scope:** Large
1. Mock GitHub responses for tree, search, file read, and repo metadata.
2. Exercise the full chain: `get_codebase_tree -> search_code -> read_codebase_file -> save_code_excerpt -> mark_code_in_body`.
3. Exercise `analyze_code` over multiple codebases and assert the response covers each referenced codebase.
4. Exercise natural-language loop behavior with the fake model: user asks to add a public repo, model calls `add_codebase`, then `get_codebase_tree` is fetchable.
5. Assert no raw secret fixture values appear in `tool_calls.result`, `code_artifacts.content`, `system_logs.details`, or model-visible tool results during the chain.

## Execution Order
1. Land migrations and store methods first, because every tool and test depends on stable persistence.
2. Add redaction utilities before GitHub file-read tooling, so no raw fetched source path is introduced without a scrubber.
3. Add the GitHub client with mocked tests before wiring tools, so provider behavior and rate-limit handling are isolated.
4. Add code tools in thin slices: management tools, then read tools, then `analyze_code`, then artifact writes.
5. Wire prompt/hot context after tool behavior is stable.
6. Add scripts and cleanup last, since they are operational wrappers over already-tested primitives.

## Validation Order
1. Run focused migration/store tests first: `pytest tests/test_codebase_store.py`.
2. Run redaction and GitHub/client tests before broader tool tests: `pytest tests/test_code_redaction.py tests/test_github_client.py`.
3. Run code tool tests with mocked HTTP: `pytest tests/test_code_tools.py`.
4. Run integration chain tests: `pytest tests/test_code_investigation.py`.
5. Run affected existing suites around loop, prompts, logging, tool registry, and Supabase adapters.
6. Finish with the full suite: `pytest`.
