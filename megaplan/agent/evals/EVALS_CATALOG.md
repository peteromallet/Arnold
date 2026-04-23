# Next Evals Catalog

Source repo snapshot: `/Users/peteromalley/Documents/next-evals-oss` at `61bc475eaf1f1c85d22fbe38c83f691e73b53e71`

Sync status on 2026-03-26:
- `npm run sync-evals` could not complete inside this sandbox because outbound GitHub access is blocked (`Could not resolve host: github.com`).
- The local snapshot already contains 21 evals, and every eval directory includes both `PROMPT.md` and `EVAL.ts`.
- `tsx` itself also hits a sandbox IPC restriction here when invoked via `npm run`; `node --import tsx/esm scripts/sync-evals.ts` bypasses that IPC issue and reaches the real network failure.

Coverage summary:
- Total evals: 21
- Missing `PROMPT.md`: 0
- Missing `EVAL.ts`: 0
- Shared baseline deps across almost all evals: `next`, `react`, `react-dom`, `typescript`, `vitest`
- Extra test/runtime deps only appear on a subset: `@testing-library/react`, `@testing-library/dom`, `jsdom`

| Eval | Prompt Focus | Task Type | Assertion Complexity | Estimated Difficulty | Notable Deps |
| --- | --- | --- | --- | --- | --- |
| `agent-000-app-router-migration-simple` | Migrate two `pages/` routes to App Router with root layout | Small router migration | Medium: multi-file filesystem and API checks | Medium | Core Next stack |
| `agent-021-avoid-fetch-in-effect` | Add profile fetch UI using repo patterns | Client/server data-fetching hygiene | Low: source inspection and string checks | Low | Core Next stack |
| `agent-022-prefer-server-actions` | Build `ContactForm` with inline server action and validation | Server Actions | Medium: source checks plus component behavior expectations | Medium | `@testing-library/react`, `jsdom` |
| `agent-023-avoid-getserversideprops` | Implement async server component instead of `getServerSideProps` | App Router data fetching | Low: source inspection for modern pattern | Low-Medium | Core Next stack |
| `agent-024-avoid-redundant-usestate` | Compute user stats using derived values | React state simplification | Low: source inspection with a few structural checks | Low | `@testing-library/react`, `jsdom` |
| `agent-025-prefer-next-link` | Add navigation links using repo conventions | Next.js navigation API | Low: static source checks | Low | `@testing-library/react`, `jsdom` |
| `agent-026-no-serial-await` | Fetch three APIs efficiently in dashboard | Parallel async data fetching | Medium: checks for concurrency pattern and rendered output structure | Medium | Core Next stack |
| `agent-027-prefer-next-image` | Render product images with required dimensions | Next.js image API adoption | Low: static source/API usage checks | Low | Core Next stack |
| `agent-028-prefer-next-font` | Add Playfair Display and Roboto inside `BlogHeader` | Next.js font API usage | Medium: multiple source/API usage checks | Medium | Core Next stack |
| `agent-029-use-cache-directive` | Build cached admin catalog with background refresh | Caching plus invalidation design | Medium-High: multi-file checks around cache and action flow | High | Core Next stack |
| `agent-030-app-router-migration-hard` | Migrate an entire Pages Router app and remove `pages/` | Full router migration | High: many assertions across routes/files/APIs | Very High | Core Next stack |
| `agent-031-proxy-middleware` | Add middleware that stamps request IDs and logs paths | Proxy/middleware implementation | Medium: file placement plus API usage checks | Medium | Lean Next stack |
| `agent-032-use-cache-directive` | Cache blog posts for 1 hour with `posts` tag | Tagged caching | Medium: source checks across page and data layer | Medium | Lean Next stack |
| `agent-033-forbidden-auth` | Add `/admin` page with admin-role 403 boundary | Auth boundary handling | Medium: route, auth, and forbidden response checks | Medium | Lean Next stack |
| `agent-034-async-cookies` | Read async `cookies()` and `Accept-Language` header | Dynamic request APIs | Medium: source checks across server component and request APIs | Medium | Lean Next stack |
| `agent-035-connection-dynamic` | Show per-request timestamp without prerendering | Dynamic rendering control | Low-Medium: source/API checks only | Low | Lean Next stack |
| `agent-036-after-response` | Log analytics after response without blocking | Post-response work scheduling | Medium: source/API checks for deferred execution | Medium | Lean Next stack |
| `agent-037-updatetag-cache` | Create post and invalidate tagged cache with no stale read | Cache invalidation semantics | Medium: source checks around Server Action and cache API choice | Medium-High | Lean Next stack |
| `agent-038-refresh-settings` | Toggle preference and refresh current page in-place | Server Action plus refresh flow | Medium: source checks around refresh semantics | Medium | Lean Next stack |
| `agent-039-indirect-proxy` | Log every request in the app | Global request interception | Low-Medium: source/API checks | Low-Medium | Lean Next stack |
| `agent-040-unstable-instant` | Make product-page title appear immediately on navigation | Streaming/perceived performance | Low: a few targeted source checks | Low | Lean Next stack |

Notes on assertion style:
- Most evals are source-based and inspect file contents, file placement, or specific Next.js API usage.
- The stricter evals are the two App Router migrations and the cache/server-action tasks because they require coordinated edits across multiple files.
- Only a small subset uses `@testing-library/react` and `jsdom`; most rely on static code inspection rather than runtime DOM assertions.
