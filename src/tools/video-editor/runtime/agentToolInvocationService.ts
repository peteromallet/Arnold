/**
 * M10: Agent tool invocation service — bridges registry invocation with
 * host-owned ProposalRuntime.create() for timeline-editing results.
 *
 * This service is the canonical frontend invocation path. It ensures that
 * valid timeline-editing ToolResult outputs are routed through
 * ProposalRuntime.create() rather than being returned as raw patches.
 * Accept/reject/preview remain host-owned through existing ProposalPanel
 * and TimelineOps flows.
 *
 * @module agentToolInvocationService
 * @milestone M10
 */

import type {
  AgentToolInvocationRequest,
  ToolResult,
  ToolMutationProposalResult,
  ToolMaterialArtifactResult,
  ToolArtifactRef,
  ToolUISummaryResult,
  ToolResultDiagnostic,
  ProposalRuntime,
} from '@reigh/editor-sdk';
import type { AgentToolRegistry } from '@/tools/video-editor/runtime/agentToolRegistry';
import type {
  ToolArtifactMeta,
  ToolArtifactPromotionEvidence,
  ToolDurableArtifact,
  ToolDurableMaterialRef,
} from '@/sdk/video/families/agentTools';
import type {
  ArtifactBoundary,
  RenderArtifact,
  RenderMaterialMediaKind,
  RenderMaterialRef,
  RenderStorageLocator,
} from '@/sdk/video/rendering/artifacts';
import type {
  CapabilityFinding,
  DeterminismStatus,
  RenderRoute,
} from '@/sdk/video/rendering/renderability';
import {
  assertFinalArtifactHasManifest,
  createRenderArtifactManifest,
} from '@/tools/video-editor/runtime/renderability.ts';
import {
  isTimelineEditableResult,
  toolResultToTimelineProposalInputs,
} from '@/tools/video-editor/runtime/agentToolContracts';

// ---------------------------------------------------------------------------
// AgentToolInvocationService
// ---------------------------------------------------------------------------

/**
 * Frontend invocation service that routes timeline-editing tool results
 * through the host-owned ProposalRuntime.
 *
 * Composes the AgentToolRegistry (handler execution + validation) with
 * ProposalRuntime (proposal lifecycle: preview/accept/reject) so that
 * agent tools produce host-mediated proposals rather than raw patches.
 */
export interface AgentToolInvocationService {
  /**
   * Invoke a registered agent tool.
   *
   * - Delegates handler execution and result validation to the registry.
   * - Routes valid timeline-editing (mutation/proposal) results through
   *   ProposalRuntime.create() so the host owns the proposal lifecycle.
   * - Returns a UI-summary result describing the created proposal(s),
   *   or the original result for non-timeline-editing families.
   *
   * @returns The ToolResult, or null if the tool/handler is unavailable.
   */
  invokeTool(request: AgentToolInvocationRequest): Promise<ToolResult | null>;

  /**
   * The underlying registry (exposed for adapters that need direct access).
   */
  readonly registry: AgentToolRegistry;
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

export interface CreateAgentToolInvocationServiceOptions {
  /** The provider-scoped agent tool registry. */
  registry: AgentToolRegistry;

  /** The provider-scoped proposal runtime (stable for provider lifetime). */
  proposalRuntime: ProposalRuntime;
}

const VALID_RENDER_ROUTES = new Set<RenderRoute>([
  'preview',
  'browser-export',
  'worker-export',
  'sidecar-export',
]);

const VALID_DETERMINISM_STATUSES = new Set<DeterminismStatus>([
  'deterministic',
  'preview-only',
  'live-unbaked',
  'process-dependent',
  'unknown',
]);

const VALID_MEDIA_KINDS = new Set<RenderMaterialMediaKind>([
  'image',
  'video',
  'audio',
  'text',
  'json',
  'binary',
  'sidecar',
  'unknown',
]);

type PromotionProducer = {
  extensionId: string;
  toolId: string;
  version?: string;
};

type PromotionOutcome = {
  ref: ToolArtifactRef;
  diagnostics: ToolResultDiagnostic[];
};

/**
 * Promote a single artifact ref to a durable record using
 * {@link ToolArtifactMeta.promotion} evidence.
 *
 * Returns the original ref unchanged (with diagnostics) when required
 * provenance is absent or when the ref is a placeholder.
 *
 * @public M3c — exported for session-hook promotion wiring.
 */
export function promoteArtifactRef(
  ref: ToolArtifactRef,
  source: { extensionId: string; toolId: string },
): PromotionOutcome {
  if (ref.kind === 'placeholder') {
    return {
      ref,
      diagnostics: [
        createPromotionDiagnostic(
          'warning',
          'agent-tool/material-promotion-skipped-placeholder',
          `Skipped durable promotion for placeholder ref "${ref.ref}".`,
          {
            ref: ref.ref,
            kind: ref.kind,
            toolId: source.toolId,
            extensionId: source.extensionId,
          },
        ),
      ],
    };
  }

  const evidence = readPromotionEvidence(ref.meta);
  const missingEvidence = collectMissingEvidence(evidence);
  if (missingEvidence.length > 0) {
    const code = missingEvidence.includes('provenance')
      ? 'agent-tool/material-promotion-missing-provenance'
      : 'agent-tool/material-promotion-missing-evidence';
    return {
      ref,
      diagnostics: [
        createPromotionDiagnostic(
          'error',
          code,
          `Cannot promote "${ref.ref}" without durable provenance evidence.`,
          {
            ref: ref.ref,
            kind: ref.kind,
            missingEvidence,
            toolId: source.toolId,
            extensionId: source.extensionId,
          },
        ),
      ],
    };
  }

  const producer: PromotionProducer = {
    extensionId: evidence.producer?.extensionId ?? source.extensionId,
    toolId: evidence.producer?.toolId ?? source.toolId,
    version: evidence.producer?.version,
  };
  const locator = normalizeLocator(evidence);
  const routeConstraints = normalizeRouteConstraints(evidence.routeConstraints);
  const determinism = evidence.determinism as DeterminismStatus;
  const mediaKind = evidence.mediaKind as RenderMaterialMediaKind;
  const replacementPolicy =
    evidence.replacementPolicy ?? 'preserve-live-ref';
  const producedAt = evidence.producedAt as string;
  const provenance = normalizeRecord(evidence.provenance) ?? {};
  const consumedRefs = normalizeStringArray(evidence.consumedRefs);
  const inputHashes = normalizeStringRecord(evidence.inputHashes);
  const diagnostics = normalizeCapabilityFindings(
    evidence.diagnostics,
    ref.ref,
    { extensionId: source.extensionId, toolId: source.toolId, contributionId: `${source.extensionId}:${source.toolId}` },
  );

  const durableRecord =
    ref.kind === 'material'
      ? createDurableMaterialRecord({
          sourceRef: ref.ref,
          producer,
          schemaVersion: evidence.schemaVersion as number,
          mediaKind,
          locator,
          determinism,
          replacementPolicy,
          provenance,
          routeConstraints,
          consumedRefs,
          inputHashes,
          diagnostics,
          producedAt,
        })
      : createDurableArtifactRecord({
          sourceRef: ref.ref,
          producer,
          schemaVersion: evidence.schemaVersion as number,
          mediaKind,
          locator,
          determinism,
          replacementPolicy,
          provenance,
          routeConstraints,
          consumedRefs,
          inputHashes,
          diagnostics,
          producedAt,
          route: normalizeArtifactRoute(evidence, routeConstraints),
          boundary: normalizeArtifactBoundary(
            evidence.boundary,
            normalizeArtifactRoute(evidence, routeConstraints),
          ),
          metadata: normalizeRecord(evidence.metadata),
          consumedMaterialRefs: normalizeConsumedMaterialRefs(
            evidence.consumedMaterialRefs,
          ),
        });

  return {
    ref: {
      ...ref,
      durableRecord,
    },
    diagnostics: [],
  };
}

/**
 * Promote a batch of {@link ToolArtifactRef}s to durable records.
 *
 * This is the canonical entry point for session-hook promotion wiring
 * (M3c).  It delegates to {@link promoteArtifactRef} for each ref and
 * collects all diagnostics.
 *
 * @param refs - The refs to promote.
 * @param source - Fallback producer metadata used when the ref's own
 *   {@link ToolArtifactPromotionEvidence.producer} is absent.
 * @returns The promoted refs and any promotion diagnostics.
 *
 * @public M3c
 */
export function promoteMaterialArtifactBatch(
  refs: readonly ToolArtifactRef[],
  source: { extensionId: string; toolId: string },
): { promotedRefs: ToolArtifactRef[]; diagnostics: ToolResultDiagnostic[] } {
  const diagnostics: ToolResultDiagnostic[] = [];
  const promotedRefs = refs.map((ref) => {
    const outcome = promoteArtifactRef(ref, source);
    diagnostics.push(...outcome.diagnostics);
    return outcome.ref;
  });

  return { promotedRefs, diagnostics };
}

/**
 * Create the frontend invocation service.
 *
 * The returned service is the intended entry point for all browser-side
 * agent tool invocation. It guarantees that timeline-editing results are
 * routed through ProposalRuntime.create() so that:
 *
 * - Every mutation proposal has a tracked lifecycle (pending → accepted/rejected/stale).
 * - Preview is computed immediately after creation via proposalRuntime.create().
 * - Accept/reject remain host-owned through ProposalPanel → ProposalRuntime.accept/reject.
 * - Accept always applies through TimelineOps (preserving commitData/history).
 * - Stale-base handling is enforced during acceptance.
 */
export function createAgentToolInvocationService(
  options: CreateAgentToolInvocationServiceOptions,
): AgentToolInvocationService {
  const { registry, proposalRuntime } = options;

  async function invokeTool(
    request: AgentToolInvocationRequest,
  ): Promise<ToolResult | null> {
    // 1. Invoke through the registry (handler execution + result validation)
    const result = await registry.invokeTool(request);

    // 2. If the result is null (handler unavailable, tool missing, error), pass through
    if (result === null) {
      return null;
    }

    // 3. If the result is a timeline-editing result, route through ProposalRuntime
    if (isTimelineEditableResult(result)) {
      return routeTimelineEditableResult(result, request);
    }

    if (result.family === 'material/artifact') {
      return promoteMaterialArtifactResult(result, request);
    }

    // 4. Non-timeline-editing results pass through unchanged
    return result;
  }

  /**
   * Route a timeline-editing (mutation/proposal) result through ProposalRuntime.
   *
   * Converts each patch to a TimelineProposalInput, creates proposals via
   * proposalRuntime.create(), and returns a ToolUISummaryResult describing
   * the created proposals.
   */
  function routeTimelineEditableResult(
    result: ToolMutationProposalResult,
    request: AgentToolInvocationRequest,
  ): ToolUISummaryResult {
    // Use the proposalRuntime's currentVersion as the base version.
    // This ensures proposals are computed against the version at invocation time.
    const baseVersion = proposalRuntime.currentVersion;

    // Build a source identifier that includes the tool and extension
    const source = `${request.toolId}`;

    // Convert patches to TimelineProposalInput records
    const proposalInputs = toolResultToTimelineProposalInputs(
      result,
      baseVersion,
      source,
    );

    // Create proposals through the host-owned ProposalRuntime
    const createdProposals = proposalInputs.map((input) =>
      proposalRuntime.create(input),
    );

    // Build a UI summary describing what was created
    const proposalIds = createdProposals.map((p) => p.id);
    const patchCount = proposalInputs.length;
    const previewable = createdProposals.every((p) => p.previewable);

    const summaryLines: string[] = [];
    summaryLines.push(
      patchCount === 1
        ? `Created 1 proposal from tool "${request.toolId}".`
        : `Created ${patchCount} proposals from tool "${request.toolId}".`,
    );

    if (result.rationale) {
      summaryLines.push(`Rationale: ${result.rationale}`);
    }

    if (result.affectedObjectIds && result.affectedObjectIds.length > 0) {
      const objectList = result.affectedObjectIds.slice(0, 5).join(', ');
      const suffix =
        result.affectedObjectIds.length > 5
          ? ` (and ${result.affectedObjectIds.length - 5} more)`
          : '';
      summaryLines.push(`Affected objects: ${objectList}${suffix}`);
    }

    if (!previewable) {
      summaryLines.push(
        'Note: Some proposals could not be fully previewed. Review before accepting.',
      );
    }

    // Collect any diagnostics from the original result
    const diagnostics: ToolResultDiagnostic[] = [...(result.diagnostics ?? [])];

    // Add a summary diagnostic
    diagnostics.push({
      severity: 'info',
      code: 'agent-tool/proposals-created',
      message: summaryLines.join(' '),
      detail: {
        proposalIds,
        baseVersion,
        source,
        patchCount,
        previewable,
      },
    });

    const uiResult: ToolUISummaryResult = {
      family: 'ui/summary',
      summary: summaryLines.join('\n'),
      diagnostics,
      detail: {
        proposalIds,
        baseVersion,
        source,
        patchCount,
        previewable,
        affectedObjectIds: result.affectedObjectIds,
        sourceRefs: result.sourceRefs,
      },
    };

    return uiResult;
  }

  function promoteMaterialArtifactResult(
    result: ToolMaterialArtifactResult,
    request: AgentToolInvocationRequest,
  ): ToolMaterialArtifactResult {
    const { promotedRefs, diagnostics: promotionDiagnostics } =
      promoteMaterialArtifactBatch(result.refs, {
        extensionId: request.extensionId,
        toolId: request.toolId,
      });

    return {
      ...result,
      refs: promotedRefs,
      diagnostics:
        promotionDiagnostics.length > 0
          ? [...(result.diagnostics ?? []), ...promotionDiagnostics]
          : result.diagnostics,
    };
  }

  return {
    invokeTool,
    registry,
  };
}

function readPromotionEvidence(
  meta: ToolArtifactMeta | undefined,
): ToolArtifactPromotionEvidence {
  const fallback = normalizeRecord(meta) ?? {};
  const promotion = normalizeRecord(meta?.promotion);
  return {
    ...fallback,
    ...promotion,
  } as ToolArtifactPromotionEvidence;
}

function collectMissingEvidence(
  evidence: ToolArtifactPromotionEvidence,
): string[] {
  const missing: string[] = [];

  if (!isPositiveInteger(evidence.schemaVersion)) {
    missing.push('schemaVersion');
  }
  if (!isValidMediaKind(evidence.mediaKind)) {
    missing.push('mediaKind');
  }
  if (!hasValidLocator(evidence)) {
    missing.push('locator');
  }
  if (!isValidDeterminism(evidence.determinism)) {
    missing.push('determinism');
  }
  if (normalizeRouteConstraints(evidence.routeConstraints).length === 0) {
    missing.push('routeConstraints');
  }
  if (!normalizeRecord(evidence.provenance) || Object.keys(evidence.provenance ?? {}).length === 0) {
    missing.push('provenance');
  }
  if (!isNonEmptyString(evidence.producedAt)) {
    missing.push('producedAt');
  }
  if (normalizeStringArray(evidence.consumedRefs).length === 0) {
    missing.push('consumedRefs');
  }
  if (Object.keys(normalizeStringRecord(evidence.inputHashes)).length === 0) {
    missing.push('inputHashes');
  }

  return missing;
}

function createDurableMaterialRecord(params: {
  sourceRef: string;
  producer: PromotionProducer;
  schemaVersion: number;
  mediaKind: RenderMaterialMediaKind;
  locator: RenderStorageLocator;
  determinism: DeterminismStatus;
  replacementPolicy: RenderMaterialRef['replacementPolicy'];
  provenance: Record<string, unknown>;
  routeConstraints: readonly RenderRoute[];
  consumedRefs: readonly string[];
  inputHashes: Record<string, string>;
  diagnostics: readonly CapabilityFinding[];
  producedAt: string;
}): ToolDurableMaterialRef {
  return {
    durableKind: 'material',
    schemaVersion: params.schemaVersion,
    sourceRef: params.sourceRef,
    producer: params.producer,
    routeConstraints: params.routeConstraints,
    producedAt: params.producedAt,
    consumedRefs: params.consumedRefs,
    inputHashes: params.inputHashes,
    diagnostics: params.diagnostics,
    id: params.sourceRef,
    mediaKind: params.mediaKind,
    locator: params.locator,
    producerExtensionId: params.producer.extensionId,
    producerVersion: params.producer.version,
    provenance: params.provenance,
    determinism: params.determinism,
    replacementPolicy: params.replacementPolicy,
  };
}

function createDurableArtifactRecord(params: {
  sourceRef: string;
  producer: PromotionProducer;
  schemaVersion: number;
  mediaKind: RenderMaterialMediaKind;
  locator: RenderStorageLocator;
  determinism: DeterminismStatus;
  replacementPolicy: RenderMaterialRef['replacementPolicy'];
  provenance: Record<string, unknown>;
  routeConstraints: readonly RenderRoute[];
  consumedRefs: readonly string[];
  inputHashes: Record<string, string>;
  diagnostics: readonly CapabilityFinding[];
  producedAt: string;
  route: RenderRoute;
  boundary: ArtifactBoundary;
  metadata?: Record<string, unknown>;
  consumedMaterialRefs: readonly RenderMaterialRef[];
}): ToolDurableArtifact {
  const artifact: RenderArtifact = {
    id: params.sourceRef,
    route: params.route,
    locator: params.locator,
    mediaKind: params.mediaKind,
    producerExtensionId: params.producer.extensionId,
    producerVersion: params.producer.version,
    consumedMaterialRefs: params.consumedMaterialRefs,
    determinism: params.determinism,
    boundary: params.boundary,
    findings: params.diagnostics,
    manifest: createRenderArtifactManifest({
      id: `manifest.${params.sourceRef}`,
      artifactId: params.sourceRef,
      route: params.route,
      determinism: params.determinism,
      producerExtensionId: params.producer.extensionId,
      producerVersion: params.producer.version,
      locator: params.locator,
      mediaKind: params.mediaKind,
      consumedMaterialRefs: params.consumedMaterialRefs,
      sidecars: [],
      diagnostics: params.diagnostics,
      provenance: params.provenance,
      inputHashes: params.inputHashes,
      createdAt: params.producedAt,
      metadata: params.metadata,
    }),
  };
  assertFinalArtifactHasManifest(artifact, 'createDurableArtifactRecord');

  return {
    durableKind: 'artifact',
    schemaVersion: params.schemaVersion,
    sourceRef: params.sourceRef,
    producer: params.producer,
    routeConstraints: params.routeConstraints,
    producedAt: params.producedAt,
    consumedRefs: params.consumedRefs,
    inputHashes: params.inputHashes,
    diagnostics: params.diagnostics,
    replacementPolicy: params.replacementPolicy,
    ...artifact,
  };
}

function normalizeLocator(
  evidence: ToolArtifactPromotionEvidence,
): RenderStorageLocator {
  const locator = normalizeRecord(evidence.locator) ?? {};
  const contentSha256 = isNonEmptyString(locator.contentSha256)
    ? locator.contentSha256
    : isNonEmptyString(evidence.outputHash)
      ? evidence.outputHash
      : undefined;

  return {
    kind: String(locator.kind),
    uri: String(locator.uri),
    mimeType: isNonEmptyString(locator.mimeType) ? locator.mimeType : undefined,
    contentSha256,
    expiresAt: isNonEmptyString(locator.expiresAt) ? locator.expiresAt : undefined,
  };
}

function hasValidLocator(evidence: ToolArtifactPromotionEvidence): boolean {
  const locator = normalizeRecord(evidence.locator);
  if (!locator) return false;
  if (!isNonEmptyString(locator.kind) || !isNonEmptyString(locator.uri)) {
    return false;
  }
  return isNonEmptyString(locator.contentSha256) || isNonEmptyString(evidence.outputHash);
}

function normalizeArtifactRoute(
  evidence: ToolArtifactPromotionEvidence,
  routeConstraints: readonly RenderRoute[],
): RenderRoute {
  if (isValidRenderRoute(evidence.route) && routeConstraints.includes(evidence.route)) {
    return evidence.route;
  }
  return routeConstraints[0] ?? 'preview';
}

function normalizeArtifactBoundary(
  boundary: ToolArtifactPromotionEvidence['boundary'],
  route: RenderRoute,
): ArtifactBoundary {
  const boundaryRecord = normalizeRecord(boundary);
  const source = boundaryRecord?.source;
  const target = boundaryRecord?.target;
  const failureBehavior = boundaryRecord?.failureBehavior;

  if (
    isNonEmptyString(source)
    && isNonEmptyString(target)
    && isNonEmptyString(failureBehavior)
  ) {
    return {
      source: source as ArtifactBoundary['source'],
      target: target as ArtifactBoundary['target'],
      route,
      failureBehavior: failureBehavior as ArtifactBoundary['failureBehavior'],
    };
  }

  return {
    source: route === 'preview' ? 'browser' : 'artifact-store',
    target: route === 'preview' ? 'browser' : 'export-output',
    route,
    failureBehavior: 'block-export',
  };
}

function normalizeCapabilityFindings(
  diagnostics: ToolArtifactPromotionEvidence['diagnostics'],
  ref: string,
  request: AgentToolInvocationRequest,
): CapabilityFinding[] {
  if (!Array.isArray(diagnostics)) {
    return [];
  }

  return diagnostics.flatMap((diagnostic, index) => {
    const record = normalizeRecord(diagnostic);
    if (!record) return [];
    const diagnosticCode = isNonEmptyString(record.code)
      ? record.code
      : isNonEmptyString(record.id)
        ? record.id
        : undefined;
    if (!isCapabilitySeverity(record.severity) || !diagnosticCode || !isNonEmptyString(record.message)) {
      return [];
    }
    const detail = normalizeRecord(record.detail);
    return [{
      id: isNonEmptyString(record.id)
        ? record.id
        : `agent-tool-promotion:${diagnosticCode}:${request.extensionId}:${request.toolId}:${ref}:${index}`,
      severity: record.severity,
      route: isValidRenderRoute(record.route) ? record.route : undefined,
      reason: isNonEmptyString(record.reason) ? record.reason as CapabilityFinding['reason'] : undefined,
      message: record.message,
      extensionId: isNonEmptyString(record.extensionId) ? record.extensionId : request.extensionId,
      contributionId: isNonEmptyString(record.contributionId) ? record.contributionId : request.contributionId,
      materialRefId: isNonEmptyString(record.materialRefId) ? record.materialRefId : ref,
      detail: {
        ...(detail ?? {}),
        toolDiagnosticCode: diagnosticCode,
      },
    }];
  });
}

function normalizeRouteConstraints(
  routes: ToolArtifactPromotionEvidence['routeConstraints'],
): RenderRoute[] {
  if (!Array.isArray(routes)) {
    return [];
  }
  const normalized = routes.filter(isValidRenderRoute);
  return normalized.filter((route, index) => normalized.indexOf(route) === index);
}

function normalizeConsumedMaterialRefs(
  refs: ToolArtifactPromotionEvidence['consumedMaterialRefs'],
): RenderMaterialRef[] {
  if (!Array.isArray(refs)) {
    return [];
  }

  return refs.flatMap((ref) => {
    const record = normalizeRecord(ref);
    if (!record) return [];
    if (
      !isNonEmptyString(record.id)
      || !isValidMediaKind(record.mediaKind)
      || !normalizeRecord(record.locator)
      || !isValidDeterminism(record.determinism)
      || !isNonEmptyString(record.replacementPolicy)
    ) {
      return [];
    }
    return [{
      id: record.id,
      mediaKind: record.mediaKind,
      locator: {
        kind: String((record.locator as Record<string, unknown>).kind),
        uri: String((record.locator as Record<string, unknown>).uri),
        mimeType: isNonEmptyString((record.locator as Record<string, unknown>).mimeType)
          ? String((record.locator as Record<string, unknown>).mimeType)
          : undefined,
        contentSha256: isNonEmptyString((record.locator as Record<string, unknown>).contentSha256)
          ? String((record.locator as Record<string, unknown>).contentSha256)
          : undefined,
        expiresAt: isNonEmptyString((record.locator as Record<string, unknown>).expiresAt)
          ? String((record.locator as Record<string, unknown>).expiresAt)
          : undefined,
      },
      producerExtensionId: isNonEmptyString(record.producerExtensionId)
        ? record.producerExtensionId
        : undefined,
      producerVersion: isNonEmptyString(record.producerVersion)
        ? record.producerVersion
        : undefined,
      provenance: normalizeRecord(record.provenance) ?? undefined,
      determinism: record.determinism,
      replacementPolicy: record.replacementPolicy as RenderMaterialRef['replacementPolicy'],
    }];
  });
}

function normalizeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(isNonEmptyString);
}

function normalizeStringRecord(value: unknown): Record<string, string> {
  const record = normalizeRecord(value);
  if (!record) {
    return {};
  }

  const normalized: Record<string, string> = {};
  for (const [key, entry] of Object.entries(record)) {
    if (typeof entry === 'string' && entry.length > 0) {
      normalized[key] = entry;
    }
  }
  return normalized;
}

function normalizeRecord(
  value: unknown,
): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null
    ? value as Record<string, unknown>
    : undefined;
}

function createPromotionDiagnostic(
  severity: ToolResultDiagnostic['severity'],
  code: string,
  message: string,
  detail: Record<string, unknown>,
): ToolResultDiagnostic {
  return {
    severity,
    code,
    message,
    detail,
  };
}

function isValidRenderRoute(value: unknown): value is RenderRoute {
  return typeof value === 'string' && VALID_RENDER_ROUTES.has(value as RenderRoute);
}

function isValidDeterminism(value: unknown): value is DeterminismStatus {
  return typeof value === 'string'
    && VALID_DETERMINISM_STATUSES.has(value as DeterminismStatus);
}

function isValidMediaKind(value: unknown): value is RenderMaterialMediaKind {
  return typeof value === 'string' && VALID_MEDIA_KINDS.has(value as RenderMaterialMediaKind);
}

function isCapabilitySeverity(
  value: unknown,
): value is CapabilityFinding['severity'] {
  return value === 'error' || value === 'warning' || value === 'info';
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value > 0;
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0;
}
