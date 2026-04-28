// deno-lint-ignore-file
import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { NO_SESSION_RUNTIME_OPTIONS, withEdgeRequest } from "../_shared/edgeHandler.ts";
import { jsonResponse } from "../_shared/http.ts";
import { verifyProjectOwnership } from "../_shared/auth.ts";
import { handleTimelineImport } from "./handler.ts";
import type { TimelineImportBody } from "./types.ts";

/**
 * Sprint 6 (Phase 6): import a Banodoco-authored timeline + asset registry
 * into a Reigh project.
 *
 * Auth: reuses `_shared/auth.ts:authenticateRequest()` via withEdgeRequest;
 * `allowJwtUserAuth: true` so Supabase user JWTs from the publish CLI are
 * accepted. Service-role keys are also accepted (for orchestrator paths).
 *
 * Concurrency: writes go through `update_timeline_config_versioned` (or
 * `update_timeline_versioned` when an asset registry is in the payload).
 * `expected_version` is required unless `--force` is set on the CLI; on a
 * `--force` request we read the current version inside the function and
 * use it as the expected value (last-write-wins semantics).
 */
serve((req) =>
  withEdgeRequest<TimelineImportBody>(
    req,
    {
      functionName: "timeline-import",
      logPrefix: "[TIMELINE-IMPORT]",
      method: "POST",
      parseBody: "strict",
      auth: { required: true, options: { allowJwtUserAuth: true } },
      ...NO_SESSION_RUNTIME_OPTIONS,
    },
    async ({ auth, body, logger, supabaseAdmin }) => {
      // Service-role callers don't carry a user identity. The publish CLI
      // path requires a user JWT; reject service-role here to keep the
      // ownership invariant simple. The orchestrator can mint a JWT if it
      // ever needs to publish on a user's behalf.
      if (!auth?.userId) {
        return jsonResponse({ error: "user JWT required (service-role not accepted on this path)" }, 401);
      }

      const result = await handleTimelineImport({
        body,
        userId: auth.userId,
        supabaseAdmin,
        logger,
        verifyOwnership: (projectId, userId) =>
          verifyProjectOwnership(supabaseAdmin, projectId, userId, "[TIMELINE-IMPORT]"),
      });

      return jsonResponse(result.body, result.status);
    },
  )
);
