import {
  contributionRefKey,
  type CapabilityFinding,
  type CapabilityRequirement,
  type CompositionGraph,
  type DeterminismStatus,
  type ProcessStatus,
  type RenderBlocker,
  type RenderBlockerReason,
  type RenderMaterialRef,
  type RenderRoute,
  RENDER_ROUTES,
  type TimelineSnapshot,
  type TimelineShaderSummary,
  getCapabilityRequirements,
} from '@reigh/editor-sdk';
import { shaderMissingMaterializerBlockerMessage } from '@/sdk/video/rendering/capabilities.ts';
import { COMPOSITION_DIAGNOSTIC_CODE } from '@/tools/video-editor/runtime/composition/diagnostics.ts';
import {
  projectShaderRefs,
  validateShaderComposition,
} from '@/tools/video-editor/runtime/composition/shaderValidation.ts';
import type {
  ContributionIndex,
  ExtensionRuntime,
  VideoEditorOutputFormatDescriptor,
  VideoEditorPlannerBlockerDescriptor,
  VideoEditorPlannerNextActionDescriptor,
  VideoEditorProcessDescriptor,
  VideoEditorProcessRequirementDescriptor,
  VideoEditorRouteRequirementDescriptor,
  VideoEditorShaderDescriptor,
} from '@/tools/video-editor/runtime/extensionSurface.ts';

export interface RenderPlannerRequest {
  readonly route?: RenderRoute;
  readonly routes?: readonly RenderRoute[];
  readonly outputFormatId?: string;
  readonly requiredCapabilities?: readonly string[];
}

export type RenderPlannerMaterialState = 'missing' | 'stale' | 'resolved' | 'unbaked';

export interface RenderPlannerMaterialStatus {
  readonly materialRefId: string;
  readonly state: RenderPlannerMaterialState;
  readonly message?: string;
  readonly updatedAt?: string;
}

export interface RenderPlannerInput {
  readonly snapshot?: TimelineSnapshot | null;
  readonly requirements?: readonly CapabilityRequirement[];
  readonly compositionGraph?: CompositionGraph;
  readonly extensionRuntime?: Pick<
    ExtensionRuntime,
    'outputFormats' | 'processes' | 'shaders' | 'contributionIndex' | 'compositionGraph'
  >;
  readonly outputFormats?: readonly VideoEditorOutputFormatDescriptor[];
  readonly processes?: readonly VideoEditorProcessDescriptor[];
  readonly shaders?: readonly VideoEditorShaderDescriptor[];
  readonly processStatuses?: readonly ProcessStatus[];
  readonly materialRefs?: readonly RenderMaterialRef[];
  readonly materialStatuses?: readonly RenderPlannerMaterialStatus[];
  readonly request?: RenderPlannerRequest;
  readonly diagnostics?: readonly CapabilityFinding[];
}

export interface RenderRouteSummary {
  readonly route: RenderRoute;
  readonly blockerCount: number;
  readonly findingCount: number;
  readonly blocked: boolean;
}

export interface RenderRoutePlan extends RenderRouteSummary {
  readonly requiredCapabilities: readonly string[];
  readonly determinism: DeterminismStatus;
  readonly blockers: readonly RenderBlocker[];
  readonly diagnostics: readonly CapabilityFinding[];
  readonly outputFormatIds: readonly string[];
  readonly processRequirements: readonly VideoEditorProcessRequirementDescriptor[];
  readonly nextActions: readonly VideoEditorPlannerNextActionDescriptor[];
}

export interface RenderPlannerGuardCompatibility {
  readonly diagnostics: readonly CapabilityFinding[];
  readonly findings: readonly CapabilityFinding[];
  readonly blockers: readonly RenderBlocker[];
  readonly unknownClipTypes: readonly string[];
  readonly unknownEffects: readonly string[];
  readonly unknownTransitions: readonly string[];
  readonly inactiveExtensionIds: {
    readonly effectIds: ReadonlySet<string>;
    readonly transitionIds: ReadonlySet<string>;
    readonly clipTypeIds: ReadonlySet<string>;
  };
  readonly hasBlockingErrors: boolean;
}

export interface RenderPlannerResult {
  readonly guard: RenderPlannerGuardCompatibility;
  readonly findings: readonly CapabilityFinding[];
  readonly blockers: readonly RenderBlocker[];
  readonly routes: readonly RenderRouteSummary[];
  readonly routePlans: readonly RenderRoutePlan[];
  readonly diagnostics: readonly CapabilityFinding[];
  readonly nextActions: readonly VideoEditorPlannerNextActionDescriptor[];
  readonly canBrowserExport: boolean;
  readonly canWorkerExport: boolean;
}

interface PlanAccumulator {
  findings: CapabilityFinding[];
  blockers: RenderBlocker[];
  nextActions: VideoEditorPlannerNextActionDescriptor[];
  routeCapabilities: Map<RenderRoute, Set<string>>;
  routeOutputFormatIds: Map<RenderRoute, Set<string>>;
  routeProcessRequirements: Map<RenderRoute, VideoEditorProcessRequirementDescriptor[]>;
  routeDeterminism: Map<RenderRoute, DeterminismStatus[]>;
}

interface ShaderCompositionDiagnosis {
  readonly snapshot: TimelineSnapshot | null | undefined;
  readonly shaders: readonly TimelineShaderSummary[] | undefined;
  readonly findings: CapabilityFinding[];
}

const EMPTY_IDS = Object.freeze({
  effectIds: Object.freeze(new Set<string>()),
  transitionIds: Object.freeze(new Set<string>()),
  clipTypeIds: Object.freeze(new Set<string>()),
});

const GRAPH_PLANNER_ROUTES = [
  'browser-export',
  'worker-export',
] as const satisfies readonly RenderRoute[];

const LEGACY_GRAPH_COMPATIBILITY_WARNING_ID = 'planner.compositionGraph.legacy-shader-ref-compatibility';

const DETERMINISM_RANK: Record<DeterminismStatus, number> = {
  deterministic: 0,
  'preview-only': 1,
  'live-unbaked': 2,
  'process-dependent': 3,
  unknown: 4,
};

function createAccumulator(): PlanAccumulator {
  return {
    findings: [],
    blockers: [],
    nextActions: [],
    routeCapabilities: new Map(),
    routeOutputFormatIds: new Map(),
    routeProcessRequirements: new Map(),
    routeDeterminism: new Map(),
  };
}

function addRouteValue<T>(map: Map<RenderRoute, T[]>, route: RenderRoute, value: T): void {
  const values = map.get(route);
  if (values) {
    values.push(value);
    return;
  }
  map.set(route, [value]);
}

function addRouteSetValue(map: Map<RenderRoute, Set<string>>, route: RenderRoute, value: string): void {
  const values = map.get(route);
  if (values) {
    values.add(value);
    return;
  }
  map.set(route, new Set([value]));
}

function freezeFinding(finding: CapabilityFinding): CapabilityFinding {
  return Object.freeze({
    ...finding,
    ...(finding.detail ? { detail: Object.freeze({ ...finding.detail }) } : {}),
  });
}

function freezeBlocker(blocker: RenderBlocker): RenderBlocker {
  return Object.freeze({
    ...blocker,
    ...(blocker.detail ? { detail: Object.freeze({ ...blocker.detail }) } : {}),
  });
}

function dedupeById<T extends { readonly id: string }>(items: readonly T[]): T[] {
  const seen = new Set<string>();
  const deduped: T[] = [];
  for (const item of items) {
    if (seen.has(item.id)) continue;
    seen.add(item.id);
    deduped.push(item);
  }
  return deduped;
}

function sortedFindings(findings: readonly CapabilityFinding[]): readonly CapabilityFinding[] {
  return Object.freeze(
    dedupeById(findings.map(freezeFinding)).sort((a, b) => a.id.localeCompare(b.id)),
  );
}

function sortedBlockers(blockers: readonly RenderBlocker[]): readonly RenderBlocker[] {
  return Object.freeze(
    dedupeById(blockers.map(freezeBlocker)).sort((a, b) => a.id.localeCompare(b.id)),
  );
}

function blockerForFinding(finding: CapabilityFinding): RenderBlocker | undefined {
  if (finding.severity !== 'error' || !finding.route || !finding.reason) return undefined;
  return {
    ...finding,
    severity: 'error',
    route: finding.route,
    reason: finding.reason,
  };
}

function routeFitFinding(requirement: CapabilityRequirement): CapabilityFinding | undefined {
  const routeFit = requirement.routeFit;
  if (!routeFit && !requirement.blocking) return undefined;
  if (routeFit?.fit === 'supported' && !requirement.blocking) return undefined;

  const reason = routeFit?.reason ?? blockerReasonForDeterminism(requirement.determinism);
  const severity = requirement.blocking || routeFit?.fit === 'blocked' ? 'error' : 'warning';
  return {
    id: `${requirement.id}.${requirement.route}.${reason}`,
    severity,
    route: requirement.route,
    reason,
    message: routeFit?.message
      ?? `Capability requirement "${requirement.id}" is ${routeFit?.fit ?? 'blocked'} for ${requirement.route}.`,
    extensionId: requirement.sourceRef.extensionId,
    contributionId: requirement.sourceRef.contributionId,
    detail: {
      source: 'capability-requirement',
      sourceRef: requirement.sourceRef,
      requiredCapabilities: [...requirement.requiredCapabilities].sort(),
      determinism: requirement.determinism,
      routeFit: routeFit ? { ...routeFit } : undefined,
    },
  };
}

function blockerReasonForDeterminism(determinism: DeterminismStatus): RenderBlockerReason {
  switch (determinism) {
    case 'preview-only':
    case 'live-unbaked':
    case 'process-dependent':
    case 'unknown':
      return determinism;
    case 'deterministic':
      return 'unknown';
  }
}

function collectRequirement(acc: PlanAccumulator, requirement: CapabilityRequirement): void {
  addRouteValue(acc.routeDeterminism, requirement.route, requirement.determinism);
  for (const capability of requirement.requiredCapabilities) {
    addRouteSetValue(acc.routeCapabilities, requirement.route, capability);
  }

  for (const finding of requirement.findings ?? []) {
    acc.findings.push(finding);
    const blocker = blockerForFinding(finding);
    if (blocker) acc.blockers.push(blocker);
  }

  const routeFit = routeFitFinding(requirement);
  if (!routeFit) return;
  acc.findings.push(routeFit);
  const blocker = blockerForFinding(routeFit);
  if (blocker) acc.blockers.push(blocker);
}

function shaderDescriptorKey(extensionId: string | undefined, contributionId: string | undefined): string {
  return `${extensionId ?? ''}:${contributionId ?? ''}`;
}

function projectSnapshotShaderRefs(
  snapshot: TimelineSnapshot | null | undefined,
  contributionIndex: ContributionIndex | undefined,
  compositionGraph?: CompositionGraph,
): TimelineSnapshot | null | undefined {
  if (!snapshot?.shaders) {
    return snapshot;
  }

  const shaders = projectShaderRefs(snapshot.shaders, contributionIndex, compositionGraph);
  if (shaders === snapshot.shaders) {
    return snapshot;
  }

  return {
    ...snapshot,
    shaders: shaders && shaders.length > 0 ? shaders : undefined,
  };
}

function stripSnapshotShaders(
  snapshot: TimelineSnapshot | null | undefined,
): TimelineSnapshot | null | undefined {
  if (!snapshot?.shaders) {
    return snapshot;
  }

  return {
    ...snapshot,
    shaders: undefined,
  };
}

function plannerCompositionGraph(input: RenderPlannerInput): CompositionGraph | undefined {
  return input.compositionGraph ?? input.extensionRuntime?.compositionGraph;
}

function shaderRefKey(
  shader: Pick<TimelineShaderSummary, 'extensionId' | 'contributionId'>,
): string {
  return contributionRefKey({
    kind: 'shader',
    extensionId: shader.extensionId,
    contributionId: shader.contributionId,
  });
}

function shaderScopeNodeId(shader: Pick<TimelineShaderSummary, 'scope' | 'clipId'>): string {
  return shader.scope === 'clip'
    ? `clip:${shader.clipId ?? 'unknown'}`
    : 'timeline-postprocess';
}

function compositionDiagnosticReason(code: string): RenderBlockerReason {
  switch (code) {
    case COMPOSITION_DIAGNOSTIC_CODE.MISSING_REF:
      return 'missing-contribution';
    case COMPOSITION_DIAGNOSTIC_CODE.DISABLED_REF:
    case COMPOSITION_DIAGNOSTIC_CODE.INACTIVE_RESERVED_REF:
      return 'inactive-extension';
    default:
      return 'unknown';
  }
}

function graphDiagnosticFindings(
  compositionGraph: CompositionGraph | undefined,
): CapabilityFinding[] {
  if (!compositionGraph || compositionGraph.diagnostics.length === 0) {
    return [];
  }

  const findings: CapabilityFinding[] = [];
  compositionGraph.diagnostics.forEach((diagnostic, diagnosticIndex) => {
    for (const route of GRAPH_PLANNER_ROUTES) {
      findings.push({
        id: `${diagnostic.code}.${route}.${diagnosticIndex}`,
        severity: diagnostic.severity === 'info' ? 'info' : diagnostic.severity,
        route,
        reason: compositionDiagnosticReason(diagnostic.code),
        message: diagnostic.message,
        extensionId: diagnostic.extensionId
          ?? (diagnostic.detail?.extensionId as string | undefined),
        contributionId: diagnostic.contributionId
          ?? (diagnostic.detail?.contributionId as string | undefined),
        detail: {
          source: 'composition-graph',
          code: diagnostic.code,
          ...(diagnostic.detail ?? {}),
        },
      });
    }
  });

  return findings;
}

function graphShaderMaterializerRequirements(
  shaders: readonly TimelineShaderSummary[] | undefined,
  compositionGraph: CompositionGraph | undefined,
): CapabilityRequirement[] {
  if (!compositionGraph || !shaders?.length) {
    return [];
  }

  const refStateByKey = new Map(
    compositionGraph.referenceStates.map((entry) => [entry.refKey, entry.state]),
  );
  const requirements: CapabilityRequirement[] = [];
  let shaderOrdinal = 0;
  for (const shader of shaders) {
    if (shader.enabled === false) {
      continue;
    }

    const refState = refStateByKey.get(shaderRefKey(shader));
    if (refState !== 'resolved') {
      continue;
    }

    const sourceRef: CapabilityRequirement['sourceRef'] = {
      source: 'extension',
      extensionId: shader.extensionId,
      contributionId: shader.contributionId,
    };

    for (const route of GRAPH_PLANNER_ROUTES) {
      requirements.push({
        id: `graph.shader.${shaderOrdinal}.${route}`,
        sourceRef,
        route,
        requiredCapabilities: ['render-material', 'shader-materializer'],
        determinism: 'preview-only',
        blocking: true,
        routeFit: {
          route,
          fit: 'blocked',
          reason: 'missing-material',
          message: shaderMissingMaterializerBlockerMessage(
            shader.shaderId,
            shader.scope,
            shader.clipId,
          ),
        },
      });
    }
    shaderOrdinal += 1;
  }

  return requirements;
}

function legacyGraphCompatibilityWarning(
  snapshot: TimelineSnapshot | null | undefined,
  requirements: readonly CapabilityRequirement[] | undefined,
  compositionGraph: CompositionGraph | undefined,
): CapabilityFinding | undefined {
  if (compositionGraph) {
    return undefined;
  }

  const hasLegacyShaderFacts = Boolean(snapshot?.shaders?.some((shader) => shader.enabled !== false))
    || Boolean(requirements?.some(isShaderMaterializerRequirement));
  if (!hasLegacyShaderFacts) {
    return undefined;
  }

  return {
    id: LEGACY_GRAPH_COMPATIBILITY_WARNING_ID,
    severity: 'warning',
    message:
      'CompositionGraph was not provided; planner shader/ref decisions are using legacy compatibility inputs and are not authoritative for M1b.',
    detail: {
      source: 'composition-graph-compatibility',
      compatibilityMode: 'legacy-shader-ref',
    },
  };
}

function createShaderDescriptorMap(
  descriptors: readonly VideoEditorShaderDescriptor[],
): ReadonlyMap<string, VideoEditorShaderDescriptor> {
  return new Map(descriptors.map((descriptor) => [
    shaderDescriptorKey(descriptor.extensionId, descriptor.id),
    descriptor,
  ]));
}

function createProcessDescriptorMap(
  descriptors: readonly VideoEditorProcessDescriptor[],
): ReadonlyMap<string, VideoEditorProcessDescriptor> {
  return new Map(descriptors.map((descriptor) => [descriptor.processId, descriptor]));
}

function isShaderMaterializerRequirement(requirement: CapabilityRequirement): boolean {
  return requirement.sourceRef.source === 'extension'
    && requirement.requiredCapabilities.includes('shader-materializer')
    && requirement.requiredCapabilities.includes('render-material');
}

function processOperationSupportsMaterializerRoute(
  process: VideoEditorProcessDescriptor | undefined,
  operationId: string | undefined,
  route: RenderRoute,
): boolean {
  if (!process) return false;
  return process.operations.some((operation) => {
    if (operationId && operation.id !== operationId) return false;
    if (!operation.routes?.includes(route)) return false;
    return !operation.outputKinds || operation.outputKinds.includes('material');
  });
}

function shaderMaterializerSupportsRoute(
  descriptor: VideoEditorShaderDescriptor,
  requirement: CapabilityRequirement,
  processById: ReadonlyMap<string, VideoEditorProcessDescriptor>,
): boolean {
  const materializer = descriptor.materializer;
  if (!materializer) return false;
  if (materializer.routes?.includes(requirement.route)) return true;
  if (!materializer.processId) return false;
  return processOperationSupportsMaterializerRoute(
    processById.get(materializer.processId),
    materializer.operationId,
    requirement.route,
  );
}

function shaderMaterializationMessage(
  descriptor: VideoEditorShaderDescriptor,
  requirement: CapabilityRequirement,
): string {
  if (descriptor.materializer?.unavailableMessage) return descriptor.materializer.unavailableMessage;
  if (descriptor.materializer?.processId) {
    return `Shader "${descriptor.shaderId}" has a materializer route for ${requirement.route}; ` +
      `run process "${descriptor.materializer.processId}" to produce RenderMaterial.`;
  }
  return `Shader "${descriptor.shaderId}" has a materializer route for ${requirement.route}; ` +
    'materialize it to produce RenderMaterial.';
}

function shaderMaterializationAction(
  descriptor: VideoEditorShaderDescriptor,
  requirement: CapabilityRequirement,
  message: string,
): VideoEditorPlannerNextActionDescriptor {
  return {
    kind: 'resolve-blocker',
    label: `Materialize shader ${descriptor.shaderId}`,
    route: requirement.route,
    processId: descriptor.materializer?.processId,
    operationId: descriptor.materializer?.operationId,
    message,
  };
}

function shaderMaterializerFinding(
  descriptor: VideoEditorShaderDescriptor,
  requirement: CapabilityRequirement,
  action: VideoEditorPlannerNextActionDescriptor,
  processStatus: ProcessStatus | undefined,
): CapabilityFinding {
  return {
    id: `${requirement.id}.${requirement.route}.shader-materializer.discovered`,
    severity: 'info',
    route: requirement.route,
    message: `Shader materializer route discovered for "${descriptor.shaderId}" on ${requirement.route}.`,
    extensionId: descriptor.extensionId,
    contributionId: descriptor.id,
    detail: {
      source: 'shader-materializer',
      shaderId: descriptor.shaderId,
      processId: descriptor.materializer?.processId,
      operationId: descriptor.materializer?.operationId,
      processState: processStatus?.state ?? 'unknown',
      materializationState: processStatus?.state === 'busy' ? 'in-progress' : 'pending',
      nextAction: action,
    },
  };
}

function collectShaderMaterializerRequirement(
  acc: PlanAccumulator,
  requirement: CapabilityRequirement,
  descriptor: VideoEditorShaderDescriptor,
  processStatusById: ReadonlyMap<string, ProcessStatus>,
): void {
  const processStatus = descriptor.materializer?.processId
    ? processStatusById.get(descriptor.materializer.processId)
    : undefined;
  const message = shaderMaterializationMessage(descriptor, requirement);
  const action = shaderMaterializationAction(descriptor, requirement, message);

  collectRequirement(acc, {
    ...requirement,
    determinism: 'process-dependent',
    blocking: true,
    routeFit: {
      route: requirement.route,
      fit: 'supported',
      reason: 'process-dependent',
      message,
    },
    findings: [
      ...(requirement.findings ?? []),
      shaderMaterializerFinding(descriptor, requirement, action, processStatus),
    ],
  });
  acc.nextActions.push(action);
}

function shaderCompositionScopeLabel(shader: TimelineShaderSummary): string {
  return shader.scope === 'clip' ? `clip:${shader.clipId ?? 'unknown'}` : 'postprocess';
}

function diagnoseSnapshotShaderComposition(
  snapshot: TimelineSnapshot | null | undefined,
  contributionIndex: ContributionIndex | undefined,
  compositionGraph?: CompositionGraph,
): ShaderCompositionDiagnosis {
  if (compositionGraph) {
    const validation = validateShaderComposition(undefined, compositionGraph);
    const graphShaders = validation.shaders && validation.shaders.length > 0
      ? validation.shaders
      : undefined;
    const graphSnapshot = snapshot
      ? {
          ...snapshot,
          shaders: graphShaders,
        }
      : snapshot;

    if (!graphShaders || graphShaders.length === 0) {
      return {
        snapshot: graphSnapshot,
        shaders: graphShaders,
        findings: graphDiagnosticFindings(compositionGraph),
      };
    }

    const findings = graphDiagnosticFindings(compositionGraph);
    const refStateByKey = new Map(
      compositionGraph.referenceStates.map((entry) => [entry.refKey, entry.state]),
    );

    for (const occupied of validation.occupied) {
      const shader = occupied.incoming;
      const refKey = shaderRefKey(shader);
      const refState = refStateByKey.get(refKey);
      for (const route of GRAPH_PLANNER_ROUTES) {
        findings.push({
          id: `${COMPOSITION_DIAGNOSTIC_CODE.SCOPE_OCCUPIED}.${route}.${shaderCompositionScopeLabel(shader)}.${shader.shaderId}`,
          severity: 'error',
          route,
          reason: 'unknown',
          message: occupied.message,
          extensionId: shader.extensionId,
          contributionId: shader.contributionId,
          detail: {
            source: 'composition-graph',
            code: COMPOSITION_DIAGNOSTIC_CODE.SCOPE_OCCUPIED,
            nodeId: shaderScopeNodeId(shader),
            refKey,
            refState,
            scope: occupied.scope,
            extensionId: shader.extensionId,
            contributionId: shader.contributionId,
            shaderId: shader.shaderId,
            clipId: occupied.clipId,
            existingShaderId: occupied.existing.shaderId,
            incomingShaderId: occupied.incoming.shaderId,
          },
        });
      }
    }

    const updatedGraphSnapshot = graphSnapshot
      ? {
          ...graphSnapshot,
          shaders: validation.shaders && validation.shaders.length > 0 ? validation.shaders : undefined,
        }
      : graphSnapshot;

    return {
      snapshot: updatedGraphSnapshot,
      shaders: validation.shaders && validation.shaders.length > 0 ? validation.shaders : undefined,
      findings,
    };
  }

  const projectedSnapshot = projectSnapshotShaderRefs(snapshot, contributionIndex);
  if (!projectedSnapshot?.shaders || projectedSnapshot.shaders.length === 0) {
    return { snapshot: projectedSnapshot, shaders: projectedSnapshot?.shaders, findings: [] };
  }

  const validation = validateShaderComposition(projectedSnapshot.shaders);
  if (validation.occupied.length === 0) {
    return { snapshot: projectedSnapshot, shaders: validation.shaders, findings: [] };
  }

  const findings: CapabilityFinding[] = [];
  for (const occupied of validation.occupied) {
    const shader = occupied.incoming;
    for (const route of ['browser-export', 'worker-export'] as const satisfies readonly RenderRoute[]) {
      findings.push({
        id: `planner.shaderComposition.${shaderCompositionScopeLabel(shader)}.${shader.shaderId}.${route}.scope-occupied`,
        severity: 'error',
        route,
        reason: 'unknown',
        message: occupied.message,
        extensionId: shader.extensionId,
        contributionId: shader.contributionId,
        detail: {
          source: 'shader-composition-limit',
          scope: occupied.scope,
          clipId: occupied.clipId,
          existingShaderId: occupied.existing.shaderId,
          incomingShaderId: occupied.incoming.shaderId,
        },
      });
    }
  }

  return {
    snapshot: {
      ...projectedSnapshot,
      shaders: validation.shaders && validation.shaders.length > 0 ? validation.shaders : undefined,
    },
    shaders: validation.shaders && validation.shaders.length > 0 ? validation.shaders : undefined,
    findings,
  };
}

function sortedRoutes(routes: readonly RenderRoute[]): readonly RenderRoute[] {
  const requested = new Set(routes);
  return Object.freeze(RENDER_ROUTES.filter((route) => requested.has(route)));
}

function requestedRoutes(request: RenderPlannerRequest | undefined): readonly RenderRoute[] {
  if (!request) return Object.freeze([]);
  if (request.routes && request.routes.length > 0) return sortedRoutes(request.routes);
  if (request.route) return Object.freeze([request.route]);
  return Object.freeze([]);
}

function collectRequestCapabilities(acc: PlanAccumulator, request: RenderPlannerRequest | undefined): void {
  if (!request?.requiredCapabilities || request.requiredCapabilities.length === 0) return;
  const routes = requestedRoutes(request);
  const targetRoutes = routes.length > 0 ? routes : RENDER_ROUTES;

  for (const route of targetRoutes) {
    for (const capability of request.requiredCapabilities) {
      addRouteSetValue(acc.routeCapabilities, route, capability);
    }
  }
}

function descriptorBlockerToFinding(
  blocker: VideoEditorPlannerBlockerDescriptor,
  fallbackRoute: RenderRoute,
  source: 'output-format' | 'process',
): CapabilityFinding {
  return {
    id: blocker.id,
    severity: 'error',
    route: blocker.route ?? fallbackRoute,
    reason: blocker.reason,
    message: blocker.message,
    extensionId: blocker.extensionId,
    contributionId: blocker.contributionId,
    detail: {
      source,
      nextAction: blocker.nextAction,
    },
  };
}

function collectDescriptorBlocker(
  acc: PlanAccumulator,
  blocker: VideoEditorPlannerBlockerDescriptor,
  fallbackRoute: RenderRoute,
  source: 'output-format' | 'process',
): void {
  const finding = descriptorBlockerToFinding(blocker, fallbackRoute, source);
  acc.findings.push(finding);
  const routeBlocker = blockerForFinding(finding);
  if (routeBlocker) acc.blockers.push(routeBlocker);
  if (blocker.nextAction) acc.nextActions.push(blocker.nextAction);
}

function processRequirementBlocker(
  outputFormat: VideoEditorOutputFormatDescriptor,
  route: RenderRoute,
  requirement: VideoEditorProcessRequirementDescriptor,
  status?: ProcessStatus,
): RenderBlocker {
  const operationSuffix = requirement.operationId ? `.${requirement.operationId}` : '';
  return {
    id: `planner.outputFormat.${outputFormat.extensionId}.${outputFormat.id}.${route}.${requirement.processId}${operationSuffix}.process-dependent`,
    severity: 'error',
    route,
    reason: 'process-dependent',
    message: processStatusMessage(outputFormat.label, requirement.processId, route, status),
    extensionId: outputFormat.extensionId,
    contributionId: outputFormat.id,
    detail: {
      source: 'output-format',
      outputFormatId: outputFormat.id,
      outputLabel: outputFormat.label,
      processId: requirement.processId,
      operationId: requirement.operationId,
      requiredCapabilities: [...requirement.requiredCapabilities].sort(),
      processState: status?.state ?? 'unknown',
    },
  };
}

function routeRequirementBlocker(
  outputFormat: VideoEditorOutputFormatDescriptor,
  routeRequirement: VideoEditorRouteRequirementDescriptor,
  route: RenderRoute,
  status?: ProcessStatus,
): RenderBlocker | undefined {
  if (!routeRequirement.processId && routeRequirement.requiredCapabilities.length === 0) return undefined;
  if (!routeRequirement.processId) return undefined;

  return {
    id: `planner.outputFormat.${outputFormat.extensionId}.${outputFormat.id}.${route}.${routeRequirement.processId}.route-process-dependent`,
    severity: 'error',
    route,
    reason: 'process-dependent',
    message: routeRequirement.unavailableMessage
      ?? processStatusMessage(outputFormat.label, routeRequirement.processId, route, status),
    extensionId: outputFormat.extensionId,
    contributionId: outputFormat.id,
    detail: {
      source: 'output-format',
      outputFormatId: outputFormat.id,
      outputLabel: outputFormat.label,
      processId: routeRequirement.processId,
      operationId: routeRequirement.operationId,
      requiredCapabilities: [...routeRequirement.requiredCapabilities].sort(),
      determinism: routeRequirement.determinism,
      processState: status?.state ?? 'unknown',
    },
  };
}

function processStatusMessage(
  outputLabel: string,
  processId: string,
  route: RenderRoute,
  status?: ProcessStatus,
): string {
  if (!status) return `Output format "${outputLabel}" requires process "${processId}" before ${route} can run.`;
  if (status.message) return status.message;
  return `Process "${processId}" is ${status.state} for ${route}.`;
}

function processStatusBlocks(status: ProcessStatus | undefined): boolean {
  if (!status) return true;
  return status.state !== 'ready' && status.state !== 'degraded';
}

function processStatusDegraded(status: ProcessStatus | undefined): boolean {
  return status?.state === 'degraded';
}

function processStatusWarning(
  blocker: RenderBlocker,
  status: ProcessStatus,
): CapabilityFinding {
  return {
    ...blocker,
    id: `${blocker.id}.degraded`,
    severity: 'warning',
    message: processStatusMessage(
      String(blocker.detail?.outputLabel ?? blocker.contributionId ?? 'output'),
      status.processId,
      blocker.route,
      status,
    ),
    detail: {
      ...blocker.detail,
      processState: status.state,
      diagnostics: status.diagnostics,
    },
  };
}

function collectOutputFormat(
  acc: PlanAccumulator,
  outputFormat: VideoEditorOutputFormatDescriptor,
  processStatusById: ReadonlyMap<string, ProcessStatus>,
): void {
  const availableRoutes = outputFormat.availableRoutes.length > 0
    ? outputFormat.availableRoutes
    : (outputFormat.requiresRender ? (['sidecar-export'] as const) : ([] as const));

  for (const route of availableRoutes) {
    addRouteSetValue(acc.routeOutputFormatIds, route, outputFormat.id);
  }

  for (const requirement of outputFormat.capabilities?.capabilityRequirements ?? []) {
    collectRequirement(acc, requirement);
  }

  for (const routeRequirement of outputFormat.routeRequirements) {
    for (const route of routeRequirement.routes) {
      addRouteValue(acc.routeDeterminism, route, routeRequirement.determinism);
      for (const capability of routeRequirement.requiredCapabilities) {
        addRouteSetValue(acc.routeCapabilities, route, capability);
      }
      const status = routeRequirement.processId ? processStatusById.get(routeRequirement.processId) : undefined;
      const routeBlocker = routeRequirementBlocker(outputFormat, routeRequirement, route, status);
      if (routeBlocker && processStatusBlocks(status)) {
        acc.findings.push(routeBlocker);
        acc.blockers.push(routeBlocker);
      } else if (routeBlocker && status && processStatusDegraded(status)) {
        acc.findings.push(processStatusWarning(routeBlocker, status));
      }
    }
  }

  for (const requirement of outputFormat.processRequirements) {
    const routes = availableRoutes.length > 0 ? availableRoutes : RENDER_ROUTES;
    for (const route of routes) {
      addRouteValue(acc.routeProcessRequirements, route, requirement);
      const status = processStatusById.get(requirement.processId);
      const blocker = processRequirementBlocker(outputFormat, route, requirement, status);
      if (processStatusBlocks(status)) {
        acc.findings.push(blocker);
        acc.blockers.push(blocker);
      } else if (status && processStatusDegraded(status)) {
        acc.findings.push(processStatusWarning(blocker, status));
      }
    }
  }

  for (const blocker of outputFormat.blockers) {
    collectDescriptorBlocker(acc, blocker, availableRoutes[0] ?? 'sidecar-export', 'output-format');
  }
  acc.nextActions.push(...outputFormat.nextActions);
}

function collectRequestedOutputRouteSupport(
  acc: PlanAccumulator,
  outputFormat: VideoEditorOutputFormatDescriptor | undefined,
  request: RenderPlannerRequest | undefined,
): void {
  if (!outputFormat) return;
  const routes = requestedRoutes(request);
  if (routes.length === 0) return;

  const availableRoutes = outputFormat.availableRoutes.length > 0
    ? outputFormat.availableRoutes
    : (outputFormat.requiresRender ? ([] as const) : (['browser-export'] as const));
  const available = new Set(availableRoutes);

  for (const route of routes) {
    if (available.has(route)) continue;
    const blocker: RenderBlocker = {
      id: `planner.outputFormat.${outputFormat.extensionId}.${outputFormat.id}.${route}.route-unsupported`,
      severity: 'error',
      route,
      reason: 'route-unsupported',
      message: `Output format "${outputFormat.label}" is not available on ${route}.`,
      extensionId: outputFormat.extensionId,
      contributionId: outputFormat.id,
      detail: {
        source: 'render-request',
        outputFormatId: outputFormat.id,
        requestedRoute: route,
        availableRoutes: [...availableRoutes].sort(),
      },
    };
    acc.findings.push(blocker);
    acc.blockers.push(blocker);
  }
}

function collectProcess(acc: PlanAccumulator, process: VideoEditorProcessDescriptor): void {
  for (const route of process.availableRoutes) {
    addRouteSetValue(acc.routeCapabilities, route, process.processId);
  }
  for (const requirement of process.capabilities?.capabilityRequirements ?? []) {
    collectRequirement(acc, requirement);
  }
  for (const blocker of process.blockers) {
    collectDescriptorBlocker(acc, blocker, process.availableRoutes[0] ?? 'sidecar-export', 'process');
  }
  acc.nextActions.push(...process.nextActions);
}

function createProcessStatusMap(statuses: readonly ProcessStatus[] | undefined): ReadonlyMap<string, ProcessStatus> {
  return new Map((statuses ?? []).map((status) => [status.processId, status]));
}

function createMaterialStatusMap(
  statuses: readonly RenderPlannerMaterialStatus[] | undefined,
): ReadonlyMap<string, RenderPlannerMaterialStatus> {
  return new Map((statuses ?? []).map((status) => [status.materialRefId, status]));
}

function materializeAction(
  label: string,
  message: string,
): VideoEditorPlannerNextActionDescriptor {
  return {
    kind: 'resolve-blocker',
    label,
    route: 'browser-export',
    message,
  };
}

function materialBlockerReason(
  materialRef: RenderMaterialRef,
  status: RenderPlannerMaterialStatus | undefined,
): RenderBlockerReason | undefined {
  if (status?.state === 'missing') return 'missing-material';
  if (status?.state === 'stale') return 'materialization-failed';
  if (status?.state === 'resolved') return undefined;
  if (status?.state === 'unbaked') return materialRef.determinism;
  if (materialRef.determinism === 'live-unbaked' || materialRef.determinism === 'process-dependent') {
    return materialRef.determinism;
  }
  return undefined;
}

function collectMaterialRef(
  acc: PlanAccumulator,
  materialRef: RenderMaterialRef,
  materialStatusById: ReadonlyMap<string, RenderPlannerMaterialStatus>,
): void {
  addRouteValue(acc.routeDeterminism, 'browser-export', materialRef.determinism);
  if (materialRef.replacementPolicy !== 'materialize-on-export') return;

  const status = materialStatusById.get(materialRef.id);
  const reason = materialBlockerReason(materialRef, status);
  if (!reason) return;
  const message = status?.message ?? `Material "${materialRef.id}" must be materialized before browser export.`;
  const blocker: RenderBlocker = {
    id: `planner.material.${materialRef.id}.browser-export.${reason}`,
    severity: 'error',
    route: 'browser-export',
    reason,
    message,
    materialRefId: materialRef.id,
    extensionId: materialRef.producerExtensionId,
    detail: {
      source: 'material-ref',
      mediaKind: materialRef.mediaKind,
      locatorKind: materialRef.locator.kind,
      replacementPolicy: materialRef.replacementPolicy,
      determinism: materialRef.determinism,
      materialState: status?.state ?? 'unbaked',
    },
  };
  acc.findings.push(blocker);
  acc.blockers.push(blocker);
  acc.nextActions.push(materializeAction(`Materialize ${materialRef.id}`, message));
}

function collectRenderGroups(acc: PlanAccumulator, snapshot: TimelineSnapshot | null | undefined): void {
  for (const group of snapshot?.renderGroups ?? []) {
    for (const pass of group.passes ?? []) {
      if (!pass.required) continue;
      if (pass.status !== 'missing' && pass.status !== 'stale') continue;

      const reason: RenderBlockerReason = pass.status === 'missing'
        ? 'missing-material'
        : 'materialization-failed';
      const message = `Render group "${group.id}" pass "${pass.passName}" is ${pass.status}.`;
      const blocker: RenderBlocker = {
        id: `planner.renderGroup.${group.id}.${pass.id}.browser-export.${reason}`,
        severity: 'error',
        route: 'browser-export',
        reason,
        message,
        materialRefId: pass.materialRefId,
        detail: {
          source: 'render-group',
          renderGroupId: group.id,
          passId: pass.id,
          passName: pass.passName,
          passStatus: pass.status,
          composable: pass.composable,
          required: pass.required,
        },
      };
      addRouteSetValue(acc.routeCapabilities, 'browser-export', 'render-groups');
      addRouteValue(acc.routeDeterminism, 'browser-export', 'process-dependent');
      acc.findings.push(blocker);
      acc.blockers.push(blocker);
      acc.nextActions.push(materializeAction(`Materialize ${group.id}:${pass.passName}`, message));
    }
  }
}

function mostConservativeDeterminism(statuses: readonly DeterminismStatus[]): DeterminismStatus {
  if (statuses.length === 0) return 'deterministic';
  return [...statuses].sort((a, b) => DETERMINISM_RANK[b] - DETERMINISM_RANK[a])[0];
}

function sortedActions(
  actions: readonly VideoEditorPlannerNextActionDescriptor[],
): readonly VideoEditorPlannerNextActionDescriptor[] {
  const seen = new Set<string>();
  return Object.freeze([...actions]
    .sort((a, b) =>
      `${a.kind}:${a.route ?? ''}:${a.processId ?? ''}:${a.operationId ?? ''}:${a.label}`
        .localeCompare(`${b.kind}:${b.route ?? ''}:${b.processId ?? ''}:${b.operationId ?? ''}:${b.label}`))
    .filter((action) => {
      const key = `${action.kind}:${action.route ?? ''}:${action.processId ?? ''}:${action.operationId ?? ''}:${action.label}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map((action) => Object.freeze({ ...action })));
}

function buildRoutePlan(
  route: RenderRoute,
  findings: readonly CapabilityFinding[],
  blockers: readonly RenderBlocker[],
  acc: PlanAccumulator,
): RenderRoutePlan {
  const routeBlockers = blockers.filter((blocker) => blocker.route === route);
  const routeFindings = findings.filter((finding) => !finding.route || finding.route === route);
  const requiredCapabilities = Object.freeze([...(acc.routeCapabilities.get(route) ?? new Set())].sort());
  const outputFormatIds = Object.freeze([...(acc.routeOutputFormatIds.get(route) ?? new Set())].sort());
  const processRequirements = Object.freeze([...(acc.routeProcessRequirements.get(route) ?? [])]
    .sort((a, b) =>
      `${a.processId}:${a.operationId ?? ''}:${a.requiredCapabilities.join(',')}`
        .localeCompare(`${b.processId}:${b.operationId ?? ''}:${b.requiredCapabilities.join(',')}`))
    .map((requirement) => Object.freeze({
      ...requirement,
      requiredCapabilities: Object.freeze([...requirement.requiredCapabilities].sort()),
    })));

  const actions = sortedActions(acc.nextActions.filter((action) => !action.route || action.route === route));
  return Object.freeze({
    route,
    blockerCount: routeBlockers.length,
    findingCount: routeFindings.length,
    blocked: routeBlockers.length > 0,
    requiredCapabilities,
    determinism: mostConservativeDeterminism(acc.routeDeterminism.get(route) ?? []),
    blockers: Object.freeze(routeBlockers),
    diagnostics: Object.freeze(routeFindings),
    outputFormatIds,
    processRequirements,
    nextActions: actions,
  });
}

function emptyGuard(
  findings: readonly CapabilityFinding[],
  blockers: readonly RenderBlocker[],
): RenderPlannerGuardCompatibility {
  return Object.freeze({
    diagnostics: findings,
    findings,
    blockers,
    unknownClipTypes: Object.freeze([]),
    unknownEffects: Object.freeze([]),
    unknownTransitions: Object.freeze([]),
    inactiveExtensionIds: EMPTY_IDS,
    hasBlockingErrors: blockers.length > 0,
  });
}

export function planRender(input: RenderPlannerInput): RenderPlannerResult {
  const acc = createAccumulator();
  const compositionGraph = plannerCompositionGraph(input);
  const nonShaderSnapshot = compositionGraph ? stripSnapshotShaders(input.snapshot) : input.snapshot;
  const shaderComposition = diagnoseSnapshotShaderComposition(
    input.snapshot,
    input.extensionRuntime?.contributionIndex,
    compositionGraph,
  );
  const requirements = compositionGraph
    ? [
        ...(input.requirements
          ?? (nonShaderSnapshot
            ? getCapabilityRequirements(nonShaderSnapshot)
            : [])),
        ...graphShaderMaterializerRequirements(shaderComposition.shaders, compositionGraph),
      ]
    : (input.requirements ?? (shaderComposition.snapshot
      ? getCapabilityRequirements(shaderComposition.snapshot)
      : []));
  const outputFormats = input.outputFormats ?? input.extensionRuntime?.outputFormats ?? [];
  const processes = input.processes ?? input.extensionRuntime?.processes ?? [];
  const shaders = input.shaders ?? input.extensionRuntime?.shaders ?? [];
  const processStatusById = createProcessStatusMap(input.processStatuses);
  const processById = createProcessDescriptorMap(processes);
  const shaderBySourceRef = createShaderDescriptorMap(shaders);
  const materialStatusById = createMaterialStatusMap(input.materialStatuses);
  const legacyCompatibilityWarning = legacyGraphCompatibilityWarning(
    input.snapshot,
    requirements,
    compositionGraph,
  );
  const requestedOutputFormat = input.request?.outputFormatId
    ? outputFormats.find((format) => format.id === input.request?.outputFormatId)
    : undefined;

  for (const requirement of requirements) {
    const shaderDescriptor = isShaderMaterializerRequirement(requirement)
      ? shaderBySourceRef.get(shaderDescriptorKey(
        requirement.sourceRef.extensionId,
        requirement.sourceRef.contributionId,
      ))
      : undefined;
    if (
      shaderDescriptor
      && shaderMaterializerSupportsRoute(shaderDescriptor, requirement, processById)
    ) {
      collectShaderMaterializerRequirement(acc, requirement, shaderDescriptor, processStatusById);
      continue;
    }
    collectRequirement(acc, requirement);
  }
  collectRequestCapabilities(acc, input.request);
  for (const outputFormat of outputFormats) {
    if (input.request?.outputFormatId && input.request.outputFormatId !== outputFormat.id) continue;
    collectOutputFormat(acc, outputFormat, processStatusById);
  }
  collectRequestedOutputRouteSupport(acc, requestedOutputFormat, input.request);
  for (const process of processes) {
    collectProcess(acc, process);
  }
  for (const materialRef of input.materialRefs ?? []) {
    collectMaterialRef(acc, materialRef, materialStatusById);
  }
  collectRenderGroups(acc, input.snapshot);
  acc.findings.push(...shaderComposition.findings);
  if (legacyCompatibilityWarning) {
    acc.findings.push(legacyCompatibilityWarning);
  }
  acc.findings.push(...(input.diagnostics ?? []));

  if (input.request?.outputFormatId && !outputFormats.some((format) => format.id === input.request?.outputFormatId)) {
    const blocker: RenderBlocker = {
      id: `planner.outputFormat.${input.request.outputFormatId}.missing`,
      severity: 'error',
      route: input.request.route ?? input.request.routes?.[0] ?? 'sidecar-export',
      reason: 'missing-contribution',
      message: `Output format "${input.request.outputFormatId}" is not registered.`,
      contributionId: input.request.outputFormatId,
      detail: {
        source: 'render-request',
        outputFormatId: input.request.outputFormatId,
      },
    };
    acc.findings.push(blocker);
    acc.blockers.push(blocker);
  }

  const findings = sortedFindings(acc.findings);
  const blockers = sortedBlockers([
    ...acc.blockers,
    ...findings.map(blockerForFinding).filter((blocker): blocker is RenderBlocker => Boolean(blocker)),
  ]);
  const routePlans = Object.freeze(RENDER_ROUTES.map((route) => buildRoutePlan(route, findings, blockers, acc)));
  const routes = Object.freeze(routePlans.map((routePlan) => Object.freeze({
    route: routePlan.route,
    blockerCount: routePlan.blockerCount,
    findingCount: routePlan.findingCount,
    blocked: routePlan.blocked,
  })));
  const browserRoute = routePlans.find((route) => route.route === 'browser-export');
  const workerRoute = routePlans.find((route) => route.route === 'worker-export');

  return Object.freeze({
    guard: emptyGuard(findings, blockers),
    findings,
    blockers,
    routes,
    routePlans,
    diagnostics: findings,
    nextActions: sortedActions(acc.nextActions),
    canBrowserExport: !browserRoute?.blocked,
    canWorkerExport: !workerRoute?.blocked,
  });
}
