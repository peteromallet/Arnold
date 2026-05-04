// deno-lint-ignore-file
import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { NO_SESSION_RUNTIME_OPTIONS, withEdgeRequest } from "../_shared/edgeHandler.ts";
import { jsonResponse } from "../_shared/http.ts";
import { ensureTaskActor } from "../_shared/requestGuards.ts";
import { authorizeTaskActor } from "../_shared/taskActorPolicy.ts";
import { handleTaskStatus } from "./handler.ts";

/**
 * Edge function: task-status (GET)
 *
 * Banodoco-poller-facing read endpoint. Accepts `GET ?task_id=<uuid>` with a
 * `Authorization: Bearer <user_jwt>` (or service-role key) header and returns
 *
 *   { status, correlation_id?, message?, failure_code?, result?: { config_version?, timeline_id?, ... } }
 *
 * which is the contract expected by `pollBanodocoTaskStatus` in
 * `supabase/functions/ai-timeline-agent/tools/delegateToBanodocoAgent.ts`.
 *
 * The legacy POST-only `get-task-status` function is left in place for any
 * existing callers; this is a separate function so we can ship the GET shape
 * without churning that contract. See the cross-repo contract notes (Bug 1).
 *
 * Auth: reuses `_shared/auth.ts:authenticateRequest()` via `withEdgeRequest`,
 * with `allowJwtUserAuth: true`. Ownership is enforced by `authorizeTaskActor`
 * (service-role bypasses; users must own the task's project).
 */
serve((req) =>
  withEdgeRequest(
    req,
    {
      functionName: "task-status",
      logPrefix: "[TASK-STATUS]",
      method: "GET",
      parseBody: "none",
      auth: { required: true, options: { allowJwtUserAuth: true } },
      ...NO_SESSION_RUNTIME_OPTIONS,
    },
    async ({ req, auth, logger, supabaseAdmin }) => {
      const actorCheck = ensureTaskActor(auth, logger);
      if (!actorCheck.ok) return actorCheck.response;

      let url: URL;
      try {
        url = new URL(req.url);
      } catch {
        return jsonResponse({ error: "invalid request url" }, 400);
      }

      const taskId = url.searchParams.get("task_id");
      if (!taskId) {
        logger.error("Missing task_id query param");
        return jsonResponse({ error: "task_id query parameter is required" }, 400);
      }

      logger.setDefaultTaskId(taskId);

      const authorization = await authorizeTaskActor({
        supabaseAdmin,
        taskId,
        auth: auth!,
        logPrefix: "[TASK-STATUS]",
      });
      if (!authorization.ok) {
        logger.error("Task access denied", {
          task_id: taskId,
          error: authorization.error,
          status_code: authorization.statusCode,
        });
        return jsonResponse({ error: authorization.error }, authorization.statusCode);
      }

      const result = await handleTaskStatus({ taskId, supabaseAdmin, logger });
      return jsonResponse(result.body, result.status);
    },
  )
);
