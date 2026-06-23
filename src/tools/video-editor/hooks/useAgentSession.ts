import { useEffect, useRef, useState, type MutableRefObject } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getSupabaseClient } from '@/integrations/supabase/client.ts';
import type { AgentSession, AgentSessionStatus, AgentTurn } from '@/tools/video-editor/types/agent-session.ts';
import { timelineQueryKey } from '@/tools/video-editor/hooks/useTimeline.ts';
import { useProposalRuntimeFromStoreSafe, useTimelineStoreApiSafe } from '@/tools/video-editor/hooks/timelineStore.ts';
import { importEdgeProposals } from '@/tools/video-editor/lib/proposal-runtime.ts';
import type { ProposalEnvelope, TimelineProposal, ProposalState } from '@/sdk/index';
import type { ProposalImportDiagnosticsState } from '@/tools/video-editor/hooks/timelineStore.ts';

const TIMELINE_AGENT_SESSIONS_TABLE = 'timeline_agent_sessions';
const AUTO_CONTINUE_LIMIT = 10;
const AUTO_CONTINUE_DELAY_MS = 300;

type AgentInvocationResponse = {
  session_id: string;
  status: AgentSessionStatus;
  turns_added: number;
  proposals?: Array<{
    id: string;
    source: string;
    rationale?: string;
    state: string;
    baseVersion: number;
    expiresAt?: number;
    patch: { version: number; operations: Array<{ op: string; target: string; payload?: Record<string, unknown> }> };
  }>;
  mutation_applied?: boolean;
};

type AgentMessageAttachment = NonNullable<AgentTurn['attachments']>[number];

type SendMessageInput = {
  message: string;
  attachments?: AgentMessageAttachment[];
};

function toErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }

  return String(error);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isAgentSessionStatus(value: unknown): value is AgentSessionStatus {
  return value === 'waiting_user'
    || value === 'processing'
    || value === 'continue'
    || value === 'done'
    || value === 'cancelled'
    || value === 'error';
}

function normalizeTurns(value: unknown): AgentTurn[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((item) => {
    if (!isRecord(item) || typeof item.content !== 'string' || typeof item.timestamp !== 'string') {
      return [];
    }

    const role = item.role;
    if (role !== 'user' && role !== 'assistant' && role !== 'tool_call' && role !== 'tool_result') {
      return [];
    }

    return [{
      role,
      content: item.content,
      attachments: Array.isArray(item.attachments) ? item.attachments : undefined,
      tool_name: typeof item.tool_name === 'string' ? item.tool_name : undefined,
      tool_args: isRecord(item.tool_args) ? item.tool_args : undefined,
      timestamp: item.timestamp,
    }];
  });
}

function normalizeSession(row: unknown): AgentSession {
  const record = isRecord(row) ? row : {};

  return {
    id: typeof record.id === 'string' ? record.id : '',
    timeline_id: typeof record.timeline_id === 'string' ? record.timeline_id : '',
    user_id: typeof record.user_id === 'string' ? record.user_id : '',
    status: isAgentSessionStatus(record.status) ? record.status : 'error',
    turns: normalizeTurns(record.turns),
    model: typeof record.model === 'string' ? record.model : 'groq',
    summary: typeof record.summary === 'string' ? record.summary : null,
    proposal_policy: typeof record.proposal_policy === 'string'
      && (record.proposal_policy === 'always' || record.proposal_policy === 'immediate')
      ? record.proposal_policy
      : null,
    cancelled_at: typeof record.cancelled_at === 'string' ? record.cancelled_at : null,
    cancelled_by: typeof record.cancelled_by === 'string' ? record.cancelled_by : null,
    cancel_source: typeof record.cancel_source === 'string' ? record.cancel_source : null,
    cancel_reason: typeof record.cancel_reason === 'string' ? record.cancel_reason : null,
    created_at: typeof record.created_at === 'string' ? record.created_at : '',
    updated_at: typeof record.updated_at === 'string' ? record.updated_at : '',
  };
}

function normalizeInvokeResponse(value: unknown): AgentInvocationResponse {
  const record = isRecord(value) ? value : {};

  const response: AgentInvocationResponse = {
    session_id: typeof record.session_id === 'string' ? record.session_id : '',
    status: isAgentSessionStatus(record.status) ? record.status : 'error',
    turns_added: typeof record.turns_added === 'number' ? record.turns_added : 0,
  };

  // M3: Preserve proposals array from edge response
  if (Array.isArray(record.proposals)) {
    response.proposals = record.proposals.filter(
      (p: unknown): p is AgentInvocationResponse['proposals'][number] =>
        isRecord(p) && typeof p.id === 'string' && typeof p.state === 'string',
    );
  }

  // M3: Preserve mutation_applied flag from edge response
  if (typeof record.mutation_applied === 'boolean') {
    response.mutation_applied = record.mutation_applied;
  }

  return response;
}

function delayWithTracking(timeoutIdsRef: MutableRefObject<Set<number>>, ms: number) {
  return new Promise<void>((resolve) => {
    const timeoutId = window.setTimeout(() => {
      timeoutIdsRef.current.delete(timeoutId);
      resolve();
    }, ms);
    timeoutIdsRef.current.add(timeoutId);
  });
}

export const agentSessionsQueryKey = (timelineId: string | null | undefined) =>
  ['timeline-agent-sessions', timelineId] as const;
export const agentSessionQueryKey = (sessionId: string | null | undefined) =>
  ['timeline-agent-session', sessionId] as const;

export function useAgentSessions(timelineId: string | null | undefined) {
  return useQuery({
    queryKey: agentSessionsQueryKey(timelineId),
    enabled: Boolean(timelineId),
    queryFn: async () => {
      const { data, error } = await getSupabaseClient()
        .from(TIMELINE_AGENT_SESSIONS_TABLE as never)
        .select('*')
        .eq('timeline_id', timelineId!)
        .order('updated_at', { ascending: false });

      if (error) {
        throw error;
      }

      return Array.isArray(data) ? data.map(normalizeSession) : [];
    },
  });
}

export function useAgentSession(sessionId: string | null | undefined) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: agentSessionQueryKey(sessionId),
    enabled: Boolean(sessionId),
    queryFn: async () => {
      const { data, error } = await getSupabaseClient()
        .from(TIMELINE_AGENT_SESSIONS_TABLE as never)
        .select('*')
        .eq('id', sessionId!)
        .maybeSingle();

      if (error) {
        throw error;
      }

      return data ? normalizeSession(data) : null;
    },
  });

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    const supabase = getSupabaseClient();
    const channel = supabase
      .channel(`timeline-agent-session:${sessionId}:${Math.random().toString(36).slice(2, 8)}`)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'timeline_agent_sessions',
          filter: `id=eq.${sessionId}`,
        },
        () => {
          void queryClient.invalidateQueries({ queryKey: agentSessionQueryKey(sessionId) });
          void queryClient.invalidateQueries({ queryKey: ['timeline-agent-sessions'] });
        },
      )
      .subscribe((status, err) => {
        if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT') {
          console.warn(`[useAgentSession] Realtime subscription failed (${status}), removing channel`);
          void supabase.removeChannel(channel);
        }
      });

    return () => {
      void supabase.removeChannel(channel);
    };
  }, [queryClient, sessionId]);

  return query;
}

export function useCreateSession(timelineId: string | null | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      if (!timelineId) {
        throw new Error('timelineId is required');
      }

      const { data: authData, error: authError } = await getSupabaseClient().auth.getUser();
      if (authError) {
        throw authError;
      }

      const userId = authData.user?.id;
      if (!userId) {
        throw new Error('User not authenticated');
      }

      const supabase = getSupabaseClient() as any;
      const { data, error } = await supabase
        .from(TIMELINE_AGENT_SESSIONS_TABLE as never)
        .insert({
          timeline_id: timelineId,
          user_id: userId,
          status: 'waiting_user',
          turns: [],
          model: 'groq',
          proposal_policy: 'immediate',
        })
        .select('*')
        .single();

      if (error) {
        throw error;
      }

      return normalizeSession(data);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: agentSessionsQueryKey(timelineId) });
    },
  });
}

export function useSendMessage(sessionId: string | null | undefined, timelineId?: string | null) {
  const queryClient = useQueryClient();
  const timeoutIdsRef = useRef<Set<number>>(new Set());
  const lastMessageRef = useRef<SendMessageInput | null>(null);
  const [continuationNotice, setContinuationNotice] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const proposalRuntime = useProposalRuntimeFromStoreSafe();
  const storeApi = useTimelineStoreApiSafe();

  useEffect(() => {
    const timeoutIds = timeoutIdsRef.current;
    return () => {
      for (const timeoutId of timeoutIds) {
        window.clearTimeout(timeoutId);
      }
      timeoutIds.clear();
    };
  }, []);

  const mutation = useMutation({
    mutationFn: async (input: SendMessageInput) => {
      if (!sessionId) {
        throw new Error('sessionId is required');
      }

      const { message, attachments } = input;
      lastMessageRef.current = {
        message,
        attachments,
      };
      setLocalError(null);

      const invokeAgent = async (
        nextUserMessage?: string,
        continueCount = 0,
      ): Promise<AgentInvocationResponse> => {
        const { data, error } = await getSupabaseClient().functions.invoke('ai-timeline-agent', {
          body: {
            session_id: sessionId,
            // M1-LOCKED: proposal_policy is durable session-scoped state sent on every
            // agent invocation and automatic continuation.  Lifecycle cleanup (stale
            // policy removal, per-invocation migration) is deferred to a later milestone.
            // See docs/extensions/extension-layer-foundation-assessment.md §2.2.
            proposal_policy: 'always',
            ...(nextUserMessage ? { user_message: nextUserMessage } : {}),
            ...(nextUserMessage && attachments?.length ? {
              selected_clips: attachments.map((clip) => ({
                clip_id: clip.clipId,
                url: clip.url,
                media_type: clip.mediaType,
                ...(typeof clip.isTimelineBacked === 'boolean'
                  ? { is_timeline_backed: clip.isTimelineBacked }
                  : {}),
                ...(clip.generationId ? { generation_id: clip.generationId } : {}),
                ...(clip.variantId ? { variant_id: clip.variantId } : {}),
                ...(clip.prompt ? { prompt: clip.prompt } : {}),
                ...(clip.shotId ? { shot_id: clip.shotId } : {}),
                ...(clip.shotName ? { shot_name: clip.shotName } : {}),
                ...(typeof clip.shotSelectionClipCount === 'number'
                  ? { shot_selection_clip_count: clip.shotSelectionClipCount }
                  : {}),
                ...(clip.trackId ? { track_id: clip.trackId } : {}),
                ...(typeof clip.at === 'number' ? { at: clip.at } : {}),
                ...(typeof clip.duration === 'number' ? { duration: clip.duration } : {}),
              })),
            } : {}),
          },
        });

        if (error) {
          // Supabase functions.invoke returns a generic "Edge Function returned a non-2xx status code"
          // message in `error`, but the actual error details are in `data`.
          const detail = typeof data === 'object' && data !== null
            ? (() => {
              const record = data as Record<string, unknown>;
              if (record.status === 'cancelled') {
                const reason = typeof record.cancel_reason === 'string' ? record.cancel_reason : null;
                const source = typeof record.cancel_source === 'string' ? record.cancel_source : null;
                const cancelledAt = typeof record.cancelled_at === 'string' ? record.cancelled_at : null;
                const parts = [
                  reason,
                  source ? `source=${source}` : null,
                  cancelledAt ? `at=${cancelledAt}` : null,
                ].filter((part): part is string => Boolean(part));
                if (parts.length > 0) {
                  return `Session cancelled (${parts.join(', ')})`;
                }
              }
              return record.error ?? record.details ?? record.message;
            })()
            : undefined;
          if (detail && typeof detail === 'string') {
            throw new Error(detail);
          }
          throw error;
        }

        const response = normalizeInvokeResponse(data);

        if (response.status !== 'continue') {
          setContinuationNotice(null);
          return response;
        }

        if (continueCount >= AUTO_CONTINUE_LIMIT) {
          setContinuationNotice(
            `Auto-continuation paused after ${AUTO_CONTINUE_LIMIT} consecutive continue responses.`,
          );
          return response;
        }

        setContinuationNotice('Agent is continuing...');
        await delayWithTracking(timeoutIdsRef, AUTO_CONTINUE_DELAY_MS);
        return invokeAgent(undefined, continueCount + 1);
      };

      return invokeAgent(message, 0);
    },
    onError: (error) => {
      // Only show error briefly — it will be cleared if realtime delivers a successful update
      setLocalError(toErrorMessage(error));
      // Auto-clear after 5s to avoid stale error banners
      const clearId = window.setTimeout(() => setLocalError(null), 5000);
      timeoutIdsRef.current.add(clearId);
    },
    onSuccess: (data: AgentInvocationResponse) => {
      setLocalError(null);

      // M3: Import edge proposals into the provider-scoped ProposalRuntime
      // BEFORE timeline invalidation decisions so the panel has data to render
      // when the response carries proposals without mutations.
      if (proposalRuntime && Array.isArray(data.proposals) && data.proposals.length > 0) {
        const now = Date.now();
        const timelineProposals: TimelineProposal[] = data.proposals.map((p) => ({
          id: p.id,
          source: p.source,
          rationale: p.rationale,
          state: (p.state as ProposalState) || 'pending',
          patch: p.patch as TimelineProposal['patch'],
          baseVersion: p.baseVersion,
          previewable: false,
          createdAt: now,
          updatedAt: now,
          expiresAt: p.expiresAt,
        }));

        const envelope: ProposalEnvelope = {
          proposals: timelineProposals,
          baseVersion: data.proposals[0].baseVersion,
          mutationApplied: data.mutation_applied ?? false,
        };

        // importEdgeProposals validates each proposal through
        // validateTimelinePatch; malformed proposals are rejected
        // diagnostically rather than throwing.
        const importResult = importEdgeProposals(envelope, proposalRuntime);

        // M4: Persist proposal import diagnostics to timelineStore so the
        // ProposalPanel and other consumers can observe import outcomes.
        // Stale diagnostics from a previous import are replaced on every
        // attempt.
        if (storeApi) {
          const diagnosticsState: ProposalImportDiagnosticsState = {
            imported: importResult.imported,
            skipped: importResult.skipped,
            rejected: importResult.rejected,
            diagnostics: importResult.diagnostics,
            timestamp: now,
          };
          storeApi.getState().setProposalImportDiagnostics(diagnosticsState);
        }
      }

      void queryClient.invalidateQueries({ queryKey: agentSessionQueryKey(sessionId) });
      void queryClient.invalidateQueries({ queryKey: ['timeline-agent-sessions'] });
      // M3: Only re-fetch the timeline when mutations were actually applied.
      // Proposal-only responses (mutation_applied: false) skip invalidation
      // to avoid an unnecessary reload of unchanged config.
      if (timelineId && data.mutation_applied !== false) {
        void queryClient.invalidateQueries({ queryKey: timelineQueryKey(timelineId) });
      }
    },
  });

  const retryLastMessage = async () => {
    if (!lastMessageRef.current) {
      return null;
    }

    setLocalError(null);
    return mutation.mutateAsync(lastMessageRef.current);
  };

  return {
    continuationNotice,
    clearContinuationNotice: () => setContinuationNotice(null),
    localError,
    clearLocalError: () => setLocalError(null),
    hasRetryableMessage: Boolean(lastMessageRef.current),
    retryLastMessage,
    ...mutation,
  };
}

export function useCancelSession(sessionId: string | null | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      if (!sessionId) {
        throw new Error('sessionId is required');
      }

      let userId: string | null = null;
      try {
        const { data: authData, error: authError } = await getSupabaseClient().auth.getUser();
        if (authError) {
          console.warn('[AgentChatCancel] Failed to resolve authenticated user before cancelling session', {
            sessionId,
            error: authError.message,
          });
        } else {
          userId = authData.user?.id ?? null;
        }
      } catch (error) {
        console.warn('[AgentChatCancel] Unexpected auth lookup failure before cancelling session', {
          sessionId,
          error: toErrorMessage(error),
        });
      }

      console.warn('[AgentChatCancel] Cancelling session from AgentChat UI', {
        sessionId,
        userId,
        path: typeof window !== 'undefined' ? window.location.pathname : null,
      });

      const supabase = getSupabaseClient() as any;
      const { error } = await supabase
        .from(TIMELINE_AGENT_SESSIONS_TABLE as never)
        .update({
          status: 'cancelled',
          cancelled_at: new Date().toISOString(),
          cancelled_by: userId,
          cancel_source: 'agent_chat_ui',
          cancel_reason: 'user_stop_button',
          updated_at: new Date().toISOString(),
        })
        .eq('id', sessionId);

      if (error) {
        console.warn('[AgentChatCancel] Session cancellation update failed', {
          sessionId,
          error: error.message,
        });
        throw error;
      }
    },
    onSuccess: () => {
      console.warn('[AgentChatCancel] Session cancellation update succeeded', {
        sessionId,
      });
      void queryClient.invalidateQueries({ queryKey: agentSessionQueryKey(sessionId) });
      void queryClient.invalidateQueries({ queryKey: ['timeline-agent-sessions'] });
    },
  });
}
