import type {
  CapabilityFinding,
  RenderArtifact,
  RenderArtifactSidecarDescriptor,
  RenderMaterial,
  RenderMaterialRef,
  RenderMaterialStatus,
} from '@reigh/editor-sdk';
import type {
  ProcessLogSummary,
  ProcessProgressEvent,
  ProcessRoundtripAction,
  ProcessRoundtripResult,
} from '@/sdk/capabilities';
import type { VideoEditorProcessDescriptor } from '@/tools/video-editor/runtime/extensionSurface.ts';
import {
  createRenderArtifactManifest,
  inferRenderArtifactManifestProfile,
  normalizeRenderArtifactSidecars,
} from '@/tools/video-editor/runtime/renderability.ts';

export const PROCESS_RESULT_ATTACH_KIND = 'process.result.attach' as const;
export const PROCESS_RESULT_ATTACH_ALIAS_KIND = 'process.attach-result' as const;

export type ProcessResultAttachInputKind =
  | typeof PROCESS_RESULT_ATTACH_KIND
  | typeof PROCESS_RESULT_ATTACH_ALIAS_KIND;

export interface ProcessResultAttachProvenance {
  readonly attachedAt: string;
  readonly attachedBy: 'host-runtime';
  readonly inputKind: ProcessResultAttachInputKind;
  readonly descriptor: {
    readonly descriptorId: string;
    readonly extensionId: string;
    readonly processId: string;
    readonly protocol: VideoEditorProcessDescriptor['protocol'];
    readonly version?: VideoEditorProcessDescriptor['spec']['version'];
    readonly requiredBy: readonly VideoEditorProcessDescriptor['requiredBy'][number][];
  };
  readonly operation: {
    readonly id: string;
    readonly label: string;
    readonly routes: readonly string[];
    readonly outputKinds: readonly string[];
    readonly requiredCapabilities: readonly string[];
    readonly determinism?: VideoEditorProcessDescriptor['operations'][number]['determinism'];
  };
  readonly result: {
    readonly requestId: string;
    readonly taskId: string;
    readonly processId: string;
    readonly operationId: string;
    readonly status: ProcessRoundtripResult['status'];
  };
  readonly upstream?: Record<string, unknown>;
}

export interface ProcessResultAttachRecord {
  readonly kind: typeof PROCESS_RESULT_ATTACH_KIND;
  readonly processRef: string;
  readonly processId: string;
  readonly operationId: string;
  readonly taskId: string;
  readonly status: ProcessRoundtripResult['status'];
  readonly returnedMaterialRefs: readonly string[];
  readonly returnedMaterials: readonly RenderMaterial[];
  readonly artifactRefs: readonly string[];
  readonly artifacts: readonly RenderArtifact[];
  readonly sidecars: readonly RenderArtifactSidecarDescriptor[];
  readonly diagnostics: readonly CapabilityFinding[];
  readonly logs: readonly ProcessLogSummary[];
  readonly progress?: ProcessProgressEvent;
  readonly availableActions: readonly ProcessRoundtripAction[];
  readonly metadata?: Record<string, unknown>;
  readonly provenance: ProcessResultAttachProvenance;
}

export interface CreateProcessResultAttachRecordOptions {
  readonly kind?: ProcessResultAttachInputKind;
  readonly processDescriptor: VideoEditorProcessDescriptor;
  readonly processRef?: string;
  readonly result: ProcessRoundtripResult;
  readonly taskId?: string;
  readonly attachedAt?: string;
  readonly upstreamProvenance?: Record<string, unknown>;
}

export interface ProjectProcessResultContractsOptions {
  readonly failedMaterialRefs?: readonly RenderMaterialRef[];
}

export interface ProcessResultContractProjection {
  readonly materialRefs: readonly RenderMaterialRef[];
  readonly materialStatuses: readonly RenderMaterialStatus[];
  readonly artifacts: readonly RenderArtifact[];
  readonly sidecars: readonly RenderArtifactSidecarDescriptor[];
}

export class ProcessResultAttachError extends Error {
  readonly code:
    | 'invalid-kind'
    | 'process-ref-mismatch'
    | 'descriptor-process-mismatch'
    | 'descriptor-operation-missing'
    | 'result-process-mismatch'
    | 'result-operation-mismatch'
    | 'result-task-mismatch'
    | 'timeline-mutation-forbidden';
  readonly processId?: string;
  readonly operationId?: string;
  readonly taskId?: string;

  constructor(
    message: string,
    options: {
      code: ProcessResultAttachError['code'];
      processId?: string;
      operationId?: string;
      taskId?: string;
      cause?: unknown;
    },
  ) {
    super(message, { cause: options.cause });
    this.name = 'ProcessResultAttachError';
    this.code = options.code;
    this.processId = options.processId;
    this.operationId = options.operationId;
    this.taskId = options.taskId;
  }
}

const FORBIDDEN_TIMELINE_MUTATION_FIELDS = Object.freeze([
  'operations',
  'patch',
  'timelinePatch',
  'timelinePlacement',
  'placement',
  'targetClipId',
  'targetTrackId',
  'insertBeforeClipId',
  'insertAfterClipId',
  'replaceClipId',
] as const);

function deepFreeze<T>(value: T): T {
  if (value === null || typeof value !== 'object' || Object.isFrozen(value)) {
    return value;
  }
  if (ArrayBuffer.isView(value)) {
    return value;
  }

  for (const nested of Object.values(value as Record<string, unknown>)) {
    deepFreeze(nested);
  }

  return Object.freeze(value);
}

function cloneFrozen<T>(value: T): T {
  return deepFreeze(structuredClone(value));
}

function mergeRecords(
  left?: Record<string, unknown>,
  right?: Record<string, unknown>,
): Record<string, unknown> | undefined {
  if (!left && !right) {
    return undefined;
  }
  return deepFreeze({
    ...(left ?? {}),
    ...(right ?? {}),
  });
}

function processAttachmentProvenance(
  record: ProcessResultAttachRecord,
): Record<string, unknown> {
  return deepFreeze({
    processRef: record.processRef,
    descriptorId: record.provenance.descriptor.descriptorId,
    extensionId: record.provenance.descriptor.extensionId,
    processId: record.processId,
    operationId: record.operationId,
    taskId: record.taskId,
    status: record.status,
    attachedAt: record.provenance.attachedAt,
    attachedBy: record.provenance.attachedBy,
    inputKind: record.provenance.inputKind,
    ...(record.provenance.descriptor.version
      ? { version: cloneFrozen(record.provenance.descriptor.version) }
      : {}),
  });
}

function mergeProcessProvenance(
  provenance: Record<string, unknown> | undefined,
  record: ProcessResultAttachRecord,
): Record<string, unknown> {
  const existing = provenance ? cloneFrozen(provenance) : undefined;
  const existingProcess = existing?.process;
  const processRecord = (existingProcess && typeof existingProcess === 'object' && !Array.isArray(existingProcess))
    ? existingProcess as Record<string, unknown>
    : undefined;

  return deepFreeze({
    ...(existing ?? {}),
    process: {
      ...(processRecord ?? {}),
      ...processAttachmentProvenance(record),
    },
  });
}

function normalizeMaterialRef(
  materialRef: RenderMaterialRef,
  record: ProcessResultAttachRecord,
): RenderMaterialRef {
  const version = record.provenance.descriptor.version?.semver;
  return deepFreeze({
    ...materialRef,
    producerExtensionId: materialRef.producerExtensionId ?? record.provenance.descriptor.extensionId,
    ...(materialRef.producerVersion ? {} : version ? { producerVersion: version } : {}),
    provenance: mergeProcessProvenance(materialRef.provenance, record),
  });
}

function normalizeSidecars(
  ...groups: readonly (readonly RenderArtifactSidecarDescriptor[] | undefined)[]
): readonly RenderArtifactSidecarDescriptor[] {
  const byKey = new Map<string, RenderArtifactSidecarDescriptor>();
  for (const group of groups) {
    for (const sidecar of group ?? []) {
      const key = sidecar.id ?? `${sidecar.kind}:${sidecar.filename}:${sidecar.mimeType}`;
      byKey.set(key, sidecar);
    }
  }
  return normalizeRenderArtifactSidecars([...byKey.values()]);
}

function deriveInputHashesFromMaterialRefs(
  materialRefs: readonly RenderMaterialRef[],
): Readonly<Record<string, string>> | undefined {
  const inputHashes: Record<string, string> = {};
  for (const materialRef of materialRefs) {
    const uri = materialRef.locator?.uri;
    const hash = materialRef.locator?.contentSha256;
    if (typeof uri === 'string' && uri.length > 0 && typeof hash === 'string' && hash.length > 0) {
      inputHashes[uri] = hash;
    }
  }
  return Object.keys(inputHashes).length > 0 ? Object.freeze(inputHashes) : undefined;
}

function buildMaterialStatus(
  materialRefId: string,
  state: RenderMaterialStatus['state'],
  updatedAt: string,
  message?: string,
): RenderMaterialStatus {
  return deepFreeze({
    materialRefId,
    state,
    updatedAt,
    ...(message ? { message } : {}),
  });
}

function normalizeArtifact(
  artifact: RenderArtifact,
  record: ProcessResultAttachRecord,
  materialRefsById: ReadonlyMap<string, RenderMaterialRef>,
  recordSidecars: readonly RenderArtifactSidecarDescriptor[],
): RenderArtifact {
  const consumedMaterialRefs = Object.freeze(
    artifact.consumedMaterialRefs.map((materialRef) => materialRefsById.get(materialRef.id) ?? materialRef),
  );
  const sidecars = normalizeSidecars(recordSidecars, artifact.sidecars);
  const version = record.provenance.descriptor.version?.semver;
  const producerExtensionId = artifact.producerExtensionId ?? record.provenance.descriptor.extensionId;
  const producerVersion = artifact.producerVersion ?? version;
  const profile = artifact.manifest?.profile ?? inferRenderArtifactManifestProfile({
    route: artifact.route,
    mediaKind: artifact.mediaKind,
    outputFormatId: artifact.manifest?.outputFormatId,
  });
  const inputHashes = artifact.manifest?.inputHashes ?? deriveInputHashesFromMaterialRefs(consumedMaterialRefs) ?? Object.freeze({});
  const manifest = createRenderArtifactManifest({
    id: artifact.manifest?.id,
    artifactId: artifact.id,
    route: artifact.route,
    determinism: artifact.determinism,
    ...(profile ? { profile } : {}),
    producerExtensionId,
    producerVersion,
    outputFormatId: artifact.manifest?.outputFormatId,
    processId: record.processId,
    processVersion: record.provenance.descriptor.version,
    operationId: record.operationId,
    locator: artifact.locator,
    mediaKind: artifact.mediaKind,
    consumedMaterialRefs,
    sidecars,
    diagnostics: artifact.manifest?.diagnostics ?? artifact.findings ?? record.diagnostics,
    provenance: mergeProcessProvenance(artifact.manifest?.provenance, record),
    inputHashes,
    renderGroupId: artifact.manifest?.renderGroupId,
    passName: artifact.manifest?.passName,
    createdAt: artifact.manifest?.createdAt ?? record.provenance.attachedAt,
    metadata: mergeRecords(artifact.manifest?.metadata, record.metadata),
  });

  return deepFreeze({
    ...artifact,
    producerExtensionId,
    ...(producerVersion ? { producerVersion } : {}),
    consumedMaterialRefs,
    ...(sidecars.length > 0 ? { sidecars } : {}),
    manifest,
  });
}

export function isProcessResultAttachKind(value: unknown): value is ProcessResultAttachInputKind {
  return value === PROCESS_RESULT_ATTACH_KIND || value === PROCESS_RESULT_ATTACH_ALIAS_KIND;
}

function normalizeKind(kind: unknown): ProcessResultAttachInputKind {
  if (kind === undefined) return PROCESS_RESULT_ATTACH_KIND;
  if (isProcessResultAttachKind(kind)) return kind;
  throw new ProcessResultAttachError('Process result attach kind must be "process.result.attach" or "process.attach-result".', {
    code: 'invalid-kind',
  });
}

export function assertNoTimelinePlacementMutation(value: Record<string, unknown>): void {
  for (const field of FORBIDDEN_TIMELINE_MUTATION_FIELDS) {
    if (!(field in value) || value[field] === undefined) continue;
    throw new ProcessResultAttachError(
      `Process result attach does not accept direct timeline placement mutation via "${field}".`,
      { code: 'timeline-mutation-forbidden' },
    );
  }
}

export function createProcessResultAttachRecord(
  options: CreateProcessResultAttachRecordOptions,
): ProcessResultAttachRecord {
  assertNoTimelinePlacementMutation(options as Record<string, unknown>);

  const kind = normalizeKind(options.kind);
  const descriptor = options.processDescriptor;
  const processRef = options.processRef ?? descriptor.id;
  const taskId = options.taskId ?? options.result.requestId;
  const result = options.result;

  if (processRef !== descriptor.id) {
    throw new ProcessResultAttachError(
      `Process ref "${processRef}" does not match declared descriptor "${descriptor.id}".`,
      {
        code: 'process-ref-mismatch',
        processId: descriptor.processId,
      },
    );
  }

  if (descriptor.processId !== descriptor.spec.id) {
    throw new ProcessResultAttachError(
      `Process descriptor "${descriptor.id}" declares mismatched process IDs "${descriptor.processId}" and "${descriptor.spec.id}".`,
      {
        code: 'descriptor-process-mismatch',
        processId: descriptor.processId,
      },
    );
  }

  if (result.processId !== descriptor.processId) {
    throw new ProcessResultAttachError(
      `Process result processId "${result.processId}" does not match declared process "${descriptor.processId}".`,
      {
        code: 'result-process-mismatch',
        processId: result.processId,
        operationId: result.operationId,
        taskId,
      },
    );
  }

  const operation = descriptor.operations.find((candidate) => candidate.id === options.result.operationId);
  if (!operation) {
    throw new ProcessResultAttachError(
      `Process "${descriptor.processId}" does not declare operation "${options.result.operationId}".`,
      {
        code: 'descriptor-operation-missing',
        processId: descriptor.processId,
        operationId: options.result.operationId,
        taskId,
      },
    );
  }

  if (options.result.operationId !== operation.id) {
    throw new ProcessResultAttachError(
      `Process result operationId "${options.result.operationId}" does not match declared operation "${operation.id}".`,
      {
        code: 'result-operation-mismatch',
        processId: descriptor.processId,
        operationId: options.result.operationId,
        taskId,
      },
    );
  }

  if (taskId !== result.requestId) {
    throw new ProcessResultAttachError(
      `Process result taskId "${taskId}" does not match result requestId "${result.requestId}".`,
      {
        code: 'result-task-mismatch',
        processId: descriptor.processId,
        operationId: operation.id,
        taskId,
      },
    );
  }

  const returnedMaterials = cloneFrozen(result.returnedMaterials);
  const artifacts = cloneFrozen(result.artifacts ?? []);
  const sidecars = cloneFrozen(result.sidecars ?? []);
  const diagnostics = cloneFrozen(result.diagnostics ?? []);
  const logs = cloneFrozen(result.logs ?? []);
  const availableActions = cloneFrozen(result.availableActions ?? []);
  const metadata = result.metadata ? cloneFrozen(result.metadata) : undefined;
  const progress = result.progress ? cloneFrozen(result.progress) : undefined;
  const upstreamProvenance = options.upstreamProvenance
    ? cloneFrozen(options.upstreamProvenance)
    : undefined;

  return deepFreeze({
    kind: PROCESS_RESULT_ATTACH_KIND,
    processRef,
    processId: descriptor.processId,
    operationId: operation.id,
    taskId,
    status: result.status,
    returnedMaterialRefs: cloneFrozen(returnedMaterials.map((material) => material.id)),
    returnedMaterials,
    artifactRefs: cloneFrozen(artifacts.map((artifact) => artifact.id)),
    artifacts,
    sidecars,
    diagnostics,
    logs,
    ...(progress ? { progress } : {}),
    availableActions,
    ...(metadata ? { metadata } : {}),
    provenance: {
      attachedAt: options.attachedAt ?? new Date().toISOString(),
      attachedBy: 'host-runtime',
      inputKind: kind,
      descriptor: {
        descriptorId: descriptor.id,
        extensionId: descriptor.extensionId,
        processId: descriptor.processId,
        protocol: descriptor.protocol,
        ...(descriptor.spec.version ? { version: cloneFrozen(descriptor.spec.version) } : {}),
        requiredBy: cloneFrozen(descriptor.requiredBy),
      },
      operation: {
        id: operation.id,
        label: operation.label,
        routes: cloneFrozen([...(operation.routes ?? [])]),
        outputKinds: cloneFrozen([...(operation.outputKinds ?? [])]),
        requiredCapabilities: cloneFrozen([...(operation.requiredCapabilities ?? [])]),
        ...(operation.determinism ? { determinism: operation.determinism } : {}),
      },
      result: {
        requestId: result.requestId,
        taskId,
        processId: result.processId,
        operationId: result.operationId,
        status: result.status,
      },
      ...(upstreamProvenance ? { upstream: upstreamProvenance } : {}),
    },
  });
}

export function projectProcessResultContracts(
  record: ProcessResultAttachRecord,
  options: ProjectProcessResultContractsOptions = {},
): ProcessResultContractProjection {
  const attachedAt = record.provenance.attachedAt;
  const resolvedMaterialRefs = record.returnedMaterials.map((material) => normalizeMaterialRef(material, record));
  const resolvedMaterialIds = new Set(resolvedMaterialRefs.map((materialRef) => materialRef.id));
  const failedMaterialRefs = record.status === 'failed'
    ? (options.failedMaterialRefs ?? [])
      .filter((materialRef) => !resolvedMaterialIds.has(materialRef.id))
      .map((materialRef) => normalizeMaterialRef(materialRef, record))
    : [];

  const materialRefs = Object.freeze([
    ...resolvedMaterialRefs,
    ...failedMaterialRefs,
  ]);
  const materialStatuses = Object.freeze([
    ...resolvedMaterialRefs.map((materialRef) =>
      buildMaterialStatus(materialRef.id, 'resolved', attachedAt)),
    ...failedMaterialRefs.map((materialRef) =>
      buildMaterialStatus(
        materialRef.id,
        'failed',
        attachedAt,
        `Process "${record.processId}" failed before "${materialRef.id}" could be attached.`,
      )),
  ]);
  const materialRefsById = new Map(materialRefs.map((materialRef) => [materialRef.id, materialRef] as const));
  const sidecars = normalizeSidecars(record.sidecars);
  const artifacts = Object.freeze(
    record.artifacts.map((artifact) =>
      normalizeArtifact(artifact, record, materialRefsById, sidecars)),
  );

  return deepFreeze({
    materialRefs,
    materialStatuses,
    artifacts,
    sidecars,
  });
}
