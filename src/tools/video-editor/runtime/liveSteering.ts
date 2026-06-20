/**
 * M11 live steering resolver.
 *
 * The resolver is pure: it classifies a proposed GenerationSession
 * reconfiguration into an explicit supersede, fork, or reject decision and
 * returns the activation diagnostics Step 15 must honor before sample delivery.
 */

import type {
  LiveChannelDescriptor,
  LiveSourceDiagnostic,
  SteeringDecision,
  SteeringDecisionKind,
  SteeringLineage,
  SteeringParameterChange,
  SteeringParameterHotness,
  SteeringPriorSamplePolicy,
  SteeringProvenance,
} from '@reigh/editor-sdk';

export interface LiveSteeringParameterDefinition {
  readonly path: string;
  readonly hotness: SteeringParameterHotness;
}

export interface LiveSteeringRequest {
  readonly sessionId: string;
  readonly currentGenerationIndex: number;
  readonly parentRefs?: readonly string[];
  readonly previousLineage?: SteeringLineage;
  readonly producerVersion: string;
  readonly provenance: SteeringProvenance;
  readonly changes: readonly SteeringParameterChange[];
  readonly parameters?: readonly LiveSteeringParameterDefinition[];
  readonly priorSamplePolicy: SteeringPriorSamplePolicy;
  readonly currentChannelId?: LiveChannelDescriptor;
  readonly replacementChannelId?: LiveChannelDescriptor;
  readonly reason?: string;
}

export interface LiveSteeringResolution {
  readonly decision: SteeringDecision;
  readonly diagnostics: readonly LiveSourceDiagnostic[];
  readonly priorSamplePolicy: SteeringPriorSamplePolicy;
  readonly hotChanges: readonly SteeringParameterChange[];
  readonly nonHotChanges: readonly SteeringParameterChange[];
  readonly canActivateLiveDelivery: boolean;
}

export interface GenerationSessionLiveDeliveryGate {
  readonly canActivate: boolean;
  readonly diagnostics: readonly LiveSourceDiagnostic[];
}

const DECISION_KINDS = new Set<SteeringDecisionKind>(['supersede', 'fork', 'reject']);
const PRIOR_SAMPLE_POLICIES = new Set<SteeringPriorSamplePolicy>([
  'replace',
  'fork',
  'retain',
  'discard',
]);

export function resolveLiveSteering(request: LiveSteeringRequest): LiveSteeringResolution {
  const diagnostics: LiveSourceDiagnostic[] = [];
  const definitions = new Map((request.parameters ?? []).map((param) => [param.path, param]));
  const classified = classifyChanges(request.changes, definitions, request.sessionId, diagnostics);

  validateRequestShape(request, diagnostics);

  const hasErrors = diagnostics.some((diagnostic) => diagnostic.severity === 'error');
  const kind = hasErrors
    ? 'reject'
    : chooseDecisionKind(request, classified.hotChanges, classified.nonHotChanges, diagnostics);
  const lineage = createLineage(request, kind);
  const decision: SteeringDecision = {
    kind,
    sessionId: request.sessionId,
    lineage,
    reason: request.reason ?? defaultReason(kind, request.priorSamplePolicy, diagnostics),
    replacementChannelId: kind === 'supersede' ? request.replacementChannelId ?? request.currentChannelId : undefined,
  };

  const gate = evaluateGenerationSessionLiveDeliveryGate(decision, diagnostics);

  return Object.freeze({
    decision,
    diagnostics: Object.freeze([...diagnostics]),
    priorSamplePolicy: request.priorSamplePolicy,
    hotChanges: Object.freeze([...classified.hotChanges]),
    nonHotChanges: Object.freeze([...classified.nonHotChanges]),
    canActivateLiveDelivery: gate.canActivate,
  });
}

export function evaluateGenerationSessionLiveDeliveryGate(
  decision: SteeringDecision | undefined,
  existingDiagnostics: readonly LiveSourceDiagnostic[] = [],
): GenerationSessionLiveDeliveryGate {
  const diagnostics = [...existingDiagnostics];

  if (!decision) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/steering-missing-decision',
      'GenerationSession live delivery requires an explicit steering decision before activation.',
    ));
    return { canActivate: false, diagnostics: Object.freeze(diagnostics) };
  }

  diagnostics.push(...validateSteeringDecision(decision));

  if (decision.kind === 'reject') {
    diagnostics.push(createDiagnostic(
      'error',
      'live/steering-rejected',
      `GenerationSession "${decision.sessionId}" cannot activate live delivery after a reject decision.`,
      undefined,
      { sessionId: decision.sessionId },
    ));
  }

  return {
    canActivate: !diagnostics.some((diagnostic) => diagnostic.severity === 'error'),
    diagnostics: Object.freeze(diagnostics),
  };
}

export function validateSteeringDecision(decision: SteeringDecision): readonly LiveSourceDiagnostic[] {
  const diagnostics: LiveSourceDiagnostic[] = [];

  if (!DECISION_KINDS.has(decision.kind)) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/steering-invalid-decision',
      'Steering decision kind must be supersede, fork, or reject.',
      undefined,
      { kind: decision.kind },
    ));
  }

  if (!isNonEmptyString(decision.sessionId)) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/steering-invalid-session',
      'Steering decision requires a non-empty sessionId.',
    ));
  }

  diagnostics.push(...validateLineage(decision.lineage, decision.sessionId));

  if (decision.kind === 'supersede' && !isNonEmptyString(decision.replacementChannelId)) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/steering-missing-replacement-channel',
      'Supersede steering decisions require a replacement channel before live sample delivery can activate.',
      undefined,
      { sessionId: decision.sessionId },
    ));
  }

  return Object.freeze(diagnostics);
}

function classifyChanges(
  changes: readonly SteeringParameterChange[],
  definitions: ReadonlyMap<string, LiveSteeringParameterDefinition>,
  sessionId: string,
  diagnostics: LiveSourceDiagnostic[],
): {
  readonly hotChanges: SteeringParameterChange[];
  readonly nonHotChanges: SteeringParameterChange[];
} {
  const hotChanges: SteeringParameterChange[] = [];
  const nonHotChanges: SteeringParameterChange[] = [];

  if (changes.length === 0) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/steering-no-changes',
      'Steering requires at least one parameter change.',
      undefined,
      { sessionId },
    ));
    return { hotChanges, nonHotChanges };
  }

  for (const change of changes) {
    const definition = definitions.get(change.path);
    const hotness = change.hotness ?? definition?.hotness;

    if (!isNonEmptyString(change.path)) {
      diagnostics.push(createDiagnostic(
        'error',
        'live/steering-invalid-change',
        'Steering parameter changes require a non-empty path.',
        undefined,
        { sessionId, change },
      ));
      continue;
    }

    if (!definition && change.hotness === undefined) {
      diagnostics.push(createDiagnostic(
        'error',
        'live/steering-unsupported-param',
        `Steering parameter "${change.path}" is not declared as hot or non-hot.`,
        undefined,
        { sessionId, path: change.path },
      ));
      continue;
    }

    if (hotness !== 'hot' && hotness !== 'non-hot') {
      diagnostics.push(createDiagnostic(
        'error',
        'live/steering-missing-hotness',
        `Steering parameter "${change.path}" is missing a valid hotness classification.`,
        undefined,
        { sessionId, path: change.path, hotness },
      ));
      continue;
    }

    if (Object.is(change.previousValue, change.nextValue)) {
      diagnostics.push(createDiagnostic(
        'warning',
        'live/steering-no-op-change',
        `Steering parameter "${change.path}" did not change value.`,
        undefined,
        { sessionId, path: change.path },
      ));
    }

    if (hotness === 'hot') {
      hotChanges.push({ ...change, hotness });
    } else {
      nonHotChanges.push({ ...change, hotness });
    }
  }

  return { hotChanges, nonHotChanges };
}

function validateRequestShape(
  request: LiveSteeringRequest,
  diagnostics: LiveSourceDiagnostic[],
): void {
  if (!isNonEmptyString(request.sessionId)) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/steering-invalid-session',
      'Steering requests require a non-empty sessionId.',
    ));
  }

  if (!Number.isInteger(request.currentGenerationIndex) || request.currentGenerationIndex < 0) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/steering-invalid-generation-index',
      'Steering requests require a finite non-negative generation index.',
      undefined,
      { sessionId: request.sessionId, currentGenerationIndex: request.currentGenerationIndex },
    ));
  }

  if (!isNonEmptyString(request.producerVersion)) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/steering-missing-producer-version',
      'Steering lineage requires a producer version.',
      undefined,
      { sessionId: request.sessionId },
    ));
  }

  if (!PRIOR_SAMPLE_POLICIES.has(request.priorSamplePolicy)) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/steering-invalid-prior-sample-policy',
      'Steering requires an explicit prior-sample policy.',
      undefined,
      { sessionId: request.sessionId, priorSamplePolicy: request.priorSamplePolicy },
    ));
  }

  validateParentRefs(request.parentRefs, request.sessionId, diagnostics);
  validateProvenance(request.provenance, request.sessionId, diagnostics);
}

function chooseDecisionKind(
  request: LiveSteeringRequest,
  hotChanges: readonly SteeringParameterChange[],
  nonHotChanges: readonly SteeringParameterChange[],
  diagnostics: LiveSourceDiagnostic[],
): SteeringDecisionKind {
  if (nonHotChanges.length > 0) {
    if (request.priorSamplePolicy === 'fork') {
      return 'fork';
    }
    diagnostics.push(createDiagnostic(
      'error',
      'live/steering-non-hot-requires-fork',
      'Non-hot steering changes require an explicit fork prior-sample policy.',
      undefined,
      {
        sessionId: request.sessionId,
        priorSamplePolicy: request.priorSamplePolicy,
        paths: nonHotChanges.map((change) => change.path),
      },
    ));
    return 'reject';
  }

  if (hotChanges.length > 0 && request.priorSamplePolicy === 'replace') {
    return 'supersede';
  }

  if (hotChanges.length > 0 && request.priorSamplePolicy === 'fork') {
    return 'fork';
  }

  diagnostics.push(createDiagnostic(
    'error',
    'live/steering-invalid-prior-sample-policy',
    'Hot steering changes must explicitly replace prior samples or fork; retain/discard cannot activate live delivery.',
    undefined,
    { sessionId: request.sessionId, priorSamplePolicy: request.priorSamplePolicy },
  ));
  return 'reject';
}

function createLineage(request: LiveSteeringRequest, kind: SteeringDecisionKind): SteeringLineage {
  const parentRefs = normalizeParentRefs(request);
  const generationIndex = kind === 'reject'
    ? request.currentGenerationIndex
    : request.currentGenerationIndex + 1;
  const provenance = normalizeProvenance(request.provenance);
  const tags = createProvenanceTags(request, kind, provenance);
  const steerHash = stableHash({
    kind,
    sessionId: request.sessionId,
    generationIndex,
    parentRefs,
    producerVersion: request.producerVersion,
    provenance,
    changes: request.changes,
    priorSamplePolicy: request.priorSamplePolicy,
    previousSteerHash: request.previousLineage?.steerHash,
    currentChannelId: request.currentChannelId,
    replacementChannelId: request.replacementChannelId,
  });

  return Object.freeze({
    generationIndex,
    steerHash,
    parentRefs: Object.freeze(parentRefs),
    producerVersion: request.producerVersion,
    provenance,
    provenanceTags: Object.freeze(tags),
  });
}

function normalizeParentRefs(request: LiveSteeringRequest): readonly string[] {
  const refs = request.parentRefs && request.parentRefs.length > 0
    ? request.parentRefs
    : [request.sessionId, ...(request.previousLineage?.parentRefs ?? [])];
  return Array.from(new Set(refs.filter(isNonEmptyString))).sort();
}

function normalizeProvenance(provenance: SteeringProvenance): SteeringProvenance {
  return Object.freeze({
    prompt: typeof provenance?.prompt === 'string' ? provenance.prompt : '',
    model: typeof provenance?.model === 'string' ? provenance.model : '',
    seed: typeof provenance?.seed === 'number' || typeof provenance?.seed === 'string'
      ? provenance.seed
      : '',
    producerExtensionId: typeof provenance?.producerExtensionId === 'string'
      ? provenance.producerExtensionId
      : undefined,
    tags: provenance?.tags ? Object.freeze([...provenance.tags]) : undefined,
  });
}

function createProvenanceTags(
  request: LiveSteeringRequest,
  kind: SteeringDecisionKind,
  provenance: SteeringProvenance,
): readonly string[] {
  return Array.from(new Set([
    ...(provenance.tags ?? []),
    `steering:${kind}`,
    `prior-samples:${request.priorSamplePolicy}`,
    `prompt:${stableHash(provenance.prompt)}`,
    `model:${provenance.model}`,
    `seed:${String(provenance.seed)}`,
    ...(provenance.producerExtensionId ? [`producer:${provenance.producerExtensionId}`] : []),
  ])).sort();
}

function validateParentRefs(
  parentRefs: readonly string[] | undefined,
  sessionId: string,
  diagnostics: LiveSourceDiagnostic[],
): void {
  if (!parentRefs) return;
  const invalid = parentRefs.filter((ref) => !isNonEmptyString(ref));
  if (invalid.length > 0) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/steering-invalid-parent-ref',
      'Steering parent refs must be non-empty strings.',
      undefined,
      { sessionId, invalid },
    ));
  }
}

function validateProvenance(
  provenance: SteeringProvenance | undefined,
  sessionId: string,
  diagnostics: LiveSourceDiagnostic[],
): void {
  if (!provenance) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/steering-missing-provenance',
      'Steering lineage requires prompt, model, and seed provenance.',
      undefined,
      { sessionId },
    ));
    return;
  }

  const missing: string[] = [];
  if (!isNonEmptyString(provenance.prompt)) missing.push('prompt');
  if (!isNonEmptyString(provenance.model)) missing.push('model');
  if (!isValidSeed(provenance.seed)) missing.push('seed');

  if (missing.length > 0) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/steering-incomplete-provenance',
      'Steering lineage requires prompt, model, and seed provenance.',
      undefined,
      { sessionId, missing },
    ));
  }
}

function validateLineage(lineage: SteeringLineage | undefined, sessionId: string): readonly LiveSourceDiagnostic[] {
  const diagnostics: LiveSourceDiagnostic[] = [];

  if (!lineage) {
    return [createDiagnostic(
      'error',
      'live/steering-missing-lineage',
      'Steering decisions require complete lineage metadata.',
      undefined,
      { sessionId },
    )];
  }

  if (!Number.isInteger(lineage.generationIndex) || lineage.generationIndex < 0) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/steering-invalid-generation-index',
      'Steering lineage requires a finite non-negative generation index.',
      undefined,
      { sessionId, generationIndex: lineage.generationIndex },
    ));
  }

  if (!isNonEmptyString(lineage.steerHash)) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/steering-missing-hash',
      'Steering lineage requires a non-empty steer hash.',
      undefined,
      { sessionId },
    ));
  }

  if (!lineage.parentRefs || lineage.parentRefs.length === 0 || lineage.parentRefs.some((ref) => !isNonEmptyString(ref))) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/steering-invalid-parent-ref',
      'Steering lineage requires at least one valid parent ref.',
      undefined,
      { sessionId, parentRefs: lineage.parentRefs },
    ));
  }

  if (!isNonEmptyString(lineage.producerVersion)) {
    diagnostics.push(createDiagnostic(
      'error',
      'live/steering-missing-producer-version',
      'Steering lineage requires a producer version.',
      undefined,
      { sessionId },
    ));
  }

  validateProvenance(lineage.provenance, sessionId, diagnostics);

  return Object.freeze(diagnostics);
}

function defaultReason(
  kind: SteeringDecisionKind,
  policy: SteeringPriorSamplePolicy,
  diagnostics: readonly LiveSourceDiagnostic[],
): string {
  if (kind === 'reject') {
    const firstError = diagnostics.find((diagnostic) => diagnostic.severity === 'error');
    return firstError?.message ?? 'Steering change rejected.';
  }
  if (kind === 'fork') return `Steering change forks prior samples with policy "${policy}".`;
  return `Steering change supersedes prior samples with policy "${policy}".`;
}

function createDiagnostic(
  severity: LiveSourceDiagnostic['severity'],
  code: string,
  message: string,
  sourceId?: string,
  detail?: Record<string, unknown>,
): LiveSourceDiagnostic {
  return { severity, code, message, sourceId, detail };
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0;
}

function isValidSeed(value: unknown): value is string | number {
  return (typeof value === 'string' && value.length > 0)
    || (typeof value === 'number' && Number.isFinite(value));
}

function stableHash(value: unknown): string {
  const text = JSON.stringify(sortObject(value));
  let hash = 0x811c9dc5;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return `fnv1a-${(hash >>> 0).toString(16).padStart(8, '0')}`;
}

function sortObject(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(sortObject);
  }
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    return Object.keys(record).sort().reduce<Record<string, unknown>>((acc, key) => {
      acc[key] = sortObject(record[key]);
      return acc;
    }, {});
  }
  return value;
}
