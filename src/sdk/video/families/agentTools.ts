/**
 * Agent Tool family module.
 *
 * Houses the agent tool family contracts extracted from the public barrel
 * (src/sdk/index.ts): AgentToolContribution manifest interface, schema/property
 * types, invocation/request/context/export context, result families, result
 * refs, diagnostics, handler, and AgentToolRegistrationService.
 *
 * This module contains only data-only types and read-only surfaces; no
 * registry, provider, resolver, or DOM behaviour lives here.
 *
 * Governance note: ProcessSpawnConfig is imported from the sibling process
 * family module (./processes).  GenerationSessionLiveDelivery is imported
 * from the canonical live-data module (../liveData).  No barrel imports.
 *
 * @publicContract
 */

import type { ContributionId } from '../../ids';
import type { DisposeHandle } from '../../dispose';
import type { DiagnosticSeverity } from '../../diagnostics';
import type { TimelineSnapshot } from '../timeline/reader';
import type { TimelinePatch } from '../timeline/patch';
import type {
  ArtifactBoundary,
  RenderArtifact,
  RenderMaterialMediaKind,
  RenderMaterialRef,
  RenderStorageLocator,
} from '../rendering/artifacts';
import type {
  CapabilityFinding,
  DeterminismStatus,
  RenderRoute,
} from '../rendering/renderability';
// Cross-family type-only imports:
import type { ProcessSpawnConfig } from './processes';
// Live-data type (canonical module under src/sdk/video/liveData.ts):
import type { GenerationSessionLiveDelivery } from '../liveData';

// ---------------------------------------------------------------------------
// M10: Agent tool contribution (manifest)
// ---------------------------------------------------------------------------

/**
 * An agent tool contribution declared in an extension manifest.
 *
 * Agent tools are host-mediated: the host owns invocation, progress,
 * cancellation, proposal creation, and UI. Extensions contribute tool
 * metadata, input schemas, and a handler that returns {@link ToolResult}
 * records. All mutations are proposal-backed through host-owned
 * {@link ProposalRuntime}.
 */
export interface AgentToolContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'agentTool';
  /** The tool identifier used in ctx.agentTools registration calls. */
  toolId: string;
  /** Human-readable label for discovery / UI. */
  label: string;
  /** Human-readable description shown in tooltips / panel. */
  description?: string;
  /**
   * Input schema defining the shape of the tool's invocation payload.
   * Uses a StandardSchema-compatible subset validated at registration time.
   */
  inputSchema?: AgentToolInputSchema;
  /**
   * Result families this tool can produce.
   * When empty, all families are accepted (validated at runtime).
   */
  resultFamilies?: readonly ToolResultFamily[];
  /** Lower values sort first. Default 0. */
  order?: number;
  /** Optional visibility predicate (evaluated by host). */
  when?: string;
}

// ---------------------------------------------------------------------------
// M10: Agent tool input schema / property types
// ---------------------------------------------------------------------------

/**
 * Supported StandardSchema subset for agent tool input schemas.
 *
 * The host uses SchemaForm to render these schemas. Only a minimal
 * StandardSchema subset is supported in M10:
 * - type: 'object' with properties
 * - property types: string, number, boolean, enum (string[])
 * - nested objects (one level)
 * - required fields
 * - title, description annotations
 */
export interface AgentToolInputSchema {
  type: 'object';
  properties?: Record<string, AgentToolInputProperty>;
  required?: readonly string[];
  title?: string;
  description?: string;
}

/** A single property in an agent tool input schema. */
export interface AgentToolInputProperty {
  type: 'string' | 'number' | 'boolean' | 'object';
  title?: string;
  description?: string;
  default?: string | number | boolean;
  enum?: readonly string[];
  /** Nested properties (only when type === 'object'). */
  properties?: Record<string, AgentToolInputProperty>;
  /** Nested required fields (only when type === 'object'). */
  required?: readonly string[];
}

// ---------------------------------------------------------------------------
// M10: Result families and result types
// ---------------------------------------------------------------------------

/**
 * Stable result families for agent tool outputs.
 *
 * New result shapes must fit an existing family or justify a new family
 * in SDK review. Reject one-off feature-specific result objects with
 * diagnostics.
 */
export type ToolResultFamily =
  | 'mutation/proposal'
  | 'generation/session'
  | 'material/artifact'
  | 'enrichment/search'
  | 'export'
  | 'process'
  | 'ui/summary';

/**
 * M10: Grouped ToolResult union.
 *
 * Every result carries a `family` discriminator and a `family`-specific
 * payload. Results that don't fit a known family are rejected with
 * diagnostics before proposals or UI updates are created.
 */
export type ToolResult =
  | ToolMutationProposalResult
  | ToolGenerationSessionResult
  | ToolMaterialArtifactResult
  | ToolEnrichmentSearchResult
  | ToolExportResult
  | ToolProcessResult
  | ToolUISummaryResult;

/** Timeline-mutation proposal result. */
export interface ToolMutationProposalResult {
  family: 'mutation/proposal';
  /** Rationale / explanation for the proposed change. */
  rationale?: string;
  /** The patch(es) to propose via ProposalRuntime. */
  patches: readonly TimelinePatch[];
  /** Affected object IDs for UI context (clip IDs, track IDs, etc.). */
  affectedObjectIds?: readonly string[];
  /** Source-to-output reference map for traceability. */
  sourceRefs?: readonly ToolSourceRef[];
  /** Structured diagnostics produced during tool execution. */
  diagnostics?: readonly ToolResultDiagnostic[];
}

/** Generation/session result for long-running generation tools. */
export interface ToolGenerationSessionResult {
  family: 'generation/session';
  /** Session handle for progress tracking and cancellation. */
  session: GenerationSession;
  /** Optional live sample delivery activation metadata. */
  liveDelivery?: GenerationSessionLiveDelivery;
  /** Rationale / explanation for the generation. */
  rationale?: string;
  /** Structured diagnostics produced during tool execution. */
  diagnostics?: readonly ToolResultDiagnostic[];
}

/** Material/artifact result referencing baked or placeholder asset refs. */
export interface ToolMaterialArtifactResult {
  family: 'material/artifact';
  /** Material or artifact references produced by the tool. */
  refs: readonly ToolArtifactRef[];
  /** Rationale / explanation for the generated artifacts. */
  rationale?: string;
  /** Structured diagnostics produced during tool execution. */
  diagnostics?: readonly ToolResultDiagnostic[];
}

/** Enrichment / search result for asset metadata suggestions. */
export interface ToolEnrichmentSearchResult {
  family: 'enrichment/search';
  /** Enrichment suggestions keyed by asset/material key. */
  suggestions?: Record<string, Record<string, unknown>>;
  /** Search result matches, when applicable. */
  matches?: readonly ToolSearchResultMatch[];
  /** Rationale / explanation for the enrichment. */
  rationale?: string;
  /** Structured diagnostics produced during tool execution. */
  diagnostics?: readonly ToolResultDiagnostic[];
}

/** Export result (planner-compatible findings). */
export interface ToolExportResult {
  family: 'export';
  /** Planner-compatible findings (CapabilityFinding shape). */
  findings?: readonly Record<string, unknown>[];
  /** Export-scoped diagnostics. */
  diagnostics?: readonly ToolResultDiagnostic[];
  /** Rationale / explanation for the findings. */
  rationale?: string;
}

/** Process invocation result (pre-M12 placeholder). */
export interface ToolProcessResult {
  family: 'process';
  /** Structured pending diagnostic (always present before M12). */
  diagnostics: readonly ToolResultDiagnostic[];
}

/** UI-only summary result (e.g. copilot explanation, analysis). */
export interface ToolUISummaryResult {
  family: 'ui/summary';
  /** Human-readable summary text. */
  summary: string;
  /** Structured detail for UI rendering. */
  detail?: Record<string, unknown>;
  /** Structured diagnostics produced during tool execution. */
  diagnostics?: readonly ToolResultDiagnostic[];
}

// ---------------------------------------------------------------------------
// M10: Result refs and diagnostics
// ---------------------------------------------------------------------------

/** A source-to-output reference for traceability. */
export interface ToolSourceRef {
  /** Source identifier (clip ID, asset key, track ID, etc.). */
  sourceId: string;
  /** Output identifier produced from the source. */
  outputId: string;
  /** Human-readable description of the transformation. */
  description?: string;
}

/** An artifact reference produced by a tool. */
export interface ToolArtifactPromotionProducer {
  /** Extension that produced the durable record, when known. */
  readonly extensionId?: string;
  /** Tool identifier that produced the durable record, when known. */
  readonly toolId?: string;
  /** Producer version, when declared by the tool or host. */
  readonly version?: string;
}

/**
 * Promotion evidence carried through {@link ToolArtifactRef.meta}.
 *
 * Agent-produced refs remain lightweight at the tool boundary; when the host
 * promotes them into durable records it reads this evidence from `meta`.
 */
export interface ToolArtifactPromotionEvidence {
  /** Version of the evidence schema used to populate this record. */
  readonly schemaVersion?: number;
  /** Durable media kind for the promoted record. */
  readonly mediaKind?: RenderMaterialMediaKind;
  /** Durable locator for the promoted bytes. */
  readonly locator?: RenderStorageLocator;
  /** Optional hash when not embedded in {@link locator}. */
  readonly outputHash?: string;
  /** Determinism posture of the produced material/artifact. */
  readonly determinism?: DeterminismStatus;
  /** Replacement behaviour when substituting for live/runtime refs. */
  readonly replacementPolicy?: RenderMaterialRef['replacementPolicy'];
  /** Routes this durable record is permitted to satisfy. */
  readonly routeConstraints?: readonly RenderRoute[];
  /** Structured provenance required for authoritative export. */
  readonly provenance?: Record<string, unknown>;
  /** Source ref IDs consumed while producing this durable record. */
  readonly consumedRefs?: readonly string[];
  /** Fully-resolved consumed materials, when already available. */
  readonly consumedMaterialRefs?: readonly RenderMaterialRef[];
  /** Stable hash map for the consumed inputs. */
  readonly inputHashes?: Record<string, string>;
  /** Capability-style diagnostics already known at promotion time. */
  readonly diagnostics?: readonly CapabilityFinding[];
  /** Artifact boundary metadata for asset/artifact promotions. */
  readonly boundary?: ArtifactBoundary;
  /** Preferred artifact route when promoting an asset ref. */
  readonly route?: RenderRoute;
  /** RFC3339 timestamp describing when the output was produced. */
  readonly producedAt?: string;
  /** Producer metadata, supplementing the invocation request. */
  readonly producer?: ToolArtifactPromotionProducer;
  /** Optional opaque metadata preserved on the promoted record manifest. */
  readonly metadata?: Record<string, unknown>;
}

/** Structured metadata carried on a {@link ToolArtifactRef}. */
export interface ToolArtifactMeta extends Record<string, unknown> {
  /** Optional promotion evidence used to create durable host records. */
  readonly promotion?: ToolArtifactPromotionEvidence;
}

/** Host-owned producer metadata for a durable promoted record. */
export interface ToolDurableRecordProducer {
  readonly extensionId: string;
  readonly toolId: string;
  readonly version?: string;
}

/** Shared durable-promotion metadata added by the host. */
export interface ToolDurableRecordBase {
  /** Promotion schema version that produced this durable record. */
  readonly schemaVersion: number;
  /** Original lightweight ref string returned by the tool. */
  readonly sourceRef: string;
  /** Host-attributed producer metadata for the durable record. */
  readonly producer: ToolDurableRecordProducer;
  /** Durable route constraints for later validation and planning. */
  readonly routeConstraints: readonly RenderRoute[];
  /** RFC3339 timestamp describing when the durable output was produced. */
  readonly producedAt: string;
  /** Stable IDs of source refs consumed while producing this output. */
  readonly consumedRefs: readonly string[];
  /** Stable input-hash map used to make determinism auditable. */
  readonly inputHashes: Readonly<Record<string, string>>;
  /** Capability-style diagnostics attached to the promoted output. */
  readonly diagnostics: readonly CapabilityFinding[];
}

/** Durable material record returned by host promotion. */
export interface ToolDurableMaterialRef
  extends RenderMaterialRef, ToolDurableRecordBase {
  readonly durableKind: 'material';
}

/** Durable artifact record returned by host promotion. */
export interface ToolDurableArtifact
  extends RenderArtifact, ToolDurableRecordBase {
  readonly durableKind: 'artifact';
  /** Replacement behaviour retained for later materialization policy checks. */
  readonly replacementPolicy: RenderMaterialRef['replacementPolicy'];
}

/** Durable record synthesized by the host from a tool artifact ref. */
export type ToolDurableRecord =
  | ToolDurableMaterialRef
  | ToolDurableArtifact;

export interface ToolArtifactRef {
  /** Artifact identifier (asset key, material key, etc.). */
  ref: string;
  /** Kind of artifact (asset, material, placeholder). */
  kind: 'asset' | 'material' | 'placeholder';
  /** Human-readable label for UI. */
  label?: string;
  /**
   * Metadata carrier for bake parameters plus optional durable-promotion
   * evidence under `meta.promotion`.
   */
  meta?: ToolArtifactMeta;
  /** Host-owned durable record synthesized after promotion, when available. */
  durableRecord?: ToolDurableRecord;
}

/** A search result match from an enrichment tool. */
export interface ToolSearchResultMatch {
  /** Asset or material key. */
  key: string;
  /** Relevance score (0-1). */
  score: number;
  /** Human-readable label. */
  label?: string;
}

/** Structured diagnostic produced during tool execution. */
export interface ToolResultDiagnostic {
  severity: DiagnosticSeverity;
  /** Stable diagnostic code (for lookup / filtering). */
  code: string;
  /** Human-readable summary. */
  message: string;
  /** Structured detail for debugging. */
  detail?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// M10: AgentToolInvocationRequest and context types
// ---------------------------------------------------------------------------

/**
 * Request to invoke an agent tool.
 *
 * Carries the tool ID, extension context, creative context slices,
 * and any tool-specific input. Edge and worker adapters receive only
 * explicit serializable slices — never raw provider internals.
 */
export interface AgentToolInvocationRequest {
  /** The tool identifier being invoked. */
  toolId: string;
  /** The extension ID that registered the tool. */
  extensionId: string;
  /** The contribution ID of the agent tool in the manifest. */
  contributionId: string;
  /** Tool-specific input matching the declared input schema. */
  input?: Record<string, unknown>;
  /**
   * Explicit creative context slices for tool execution.
   * Only serializable projections are included — never raw provider internals.
   */
  context?: AgentToolRequestContext;
}

/** Explicit creative context slices passed to a tool invocation. */
export interface AgentToolRequestContext {
  /** Read-only timeline snapshot at invocation time. */
  timeline?: TimelineSnapshot;
  /** Asset keys and metadata relevant to the request. */
  assets?: readonly { key: string; metadata?: Record<string, unknown> }[];
  /** Material keys and metadata relevant to the request. */
  materials?: readonly { key: string; metadata?: Record<string, unknown> }[];
  /** Export context (selected format, blockers, etc.). */
  export?: AgentToolExportContext;
  /** Opaque request metadata. */
  meta?: Record<string, unknown>;
}

/** Export context passed to export-adjacent tools. */
export interface AgentToolExportContext {
  /** Selected output format ID. */
  outputFormatId?: string;
  /** Known render blockers at invocation time. */
  blockers?: readonly Record<string, unknown>[];
  /** Contribution IDs available for export. */
  contributionIds?: readonly string[];
}

// ---------------------------------------------------------------------------
// M10: GenerationSession (long-running generation)
// ---------------------------------------------------------------------------

/**
 * Long-running generation session handle returned by agent tools.
 *
 * Provides progress reporting, cancellation, and a preview-only
 * sample channel placeholder. Live media buffers and bake internals
 * are deferred to M11/M12.
 */
export interface GenerationSession {
  /** Unique session identifier. */
  readonly id: string;
  /** Current progress (0-100). */
  readonly progress: number;
  /** Human-readable progress label. */
  readonly progressLabel?: string;
  /** Whether the session has been cancelled. */
  readonly cancelled: boolean;
  /** Whether the session is complete. */
  readonly completed: boolean;
  /** Accumulated structured diagnostics. */
  readonly diagnostics: readonly ToolResultDiagnostic[];
  /** Optional live delivery activation metadata. */
  readonly liveDelivery?: GenerationSessionLiveDelivery;
  /**
   * Update progress with an optional label.
   * Safe to call from any context; silent no-op if cancelled or complete.
   */
  updateProgress(progress: number, label?: string): void;
  /**
   * Request cancellation.
   * Safe to call multiple times; idempotent. Sets cancelled flag and
   * emits a terminal progress update at the current progress value.
   */
  cancel(): void;
  /**
   * Mark the session as complete with final result data.
   * Safe to call once; subsequent calls are ignored.
   */
  complete(result?: Record<string, unknown>): void;
}

// ---------------------------------------------------------------------------
// M10: AgentToolRegistrationService and handler
// ---------------------------------------------------------------------------

/**
 * Agent tool registration service available as `ctx.agentTools` during activate().
 *
 * Extensions register agent tool handlers imperatively. The host owns
 * invocation, progress, cancellation, proposal creation, and UI.
 */
export interface AgentToolRegistrationService {
  /**
   * Register an agent tool handler.
   *
   * The `toolId` must match the `toolId` field of an `AgentToolContribution`
   * declared by this extension in its manifest.
   *
   * The handler receives an {@link AgentToolInvocationRequest} and returns
   * a {@link ToolResult} (or Promise thereof).
   *
   * Returns a DisposeHandle that unregisters the handler when dispose() is
   * called (safe to call multiple times; idempotent).
   */
  registerTool(
    toolId: string,
    handler: AgentToolHandler,
  ): DisposeHandle;

  /**
   * Invoke a process-backed tool (pre-M12 placeholder).
   *
   * Always returns a `ToolProcessResult` with a structured pending
   * diagnostic indicating process execution is not available until M12.
   */
  invokeProcess(
    toolId: string,
    config: ProcessSpawnConfig,
  ): Promise<ToolProcessResult>;
}

/**
 * Agent tool handler function registered by an extension.
 *
 * Receives an invocation request with explicit context slices and
 * returns a ToolResult. May be synchronous or async. Thrown errors
 * are caught by the runtime and published as diagnostics.
 */
export type AgentToolHandler = (
  request: AgentToolInvocationRequest,
) => ToolResult | Promise<ToolResult>;
