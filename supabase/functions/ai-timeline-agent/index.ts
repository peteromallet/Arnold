import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { NO_SESSION_RUNTIME_OPTIONS, withEdgeRequest } from "../_shared/edgeHandler.ts";
import { toErrorMessage } from "../_shared/errorMessage.ts";
import { jsonResponse } from "../_shared/http.ts";
import { persistSessionState } from "./db.ts";
import { isRecord, normalizeSessionRow } from "./llm/messages.ts";
import { runAgentLoop } from "./loop.ts";
import { enrichClipsWithPrompts, normalizeSelectedClips } from "./selectedClips.ts";
import { TIMELINE_AGENT_TOOLS } from "./tool-schemas.ts";
import type { AgentInvocationBody } from "./types.ts";

serve((req) => withEdgeRequest<AgentInvocationBody>(
  req,
  {
    functionName: "ai-timeline-agent",
    logPrefix: "[AI-TIMELINE-AGENT]",
    method: "POST",
    parseBody: "strict",
    auth: { required: true, options: { allowJwtUserAuth: true } },
    ...NO_SESSION_RUNTIME_OPTIONS,
  },
  async ({ auth, body, logger, req, supabaseAdmin }) => {
    if (!auth?.userId) return jsonResponse({ error: "Authentication failed" }, 401);
    // Sprint 7 (SD-022): re-extract the raw Bearer token so the
    // delegateToBanodocoAgent tool can forward it to the orchestrator.
    // The agent only sees this when the caller authenticated via JWT
    // (auth.isJwtAuth === true); PAT-authenticated callers can't drive
    // the bidirectional handoff in v1 because the worker requires a
    // user JWT to verify against JWKS.
    const rawAuthHeader = req.headers.get("Authorization") ?? "";
    const userJwt = rawAuthHeader.startsWith("Bearer ") && auth.isJwtAuth
      ? rawAuthHeader.slice("Bearer ".length)
      : "";
    const sessionId = typeof body.session_id === "string" ? body.session_id.trim() : "";
    const userMessage = body.user_message === undefined || body.user_message === null
      ? undefined
      : typeof body.user_message === "string" ? body.user_message.trim() : null;
    const selectedClips = normalizeSelectedClips(body.selected_clips);
    // M3: Extract raw proposal_policy from body (validated but not resolved yet)
    const bodyProposalPolicy = typeof body.proposal_policy === "string"
      && (body.proposal_policy === "always" || body.proposal_policy === "immediate")
      ? body.proposal_policy
      : undefined;
    if (!sessionId) return jsonResponse({ error: "session_id is required" }, 400);
    if (userMessage === null) return jsonResponse({ error: "user_message must be a string when provided" }, 400);

    const { data: rawSession, error: sessionError } = await supabaseAdmin.from("timeline_agent_sessions").select("*").eq("id", sessionId).maybeSingle();
    if (sessionError) {
      logger.error("Failed to load session", { session_id: sessionId, error: sessionError.message });
      return jsonResponse({ error: "Failed to load session" }, 500);
    }
    if (!rawSession || !isRecord(rawSession)) return jsonResponse({ error: "Session not found" }, 404);

    const session = normalizeSessionRow(rawSession);
    if (session.user_id !== auth.userId) return jsonResponse({ error: "Forbidden" }, 403);
    if (session.status === "cancelled") {
      logger.warn("Rejected invoke for cancelled session", {
        session_id: session.id,
        user_id: auth.userId,
        status: session.status,
        cancelled_at: session.cancelled_at,
        cancelled_by: session.cancelled_by,
        cancel_source: session.cancel_source,
        cancel_reason: session.cancel_reason,
      });
      return jsonResponse({
        error: "Session cancelled",
        status: "cancelled",
        cancelled_at: session.cancelled_at,
        cancelled_by: session.cancelled_by,
        cancel_source: session.cancel_source,
        cancel_reason: session.cancel_reason,
      }, 409);
    }

    // M3: Resolve effective proposal_policy — request body, then session row, then immediate default.
    // 'always' → proposal mode (agent returns proposals instead of mutating)
    // 'immediate' / absent → immediate mode (agent applies mutations directly)
    const sessionProposalPolicy = session.proposal_policy;
    const effectiveProposalPolicy = bodyProposalPolicy ?? sessionProposalPolicy ?? "immediate";
    const timelineMutationMode: "immediate" | "proposal" =
      effectiveProposalPolicy === "always" ? "proposal" : "immediate";

    // Persist policy change when body supplies a valid value that differs from stored state
    if (bodyProposalPolicy && bodyProposalPolicy !== sessionProposalPolicy) {
      const { error: policyUpdateError } = await supabaseAdmin
        .from("timeline_agent_sessions")
        .update({ proposal_policy: bodyProposalPolicy })
        .eq("id", session.id);
      if (policyUpdateError) {
        logger.warn("Failed to persist proposal_policy update", {
          session_id: session.id,
          error: policyUpdateError.message,
        });
      }
    }

    const lastTurn = session.turns[session.turns.length - 1];
    const nextUserMessage = userMessage && lastTurn?.role === "user" && lastTurn.content === userMessage ? undefined : userMessage;

    try {
      const enrichedSelectedClips = await enrichClipsWithPrompts(supabaseAdmin, selectedClips);
      const result = await runAgentLoop({
        session,
        userMessage: nextUserMessage,
        selectedClips: enrichedSelectedClips,
        supabaseAdmin,
        userJwt,
        logger,
        timelineMutationMode,
      });
      await persistSessionState(supabaseAdmin, {
        sessionId: session.id,
        status: result.status,
        turns: result.turns,
        summary: result.summary,
      });
      return jsonResponse({
        session_id: session.id,
        status: result.status,
        turns_added: result.turns.length - session.turns.length,
        tool_count: TIMELINE_AGENT_TOOLS.length,
        model: session.model,
        mutation_applied: result.mutation_applied,
        ...(result.proposals && result.proposals.length > 0
          ? { proposals: result.proposals }
          : {}),
      });
    } catch (error: unknown) {
      return jsonResponse({
        error: "Failed to process timeline agent request",
        details: toErrorMessage(error),
      }, 500);
    }
  },
));
