# Batch 3 attempt 5 — final route-aware inventory validation

Final inventory identities:

- Inventory: `docs/nbf-signal-inventory.json`
- Inventory SHA-256: `e92b6c90c6adf7c6d5f05a8d10c888f4900b1a2395cf35ce55689323987568da`
- Inventory entries: `120`
- Source-input SHA-256: `60d5d933e722d8f49905b534866e1a2bdb6d0c7766103f3176adacd7cd33a958`
- Generator version: `nbf05-signal-inventory-v1`
- Discovery rules version: `nbf05-discovery-rules-v1`
- Source digest version: `nbf05-source-inputs-v2`

## Commands and results

All commands ran from the repository root with fresh temporary pytest
basetemps and no candidate source mutation.

1. `python3 scripts/generate_nbf_signal_inventory.py`
   Result: PASS; regenerated the route-aware inventory.
2. `python3 scripts/generate_nbf_signal_inventory.py --check`
   Result: PASS; first freshness check.
3. `python3 scripts/generate_nbf_signal_inventory.py --check`
   Result: PASS; second independent freshness check.
4. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q --cache-clear --basetemp "$(mktemp -d /private/tmp/nbf-shell-semantic.XXXXXX)" tests/cloud/test_repository_signal_inventory.py tests/arnold_pipelines/megaplan/test_python_signal_inventory.py tests/test_no_bare_subprocess.py tests/arnold_pipelines/megaplan/test_subagent_launcher_disposition.py`
   Result: PASS: 31 passed.
   This covers all 120 generated rows, action-aware classifications, fan
   lifecycle routing, declaration filtering, and no-bare checks.
5. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q --cache-clear --basetemp "$(mktemp -d /private/tmp/nbf-shell-tmux.XXXXXX)" tests/cloud/test_watchdog_dispositions.py`
   Result: PASS: 18 passed.
   This covers the relevant disposition, canonical wrapper, and tmux
   post-proof behavior.
6. `bash -n` on `arnold-supervisor-runtime-lib`, `arnold-heartbeat`,
   `arnold-progress-auditor`, `arnold-watchdog`, and both ensure-service
   wrappers.
   Result: PASS: 6 files.
7. In-memory `compile()` over touched Python files reported by
   `git status --porcelain`.
   Result: PASS: 39 files; no bytecode was written.
8. `git diff --check`
   Result: PASS.

## Semantic evidence

- Runtime-lib signal function declarations at their source locations are
  absent from the generated rows; only the actual bridge call body remains.
- Canonical helper callers in heartbeat, progress-auditor, watchdog,
  systemd, and runtime-lib are non-worker lifecycle rows with
  `shell-nbf05-v1`, runtime-lib two-scan ownership, and the canonical
  non-worker resolver.
- `pgrep`, `kill -0`, and `wait` rows are explicit zero-scan exclusions.
- Direct watchdog `tmux kill-session` is explicitly classified as
  post-proof non-worker cleanup with no confirmation policy.
- All 120 generated test-binding symbols resolve through the inventory test
  suite/collection; the four exact route-aware validators also resolve.

No production runtime semantics, tasklist, Oracle packet, or NBF08 artifact
was edited in this lane.

