# Slot-First M0 Audit 05: Worker Contract Surface

Generated: 2026-05-20T09:33:36Z

## Scope

This audit records the cross-repo worker/orchestrator/Astrid contract surface that M3 must burn down. Mounted repositories were inspected read-only. Missing worktrees are recorded as blocked evidence.

## Repository Availability

Command:
```bash
for p in /workspace/reigh-worker /workspace/reigh-worker-orchestrator /workspace/Astrid /workspace/reigh-worker-fix-contract; do if [ -e "$p" ]; then if git -C "$p" rev-parse --is-inside-work-tree >/dev/null 2>&1; then echo "FOUND $p branch=$(git -C "$p" branch --show-current) head=$(git -C "$p" rev-parse --short HEAD)"; else echo "FOUND $p git=not-a-worktree"; fi; else echo "MISSING $p"; fi; done
```

Output:
```
FOUND /workspace/reigh-worker branch=main head=3bfe7ac
FOUND /workspace/reigh-worker-orchestrator branch=main head=fcec14f
FOUND /workspace/Astrid branch=main head=8741e18
MISSING /workspace/reigh-worker-fix-contract
```

BLOCKED: repo unavailable in harness: `/workspace/reigh-worker-fix-contract`. The required M3 touchpoint remains unverified here: close that worktree or rebase/merge its stale contract code before cutover.

## reigh-worker Required Legacy Search

Command:
```bash
rg -n "parent_generation_id|pair_shot_generation_id|child_generation_id" /workspace/reigh-worker/source /workspace/reigh-worker/scripts
```

Output:
```
/workspace/reigh-worker/scripts/dual_run_compare/oracles.py:162:        "parent_generation_id": None,
/workspace/reigh-worker/scripts/dual_run_compare/oracles.py:163:        "child_generation_id": None,
/workspace/reigh-worker/scripts/dual_run_compare/oracles.py:440:                else observation.get("parent_generation_id") is None and observation.get("child_generation_id") is None
/workspace/reigh-worker/scripts/dual_run_compare/oracles.py:445:            parent_generation_id=observation.get("parent_generation_id"),
/workspace/reigh-worker/scripts/dual_run_compare/oracles.py:446:            child_generation_id=observation.get("child_generation_id"),
/workspace/reigh-worker/source/task_handlers/join/orchestrator.py:330:        parent_generation_id = (
/workspace/reigh-worker/source/task_handlers/join/orchestrator.py:331:            task_params_from_db.get("parent_generation_id")
/workspace/reigh-worker/source/task_handlers/join/orchestrator.py:332:            or orchestrator_payload.get("parent_generation_id")
/workspace/reigh-worker/source/task_handlers/join/orchestrator.py:357:                parent_generation_id=parent_generation_id,
/workspace/reigh-worker/source/task_handlers/join/orchestrator.py:371:                parent_generation_id=parent_generation_id,
/workspace/reigh-worker/source/task_handlers/join/task_builder.py:72:    parent_generation_id: str | None,
/workspace/reigh-worker/source/task_handlers/join/task_builder.py:90:        parent_generation_id: Parent generation ID for variant linking
/workspace/reigh-worker/source/task_handlers/join/task_builder.py:166:        "parent_generation_id": parent_generation_id,
/workspace/reigh-worker/source/task_handlers/join/task_builder.py:207:    parent_generation_id: str | None,
/workspace/reigh-worker/source/task_handlers/join/task_builder.py:227:        parent_generation_id: Parent generation ID for variant linking
/workspace/reigh-worker/source/task_handlers/join/task_builder.py:300:        "parent_generation_id": parent_generation_id,
/workspace/reigh-worker/source/core/db/dependencies/task_dependencies_queries.py:61:    parent_generation_id: str | None = None,
/workspace/reigh-worker/source/core/db/dependencies/task_dependencies_queries.py:62:    child_generation_id: str | None = None,
/workspace/reigh-worker/source/core/db/dependencies/task_dependencies_queries.py:68:        parent_generation_id=parent_generation_id,
/workspace/reigh-worker/source/core/db/dependencies/task_dependencies_queries.py:69:        child_generation_id=child_generation_id,
/workspace/reigh-worker/source/task_handlers/travel/predecessor_resolver.py:37:    parent_generation_id: str | None,
/workspace/reigh-worker/source/task_handlers/travel/predecessor_resolver.py:38:    child_generation_id: str | None,
/workspace/reigh-worker/source/task_handlers/travel/predecessor_resolver.py:44:        parent_generation_id=parent_generation_id,
/workspace/reigh-worker/source/task_handlers/travel/predecessor_resolver.py:45:        child_generation_id=child_generation_id,
/workspace/reigh-worker/source/core/db/task_dependencies.py:348:    parent_generation_id: str | None = None,
/workspace/reigh-worker/source/core/db/task_dependencies.py:356:    2. Generation sibling lookup — for individual segment regens (needs parent_generation_id + child_order)
/workspace/reigh-worker/source/core/db/task_dependencies.py:368:    if parent_generation_id:
/workspace/reigh-worker/source/core/db/task_dependencies.py:369:        payload["parent_generation_id"] = parent_generation_id
/workspace/reigh-worker/source/core/db/task_dependencies.py:411:    parent_generation_id: str | None = None,
/workspace/reigh-worker/source/core/db/task_dependencies.py:412:    child_generation_id: str | None = None,
/workspace/reigh-worker/source/core/db/task_dependencies.py:420:    2. Generation sibling lookup — for individual segment regens (parent_generation_id + child_order)
/workspace/reigh-worker/source/core/db/task_dependencies.py:431:        parent_generation_id=parent_generation_id,
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:293:# - orchestrator_task_id, run_id, parent_generation_id, shot_id, generation_name,
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:297:# - input_image_paths_resolved, input_image_generation_ids, pair_shot_generation_ids,
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:328:        "parent_generation_id",
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:339:        "pair_shot_generation_ids",
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:1855:        raw_pair_shot_generation_ids = orchestrator_payload.get("pair_shot_generation_ids")
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:1856:        pair_shot_generation_ids = raw_pair_shot_generation_ids if isinstance(raw_pair_shot_generation_ids, list) else []
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:1857:        if pair_shot_generation_ids and len(pair_shot_generation_ids) < num_segments:
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:1859:                "[PAIR_SHOT_GENERATION_IDS] Received fewer pair_shot_generation_ids than segments; "
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:1862:                pair_shot_generation_id_count=len(pair_shot_generation_ids),
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2038:            segment_pair_shot_generation_id = None
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2039:            if idx < len(pair_shot_generation_ids):
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2040:                pair_value = pair_shot_generation_ids[idx]
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2042:                    segment_pair_shot_generation_id = pair_value
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2045:                        "[PAIR_SHOT_GENERATION_IDS] Ignoring blank or non-string pair_shot_generation_id entry",
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2048:                        pair_shot_generation_id=pair_value,
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2050:            elif pair_shot_generation_ids:
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2052:                    "[PAIR_SHOT_GENERATION_IDS] Missing pair_shot_generation_id entry for segment payload",
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2068:                **({"pair_shot_generation_id": segment_pair_shot_generation_id} if segment_pair_shot_generation_id else {}),
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2070:                "parent_generation_id": (
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2071:                    task_params_from_db.get("parent_generation_id")
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2072:                    or orchestrator_payload.get("parent_generation_id")
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2073:                    or orchestrator_payload.get("orchestrator_details", {}).get("parent_generation_id")
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2346:                "parent_generation_id": (
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2347:                    task_params_from_db.get("parent_generation_id")
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2348:                    or orchestrator_payload.get("parent_generation_id")
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2349:                    or orchestrator_payload.get("orchestrator_details", {}).get("parent_generation_id")
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2435:                "parent_generation_id": (
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2436:                    task_params_from_db.get("parent_generation_id")
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py:2437:                    or orchestrator_payload.get("parent_generation_id")
/workspace/reigh-worker/source/task_handlers/edit_video_orchestrator.py:620:        parent_generation_id = (
/workspace/reigh-worker/source/task_handlers/edit_video_orchestrator.py:621:            task_params_from_db.get("parent_generation_id")
/workspace/reigh-worker/source/task_handlers/edit_video_orchestrator.py:622:            or orchestrator_payload.get("parent_generation_id")
/workspace/reigh-worker/source/task_handlers/edit_video_orchestrator.py:634:            parent_generation_id=parent_generation_id,
/workspace/reigh-worker/source/core/params/contracts.py:121:    parent_generation_id: Optional[str]
/workspace/reigh-worker/source/task_handlers/travel/guide_builder.py:158:            parent_generation_id=resolve_generation_id(
/workspace/reigh-worker/source/task_handlers/travel/guide_builder.py:159:                "parent_generation_id",
/workspace/reigh-worker/source/task_handlers/travel/guide_builder.py:164:            child_generation_id=resolve_generation_id(
/workspace/reigh-worker/source/task_handlers/travel/guide_builder.py:165:                "child_generation_id",
/workspace/reigh-worker/source/task_handlers/tasks/task_registry.py:538:            parent_generation_id=resolve_generation_id(
/workspace/reigh-worker/source/task_handlers/tasks/task_registry.py:539:                "parent_generation_id",
/workspace/reigh-worker/source/task_handlers/tasks/task_registry.py:544:            child_generation_id=resolve_generation_id(
/workspace/reigh-worker/source/task_handlers/tasks/task_registry.py:545:                "child_generation_id",
```

Worker test search command:
```bash
find /workspace/reigh-worker -name "test_*.py" -o -name "*_test.py" | sort | xargs grep -l "generation_id"
```

Output:
```
/workspace/reigh-worker/scripts/live_test/tests/test_primitives.py
/workspace/reigh-worker/tests/test_join_orchestrator_and_registry.py
/workspace/reigh-worker/tests/test_predecessor_resolver.py
/workspace/reigh-worker/tests/test_task_registry_ic_lora_dedup.py
/workspace/reigh-worker/tests/test_template_routing.py
/workspace/reigh-worker/tests/test_vibecomfy_backend_selection.py
```

Selector-awareness baseline command:
```bash
sed -n '210,240p' /workspace/reigh-worker/source/core/db/task_claim.py
```

Output:
```
    )

    if not edge_url:
        headless_logger.error("[TASK_COUNTS] No edge function URL available")
        return None

    try:
        # Use the configured bearer credential for edge access.
        # The edge endpoint determines how the credential is interpreted.
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }

        worker_backend = parse_worker_backend()
        selector_namespace = _selector_namespace()
        selector_version = _selector_version()
        worker_profile = _worker_profile()
        worker_contract_version = _worker_contract_version()
        payload = {
            "run_type": run_type,
            "include_active": True,
            "worker_backend": worker_backend.value,
            "worker_profile": worker_profile,
            "selector_namespace": selector_namespace,
            "selector_version": selector_version,
            "worker_contract_version": worker_contract_version,
        }

        headless_logger.debug(f"DEBUG check_task_counts_supabase: Calling task-counts at {edge_url}")
        resp = httpx.post(edge_url, json=payload, headers=headers, timeout=10)
```

## reigh-worker-orchestrator Search

Command:
```bash
rg -n "task-counts|claim-next-task|generation_id|pair_shot_generation_id|parent_generation_id|child_generation_id" /workspace/reigh-worker-orchestrator
```

Output:
```
/workspace/reigh-worker-orchestrator/docs/sprint11b-dashboard-evidence.redacted.json:110:      "reason": "No live task-counts claim-suppression response was mechanically verified."
/workspace/reigh-worker-orchestrator/tasks/canary-rollback-orchestrator.md:176:curl --fail-with-body -sS "$SUPABASE_URL/functions/v1/task-counts" \
/workspace/reigh-worker-orchestrator/tasks/canary-rollback-orchestrator.md:186:| tee /tmp/sprint11b-rollback-task-counts.redacted.json
/workspace/reigh-worker-orchestrator/gpu_orchestrator/database.py:155:        Get available task count using the new task-counts endpoint.
/workspace/reigh-worker-orchestrator/gpu_orchestrator/database.py:173:            task_counts_url = f"{supabase_url}/functions/v1/task-counts"
/workspace/reigh-worker-orchestrator/gpu_orchestrator/database.py:210:        Get detailed task count breakdown using the new task-counts endpoint.
/workspace/reigh-worker-orchestrator/gpu_orchestrator/database.py:224:            task_counts_url = f"{supabase_url}/functions/v1/task-counts"
/workspace/reigh-worker-orchestrator/gpu_orchestrator/database.py:289:    # Note: Task claiming is handled by the edge function at /functions/v1/claim-next-task
/workspace/reigh-worker-orchestrator/config/alerts/section11-canary.yaml:115:      source: task-counts.claim_suppression
/workspace/reigh-worker-orchestrator/tests/gpu_orchestrator/test_sprint10_canary_rollback.py:253:                "source_ref": {"kind": "claim-next-task", "path": "system_logs.metadata.claim"},
/workspace/reigh-worker-orchestrator/tests/gpu_orchestrator/test_sprint10_canary_rollback.py:261:                "source_ref": {"kind": "claim-next-task", "path": "system_logs.metadata.claim"},
/workspace/reigh-worker-orchestrator/tests/gpu_orchestrator/test_sprint10_canary_rollback.py:269:                "source_ref": {"kind": "claim-next-task", "path": "system_logs.metadata.claim"},
/workspace/reigh-worker-orchestrator/tests/gpu_orchestrator/test_sprint10_canary_rollback.py:353:        "concurrent_claims": [{"kind": "claim-next-task", "path": "system_logs.metadata.claim"}],
/workspace/reigh-worker-orchestrator/api_orchestrator/task_utils.py:24:        "claim": f"{base_url}/functions/v1/claim-next-task" if base_url else "",
/workspace/reigh-worker-orchestrator/api_orchestrator/task_utils.py:48:    """Count tasks using the new task-counts endpoint."""
/workspace/reigh-worker-orchestrator/api_orchestrator/task_utils.py:51:        task_counts_url = f"{supabase_url}/functions/v1/task-counts"
```

## Standalone Astrid Search

Required command:
```bash
rg -l "generation_id|reigh-data-fetch" /workspace/Astrid | sort
```

Output:
```
/workspace/Astrid/astrid/core/project/cli.py
/workspace/Astrid/astrid/core/reigh/data_provider.py
/workspace/Astrid/astrid/core/reigh/env.py
/workspace/Astrid/astrid/core/reigh/errors.py
/workspace/Astrid/astrid/core/reigh/timeline_io.py
/workspace/Astrid/astrid/packs/builtin/reigh_data/STAGE.md
/workspace/Astrid/astrid/packs/builtin/reigh_data/run.py
/workspace/Astrid/docs/integration_contracts.md
/workspace/Astrid/tests/test_project_cli.py
/workspace/Astrid/tests/test_reigh_data.py
/workspace/Astrid/tests/test_supabase_data_provider.py
```

Line-level command including generated TS camelCase fields:
```bash
rg -n "generation_id|reigh-data-fetch|generationId|variantId" /workspace/Astrid | sort
```

Output:
```
/workspace/Astrid/astrid/core/project/cli.py:314:    """List timelines for a reigh-app project via reigh-data-fetch."""
/workspace/Astrid/astrid/core/project/cli.py:9:``expected_version`` (read from reigh-data-fetch's ``config_version``).
/workspace/Astrid/astrid/core/reigh/data_provider.py:138:            raise TimelineNotFoundError("reigh-data-fetch returned non-object payload")
/workspace/Astrid/astrid/core/reigh/env.py:9:DEFAULT_FUNCTION_NAME = "reigh-data-fetch"
/workspace/Astrid/astrid/core/reigh/errors.py:7:    """Raised when reigh-data-fetch returns no timeline for the requested id."""
/workspace/Astrid/astrid/core/reigh/timeline_io.py:108:            f"reigh-data-fetch did not return timeline {timeline_id}"
/workspace/Astrid/astrid/core/reigh/timeline_io.py:114:            f"reigh-data-fetch row for {timeline_id} has no config object"
/workspace/Astrid/astrid/core/reigh/timeline_io.py:119:            "reigh-data-fetch payload is missing config_version. "
/workspace/Astrid/astrid/core/reigh/timeline_io.py:1:"""Versioned timeline read/write loop against reigh-data-fetch + RPC.
/workspace/Astrid/astrid/core/reigh/timeline_io.py:7:``reigh-data-fetch`` Edge Function, apply a caller-supplied mutator, then call
/workspace/Astrid/astrid/core/reigh/timeline_io.py:80:    """Call ``reigh-data-fetch`` and return ``(timeline_config, config_version)``."""
/workspace/Astrid/astrid/core/reigh/timeline_io.py:90:            f"reigh-data-fetch returned non-object payload for timeline {timeline_id}"
/workspace/Astrid/astrid/core/reigh/timeline_io.py:95:            f"reigh-data-fetch returned no timelines for {timeline_id}"
/workspace/Astrid/astrid/core/task/validator.py:19:InvariantId = Literal[
/workspace/Astrid/astrid/core/task/validator.py:207:    "InvariantId",
/workspace/Astrid/astrid/core/task/validator.py:28:INVARIANTS: tuple[InvariantId, ...] = (
/workspace/Astrid/astrid/core/task/validator.py:41:    def __init__(self, invariant_id: InvariantId, element: str, reason: str) -> None:
/workspace/Astrid/astrid/packs/builtin/reigh_data/STAGE.md:10:directly from Astrid: the canonical read path is the `reigh-data-fetch` Edge
/workspace/Astrid/astrid/packs/builtin/reigh_data/run.py:69:        description="Fetch canonical Reigh project data through the reigh-data-fetch Edge Function."
/workspace/Astrid/astrid/packs/builtin/reigh_data/run.py:75:    parser.add_argument("--api-url", help="Full Edge Function URL. Defaults to env-derived reigh-data-fetch URL.")
/workspace/Astrid/astrid/timeline.py:108:        generationId: str
/workspace/Astrid/astrid/timeline.py:380:        "generationId",
/workspace/Astrid/astrid/timeline.py:381:        "variantId",
/workspace/Astrid/docs/integration_contracts.md:139:- `/Users/peteromalley/Documents/reigh-workspace/reigh-app/supabase/functions/reigh-data-fetch/index.ts`
/workspace/Astrid/docs/integration_contracts.md:327:- T2 must patch `reigh-data-fetch` so `TIMELINES_SELECT` includes
/workspace/Astrid/examples/hype.assets.full.json:13:      "generationId": "gen-main",
/workspace/Astrid/examples/hype.assets.full.json:14:      "variantId": "variant-main",
/workspace/Astrid/examples/hype.assets.full.json:23:      "generationId": "gen-broll",
/workspace/Astrid/examples/hype.assets.full.json:24:      "variantId": "variant-broll",
/workspace/Astrid/examples/hype.assets.full.json:33:      "generationId": "gen-poster",
/workspace/Astrid/examples/hype.assets.full.json:34:      "variantId": "variant-poster",
/workspace/Astrid/remotion/__smoke__/bundle.mjs:27:    'generationId',
/workspace/Astrid/remotion/__smoke__/bundle.mjs:33:    'variantId',
/workspace/Astrid/remotion/src/types.generated.d.ts:184:    generationId: unknown;
/workspace/Astrid/remotion/src/types.generated.d.ts:190:    variantId: unknown;
/workspace/Astrid/remotion/src/types.generated.d.ts:344:export declare const _ASSET_ENTRY_ALLOWED: readonly ["content_sha256", "duration", "etag", "file", "fps", "generationId", "resolution", "thumbnailUrl", "type", "url", "url_expires_at", "variantId"];
/workspace/Astrid/remotion/src/types.generated.d.ts:45:    generationId: unknown;
/workspace/Astrid/remotion/src/types.generated.d.ts:51:    variantId: unknown;
/workspace/Astrid/remotion/src/types.generated.d.ts:62:    generationId: unknown;
/workspace/Astrid/remotion/src/types.generated.d.ts:68:    variantId: unknown;
/workspace/Astrid/remotion/src/types.generated.js:2:export const _ASSET_ENTRY_ALLOWED = ['content_sha256', 'duration', 'etag', 'file', 'fps', 'generationId', 'resolution', 'thumbnailUrl', 'type', 'url', 'url_expires_at', 'variantId'];
/workspace/Astrid/remotion/src/types.generated.ts:208:  generationId: unknown;
/workspace/Astrid/remotion/src/types.generated.ts:214:  variantId: unknown;
/workspace/Astrid/remotion/src/types.generated.ts:387:export const _ASSET_ENTRY_ALLOWED = ['content_sha256', 'duration', 'etag', 'file', 'fps', 'generationId', 'resolution', 'thumbnailUrl', 'type', 'url', 'url_expires_at', 'variantId'] as const;
/workspace/Astrid/remotion/src/types.generated.ts:53:  generationId: unknown;
/workspace/Astrid/remotion/src/types.generated.ts:59:  variantId: unknown;
/workspace/Astrid/remotion/src/types.generated.ts:72:  generationId: unknown;
/workspace/Astrid/remotion/src/types.generated.ts:78:  variantId: unknown;
/workspace/Astrid/tests/test_project_cli.py:117:            return_value="https://x/functions/v1/reigh-data-fetch",
/workspace/Astrid/tests/test_project_cli.py:122:        self.assertEqual(captured[0]["url"], "https://x/functions/v1/reigh-data-fetch")
/workspace/Astrid/tests/test_project_cli.py:188:            return_value="https://x/functions/v1/reigh-data-fetch",
/workspace/Astrid/tests/test_project_cli.py:9:* `list` POSTs to reigh-data-fetch with PAT auth and prints per-timeline rows.
/workspace/Astrid/tests/test_reigh_data.py:42:        api_url="https://example.functions.supabase.co/functions/v1/reigh-data-fetch",
/workspace/Astrid/tests/test_reigh_data.py:48:    assert captured["url"] == "https://example.functions.supabase.co/functions/v1/reigh-data-fetch"
/workspace/Astrid/tests/test_reigh_data.py:65:        == "https://example.supabase.co/functions/v1/reigh-data-fetch"
/workspace/Astrid/tests/test_reigh_data.py:92:            api_url="https://example.functions.supabase.co/functions/v1/reigh-data-fetch",
/workspace/Astrid/tests/test_supabase_data_provider.py:123:                    fetch_url="https://x/functions/v1/reigh-data-fetch",
/workspace/Astrid/tests/test_supabase_data_provider.py:169:            fetch_url="https://example.supabase.co/functions/v1/reigh-data-fetch",
/workspace/Astrid/tests/test_supabase_data_provider.py:35:    """Stand-in for reigh-data-fetch responses."""
/workspace/Astrid/tests/test_supabase_data_provider.py:62:                    fetch_url="https://example.supabase.co/functions/v1/reigh-data-fetch",
/workspace/Astrid/tests/test_supabase_data_provider.py:91:                fetch_url="https://x/functions/v1/reigh-data-fetch",
```

## reigh-app Edge Function Surfaces Called By Sibling Repos

Command:
```bash
rg -n "worker_backend|selector_namespace|pair_shot_generation_id|parent_generation_id|child_generation_id|generation_id|shot_generations|task-counts|claim-next-task|reigh-data-fetch" supabase/functions/claim-next-task supabase/functions/task-counts supabase/functions/reigh-data-fetch supabase/functions/update-shot-pair-prompts supabase/functions/complete_task 2>/dev/null | sort
```

Output:
```
supabase/functions/claim-next-task/index.test.ts:129:    const response = await handler(new Request('https://edge.test/claim-next-task', { method: 'POST' }));
supabase/functions/claim-next-task/index.test.ts:173:    const response = await handler(new Request('https://edge.test/claim-next-task', { method: 'POST' }));
supabase/functions/claim-next-task/index.test.ts:218:    const response = await handler(new Request('https://edge.test/claim-next-task', { method: 'POST' }));
supabase/functions/claim-next-task/index.test.ts:266:    const response = await handler(new Request('https://edge.test/claim-next-task', { method: 'POST' }));
supabase/functions/claim-next-task/index.test.ts:293:    const response = await handler(new Request('https://edge.test/claim-next-task', { method: 'POST' }));
supabase/functions/claim-next-task/index.test.ts:316:    const response = await handler(new Request('https://edge.test/claim-next-task', { method: 'POST' }));
supabase/functions/claim-next-task/index.test.ts:39:describe('claim-next-task edge entrypoint', () => {
supabase/functions/claim-next-task/index.test.ts:64:    const response = await handler(new Request('https://edge.test/claim-next-task', { method: 'POST' }));
supabase/functions/claim-next-task/index.test.ts:74:    const response = await handler(new Request('https://edge.test/claim-next-task', { method: 'POST' }));
supabase/functions/claim-next-task/index.test.ts:97:    const response = await handler(new Request('https://edge.test/claim-next-task', { method: 'POST' }));
supabase/functions/claim-next-task/index.ts:19: * NOTE: For task counts and statistics, use the separate task-counts function.
supabase/functions/claim-next-task/index.ts:21: * POST /functions/v1/claim-next-task
supabase/functions/claim-next-task/index.ts:44:  functionName: "claim-next-task",
supabase/functions/claim-next-task/index.ts:6: * Edge function: claim-next-task
supabase/functions/complete_task/cleanupMaterializedInputs.test.ts:112:      { generation_id: 'gen-a', kind: 'file', target: '/tmp/gen-a.png' },
supabase/functions/complete_task/cleanupMaterializedInputs.test.ts:113:      { generation_id: 'gen-b', kind: 'remote', target: 'objects/gen-b.png' },
supabase/functions/complete_task/cleanupMaterializedInputs.test.ts:126:      { generation_id: 'gen-x', kind: 'unknown', target: 'whatever' } as unknown as never,
supabase/functions/complete_task/cleanupMaterializedInputs.test.ts:127:      { generation_id: 'gen-y', kind: 'remote', target: 'objects/gen-y.png' },
supabase/functions/complete_task/cleanupMaterializedInputs.test.ts:64:      { generation_id: 'gen-1', kind: 'remote', target: 'projects/abc/source.png' },
supabase/functions/complete_task/cleanupMaterializedInputs.test.ts:77:      { generation_id: 'gen-2', kind: 'file', target: '/Users/me/.reigh-local-files/gen-2.png' },
supabase/functions/complete_task/cleanupMaterializedInputs.test.ts:86:      expect.objectContaining({ generation_id: 'gen-2' }),
supabase/functions/complete_task/cleanupMaterializedInputs.test.ts:94:      { generation_id: 'gen-3', kind: 'remote', target: 'projects/abc/dead.png' },
supabase/functions/complete_task/cleanupMaterializedInputs.test.ts:95:      { generation_id: 'gen-4', kind: 'remote', target: 'projects/abc/alive.png' },
supabase/functions/complete_task/cleanupMaterializedInputs.ts:15:    typeof r.generation_id === 'string' &&
supabase/functions/complete_task/cleanupMaterializedInputs.ts:46:        { generation_id: record.generation_id },
supabase/functions/complete_task/completionHelpers.ts:9:  generation_id: string;
supabase/functions/complete_task/generation-child-diagnostics.test.ts:14:        pair_shot_generation_ids: ['pair-0', 'pair-1'],
supabase/functions/complete_task/generation-child-diagnostics.ts:29:  const pairShotGenIds = Array.isArray(orchestratorDetails.pair_shot_generation_ids)
supabase/functions/complete_task/generation-child-diagnostics.ts:30:    ? orchestratorDetails.pair_shot_generation_ids
supabase/functions/complete_task/generation-child.test.ts:138:        parent_generation_id: 'parent-1',
supabase/functions/complete_task/generation-child.test.ts:208:        params: { pair_shot_generation_id: 'pair-shot-1' },
supabase/functions/complete_task/generation-child.test.ts:278:    expect(generationsQuery.eq).toHaveBeenCalledWith('pair_shot_generation_id', 'pair-shot-1');
supabase/functions/complete_task/generation-child.test.ts:299:    expect(generationsQuery.eq).toHaveBeenCalledWith('pair_shot_generation_id', 'pair-shot-missing');
supabase/functions/complete_task/generation-child.ts:101:        existing_generation_id: existingGenId,
supabase/functions/complete_task/generation-child.ts:120:          pair_shot_generation_id: pairShotGenId,
supabase/functions/complete_task/generation-child.ts:159:    .eq('generation_id', parentGenerationId);
supabase/functions/complete_task/generation-child.ts:182:// Note: (parent_generation_id, child_order) and (parent_generation_id, pair_shot_generation_id)
supabase/functions/complete_task/generation-child.ts:184:// pair_shot_generation_id is the durable position key. We use order(created_at DESC)+limit(1)
supabase/functions/complete_task/generation-child.ts:197:      .eq('parent_generation_id', parentGenerationId)
supabase/functions/complete_task/generation-child.ts:199:      .eq('pair_shot_generation_id', pairShotGenId)
supabase/functions/complete_task/generation-child.ts:214:      .eq('parent_generation_id', parentGenerationId)
supabase/functions/complete_task/generation-child.ts:246:  if (pairShotGenerationId && !generationParams.pair_shot_generation_id) {
supabase/functions/complete_task/generation-child.ts:247:    generationParams = { ...generationParams, pair_shot_generation_id: pairShotGenerationId };
supabase/functions/complete_task/generation-child.ts:272:    generation_id: newGenerationId,
supabase/functions/complete_task/generation-child.ts:273:    parent_generation_id: parentGenerationId,
supabase/functions/complete_task/generation-child.ts:277:    pair_shot_generation_id: pairShotGenerationId || null,
supabase/functions/complete_task/generation-child.ts:280:  // Verify pair_shot_generation_id still exists before inserting (FK constraint check)
supabase/functions/complete_task/generation-child.ts:285:      .from('shot_generations')
supabase/functions/complete_task/generation-child.ts:309:    parent_generation_id: parentGenerationId,
supabase/functions/complete_task/generation-child.ts:312:    // Store pair_shot_generation_id as proper column (not just in params)
supabase/functions/complete_task/generation-child.ts:315:    pair_shot_generation_id: validatedPairShotGenId,
supabase/functions/complete_task/generation-child.ts:46:      parent_generation_id: parentGenerationId,
supabase/functions/complete_task/generation-child.ts:52:      parent_generation_id: parentGenerationId,
supabase/functions/complete_task/generation-child.ts:70:    parent_generation_id: parentGenerationId,
supabase/functions/complete_task/generation-core.test.ts:140:        generation_id: 'gen-1',
supabase/functions/complete_task/generation-core.test.ts:169:      p_generation_id: 'gen-1',
supabase/functions/complete_task/generation-core.ts:178:    .eq('parent_generation_id', parentGenerationId)
supabase/functions/complete_task/generation-core.ts:209:    generation_id: generationId,
supabase/functions/complete_task/generation-core.ts:249:      p_generation_id: generationId,
supabase/functions/complete_task/generation-handlers.test.ts:109:  it('creates a stitched parent variant when parent_generation_id is provided directly', async () => {
supabase/functions/complete_task/generation-handlers.test.ts:120:          parent_generation_id: 'parent-1',
supabase/functions/complete_task/generation-handlers.test.ts:181:      generation_id: 'gen-source',
supabase/functions/complete_task/generation-handlers.test.ts:227:        generation_id: string;
supabase/functions/complete_task/generation-handlers.test.ts:239:        generation_id: 'gen-standalone',
supabase/functions/complete_task/generation-handlers.test.ts:254:      parent_generation_id: 'parent-1',
supabase/functions/complete_task/generation-handlers.ts:117:          source_generation_id: basedOnGenerationId,
supabase/functions/complete_task/generation-handlers.ts:123:      generation_id: basedOnGenerationId,
supabase/functions/complete_task/generation-handlers.ts:138:        source_generation_id: basedOnGenerationId,
supabase/functions/complete_task/generation-handlers.ts:163:  const directParentGenerationId = typeof taskData.params?.parent_generation_id === 'string'
supabase/functions/complete_task/generation-handlers.ts:164:    ? taskData.params.parent_generation_id
supabase/functions/complete_task/generation-handlers.ts:182:        ...(directParentGenerationId ? { parent_generation_id: directParentGenerationId } : {}),
supabase/functions/complete_task/generation-handlers.ts:189:    parent_generation_id: parentGen.id,
supabase/functions/complete_task/generation-handlers.ts:253:          source_generation_id: String(basedOnId),
supabase/functions/complete_task/generation-handlers.ts:267: * Used by: individual_travel_segment (when child_generation_id is present)
supabase/functions/complete_task/generation-handlers.ts:278:  logger?.info("individual_travel_segment with child_generation_id", {
supabase/functions/complete_task/generation-handlers.ts:280:    child_generation_id: childGenId,
supabase/functions/complete_task/generation-handlers.ts:298:        child_generation_id: childGenId,
supabase/functions/complete_task/generation-handlers.ts:304:  // Extract pair_shot_generation_id from nested locations if not at top level
supabase/functions/complete_task/generation-handlers.ts:305:  const pairShotGenerationId = taskData.params?.pair_shot_generation_id ||
supabase/functions/complete_task/generation-handlers.ts:306:                                taskData.params?.individual_segment_params?.pair_shot_generation_id;
supabase/functions/complete_task/generation-handlers.ts:313:    ...(pairShotGenerationId && { pair_shot_generation_id: pairShotGenerationId }),
supabase/functions/complete_task/generation-handlers.ts:318:    childGen.parent_generation_id,
supabase/functions/complete_task/generation-handlers.ts:389:    generation_id: newGenerationId,
supabase/functions/complete_task/generation-handlers.ts:403:    parent_generation_id: null,
supabase/functions/complete_task/generation-handlers.ts:428:      generation_id: newGeneration.id,
supabase/functions/complete_task/generation-handlers.ts:79:          source_generation_id: basedOnGenerationId,
supabase/functions/complete_task/generation-parent.ts:123:              parent_generation_id: String(ensuredParentId),
supabase/functions/complete_task/generation-parent.ts:181:        parent_generation_id: parentGenId,
supabase/functions/complete_task/generation-parent.ts:225:        parent_generation_id: parentGenId,
supabase/functions/complete_task/generation-parent.ts:239: * 1. individual_travel_segment with child_generation_id (SPECIAL CASE 1a)
supabase/functions/complete_task/generation-parent.ts:253:    childGeneration?: { parent_generation_id: string | null; is_child: boolean };
supabase/functions/complete_task/generation-parent.ts:264:  const parentId = options.childGeneration?.parent_generation_id || options.parentGenerationId;
supabase/functions/complete_task/generation-parent.ts:275:        .eq('parent_generation_id', parentId)
supabase/functions/complete_task/generation-parent.ts:27:    // Check if orchestrator already specifies a parent_generation_id
supabase/functions/complete_task/generation-parent.ts:40:    // Check for parent_generation_id in orchestrator params
supabase/functions/complete_task/generation-parent.ts:47:    const parentGenId = orchestrationContract?.parent_generation_id ||
supabase/functions/complete_task/generation-parent.ts:48:                        orchTask?.params?.parent_generation_id ||
supabase/functions/complete_task/generation-parent.ts:49:                        orchTask?.params?.orchestrator_details?.parent_generation_id ||
supabase/functions/complete_task/generation-parent.ts:50:                        segmentParams?.orchestration_contract?.parent_generation_id ||
supabase/functions/complete_task/generation-parent.ts:51:                        segmentParams?.full_orchestrator_payload?.parent_generation_id;
supabase/functions/complete_task/generation-parent.ts:71:          parent_generation_id: String(parentGenId),
supabase/functions/complete_task/generation-parent.ts:83:    // Fall back to the canonical shot parent for legacy tasks that might be missing parent_generation_id.
supabase/functions/complete_task/generation.ts:230: * 3. Variant on child: child_generation_id present → variant on existing child
supabase/functions/complete_task/generation.ts:232: * 5. Child generation: parent_generation_id present → child under parent
supabase/functions/complete_task/generation.ts:260:    child_generation_id: routeParams.childGenerationId,
supabase/functions/complete_task/generation.ts:261:    parent_generation_id: routeParams.parentGenerationId,
supabase/functions/complete_task/generation.ts:384:    existing_generation_id: existingGeneration.id,
supabase/functions/complete_task/generation.ts:424:        existing_generation_id: existingGeneration.id,
supabase/functions/complete_task/generation.ts:431:    generation_id: existingGeneration.id,
supabase/functions/complete_task/generation.ts:54:  generation_id: string;
supabase/functions/complete_task/handler.test.ts:558:      generation_id: 'gen-1',
supabase/functions/complete_task/handler.test.ts:570:      anchor_generation_id: 'gen-source-1',
supabase/functions/complete_task/handler.test.ts:601:        generation_id: 'gen-1',
supabase/functions/complete_task/handler.test.ts:703:        generation_id: 'gen-1',
supabase/functions/complete_task/handler.test.ts:786:        generation_id: 'gen-1',
supabase/functions/complete_task/handler.ts:117:    generation_id: options.generationId,
supabase/functions/complete_task/handler.ts:349:                generation_id: generationId,
supabase/functions/complete_task/handler.ts:368:                    generation_id: generationId,
supabase/functions/complete_task/handler.ts:378:                    generation_id: generationId,
supabase/functions/complete_task/handler.ts:388:                  generation_id: generationId,
supabase/functions/complete_task/handler.ts:422:                generation_id: generationId,
supabase/functions/complete_task/handler.ts:586:      generation_id: createdGenerationId,
supabase/functions/complete_task/placement.test.ts:150:        generation_id: "gen-placed-1",
supabase/functions/complete_task/placement.test.ts:203:        generation_id: "gen-placed-1",
supabase/functions/complete_task/placement.test.ts:271:        generation_id: "gen-placed-1",
supabase/functions/complete_task/placement.test.ts:62:        anchor_generation_id: "gen-source-1",
supabase/functions/complete_task/placement.test.ts:70:        generation_id: "gen-placed-1",
supabase/functions/complete_task/placement.ts:115:  const anchorGenerationId = asTrimmedString(placementIntent.anchor_generation_id) ?? undefined;
supabase/functions/complete_task/placement.ts:121:    ...(anchorGenerationId ? { anchor_generation_id: anchorGenerationId } : {}),
supabase/functions/complete_task/placement.ts:76:    generationId: completionAssetRef.generation_id,
supabase/functions/complete_task/taskParamNormalizer.test.ts:15:            pair_shot_generation_ids: ['pair-0', 'pair-1', 'pair-2'],
supabase/functions/complete_task/taskParamNormalizer.test.ts:16:            input_image_generation_ids: ['img-a', 'img-b', 'img-c', 'img-d'],
supabase/functions/complete_task/taskParamNormalizer.test.ts:28:    expect(normalized.params.start_image_generation_id).toBe('img-b');
supabase/functions/complete_task/taskParamNormalizer.test.ts:29:    expect(normalized.params.end_image_generation_id).toBe('img-c');
supabase/functions/complete_task/taskParamNormalizer.test.ts:31:    // pair_shot_generation_id is no longer synthesized from orchestrator array by index.
supabase/functions/complete_task/taskParamNormalizer.test.ts:36:  it('uses direct pair_shot_generation_id param over orchestrator array', () => {
supabase/functions/complete_task/taskParamNormalizer.test.ts:41:          pair_shot_generation_id: 'direct-pair-id',
supabase/functions/complete_task/taskParamNormalizer.test.ts:43:            pair_shot_generation_ids: ['pair-0', 'pair-1', 'pair-2'],
supabase/functions/complete_task/taskParamNormalizer.ts:59:  const startImageGenId = extractFromArray(orchestratorDetails.input_image_generation_ids, segmentIndex);
supabase/functions/complete_task/taskParamNormalizer.ts:61:    nextParams.start_image_generation_id = startImageGenId;
supabase/functions/complete_task/taskParamNormalizer.ts:64:  const endImageGenId = extractFromArray(orchestratorDetails.input_image_generation_ids, segmentIndex + 1);
supabase/functions/complete_task/taskParamNormalizer.ts:66:    nextParams.end_image_generation_id = endImageGenId;
supabase/functions/complete_task/taskParamNormalizer.ts:98:    toStringOrNull(normalizedParams.pair_shot_generation_id) ??
supabase/functions/complete_task/taskParamNormalizer.ts:99:    toStringOrNull(individualSegmentParams.pair_shot_generation_id);
supabase/functions/reigh-data-fetch/index.test.ts:108:describe("reigh-data-fetch edge entrypoint", () => {
supabase/functions/reigh-data-fetch/index.test.ts:136:      generation_id: "gen-1",
supabase/functions/reigh-data-fetch/index.test.ts:159:      generation_id: "gen-2",
supabase/functions/reigh-data-fetch/index.test.ts:179:      generation_id: "gen-3",
supabase/functions/reigh-data-fetch/index.test.ts:222:      parent_generation_id: null,
supabase/functions/reigh-data-fetch/index.test.ts:269:          shot_generations: { data: shotGenerationRows, error: null },
supabase/functions/reigh-data-fetch/index.test.ts:284:      generation_id: "gen-1",
supabase/functions/reigh-data-fetch/index.test.ts:286:      shot_generation_id: "sg-1",
supabase/functions/reigh-data-fetch/index.test.ts:327:      parent_generation_id: undefined,
supabase/functions/reigh-data-fetch/index.test.ts:340:    await handler(new Request("https://edge.test/reigh-data-fetch", { method: "POST" }));
supabase/functions/reigh-data-fetch/index.test.ts:345:        functionName: "reigh-data-fetch",
supabase/functions/reigh-data-fetch/index.test.ts:370:    const response = await handler(new Request("https://edge.test/reigh-data-fetch", { method: "POST" }));
supabase/functions/reigh-data-fetch/index.test.ts:388:    const response = await handler(new Request("https://edge.test/reigh-data-fetch", { method: "POST" }));
supabase/functions/reigh-data-fetch/index.test.ts:408:    const response = await handler(new Request("https://edge.test/reigh-data-fetch", { method: "POST" }));
supabase/functions/reigh-data-fetch/index.test.ts:426:      shot_generations: { data: shotGenerationRows, error: null },
supabase/functions/reigh-data-fetch/index.test.ts:447:    const response = await handler(new Request("https://edge.test/reigh-data-fetch", { method: "POST" }));
supabase/functions/reigh-data-fetch/index.test.ts:556:    expect(supabase.calls.shot_generations).toContainEqual(["in", "shot_id", [shotId]]);
supabase/functions/reigh-data-fetch/index.test.ts:557:    expect(supabase.calls.shot_generations).toContainEqual([
supabase/functions/reigh-data-fetch/index.ts:126:  parent_generation_id?: string | null;
supabase/functions/reigh-data-fetch/index.ts:133:  generation_id?: string;
supabase/functions/reigh-data-fetch/index.ts:142:  generation_id: string;
supabase/functions/reigh-data-fetch/index.ts:144:  shot_generation_id: string;
supabase/functions/reigh-data-fetch/index.ts:17:  generation_id,
supabase/functions/reigh-data-fetch/index.ts:19:  generation:generations!shot_generations_generation_id_generations_id_fk (
supabase/functions/reigh-data-fetch/index.ts:319:    parent_generation_id: item.parent_generation_id ?? undefined,
supabase/functions/reigh-data-fetch/index.ts:365:    generation_id: gen.id,
supabase/functions/reigh-data-fetch/index.ts:367:    shot_generation_id: sg.id,
supabase/functions/reigh-data-fetch/index.ts:395:  return new Set(rows.map((row) => row.generation_id).filter(Boolean)).size;
supabase/functions/reigh-data-fetch/index.ts:402:      .map((row) => row.generation_id)
supabase/functions/reigh-data-fetch/index.ts:522:    .from("shot_generations")
supabase/functions/reigh-data-fetch/index.ts:575:    functionName: "reigh-data-fetch",
supabase/functions/reigh-data-fetch/index.ts:60:  parent_generation_id,
supabase/functions/task-counts/index.test.ts:209:describe('task-counts edge entrypoint', () => {
supabase/functions/task-counts/index.test.ts:237:    const response = await handler(new Request('https://edge.test/task-counts', { method: 'POST' }));
supabase/functions/task-counts/index.test.ts:245:    const response = await handler(new Request('https://edge.test/task-counts', { method: 'POST' }));
supabase/functions/task-counts/index.test.ts:279:    const response = await handler(new Request('https://edge.test/task-counts', { method: 'POST' }));
supabase/functions/task-counts/index.ts:124:    functionName: "task-counts",
supabase/functions/task-counts/index.ts:67: * Edge function: task-counts
supabase/functions/task-counts/index.ts:75: * POST /functions/v1/task-counts
supabase/functions/update-shot-pair-prompts/index.ts:101:    .from("shot_generations")
supabase/functions/update-shot-pair-prompts/index.ts:104:      generation_id,
supabase/functions/update-shot-pair-prompts/index.ts:107:      generation:generations!shot_generations_generation_id_generations_id_fk(
supabase/functions/update-shot-pair-prompts/index.ts:11: * Updates the shot_generations.metadata.enhanced_prompt field for all positioned
supabase/functions/update-shot-pair-prompts/index.ts:120:    logger.error("Error fetching shot_generations", {
supabase/functions/update-shot-pair-prompts/index.ts:128:    logger.warn("No shot_generations found for shot", { shot_id });
supabase/functions/update-shot-pair-prompts/index.ts:146:  logger.info("Found shot_generations", {
supabase/functions/update-shot-pair-prompts/index.ts:207:      .from("shot_generations")
supabase/functions/update-shot-pair-prompts/index.ts:27: * - 200 OK with updated shot_generations count
supabase/functions/update-shot-pair-prompts/index.ts:99:  // Get all shot_generations for this shot, filtering for images with timeline_frame
```

## M3 Burn-Down Table

| Repo | File/surface | Current contract | M3 action |
| --- | --- | --- | --- |
| reigh-worker | `/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py` | Travel orchestration payload creates segment `pair_shot_generation_id` and parent IDs; calls `update-shot-pair-prompts`. | M3 rewrite child task payloads to slot/attempt contract and update edge endpoint usage. |
| reigh-worker | `/workspace/reigh-worker/source/task_handlers/edit_video_orchestrator.py` | Reads and forwards `parent_generation_id` for edit-video predecessor resolution. | M3 replace parent-generation contract with attempt/slot ancestry. |
| reigh-worker | `/workspace/reigh-worker/source/task_handlers/join/orchestrator.py` | Reads and forwards `parent_generation_id` into join dependencies. | M3 replace with slot/attempt join contract. |
| reigh-worker | `/workspace/reigh-worker/source/task_handlers/join/task_builder.py` | Builds task payload with `parent_generation_id`. | M3 replace task-builder schema. |
| reigh-worker | `/workspace/reigh-worker/source/core/db/task_dependencies.py` | Generation sibling dependency lookup uses parent/child generation IDs. | M3 replace dependency lookup with slot/attempt/task relationship. |
| reigh-worker | `/workspace/reigh-worker/source/core/db/dependencies/task_dependencies_queries.py` | Query wrapper exposes parent/child generation IDs. | M3 replace query wrapper contract. |
| reigh-worker | `/workspace/reigh-worker/source/task_handlers/tasks/task_registry.py` | Registry resolves parent/child generation IDs from task params. | M3 update registry contracts. |
| reigh-worker | `/workspace/reigh-worker/source/core/params/contracts.py` | Typed params include `parent_generation_id`. | M3 update shared param contract. |
| reigh-worker | `/workspace/reigh-worker/source/task_handlers/travel/predecessor_resolver.py` | Predecessor resolver accepts parent/child generation IDs. | M3 replace predecessor resolver inputs. |
| reigh-worker | `/workspace/reigh-worker/scripts/live_test/completion_poller.py` | Known required touchpoint absent from current required rg output but retained from brief as M3 verification target. | M3 inspect manually during worker migration. |
| reigh-worker-orchestrator | `/workspace/reigh-worker-orchestrator/gpu_orchestrator/database.py` | Calls `task-counts` endpoint. | M3 ensure endpoint payload/response uses selector and slot-first task contract. |
| reigh-worker-orchestrator | `/workspace/reigh-worker-orchestrator/api_orchestrator/task_utils.py` | Calls `task-counts` and `claim-next-task` endpoints. | M3 ensure endpoint payload/response uses selector and slot-first task contract. |
| Astrid | `/workspace/Astrid/astrid/core/reigh/data_provider.py` | Calls `reigh-data-fetch` canonical data endpoint. | M3 update data provider after reigh-data-fetch emits slot-first payload. |
| Astrid | `/workspace/Astrid/remotion/src/types.generated.ts` | Generated TS includes `generationId`/`variantId` asset entry fields. | M3 regenerate types from slot-first schema. |

## Required Unverified/Missing Touchpoints

- `/workspace/reigh-worker-fix-contract`: BLOCKED: repo unavailable in harness. M3 must close, delete, or rebase this worktree before cutover.
- Historical `reigh-app-cloud-chain`: BLOCKED in T2. M4 must rescan sibling worktrees before zero-ref cutover.
- `/workspace/reigh-worker/scripts/live_test/completion_poller.py`: preserved as a required M3 review target from the brief even though the exact required rg did not hit it in this checkout.

## Contract Decisions For Later Milestones

- M3 owns all worker, orchestrator, and standalone Astrid cross-repo payload changes. M0 only records the surface.
- `claim-next-task` and `task-counts` selector-awareness exists in the current worker baseline; do not regress `worker_backend` or `selector_namespace` while replacing legacy generation IDs.
- `complete_task`, `reigh-data-fetch`, and `update-shot-pair-prompts` are reigh-app edge surfaces that still expose generation-shaped identifiers. M3 must rewrite them with the worker changes, not after.
