// deno-lint-ignore-file
import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { bootstrapEdgeHandler, NO_SESSION_RUNTIME_OPTIONS } from "../_shared/edgeHandler.ts";

declare const Deno: { env: { get: (key: string) => string | undefined } };

const LOG_PREFIX = "[ROUTE-CONTRACT-SENTINEL]";

// Layer 4 sentinel: classify queue + worker state each minute and page on
// persistent UNCLAIMABLE_WORK / WORKERS_STUCK_INITIALIZING. Invoked once per
// minute by the pg_cron job 'route-contract-sentinel' scheduled in migration
// 20260513120300_sentinel_infra.sql.

type SentinelState =
  | "OK"
  | "NO_WORK"
  | "UNCLAIMABLE_WORK"
  | "NO_READY_WORKERS"
  | "WORKERS_STUCK_INITIALIZING";

const PAGE_AFTER_CONSECUTIVE = 5;
const PAUSE_SCALING_MINUTES = 30;
const WORKER_INITIALIZING_STUCK_MINUTES = 30;
const DEFAULT_POOL = "production";

interface TaskRow {
  id: string;
  task_type: string | null;
  status: string;
  route_key: string | null;
  selector_namespace: string | null;
  selected_backend: string | null;
  params: Record<string, unknown> | null;
  created_at: string | null;
}

interface WorkerRow {
  id: string;
  status: string | null;
  last_heartbeat: string | null;
  metadata: Record<string, unknown> | null;
}

interface ClaimDecisionRow {
  eligible: boolean | null;
  decision_reason: string | null;
}

serve(async (req) => {
  const bootstrap = await bootstrapEdgeHandler(req, {
    functionName: "route-contract-sentinel",
    logPrefix: LOG_PREFIX,
    method: "POST",
    parseBody: "none",
    auth: {
      required: true,
      requireServiceRole: true,
    },
    ...NO_SESSION_RUNTIME_OPTIONS,
  });
  if (!bootstrap.ok) {
    return bootstrap.response;
  }

  const { supabaseAdmin, logger } = bootstrap.value;
  const webhookUrl = Deno.env.get("SENTINEL_WEBHOOK_URL");

  try {
    // Direct task query: include orchestrator types (the breakdown RPC excludes
    // them, which is what blinded the orchestrator's lifecycle safety net).
    const queuedQuery = await supabaseAdmin
      .from("tasks")
      .select("id, task_type, status, route_key, selector_namespace, selected_backend, params, created_at")
      .eq("status", "Queued")
      .limit(500);

    if (queuedQuery.error) {
      logger.error("Failed to load queued tasks", { error: queuedQuery.error.message });
      return new Response(JSON.stringify({ error: "queue_query_failed" }), { status: 500 });
    }
    const queuedTasks = (queuedQuery.data ?? []) as TaskRow[];

    const workersQuery = await supabaseAdmin
      .from("workers")
      .select("id, status, last_heartbeat, metadata")
      .in("status", ["active", "spawning"])
      .limit(500);

    if (workersQuery.error) {
      logger.error("Failed to load workers", { error: workersQuery.error.message });
      return new Response(JSON.stringify({ error: "workers_query_failed" }), { status: 500 });
    }
    const workers = (workersQuery.data ?? []) as WorkerRow[];

    const nonOrchestrator = queuedTasks.filter(
      (t) => typeof t.task_type === "string" && !t.task_type.endsWith("_orchestrator"),
    );

    const readyWorkers = workers.filter(
      (w) => w.status === "active" && (w.metadata?.ready_for_tasks === true),
    );

    const now = Date.now();
    const stuckInitializing = workers.filter((w) => {
      if (w.status !== "spawning" && w.metadata?.ready_for_tasks !== true) {
        const hb = w.last_heartbeat ? Date.parse(w.last_heartbeat) : NaN;
        if (Number.isFinite(hb) && now - hb > WORKER_INITIALIZING_STUCK_MINUTES * 60_000) {
          return true;
        }
      }
      if (w.status === "spawning") {
        const hb = w.last_heartbeat ? Date.parse(w.last_heartbeat) : NaN;
        if (!Number.isFinite(hb)) {
          // No heartbeat yet — treat as stuck only if metadata.started_at is old.
          const startedAt = typeof w.metadata?.started_at === "string"
            ? Date.parse(w.metadata.started_at as string)
            : NaN;
          if (Number.isFinite(startedAt) && now - startedAt > WORKER_INITIALIZING_STUCK_MINUTES * 60_000) {
            return true;
          }
          return false;
        }
        return now - hb > WORKER_INITIALIZING_STUCK_MINUTES * 60_000;
      }
      return false;
    });

    // For each queued non-orchestrator task with a route_key + selected_backend
    // (or both backends if NULL), probe route_backend_claim_decision and count
    // the unclaimable ones. Cap probes at 25 to keep tick latency bounded.
    const probeBudget = 25;
    let unclaimableCount = 0;
    const unclaimableSample: { id: string; route_key: string | null; reasons: string[] }[] = [];

    const probeTargets = nonOrchestrator.slice(0, probeBudget);
    for (const t of probeTargets) {
      if (!t.route_key) {
        unclaimableCount += 1;
        if (unclaimableSample.length < 5) {
          unclaimableSample.push({ id: t.id, route_key: null, reasons: ["route_key_null"] });
        }
        continue;
      }
      const namespace = t.selector_namespace ?? "production";
      const backendsToProbe = t.selected_backend ? [t.selected_backend] : ["wgp", "vibecomfy"];
      const reasons: string[] = [];
      let eligible = false;

      for (const backend of backendsToProbe) {
        const { data, error } = await supabaseAdmin.rpc("route_backend_claim_decision", {
          p_selector_namespace: namespace,
          p_route_key: t.route_key,
          p_worker_backend: backend,
        });
        if (error) {
          reasons.push(`${backend}: rpc_error:${error.message}`);
          continue;
        }
        const row = Array.isArray(data) && data.length > 0 ? (data[0] as ClaimDecisionRow) : null;
        if (row?.eligible === true) {
          eligible = true;
          break;
        }
        reasons.push(`${backend}: ${row?.decision_reason ?? "unknown"}`);
      }

      if (!eligible) {
        unclaimableCount += 1;
        if (unclaimableSample.length < 5) {
          unclaimableSample.push({ id: t.id, route_key: t.route_key, reasons });
        }
      }
    }

    let state: SentinelState;
    if (nonOrchestrator.length === 0) {
      state = "NO_WORK";
    } else if (unclaimableCount > 0) {
      state = "UNCLAIMABLE_WORK";
    } else if (stuckInitializing.length > 0) {
      state = "WORKERS_STUCK_INITIALIZING";
    } else if (readyWorkers.length === 0) {
      state = "NO_READY_WORKERS";
    } else {
      state = "OK";
    }

    const detail = {
      queued_total: queuedTasks.length,
      queued_non_orchestrator: nonOrchestrator.length,
      workers_active: workers.filter((w) => w.status === "active").length,
      workers_spawning: workers.filter((w) => w.status === "spawning").length,
      workers_ready: readyWorkers.length,
      workers_stuck_initializing: stuckInitializing.length,
      stuck_worker_ids: stuckInitializing.slice(0, 5).map((w) => w.id),
      unclaimable_probed: probeTargets.length,
      unclaimable_count: unclaimableCount,
      unclaimable_sample: unclaimableSample,
    };

    const insertResult = await supabaseAdmin
      .from("sentinel_ticks")
      .insert({ state, detail });
    if (insertResult.error) {
      logger.error("Failed to record sentinel tick", { error: insertResult.error.message });
    }

    // Check the last PAGE_AFTER_CONSECUTIVE ticks (newest first). Page if the
    // current state matches one of the alarm states AND every recent tick
    // (including this one) shows the same alarm state. Counting "5 consecutive"
    // means 5 recorded ticks; this tick is the 5th if 4 prior ticks already
    // matched.
    const alarmStates: SentinelState[] = ["UNCLAIMABLE_WORK", "WORKERS_STUCK_INITIALIZING"];
    let paged = false;
    if (alarmStates.includes(state)) {
      const recentQuery = await supabaseAdmin
        .from("sentinel_ticks")
        .select("ts, state")
        .order("ts", { ascending: false })
        .limit(PAGE_AFTER_CONSECUTIVE);

      const recent = (recentQuery.data ?? []) as { ts: string; state: string }[];
      const allMatch =
        recent.length >= PAGE_AFTER_CONSECUTIVE &&
        recent.every((r) => r.state === state);

      if (allMatch && webhookUrl) {
        const summary =
          state === "UNCLAIMABLE_WORK"
            ? `${unclaimableCount}/${probeTargets.length} probed queued tasks unclaimable`
            : `${stuckInitializing.length} worker(s) stuck initializing for >${WORKER_INITIALIZING_STUCK_MINUTES}m`;

        try {
          const webhookRes = await fetch(webhookUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              text: `[reigh sentinel] ${state} sustained for ${PAGE_AFTER_CONSECUTIVE} consecutive ticks — ${summary}`,
              state,
              detail,
            }),
          });
          if (!webhookRes.ok) {
            logger.warn("Sentinel webhook returned non-2xx", {
              status: webhookRes.status,
            });
          }
          paged = true;
        } catch (webhookErr) {
          logger.error("Sentinel webhook POST failed", {
            error: webhookErr instanceof Error ? webhookErr.message : String(webhookErr),
          });
        }

        const until = new Date(now + PAUSE_SCALING_MINUTES * 60_000).toISOString();
        const upsertResult = await supabaseAdmin
          .from("pause_scaling")
          .upsert(
            {
              pool: DEFAULT_POOL,
              until,
              reason: `${state}: ${summary}`,
            },
            { onConflict: "pool" },
          );
        if (upsertResult.error) {
          logger.error("Failed to upsert pause_scaling", { error: upsertResult.error.message });
        }
      } else if (allMatch && !webhookUrl) {
        logger.warn("Would page but SENTINEL_WEBHOOK_URL is not configured", {
          state,
          consecutive: recent.length,
        });
      }
    }

    return new Response(
      JSON.stringify({ state, paged, detail }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    logger.error("Sentinel tick failed", { error: message });
    return new Response(JSON.stringify({ error: message }), { status: 500 });
  }
});
