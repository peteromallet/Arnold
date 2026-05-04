// deno-lint-ignore-file
import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { withEdgeRequest } from "../_shared/edgeHandler.ts";

/**
 * Edge function: claim-next-task
 *
 * OPTIMIZED VERSION - Performance improvements over original:
 * - Single database query instead of N+1 queries
 * - Database-level filtering instead of JavaScript filtering
 * - Atomic operations to prevent race conditions
 * - Dramatically reduced network round trips
 * - Enhanced debugging capabilities
 *
 * Claims the next queued task atomically using optimized PostgreSQL functions.
 * - Service-role key: claims any task across all users (cloud processing)
 * - User token: claims only tasks for that specific user (local processing)
 *
 * NOTE: For task counts and statistics, use the separate task-counts function.
 *
 * POST /functions/v1/claim-next-task
 * Headers: Authorization: Bearer <service-key or PAT>
 * Body: {
 *   worker_id?: string,        // Optional worker ID for service role
 *   run_type?: 'gpu' | 'api' | 'banodoco-worker',  // Optional: filter tasks by execution environment
 *                              // 'banodoco-worker' is only valid when worker_pool === 'banodoco'.
 *   worker_pool?: string,      // Optional: identifies a dedicated worker pool (e.g. 'banodoco').
 *                              // When 'banodoco', only banodoco_* task types are claimable.
 *   task_types?: string[],     // Optional: restrict claimable tasks to these task_type values.
 *   same_model_only?: boolean, // Optional: only claim tasks matching worker's current_model
 *   max_task_wait_minutes?: number, // Optional: max age in minutes for claimable tasks (default 5, must be positive finite number)
 *   debug?: boolean            // Optional: enable verbose logging/analysis on 204 responses
 * }
 *
 * Returns:
 * - 200 OK with task data if task claimed successfully
 * - 204 No Content if no tasks available
 * - 401 Unauthorized if no valid token
 * - 403 Forbidden if token invalid or user not found
 * - 500 Internal Server Error
 */
serve((req) => {
  return withEdgeRequest(req, {
  functionName: "claim-next-task",
  logPrefix: "[CLAIM-NEXT-TASK]",
  parseBody: "loose",
  errorResponseFormat: "text",
  auth: {
    required: true,
  },
}, async ({ supabaseAdmin, logger, body: requestBody, auth }) => {
  if (!auth || (!auth.userId && !auth.isServiceRole)) {
    return new Response("Authentication failed", { status: 401 });
  }

  const workerId = typeof requestBody.worker_id === "string"
    ? requestBody.worker_id
    : `edge_${crypto.randomUUID()}`;
  const workerPool = typeof requestBody.worker_pool === "string" && requestBody.worker_pool.length > 0
    ? requestBody.worker_pool
    : null;
  // Accept 'banodoco-worker' run_type only when worker_pool === 'banodoco'.
  // Existing 'gpu' / 'api' paths are unchanged.
  const rawRunType = requestBody.run_type;
  const runType = rawRunType === "gpu" || rawRunType === "api"
    ? rawRunType
    : (rawRunType === "banodoco-worker" && workerPool === "banodoco")
      ? rawRunType
      : null;
  const taskTypes = Array.isArray(requestBody.task_types)
    ? requestBody.task_types.filter((t: unknown): t is string => typeof t === "string" && t.length > 0)
    : null;
  const taskTypesFilter = taskTypes && taskTypes.length > 0 ? taskTypes : null;
  const sameModelOnly = requestBody.same_model_only === true;
  const rawMaxWait = requestBody.max_task_wait_minutes;
  const maxTaskWaitMinutes = typeof rawMaxWait === "number" && rawMaxWait > 0 && isFinite(rawMaxWait)
    ? rawMaxWait
    : 5;
  const debug = requestBody.debug === true;

  const isServiceRole = auth!.isServiceRole;
  const callerId = auth!.userId;

  if (isServiceRole) {
    logger.info("Authenticated via service-role key", {
      worker_id: workerId,
      run_type: runType,
      worker_pool: workerPool,
    });
  } else {
    logger.info("Authenticated via PAT", { user_id: callerId });
  }

  if (isServiceRole) {
    // ═══════════════════════════════════════════════════════════════
    // SERVICE ROLE PATH: Use optimized PostgreSQL function
    // ═══════════════════════════════════════════════════════════════
    const pathType = runType === 'api'
      ? 'API'
      : runType === 'banodoco-worker'
        ? 'BANODOCO'
        : 'GPU';
    logger.info(`Claiming task (service-role, ${pathType} path)`, {
      worker_id: workerId,
      run_type: runType,
      worker_pool: workerPool,
      task_types: taskTypesFilter,
      same_model_only: sameModelOnly,
      max_task_wait_minutes: maxTaskWaitMinutes,
    });

    let claimResult, claimError;
    try {
      // For banodoco-worker pool we don't pass run_type into the RPC's
      // get_task_run_type filter (it only knows about gpu/api). Instead,
      // filtering is handled by p_worker_pool / p_task_types.
      const rpcRunType = runType === 'banodoco-worker' ? null : runType;
      const rpcResponse = await supabaseAdmin
        .rpc('claim_next_task_service_role', {
          p_worker_id: workerId,
          p_include_active: false,
          p_run_type: rpcRunType,
          p_same_model_only: sameModelOnly,
          p_max_task_wait_minutes: maxTaskWaitMinutes,
          p_worker_pool: workerPool,
          p_task_types: taskTypesFilter,
        });

      claimResult = rpcResponse.data;
      claimError = rpcResponse.error;

    } catch (e: unknown) {
      logger.error("Exception during RPC call", { error: e?.message });
      throw e;
    }

    if (claimError) {
      logger.error("Claim RPC error", {
        error: claimError.message,
        code: claimError.code
      });
      throw claimError;
    }

    if (!claimResult || claimResult.length === 0) {
      // Only log and analyze when debug=true to reduce overhead for frequent polling
      if (debug) {
        logger.info("No eligible tasks available", {
          worker_id: workerId,
          run_type: runType,
          same_model_only: sameModelOnly,
          max_task_wait_minutes: maxTaskWaitMinutes,
        });

        // Detailed debugging analysis (only when debug=true)
        try {
          const { data: analysis } = await supabaseAdmin
            .rpc('analyze_task_availability_service_role', {
              p_include_active: false,
              p_run_type: runType
            });

          if (analysis && analysis.total_tasks > 0 && analysis.eligible_tasks === 0) {
            const reasons = analysis.rejection_reasons || {};
            logger.debug("Task availability analysis", {
              total_tasks: analysis.total_tasks,
              eligible_tasks: analysis.eligible_tasks,
              no_credits: reasons.no_credits,
              cloud_disabled: reasons.cloud_disabled,
              concurrency_limit: reasons.concurrency_limit,
              dependency_blocked: reasons.dependency_blocked
            });
          }
        } catch (debugError: unknown) {
          logger.debug("Debug analysis failed", { error: debugError?.message });
        }
      }
      return new Response(null, { status: 204 });
    }

    const task = claimResult[0];

    // Now we have a task_id - set it for this log entry
    logger.setDefaultTaskId(task.task_id);
    logger.info("Task claimed successfully", {
      task_id: task.task_id,
      task_type: task.task_type,
      worker_id: workerId,
      project_id: task.project_id
    });

    return new Response(JSON.stringify({
      task_id: task.task_id,
      params: task.params,
      task_type: task.task_type,
      project_id: task.project_id
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  } else {
    // ═══════════════════════════════════════════════════════════════
    // USER TOKEN PATH: Use optimized PostgreSQL function for specific user
    // ═══════════════════════════════════════════════════════════════
    logger.info("Claiming task (user PAT path)", { user_id: callerId, run_type: runType });

    // Claim next eligible task for this user using PAT-friendly function
    // NOTE: PAT users run on their own hardware — no run_type filtering.
    // They can claim any task (gpu or api) regardless of what the worker sends.
    const { data: claimResult, error: claimError } = await supabaseAdmin
      .rpc('claim_next_task_user_pat', {
        p_user_id: callerId,
        p_include_active: false
      });

    if (claimError) {
      logger.error("Claim RPC error (user path)", {
        user_id: callerId,
        error: claimError.message
      });
      throw claimError;
    }

    if (!claimResult || claimResult.length === 0) {
      // Only log and analyze when debug=true to reduce overhead
      if (debug) {
        logger.info("No eligible tasks for user", { user_id: callerId });

        // Detailed debugging analysis for user (only when debug=true)
        try {
          const { data: analysis } = await supabaseAdmin
            .rpc('analyze_task_availability_user_pat', {
              p_user_id: callerId,
              p_include_active: false
            });

          if (analysis) {
            const userInfo = analysis.user_info || {};
            logger.debug("User task availability analysis", {
              user_id: callerId,
              credits: userInfo.credits,
              allows_local: userInfo.allows_local,
              projects_count: (analysis.projects || []).length,
              recent_tasks_count: (analysis.recent_tasks || []).length,
              eligible_count: analysis.eligible_count
            });
          }
        } catch (debugError: unknown) {
          logger.debug("User debug analysis failed", { error: debugError?.message });
        }
      }
      return new Response(null, { status: 204 });
    }

    const task = claimResult[0];

    // Now we have a task_id - set it for this log entry
    logger.setDefaultTaskId(task.task_id);
    logger.info("Task claimed successfully (user)", {
      task_id: task.task_id,
      task_type: task.task_type,
      user_id: callerId,
      project_id: task.project_id
    });

    return new Response(JSON.stringify({
      task_id: task.task_id,
      params: task.params,
      task_type: task.task_type,
      project_id: task.project_id
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  }
});
});
