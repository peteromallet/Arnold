import type {
  AgentSession,
  AgentSessionStatus,
  AgentTurn,
} from "../../../src/tools/video-editor/index.ts";
import type { TimelinePlacement } from "../create-task/resolvers/shared/lineage.ts";
import type { AssetRegistry, TimelineConfig } from "../../../src/tools/video-editor/index.ts";

export type { AgentSession, AgentSessionStatus, AgentTurn };

/** A single proposal in a structured edge proposal envelope. */
export interface EdgeProposal {
  /** Unique proposal identifier. */
  id: string;
  /** Source that created this proposal (tool name, agent, etc.). */
  source: string;
  /** Human-readable rationale / description. */
  rationale?: string;
  /** Lifecycle state — always 'pending' when produced by the edge. */
  state: 'pending';
  /** Config version the proposal was created against. */
  baseVersion: number;
  /** Epoch-ms expiry timestamp, or undefined for no TTL. */
  expiresAt?: number;
  /** The patch that would be applied if accepted. */
  patch: {
    version: number;
    operations: Array<{
      op: string;
      target: string;
      payload?: Record<string, unknown>;
    }>;
  };
}

export type ToolResult = {
  result: string;
  config?: TimelineConfig;
  stopLoop?: boolean;
  nextStatus?: AgentSessionStatus;
  /** Structured proposals produced in proposal mode (M3). */
  proposals?: EdgeProposal[];
};

export type ToolContext = {
  config: TimelineConfig;
  registry: AssetRegistry;
  projectId: string;
  shotNamesById: Record<string, string>;
};

export type ToolHandler = (
  args: Record<string, unknown>,
  context: ToolContext,
) => ToolResult | Promise<ToolResult>;

type SupabaseError = { message: string };
type SupabaseListResult = Promise<{ data: unknown; error: SupabaseError | null }>;
type SupabaseMaybeSingleResult = Promise<{ data: unknown; error: SupabaseError | null }>;
type SupabaseUpdateResult = Promise<{ error: SupabaseError | null }>;
type SupabaseInsertResult = Promise<{ data?: unknown; error: SupabaseError | null }>;

type SupabaseSelectQuery = {
  eq: (column: string, value: string) => SupabaseSelectQuery;
  in: (column: string, values: string[]) => SupabaseListResult;
  or: (filter: string) => SupabaseSelectQuery;
  limit: (count: number) => SupabaseListResult;
  maybeSingle: () => SupabaseMaybeSingleResult;
};

type SupabaseUpdateQuery = {
  eq: (column: string, value: string) => SupabaseUpdateResult;
};

export type SupabaseAdmin = {
  from: (table: string) => {
    select: (query: string) => SupabaseSelectQuery;
    insert: (payload: Record<string, unknown> | Record<string, unknown>[]) => SupabaseInsertResult;
    update: (payload: Record<string, unknown>) => SupabaseUpdateQuery;
  };
  rpc: (
    fn: string,
    args: Record<string, unknown>,
  ) => {
    maybeSingle: () => SupabaseMaybeSingleResult;
  };
};

export type TimelineState = {
  config: TimelineConfig;
  previousConfig?: TimelineConfig;
  configVersion: number;
  registry: AssetRegistry;
  projectId: string;
  shotNamesById: Record<string, string>;
};

export type LlmMessage = {
  role: "system" | "user" | "assistant" | "tool";
  content: string | null;
  tool_call_id?: string;
  tool_calls?: Array<{
    id: string;
    type: "function";
    function: {
      name: string;
      arguments: string;
    };
  }>;
};

export type SelectedClipPayload = {
  clip_id: string;
  url: string;
  media_type: "image" | "video";
  is_timeline_backed?: boolean;
  generation_id?: string;
  variant_id?: string;
  prompt?: string;
  shot_id?: string;
  shot_name?: string;
  shot_selection_clip_count?: number;
  track_id?: string;
  at?: number;
  duration?: number;
  timeline_placement?: TimelinePlacement;
};

export type ResolvedSelectionContext = {
  timeline_id: string;
  clip_id: string;
  generation_id?: string;
  variant_id?: string;
  track_id: string;
  at: number;
  duration: number;
  shot_id?: string;
  shot_name?: string;
  source: "timeline" | "gallery";
  is_on_timeline: boolean;
};

export type PlacementIntent = {
  timeline_id: string;
  anchor_clip_id: string;
  anchor_generation_id?: string;
  anchor_variant_id?: string;
  relation: "after";
  preferred_track_id: string;
  fallback_at: number;
  fallback_track_id: string;
};

export type AgentTextToImageModel = "qwen-image" | "qwen-image-2512" | "z-image";

export type AgentReferenceMode = "style" | "subject" | "style-character" | "scene" | "custom";

export interface AgentProjectImageSettingsReference {
  id: string;
  resourceId: string;
  referenceMode?: AgentReferenceMode;
  styleReferenceStrength?: number;
  subjectStrength?: number;
  subjectDescription?: string;
  inThisScene?: boolean;
  inThisSceneStrength?: number;
}

export interface AgentProjectImageSettings {
  selectedTextModel?: AgentTextToImageModel;
  references?: AgentProjectImageSettingsReference[];
  selectedReferenceIdByShot?: Record<string, string | null>;
  selectedLorasByCategory?: Partial<Record<"qwen" | "z-image", Array<{ path: string; strength: number }>>>;
}

export interface AgentVideoTravelSettings {
  selectedModel: string;
  frames: number;
  steps: number;
  amountOfMotion: number;
  guidanceScale?: number;
  turboMode: boolean;
  enhancePrompt: boolean;
  negativePrompt?: string;
  textBeforePrompts?: string;
  textAfterPrompts?: string;
  generationTypeMode: "i2v" | "vace";
  generationMode: "batch" | "by-pair" | "timeline";
  loras: Array<{
    id: string;
    name: string;
    path: string;
    strength: number;
    triggerWord?: string;
    lowNoisePath?: string;
    isMultiStage?: boolean;
  }>;
  phaseConfig?: Record<string, unknown>;
  smoothContinuations: boolean;
}

export interface ResolvedReference {
  url: string;
  referenceMode: AgentReferenceMode;
  styleReferenceStrength?: number;
  subjectStrength?: number;
  subjectDescription?: string;
  inThisScene?: boolean;
  inThisSceneStrength?: number;
}

export interface GenerationContext {
  image: {
    defaultModelName?: AgentTextToImageModel;
    activeReference?: ResolvedReference | null;
    selectedLorasByCategory?: Partial<Record<"qwen" | "z-image", Array<{ path: string; strength: number }>>>;
  } | null;
  travel: AgentVideoTravelSettings | null;
}

export interface AgentInvocationBody {
  session_id?: unknown;
  user_message?: unknown;
  selected_clips?: unknown;
  /** M3: proposal mode policy — 'immediate' (default) applies mutations directly; 'always' returns proposals. */
  proposal_policy?: unknown;
}

export interface TimelineRow {
  config: TimelineConfig;
  config_version: number;
  asset_registry: AssetRegistry;
  project_id: string;
}

export type Difficulty = "easy" | "okay" | "hard";

export interface OpenRouterParams {
  model: string;
  messages: unknown[];
  tools?: unknown[];
  tool_choice?: string;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
}

export interface OpenRouterResponse {
  choices: Array<{
    message: {
      role: string;
      content: string | null;
      tool_calls?: Array<{
        id: string;
        type: "function";
        function: {
          name: string;
          arguments: string;
        };
      }>;
    };
  }>;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}
