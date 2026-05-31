# M3a Silent Failure Census — Authoritative Decision Table

> **Phase 1 checkpoint** — completed T3, refined T4 (2026-05-25)
>
> Census tool: `scripts/silent_failure_census.py`
>
> `needs_review` is **empty** ✅ — all 1,049 silent `except` handlers and 100 `print(..., file=sys.stderr)` sites across 255 files are classified into exactly one of three buckets.

---

## Summary

| Metric | Count |
|---|---|
| Files scanned | 837 |
| Files with findings | 255 |
| Silent `except` handlers | 1,049 |
| `print(..., file=sys.stderr)` sites | 100 |
| **In-scope core** (eligible for M3a patching) | 14 files |
| **Explicitly excluded** (out of scope) | 172 files |
| **Classified out of M3a** (deferred to M3b+) | 69 files |
| **Needs review** (unclassified) | **0** |

---

## Bucket 1: In-Scope Core Decision Table (14 files)

These files are eligible for M3a **warning-level visibility changes only**. All control-flow changes (halts, raises, strict downgrades) are deferred to M3b per SD1. Each row includes a **grep-stable token** to be used in the emitted `logger.warning()` message so that downstream monitoring and post-mortem tooling can locate specific failure sites.

### `megaplan/handlers/gate.py` — 2 silent handlers

| Line | Failure Class | Current Behavior | Decision | Rationale | Milestone | Token |
|---|---|---|---|---|---|---|
| 416 | `corrupt-read` | `except Exception` → `return set()` — silently returns empty set when prior unresolved flags file is corrupt/unreadable | Add `logger.warning` on corrupt/missing read; keep `return set()` | Flags file is an optimization cache; empty set is a safe fallback. Making corruption visible aids debugging without changing gate behavior. | M3a | `M3A_WARN_CORRUPT_PRIOR_FLAGS` |
| 541 | `observability-emit-failure` | `except Exception` → `pass` — silently swallows failures when emitting FLAG_RAISED/FLAG_RESOLVED events | Add `logger.warning` with event kind context; keep `pass` | Event emission is best-effort observability. Loss should be visible but must not block gate completion. | M3a | `M3A_WARN_EMIT_FLAG_EVENT` |

### `megaplan/handlers/critique.py` — 1 silent handler + 1 stderr print

| Line | Failure Class | Current Behavior | Decision | Rationale | Milestone | Token |
|---|---|---|---|---|---|---|
| 97 | `parse-fallback` | `except ValueError` → `assign 999` — silently defaults critique rank to 999 when model name can't be parsed | Add `logger.warning` with model name context; keep `assign 999` | 999 is a safe "lowest-priority" sentinel. The parse failure should be visible so operators can detect model roster mismatches. | M3a | `M3A_WARN_CRITIQUE_RANK_PARSE` |
| 240 | `stderr-bypass` | `print(..., file=sys.stderr)` — writes parallel-critique fallback notice directly to stderr, bypassing logging framework | Route through `logger.warning("megaplan")`; preserve message text | Raw stderr prints are invisible to structured logging consumers. Routing through the logger makes them observable without changing user-facing behavior. | M3a | `M3A_WARN_PARALLEL_CRITIQUE_FALLBACK` |

### `megaplan/handlers/override.py` — 8 silent handlers

All 8 sites follow the same pattern: `try: emit(EventKind.OVERRIDE_APPLIED, ...) \n except Exception: pass`. They are best-effort observability emissions that should not block override actions.

| Line | Failure Class | Current Behavior | Decision | Rationale | Milestone | Token |
|---|---|---|---|---|---|---|
| 93 | `read-race` | `except (OSError, ValueError)` → `continue` — skips unreadable revise start timestamps during iteration | Add `logger.warning`; keep `continue` | Timestamp iteration is a liveness scan; a single corrupt entry should not abort the scan. | M3a | `M3A_WARN_REVISE_START_READ` |
| 158 | `observability-emit-failure` | `except Exception` → `pass` — swallows emit failure for OVERRIDE_APPLIED (add-note) | Add `logger.warning`; keep `pass` | Best-effort observability; emit failure must not block note attachment. | M3a | `M3A_WARN_EMIT_OVERRIDE_ADD_NOTE` |
| 184 | `observability-emit-failure` | `except Exception` → `pass` — swallows emit failure for OVERRIDE_APPLIED (abort) | Add `logger.warning`; keep `pass` | Best-effort observability; emit failure must not block abort. | M3a | `M3A_WARN_EMIT_OVERRIDE_ABORT` |
| 319 | `observability-emit-failure` | `except Exception` → `pass` — swallows emit failure for OVERRIDE_APPLIED (force-proceed) | Add `logger.warning`; keep `pass` | Best-effort observability; emit failure must not block force-proceed. | M3a | `M3A_WARN_EMIT_OVERRIDE_FORCE_PROCEED` |
| 359 | `observability-emit-failure` | `except Exception` → `pass` — swallows emit failure for OVERRIDE_APPLIED (replan) | Add `logger.warning`; keep `pass` | Best-effort observability; emit failure must not block replan. | M3a | `M3A_WARN_EMIT_OVERRIDE_REPLAN` |
| 572 | `observability-emit-failure` | `except Exception` → `pass` — swallows emit failure for OVERRIDE_APPLIED (set-robustness) | Add `logger.warning`; keep `pass` | Best-effort observability; emit failure must not block robustness changes. | M3a | `M3A_WARN_EMIT_OVERRIDE_ROBUSTNESS` |
| 633 | `observability-emit-failure` | `except Exception` → `pass` — swallows emit failure for OVERRIDE_APPLIED (set-profile) | Add `logger.warning`; keep `pass` | Best-effort observability; emit failure must not block profile changes. | M3a | `M3A_WARN_EMIT_OVERRIDE_PROFILE` |
| 777 | `observability-emit-failure` | `except Exception` → `pass` — swallows emit failure in `_infer_phase_agent` profile-load fallback | Add `logger.warning` with profile context; keep `pass` | Profile loading is best-effort in this code path; failure should be visible but the agent inference fallback must proceed. | M3a | `M3A_WARN_EMIT_PROFILE_LOAD` |

### `megaplan/handlers/verifiability.py` — 1 silent handler

| Line | Failure Class | Current Behavior | Decision | Rationale | Milestone | Token |
|---|---|---|---|---|---|---|
| 54 | `corrupt-read` | `except Exception` → `assign []` — silently returns empty list when verifications file is corrupt/unreadable | Add `logger.warning` distinguishing missing-vs-corrupt; keep `assign []` | Empty verifications list is the safe fallback (no verifications recorded). Warning on corrupt file aids debugging; missing files on first run remain silent per SD3. | M3a | `M3A_WARN_CORRUPT_VERIFICATIONS` |

### `megaplan/handlers/shared.py` — 1 stderr print

| Line | Failure Class | Current Behavior | Decision | Rationale | Milestone | Token |
|---|---|---|---|---|---|---|
| 152 | `stderr-bypass` | `print(f"[megaplan] Starting {step}...", file=sys.stderr)` — phase notice written directly to stderr | Route through `logger.info("megaplan")`; preserve message text | Phase notices are informational lifecycle events that should flow through structured logging. The `[megaplan]` prefix becomes the logger name. | M3a | `M3A_PHASE_NOTICE` |

### `megaplan/handlers/finalize.py` — No findings

(Allowlisted; no silent handlers or stderr prints detected. M3a will ensure it uses `logging.getLogger("megaplan")` for any future logging.)

### `megaplan/_pipeline/executor.py` — 1 silent handler

| Line | Failure Class | Current Behavior | Decision | Rationale | Milestone | Token |
|---|---|---|---|---|---|---|
| 124 | `corrupt-overwrite` | `except json.JSONDecodeError` → `pass` — silently overwrites corrupt state.json with executor-owned state | Add `logger.warning`; keep overwrite behavior (M3b will add halt) | The current behavior silently replaces a corrupt file — this is data-loss-prone. M3a makes it visible; M3b will change control flow to halt. **Do not halt in M3a.** | M3a | `M3A_WARN_CORRUPT_STATE_OVERWRITE` |

### `megaplan/_pipeline/faults.py` — 1 silent handler

| Line | Failure Class | Current Behavior | Decision | Rationale | Milestone | Token |
|---|---|---|---|---|---|---|
| 90 | `corrupt-read` | `except json.JSONDecodeError` → `return cls()` — silently returns empty FaultRegistry when faults.json is corrupt | Add `logger.warning`; keep `return cls()` | Empty registry is the safe fallback (no faults tracked). Warning makes corruption visible. Note: only `json.JSONDecodeError` is currently caught; `OSError`/`UnicodeDecodeError` would propagate — M3b may add defensive catches. | M3a | `M3A_WARN_CORRUPT_FAULTS` |

### `megaplan/_pipeline/run_cli.py` — 4 silent handlers + 7 stderr prints

| Line | Failure Class | Current Behavior | Decision | Rationale | Milestone | Token |
|---|---|---|---|---|---|---|
| 258 | `corrupt-read` | `except (json.JSONDecodeError, OSError)` → `assign <empty-collection>` — silently returns empty collection when state file is corrupt/unreadable | Add `logger.warning`; keep return value | Empty collection is safe fallback for pipeline state loading. | M3a | `M3A_WARN_PIPELINE_STATE_READ` |
| 269 | `corrupt-read` | `except (json.JSONDecodeError, OSError)` → `assign None` — silently returns None for corrupt/unreadable plan metadata | Add `logger.warning`; keep `return None` | None is the "no plan loaded" sentinel. | M3a | `M3A_WARN_PLAN_META_READ` |
| 327 | `file-missing` | `except OSError` → `pass` — silently skips missing state file during pipeline run | Add `logger.warning` (only if file was expected to exist); keep `pass` | Distinguish first-run missing (silent per SD3) from unexpected missing. | M3a | `M3A_WARN_RUN_STATE_MISSING` |
| 430 | `corrupt-read` | `except json.JSONDecodeError` → `assign <empty-collection>` — silently returns empty collection for corrupt creative idea seed | Add `logger.warning`; keep return value | Empty collection is safe fallback. | M3a | `M3A_WARN_CREATIVE_SEED_READ` |
| 132,145,187,220,228,333,463 | `stderr-bypass` | Various `print(..., file=sys.stderr)` sites for CLI progress and pipeline status | Route through `logger.info("megaplan")` where they convey pipeline state; leave CLI-user-facing prints unchanged | Some prints are pipeline-status messages suitable for logging; others are interactive CLI output that should stay on stderr. Classify each site individually. | M3a | `M3A_CLI_PIPELINE_STATUS` |

### `megaplan/_pipeline/stages/inprocess_step.py` — 1 silent handler

| Line | Failure Class | Current Behavior | Decision | Rationale | Milestone | Token |
|---|---|---|---|---|---|---|
| 126 | `corrupt-read` | `except json.JSONDecodeError` → `return <empty-collection>` — silently returns empty dict when in-process state is corrupt | Add `logger.warning`; keep return value | Empty dict is safe "no state" fallback for in-process step reading. | M3a | `M3A_WARN_INPROCESS_STATE_READ` |

### `megaplan/auto.py` — 23 silent handlers + 1 stderr print

`auto.py` has the most complex classification surface. Handlers fall into four categories:

#### Category A: Read-path corrupt/unreadable (JSON/Unicode/Value errors)

| Line | Function | Failure Class | Current Behavior | Decision | Milestone | Token |
|---|---|---|---|---|---|---|
| 423 | `_format_phase_heartbeat` | `corrupt-read` | `except (OSError, json.JSONDecodeError)` → `assign None` | Add `logger.warning` (corrupt token for JSON, unreadable for OSError); keep `assign None` | M3a | `M3A_WARN_HEARTBEAT_STATE_READ` |
| 552 | `_read_unresolved_flag_ids` | `corrupt-read` | `except (OSError, json.JSONDecodeError)` → `continue` | Add `logger.warning`; keep `continue` | M3a | `M3A_WARN_AUTO_FLAGS_READ` |
| 624 | `_sum_history_cost_usd` | `corrupt-read` | `except (OSError, json.JSONDecodeError)` → `return 0.0` | Add `logger.warning`; keep `return 0.0` | M3a | `M3A_WARN_HISTORY_COST_READ` |
| 713 | `_record_lifecycle_failure` | `corrupt-read` | `except (OSError, json.JSONDecodeError, ValueError)` → `assign <fallback>` | Add `logger.warning`; keep fallback | M3a | `M3A_WARN_LIFECYCLE_FAILURE_READ` |
| 796 | `_recover_execute_callback_failure_state` | `corrupt-read` | `except (OSError, RuntimeError, ValueError, json.JSONDecodeError)` → `return False` | Add `logger.warning`; keep `return False` | M3a | `M3A_WARN_CALLBACK_RECOVERY_READ` |
| 842 | `_quarantine_phase_outputs` | `corrupt-read` | `except (json.JSONDecodeError, ValueError)` → `assign None` | Add `logger.warning`; keep `assign None` | M3a | `M3A_WARN_QUARANTINE_READ` |
| 873 | `_clear_orphaned_active_step` | `corrupt-read` | `except (OSError, json.JSONDecodeError, ValueError)` → `return False` | Add `logger.warning`; keep `return False` | M3a | `M3A_WARN_ORPHAN_CLEAR_READ` |

#### Category B: Stat-race / liveness OSError (not corrupt, just race conditions)

| Line | Function | Failure Class | Current Behavior | Decision | Rationale | Milestone | Token |
|---|---|---|---|---|---|---|---|
| 380 | `_plan_liveness_mtime` | `stat-race` | `except OSError` → `pass` | **Keep silent** — stat races on liveness files are normal | Files disappearing between listing and reading is expected during concurrent plan operations. Warning would be noise. | None | — |
| 386 | `_plan_liveness_mtime` | `stat-race` | `except OSError` → `continue` | **Keep silent** — same rationale as line 380 | M3b may add debug-level logging for stat races. | None | — |
| 518 | `_latest_versioned_artifact` | `stat-race` | `except OSError` → `return None` | **Keep silent** — artifact listing race | Expected when artifacts are being written concurrently. | None | — |
| 659 | `_get_review_marker` | `stat-race` | `except (OSError, FileNotFoundError)` → `return None` | **Keep silent** — marker file race | Expected during review cycles. | None | — |
| 668 | `_latest_artifact_name` | `stat-race` | `except (OSError, RuntimeError, ValueError)` → `return None` | **Keep silent** — artifact scan race | Expected during artifact generation. | None | — |
| 683 | `_phase_result_signature` | `stat-race` | `except OSError` → `return None` | **Keep silent** — signature file race | Expected during phase transitions. | None | — |
| 727 | `_record_lifecycle_failure` | `file-missing` | `except (OSError, RuntimeError, ValueError)` → `return` | **Keep silent** — expected missing file | When lifecycle failure file doesn't exist yet, that's normal state. | None | — |
| 836 | `_quarantine_phase_outputs` | `stat-race` | `except OSError` → `continue` | **Keep silent** — quarantine race | Expected when outputs are being moved concurrently. | None | — |
| 853 | `_quarantine_phase_outputs` | `stat-race` | `except OSError` → `continue` | **Keep silent** — quarantine race | Same as 836. | None | — |
| 895 | `_clear_orphaned_active_step` | `stat-race` | `except OSError` → `return False` | **Keep silent** — orphaned step race | Expected when active steps are being modified. | None | — |

#### Category C: Drive-loop broad Exception swallows

| Line | Function | Failure Class | Current Behavior | Decision | Rationale | Milestone | Token |
|---|---|---|---|---|---|---|---|
| 1194,1362,1546,1656,1986 | `drive` | `broad-swallow` | `except Exception` → `pass` — five identical broad Exception swallows in the `drive()` main loop | Add `logger.warning` with location context; keep `pass` | These are catch-all safety nets in the auto-pilot loop. Making them visible helps diagnose what's being swallowed; changing control flow risks breaking the loop. | M3a | `M3A_WARN_DRIVE_LOOP_SWALLOW` |

#### Category D: Stderr bypass (heartbeat)

| Line | Failure Class | Current Behavior | Decision | Rationale | Milestone | Token |
|---|---|---|---|---|---|---|
| 335 | `stderr-bypass` | `print(_format_phase_heartbeat(...), file=sys.stderr, flush=True)` — heartbeat written directly to stderr | Route through `logger.info("megaplan")` with message text preserved | Heartbeats are structured observability data that should flow through logging for collection and analysis. | M3a | `M3A_HEARTBEAT` |

#### Category E: Miscellaneous type/value coercion

| Line | Function | Failure Class | Current Behavior | Decision | Rationale | Milestone | Token |
|---|---|---|---|---|---|---|---|
| 636 | `_sum_history_cost_usd` | `type-coercion` | `except (TypeError, ValueError)` → `continue` | Add `logger.warning`; keep `continue` | Cost computation should not fail on malformed data, but malformed data should be visible. | M3a | `M3A_WARN_COST_COERCION` |

### `megaplan/_core/io.py` — 6 silent handlers + 1 stderr print

| Line | Failure Class | Current Behavior | Decision | Rationale | Milestone | Token |
|---|---|---|---|---|---|---|
| 253 | `write-failure` | `except Exception` → `pass` — silently swallows atomic write failures | Add `logger.warning`; keep `pass` | Atomic write failure is a data-loss risk. M3a makes it visible; M3b will consider halting. **Do not halt in M3a.** | M3a | `M3A_WARN_ATOMIC_WRITE_FAILED` |
| 394 | `corrupt-read` | `except (UnicodeDecodeError, json.JSONDecodeError)` → `return` — silently returns on corrupt JSON record during iteration | Add `logger.warning` with record context; keep `return` | Graceful degradation on corrupt records is correct, but the corruption must be visible. | M3a | `M3A_WARN_CORRUPT_JSON_RECORD` |
| 593 | `file-missing` | `except FileNotFoundError` → `continue` — skips missing staging files during cleanup | **Keep silent** — stale staging file cleanup is idempotent; file disappearing between listing and deletion is normal | M3b may add debug-level logging. | None | — |
| 863 | `git-error` | `except OSError` → `return None` — silently returns None when git common dir can't be read | Add `logger.warning`; keep `return None` | Git operations failing silently hides repo configuration issues. | M3a | `M3A_WARN_GIT_COMMON_DIR` |
| 1028 | `git-error` | `except (FileNotFoundError, subprocess.TimeoutExpired)` → `return None` — silently returns None on branch diff base failure | Add `logger.warning`; keep `return None` | Git diff failures should be visible for debugging pipeline drift analysis. | M3a | `M3A_WARN_BRANCH_DIFF_BASE` |
| 1055 | `git-error` | `except (FileNotFoundError, subprocess.TimeoutExpired)` → `return ''` — silently returns empty string on branch diff summary failure | Add `logger.warning`; keep `return ''` | Empty string is the safe fallback; failure visibility aids debugging. | M3a | `M3A_WARN_BRANCH_DIFF_SUMMARY` |
| 740 | `stderr-bypass` | `print(..., file=sys.stderr)` — config load message written directly to stderr | Evaluate: if this is a user-facing config message, keep on stderr; if it's pipeline-status, route through logger | This site is in `load_config` which is called from both CLI and programmatic paths. Route through logger for programmatic paths; keep stderr for CLI. | M3a | `M3A_CONFIG_LOAD_NOTICE` |

### `megaplan/chain.py` — 17 silent handlers

Chain.py has the largest single-file concentration of silent handlers. They fall into three categories:

#### Category A: JSON/OSError read fallbacks

| Line | Function | Failure Class | Current Behavior | Decision | Milestone | Token |
|---|---|---|---|---|---|---|
| 566 | `load_runtime_policy` | `corrupt-read` | `except json.JSONDecodeError` → `return <empty-collection>` | Add `logger.warning`; keep return value | M3a | `M3A_WARN_CHAIN_POLICY_READ` |
| 632 | `_write_chain_policy_into_plan_meta` | `write-failure` | `except CliError` → `return` | Add `logger.warning`; keep `return` | M3a | `M3A_WARN_CHAIN_POLICY_WRITE` |
| 639 | `_write_chain_policy_into_plan_meta` | `write-failure` | `except (json.JSONDecodeError, OSError)` → `return` | Add `logger.warning`; keep `return` | M3a | `M3A_WARN_CHAIN_META_WRITE` |
| 979 | `_claimed_paths` | `corrupt-read` | `except json.JSONDecodeError` → `continue` | Add `logger.warning`; keep `continue` | M3a | `M3A_WARN_CHAIN_CLAIMED_PATHS` |
| 1574 | `_latest_execute_result` | `corrupt-read` | `except (OSError, json.JSONDecodeError)` → `return None` | Add `logger.warning`; keep `return None` | M3a | `M3A_WARN_EXECUTE_RESULT_READ` |

#### Category B: Git/path operation fallbacks

| Line | Function | Failure Class | Current Behavior | Decision | Milestone | Token |
|---|---|---|---|---|---|---|
| 1001 | `_claimed_nested_repo_paths` | `path-error` | `except (OSError, ValueError)` → `continue` | Add `logger.warning`; keep `continue` | M3a | `M3A_WARN_NESTED_REPO_PATHS` |
| 1021 | `_claimed_root_paths` | `path-error` | `except (OSError, ValueError)` → `continue` | Add `logger.warning`; keep `continue` | M3a | `M3A_WARN_ROOT_PATHS` |
| 1062 | `_dirty_nested_repos_from_claimed_paths` | `path-error` | `except (OSError, ValueError)` → `assign repo.as_posix(...)` | Add `logger.warning`; keep fallback | M3a | `M3A_WARN_DIRTY_NESTED_REPOS` |
| 1098 | `_reset_staged_paths` | `path-error` | `except (OSError, ValueError)` → `continue` | Add `logger.warning`; keep `continue` | M3a | `M3A_WARN_RESET_STAGED` |
| 1131 | `_branch_head` | `git-error` | `except (subprocess.TimeoutExpired, FileNotFoundError, OSError)` → `pass` | Add `logger.warning`; keep `pass` | M3a | `M3A_WARN_BRANCH_HEAD` |
| 1151 | `_remote_branch_head` | `git-error` | `except (subprocess.TimeoutExpired, FileNotFoundError, OSError)` → `pass` | Add `logger.warning`; keep `pass` | M3a | `M3A_WARN_REMOTE_BRANCH_HEAD` |
| 1168 | `_is_worktree_dirty` | `git-error` | `except (subprocess.TimeoutExpired, FileNotFoundError, OSError)` → `return False` | Add `logger.warning`; keep `return False` | M3a | `M3A_WARN_WORKTREE_DIRTY` |
| 1303 | `_commit_and_push_phase` | `path-error` | `except (OSError, ValueError)` → `continue` | Add `logger.warning`; keep `continue` | M3a | `M3A_WARN_COMMIT_PUSH_PATH` |
| 1309 | `_commit_and_push_phase` | `path-error` | `except (OSError, ValueError)` → `continue` | Add `logger.warning`; keep `continue` | M3a | `M3A_WARN_COMMIT_PUSH_PATH2` |

#### Category C: CLI/business-logic fallbacks

| Line | Function | Failure Class | Current Behavior | Decision | Rationale | Milestone | Token |
|---|---|---|---|---|---|---|---|
| 1520 | `_warn_vendor_ignored_for_locked_profile` | `vendor-lock` | `except Exception` → `return` — silently returns when vendor lock warning fails | Add `logger.warning`; keep `return`. **Do not raise in M3a.** | Vendor-lock warning failure is a policy enforcement gap. M3b may change to raise. | M3a | `M3A_WARN_VENDOR_LOCK` |
| 1530 | `_warn_vendor_ignored_for_locked_profile` | `vendor-lock` | `except Exception` → `assign None` — silently assigns None when vendor check fails | Add `logger.warning`; keep `assign None`. **Do not raise in M3a.** | Same rationale as line 1520. | M3a | `M3A_WARN_VENDOR_LOCK_RESOLVE` |
| 1659 | `_recover_blocked_execute_if_tasks_done` | `recovery-fallback` | `except CliError` → `return False` | Add `logger.warning`; keep `return False` | Recovery failure should be visible for pipeline debugging. | M3a | `M3A_WARN_BLOCKED_EXECUTE_RECOVERY` |

### `megaplan/execute/core.py` — 3 silent handlers

| Line | Failure Class | Current Behavior | Decision | Rationale | Milestone | Token |
|---|---|---|---|---|---|---|
| 563 | `write-fallback` | `except Exception` → `assign str(error)` — silently coerces final.md write failure to error string | Add `logger.warning`; keep str coercion | M3b may halt on write failure. M3a only warns. | M3a | `M3A_WARN_FINAL_MD_WRITE` |
| 761 | `snapshot-fallback` | `except Exception` → `assign {}, "snapshot unavailable"` — silently falls back to empty snapshot when git status capture fails | Add `logger.warning`; keep fallback values | Git status snapshot is a best-effort drift analysis input. Empty fallback is safe but the failure must be visible. | M3a | `M3A_WARN_GIT_SNAPSHOT_FALLBACK` |
| 828 | `batch-swallow` | `except Exception` → `continue` — silently skips to next batch on any failure in execute batch processing | Add `logger.warning` with batch context; keep `continue` | Batch processing should be resilient to individual batch failures, but failures must be visible. | M3a | `M3A_WARN_EXECUTE_BATCH_SWALLOW` |

### `megaplan/execute/quality.py` — 1 silent handler

| Line | Failure Class | Current Behavior | Decision | Rationale | Milestone | Token |
|---|---|---|---|---|---|---|
| 355 | `normalize-fallback` | `except ValueError` → `pass` — silently passes on path normalization failure | Add `logger.warning`; keep `pass` | Path normalization failure may indicate malformed execute output; should be visible for quality debugging. | M3a | `M3A_WARN_PATH_NORMALIZE` |

---

## Appendix A: Explicitly Excluded (172 files)

These files are excluded from M3a by policy. They belong to subsystems with their own observability and logging conventions that require separate hardening milestones.

### Exclusion rules

1. `megaplan/agent/**` — agent runtime, tools, gateway, environments (auto-generated / third-party integration surface)
2. `megaplan/cloud/**` — cloud deployment and supervision (external-facing infrastructure)
3. `megaplan/workers/**` — worker implementations: codex, hermes, shannon (worker-specific logging contracts)
4. `megaplan/tests/**` — test suite (test-only code, not production surface)
5. `megaplan/cli.py` — CLI entrypoint (user-facing surface with its own stderr contract)

### Aggregate counts

| Subsystem | File count | Silent handlers | stderr prints |
|---|---|---|---|
| agent/ | ~130 | many | few |
| cloud/ | ~4 | several | none |
| workers/ | ~3 | many | many |
| tests/ | ~3 | several | 1 |
| cli.py | 1 | many | many |

### Examples of excluded patterns

- **agent/**: `except Exception: pass` in tool execution wrappers, retry loops, and API error adapters. Example: agent tool error handlers that translate arbitrary exceptions into structured tool-result dicts.
- **cloud/**: `except Exception: continue` in supervisor health-check loops and deployment status polling.
- **workers/**: `except json.JSONDecodeError: return <empty>` in worker output parsers; `except Exception: pass` in worker lifecycle cleanup.
- **cli.py**: `except CliError: print(..., file=sys.stderr)` in argument parsing and user-facing error reporting.
- **tests/**: `except Exception: pass` in test fixtures and mock setup/teardown.

### Rationale

These surfaces are either:
- **Auto-generated** or heavily templated (agent tools, worker parsers) — changing them requires upstream template changes.
- **External-facing** (cloud, workers, CLI) — their error-reporting contracts are part of their public API.
- **Test-only** — test code silences are intentional for fixture management.
- **Already observable** — CLI already writes to stderr explicitly; workers have their own logging.

Adding M3a warnings here would sweep unrelated surfaces into this milestone, violating SC8 (anti-scope constraint).

### Revisit guidance

- **M3b+**: Agent and worker silent handlers should be audited in a dedicated worker/agent hardening milestone with worker-specific logging conventions.
- **CLI**: CLI error paths should be reviewed in a user-facing error UX milestone, not an internal observability milestone.
- **Cloud**: Cloud deployment error handling should be hardened in a cloud-supervision milestone.
- **Tests**: No action needed; test silences are expected.

---

## Appendix B: Classified Out of M3a (69 files)

These are hand-written core-adjacent files with silent handlers that are **deferred to M3b or later**. They are documented here so the Phase 1 checkpoint is complete, but they will **not** be patched in M3a.

### Classification rationale

Per SD1, M3a scope is limited to the 14 allowlisted core files. All other hand-written code is classified out with the understanding that:

1. The silent handlers are real and warrant attention.
2. Making them loud requires design decisions (logging framework integration, error taxonomy, caller expectations) that belong in M3b.
3. The Phase 1 census must be complete (no `needs_review`) before M3a implementation proceeds.

### Subsystem breakdown with concrete examples

| Subsystem | Files | Count (handlers/prints) | Concrete example | Rationale for deferral |
|---|---|---|---|---|
| `_core/` (state, phase_runtime, user_config, hermes_fanout) | 4 | 9/0 | `state.py:116`: `except ValueError: return None` — silently returns None on invalid timestamp parsing | Core state utilities; changing logging requires understanding full call graph |
| `_pipeline/` (patterns, preflight, registry, resume, step_helpers, steps/human_gate) | 6 | 8/1 | `registry.py:313`: `except ImportError: return None` — silently returns None on module load failure | Pipeline infrastructure; preflight stderr is CLI-adjacent |
| `audits/hermes_vendoring.py` | 1 | 1/0 | Line 121: `except OSError: continue` — skips unreadable files during vendoring audit | Audit tool; separate hardening path |
| `bakeoff/` (handlers, judge, lifecycle, live_status, merge, metrics, worktree) | 7 | 11/2 | `judge.py:192`: `except json.JSONDecodeError: pass` — silently skips corrupt JSON in bakeoff judge | Bakeoff subsystem; has its own error handling conventions |
| `blocker_recovery.py` | 1 | 3/0 | Line 498: `except Exception: assign str(...)` — coerces any quality blocker exception to string | Blocker recovery is a specialized domain with complex failure modes |
| `execute/merge.py` | 1 | 2/0 | Line 100: `except UnicodeDecodeError: assign <fallback>` — silently falls back on encoding errors | Execute subsystem; encoding fallback behavior needs careful design |
| `forms/directors_notes.py` | 1 | 1/0 | Line 54: `except (OSError, ValueError): assign <empty-collection>` — silently returns empty on missing notes | Form rendering; missing notes is normal state |
| `handlers/` (init, review, tickets) | 3 | 2/11 | `review.py:164`: `except (OSError, ValueError): return None` — silently returns None when finalize.json is unreadable | Review/ticket handlers; stderr prints are CLI-adjacent |
| `loop/` (engine, git) | 2 | 3/0 | `engine.py:208`: `except ValueError: continue` — skips unparseable metrics | Loop engine; metric parsing is hot-path |
| `observability/` (doctor, events, introspect, trace) | 4 | 33/2 | `events.py:203`: `except (ValueError, FileNotFoundError): assign <fallback>` — silently falls back in event writer | Observability infrastructure; modifying its own error handling while making other things observable creates recursion risk |
| `orchestration/` (evaluation, feedback, phase_result, prep_research, progress) | 5 | 7/1 | `evaluation.py:81`: `except (ValueError, OSError): pass` — silently passes on path normalization failure | Orchestration layer; evaluation.py is specifically called out by the gate as M3b-deferred |
| `pipelines/` (creative, doc prompts, doc steps) | 3 | 3/0 | `creative/prompts/critique_creative.py:36`: `except (OSError, ValueError): return <empty-collection>` — silently returns empty on missing prior provocations | Pipeline prompt construction; missing prior data is normal on first run |
| `pricing/` (claude, codex, fireworks) | 3 | 4/0 | `claude.py:102`: `except (TypeError, ValueError): return 0.0` — silently returns $0 on cost parse failure | Pricing computation; 0.0 is the safe default for cost accounting |
| `profiles/__init__.py` | 1 | 7/0 | Line 850: `except CliError: assign <empty-collection>` — silently returns empty on profile resolution failure | Profile resolution is hot-path with many callers |
| `prompts/` (execute, feedback, planning, review, review_doc, review_joke, tiebreaker) | 7 | 9/0 | `feedback.py:31`: `except (FileNotFoundError, OSError, json.JSONDecodeError): return None` — silently returns None on unreadable feedback | Prompt construction; missing data is normal first-run state |
| `receipts/` (drift, query, report, schema) | 4 | 4/0 | `drift.py:78`: `except ValueError: return 0` — silently returns 0 on numstat parse failure | Accounting/receipts; parse failures should not block accounting |
| `resident/` (agent_loop, cloud, profile) | 3 | 7/0 | `agent_loop.py:128`: `except asyncio.TimeoutError: assign <empty-collection>` — silently returns empty on tool timeout | Resident subsystem; tool execution has complex async error handling |
| `review/mechanical.py` | 1 | 2/0 | Line 288: `except (OSError, SyntaxError, UnicodeDecodeError): continue` — skips unreadable files in static analysis | Static analysis tool; file read failures are expected during analysis |
| `runtime/` (doc_assembly, key_pool, process, sandbox) | 4 | 14/2 | `process.py:40`: `except (ProcessLookupError, OSError): pass` — silently passes on already-dead process | Runtime infrastructure; process lifecycle has inherent race conditions |
| `store/` (compat, db, identity, multi) | 4 | 12/2 | `multi.py:152`: `except Exception: return None` — silently returns None on backend load failure | Store layer; error propagation across backends needs careful design |
| `tickets/` (core, files, identity, registry) | 4 | 8/0 | `registry.py:54`: `except OSError: return <empty-collection>` — silently returns empty on ticket registry read failure | Ticket management; separate hardening path |

### Deferred M3b items (known required rows)

The following specific sites are **explicitly called out** as needing M3b attention. They are documented here so they are not lost:

| Site | Current Behavior | M3b Action Needed | Risk if not addressed |
|---|---|---|---|
| `_pipeline/executor.py:124` — corrupt state overwrite | `except json.JSONDecodeError: pass` → overwrites corrupt state | Halt on corrupt state instead of overwriting | Data loss: executor silently replaces corrupt state.json |
| `auto.py:1194,1362,1546,1656,1986` — drive() Exception swallows | `except Exception: pass` | Add structured error classification; potentially halt on unrecoverable categories | Unknown failures in auto-pilot loop go completely unnoticed |
| `chain.py:1520,1530` — vendor-lock warnings | `except Exception: return/assign None` | Raise on vendor-lock policy violation | Vendor lock policy silently ignored |
| `chain.py:1659` — blocked execute recovery | `except CliError: return False` | Structured error with recovery path logging | Blocked execution recovery failures invisible |
| `_core/io.py:253` — atomic write failure | `except Exception: pass` | Halt or retry on write failure | Silent data loss on atomic write |
| `execute/core.py:563` — final.md write failure | `except Exception: assign str(error)` | Halt on final.md write failure | Final output silently missing |
| `orchestration/evaluation.py:81,140,171` — path normalization / git status | `except (ValueError, OSError): pass/continue` | Warn + structured fallback | Orchestration silently skips malformed paths |
| `_core/state.py:420,533` — state save failures | `except Exception: assign None / return` | Structured error taxonomy for state persistence | State save failures invisible |
| `observability/events.py:203-434` — event writer failures | Multiple `except ... : pass/assign` | Observability self-monitoring | Event loss invisible to operators |
| `handlers/review.py:164,185` — review marker read failures | `except (OSError, ValueError): return None/return` | Warn + structured fallback | Review state silently missed |

### Revisit guidance

- **M3b should prioritize**: `_pipeline/executor.py:124` (data loss), `_core/io.py:253` (data loss), `chain.py:1520` (policy violation), `auto.py:1194` (unknown failures in main loop).
- **M3b should classify**: Each classified-out file into (a) needs warning, (b) needs control-flow change, (c) acceptable silence.
- **M3b design decisions needed**: Logging framework integration for observability subsystem, error taxonomy for runtime/process, structured fallback for store layer.

---

## Appendix C: Classification Decision Table

Every file with findings was classified using the following decision tree:

1. **Is it in the M3a allowlist?** → `in_scope_core` (14 files)
2. **Is it in an explicitly excluded directory?** (`agent/`, `cloud/`, `workers/`, `tests/`) → `explicitly_excluded` (172 files)
3. **Is it the CLI entrypoint?** (`megaplan/cli.py`) → `explicitly_excluded`
4. **Is it a hand-written core-adjacent file not in the allowlist?** → `classified_out_of_m3a` (69 files)

After classification: **0 files in `needs_review`** ✅

### Allowlist (14 core files)

- `megaplan/handlers/gate.py`
- `megaplan/handlers/critique.py`
- `megaplan/handlers/override.py`
- `megaplan/handlers/verifiability.py`
- `megaplan/handlers/shared.py`
- `megaplan/handlers/finalize.py`
- `megaplan/_pipeline/executor.py`
- `megaplan/_pipeline/faults.py`
- `megaplan/_pipeline/run_cli.py`
- `megaplan/_pipeline/stages/inprocess_step.py`
- `megaplan/auto.py`
- `megaplan/_core/io.py`
- `megaplan/chain.py`
- `megaplan/execute/core.py`
- `megaplan/execute/quality.py`

(Note: The census script has 15 entries including `finalize.py` which has zero findings — it is allowlisted for M3a logger consistency changes per Phase 4.)

---

## Validation

```bash
# Run the census — exit code 0 means needs_review is empty
python scripts/silent_failure_census.py --quiet && echo "PASS: Phase 1 checkpoint satisfied"

# Count classifications
python scripts/silent_failure_census.py --json | python3 -c "
import json, sys
b = json.load(sys.stdin)['buckets']
for k in ['in_scope_core','explicitly_excluded','classified_out_of_m3a','needs_review']:
    print(f'{k}: {len(b.get(k,[]))} files')
"

# Verify grep-stable tokens are unique across the codebase (post-M3a implementation)
rg -l 'M3A_WARN_' megaplan/

# Verify no anti-scope drift
rg -n 'logger\.(warning|error|info)\(' megaplan/handlers/gate.py megaplan/handlers/critique.py megaplan/handlers/override.py
```

---

## Next Steps (M3a Phases 2–4)

With the Phase 1 checkpoint complete (`needs_review` empty, decision table authoritative):

- **Phase 2 (T5)**: Apply event-emission warning changes to `in_scope_core` files — shared helper in `shared.py` + per-file `logger.warning()` calls with grep-stable tokens.
- **Phase 3 (T6)**: Apply missing-vs-corrupt/unreadable read warnings with focused tests. Distinguish: missing files (silent per SD3) vs corrupt/unreadable files (warn with token).
- **Phase 4 (T7)**: Logging consistency — route stderr bypasses through `logging.getLogger("megaplan")`, update `finalize.py`, preserve message text.
- **Phase 5 (T8-T9)**: Focused regression tests, full pytest baseline, census re-validation, guardrail greps.
