import type { TimelinePlacement } from '../../../../supabase/functions/create-task/resolvers/shared/lineage.ts';

export type AgentSessionStatus =
  | "waiting_user"
  | "processing"
  | "continue"
  | "done"
  | "cancelled"
  | "error";

export type AgentTurnAttachment = {
  clipId: string;
  url: string;
  mediaType: "image" | "video";
  isTimelineBacked?: boolean;
  generationId?: string;
  variantId?: string;
  prompt?: string;
  shotId?: string;
  shotName?: string;
  shotSelectionClipCount?: number;
  trackId?: string;
  at?: number;
  duration?: number;
  timelinePlacement?: TimelinePlacement;
};

export type AgentTurn = {
  role: "user" | "assistant" | "tool_call" | "tool_result";
  content: string;
  attachments?: AgentTurnAttachment[];
  tool_name?: string;
  tool_args?: Record<string, unknown>;
  timestamp: string;
};

export type AgentSession = {
  id: string;
  timeline_id: string;
  user_id: string;
  status: AgentSessionStatus;
  turns: AgentTurn[];
  model: string;
  summary: string | null;
  proposal_policy?: 'always' | 'immediate' | null;
  cancelled_at?: string | null;
  cancelled_by?: string | null;
  cancel_source?: string | null;
  cancel_reason?: string | null;
  created_at: string;
  updated_at: string;
};
