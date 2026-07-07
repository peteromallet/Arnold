/**
 * output-format-sidecar-composed-example — EX-04 graph-backed sidecar fixture.
 *
 * Composes the trusted local process declaration from `process-example`
 * with the metadata JSON output contract from `metadata-json-output-example`
 * into a release-governance fixture for M7b. The fixture stays data-only:
 * it exposes a render-dependent output declaration, typed `requires` and
 * `consumes` graph facts, sidecar-export artifact completion evidence, and
 * a stopped-process repair path without claiming sandboxing or execution.
 *
 * This file must NOT import from editor internals (src/tools/video-editor/*).
 * It imports only from the public @reigh/editor-sdk package surface and
 * sibling public examples.
 *
 * @publicContract
 */

import {
  ARTIFACT_MANIFEST_PROFILE_KINDS,
  COMPOSITION_EDGE_KINDS,
  COMPOSITION_NODE_KINDS,
  REFERENCE_STATES,
  contributionRefKey,
  defineExtension,
} from '@reigh/editor-sdk';
import type {
  ArtifactManifestProfile,
  ArtifactManifestProfileBase,
  ArtifactManifestProfileKind,
  AudioArtifactManifestProfile,
  CompositionGraph,
  CompositionGraphEdge,
  CompositionGraphNode,
  CompositionGraphPreviewResult,
  CompositionEdgeKind,
  CompositionNodeKind,
  CompositionReferenceStateEntry,
  ContributionRef,
  DisposeHandle,
  ExecutablePackageArtifactManifestProfile,
  ExtensionContext,
  MachinePathArtifactManifestProfile,
  MaterialRef,
  OutputFormatContribution,
  OutputFormatRef,
  ProcessContribution,
  ProcessManifestEntry,
  PreviewArtifactManifestProfile,
  ReferenceState,
  ReighExtension,
  RenderArtifact,
  RenderArtifactSidecarDescriptor,
  RenderBlocker,
  RenderDependentOutputFormatContribution,
  RenderMaterialRef,
  RenderRoute,
  SidecarArtifactManifestProfile,
  TimelineAutomationSummary,
  TransitionMaterialSlotDeclaration,
  VideoArtifactManifestProfile,
} from '@reigh/editor-sdk';
import { metadataJsonOutputExtension } from './metadata-json-output-example';
import { processExample } from './process-example';

type ProcessOperationSpec = NonNullable<ProcessManifestEntry['operations']>[number];
type ProcessStatus =
  | {
      readonly processId: string;
      readonly state: 'ready';
      readonly label?: string;
      readonly message?: string;
      readonly updatedAt?: string;
      readonly pid?: number;
      readonly version?: ProcessManifestEntry['version'];
    }
  | {
      readonly processId: string;
      readonly state: 'stopped';
      readonly label?: string;
      readonly message?: string;
      readonly updatedAt?: string;
    };

const EX04_EXTENSION_ID = 'com.reigh.examples.output-format-sidecar-composed';
const EX04_OUTPUT_FORMAT_ID = 'metadata-json-sidecar' as OutputFormatContribution['id'];
const EX04_GRAPH_PATH_MARKER = 'EX-04/output-format-sidecar-composed';
const EX04_SOURCE_EXAMPLES = Object.freeze([
  'process-example',
  'metadata-json-output-example',
] as const);
const EX04_ROUTE_CONSTRAINTS = Object.freeze(['sidecar-export'] as const satisfies readonly RenderRoute[]);
const EX04_PROCESS_EXPORT_OPERATION_ID = 'exportMetadataJson';
const EX04_PROCESS_HEALTH_OPERATION_ID = 'health';
const EX04_SOURCE_CLIP_ID = 'clip-ex04-source';
const EX04_SOURCE_MATERIAL_ID = 'mat-ex04-source';
const EX04_ARTIFACT_ID = 'artifact.ex04.metadata-json';
const EX04_MANIFEST_ID = 'manifest.ex04.metadata-json';

function hash(char: string): string {
  return char.repeat(64);
}

function assertPresent<T>(value: T | null | undefined, label: string): T {
  if (value == null) {
    throw new Error(`EX-04 fixture is missing ${label}.`);
  }
  return value;
}

function isProcessContribution(value: unknown): value is ProcessContribution {
  return typeof value === 'object' && value !== null && (value as { kind?: unknown }).kind === 'process';
}

function isOutputFormatContribution(value: unknown): value is OutputFormatContribution {
  return typeof value === 'object' && value !== null && (value as { kind?: unknown }).kind === 'outputFormat';
}

function findProcessOperation(
  spec: ProcessManifestEntry,
  operationId: string,
): ProcessOperationSpec | undefined {
  return spec.operations?.find((operation) => operation.id === operationId);
}

const sourceProcessContribution = assertPresent(
  processExample.manifest.contributions?.find(isProcessContribution),
  'source process contribution',
);
const sourceProcessSpec = assertPresent(
  processExample.manifest.processes?.[0],
  'source process manifest entry',
);
const sourceAnalyzeOperation = assertPresent(
  findProcessOperation(sourceProcessSpec, 'analyze'),
  'source analyze operation',
);
const sourceHealthOperation = assertPresent(
  findProcessOperation(sourceProcessSpec, EX04_PROCESS_HEALTH_OPERATION_ID),
  'source health operation',
);
const sourceMetadataOutput = assertPresent(
  metadataJsonOutputExtension.manifest.contributions?.find(isOutputFormatContribution),
  'source metadata output contribution',
);

const ex04ExportOperation: ProcessOperationSpec = Object.freeze({
  id: EX04_PROCESS_EXPORT_OPERATION_ID,
  label: 'Export Metadata JSON Sidecar',
  description:
    'Derived from the trusted Example Analyzer process and scoped to EX-04 metadata sidecar export.',
  inputSchema: sourceAnalyzeOperation.inputSchema,
  outputKinds: Object.freeze(['artifact', 'sidecar', 'diagnostic'] as const),
  requiredCapabilities: Object.freeze(['json-rpc', 'sidecar-export'] as const),
  routes: EX04_ROUTE_CONSTRAINTS,
  determinism: 'process-dependent',
});

const ex04ProcessSpec: ProcessManifestEntry = Object.freeze({
  ...sourceProcessSpec,
  description:
    'Trusted local stdio-JSON-RPC process composed into EX-04 for route-scoped metadata sidecar export evidence.',
  operations: Object.freeze([
    ex04ExportOperation,
    {
      ...sourceHealthOperation,
      id: EX04_PROCESS_HEALTH_OPERATION_ID,
    },
  ]),
});

const ex04ProcessContribution: ProcessContribution = Object.freeze({
  ...sourceProcessContribution,
  spec: ex04ProcessSpec,
});

const ex04Sidecars = Object.freeze([
  {
    id: 'sidecar.ex04.manifest',
    filename: 'metadata-export.manifest.json',
    mimeType: 'application/json',
    kind: 'manifest',
    byteSize: 812,
    locator: {
      kind: 'artifact-store',
      uri: 'artifact://sidecars/ex04/metadata-export.manifest.json',
      mimeType: 'application/json',
      contentSha256: hash('b'),
    },
    provenance: {
      graphPathMarker: EX04_GRAPH_PATH_MARKER,
      routeConstraints: EX04_ROUTE_CONSTRAINTS,
      sourceExamples: EX04_SOURCE_EXAMPLES,
    },
  },
  {
    id: 'sidecar.ex04.provenance',
    filename: 'metadata-export.provenance.json',
    mimeType: 'application/json',
    kind: 'provenance',
    byteSize: 534,
    locator: {
      kind: 'artifact-store',
      uri: 'artifact://sidecars/ex04/metadata-export.provenance.json',
      mimeType: 'application/json',
      contentSha256: hash('c'),
    },
    provenance: {
      graphPathMarker: EX04_GRAPH_PATH_MARKER,
      routeConstraints: EX04_ROUTE_CONSTRAINTS,
      processId: ex04ProcessSpec.id,
      operationId: ex04ExportOperation.id,
    },
  },
] as const satisfies readonly RenderArtifactSidecarDescriptor[]);

const ex04OutputFormatContribution = Object.freeze({
  id: EX04_OUTPUT_FORMAT_ID,
  kind: 'outputFormat',
  label: 'Metadata JSON Sidecar Export',
  requiresRender: true,
  outputExtension: sourceMetadataOutput.outputExtension,
  outputMimeType: sourceMetadataOutput.outputMimeType,
  description:
    'Composes metadata JSON export with a trusted local process and requires sidecar-export completion evidence before release claims are considered complete.',
  order: sourceMetadataOutput.order,
  render: {
    routes: EX04_ROUTE_CONSTRAINTS,
    requiredCapabilities: Object.freeze(['json-rpc', 'sidecar-export'] as const),
    processId: ex04ProcessSpec.id,
    operationId: ex04ExportOperation.id,
    determinism: 'process-dependent',
    unavailableMessage:
      'Start the Example Analyzer process before requesting metadata JSON sidecar export.',
  },
  sidecars: ex04Sidecars,
} as const satisfies RenderDependentOutputFormatContribution);

function noOpActivate(_ctx: ExtensionContext): DisposeHandle {
  return {
    dispose(): void {
      // EX-04 is a data-only contract fixture; runtime wiring stays external.
    },
  };
}

export const outputFormatSidecarComposedExample: ReighExtension = defineExtension({
  manifest: {
    id: EX04_EXTENSION_ID as any,
    version: '1.0.0',
    label: 'Output Format Sidecar Composed Example',
    description:
      'Graph-backed EX-04 fixture combining trusted-process and metadata JSON output contracts for sidecar-export governance.',
    apiVersion: 1,
    contributions: [
      ex04OutputFormatContribution,
      ex04ProcessContribution,
    ],
    processes: [ex04ProcessSpec],
    messages: {
      activated: 'EX-04 composed fixture mounted.',
      disposed: 'EX-04 composed fixture disposed.',
    },
  },
  activate: noOpActivate,
});

const ex04OutputFormatRef: OutputFormatRef = Object.freeze({
  kind: 'outputFormat',
  extensionId: EX04_EXTENSION_ID,
  contributionId: ex04OutputFormatContribution.id,
});

const ex04ProcessRef: ContributionRef = Object.freeze({
  kind: 'process',
  extensionId: EX04_EXTENSION_ID,
  contributionId: ex04ProcessContribution.id,
});

const ex04OutputNodeId = `contribution:${contributionRefKey(ex04OutputFormatRef)}`;
const ex04ProcessNodeId = `contribution:${contributionRefKey(ex04ProcessRef)}`;
const ex04ClipNodeId = `clip:${EX04_SOURCE_CLIP_ID}`;

const ex04GraphNodes = Object.freeze([
  {
    id: ex04OutputNodeId,
    kind: 'contribution',
    ref: ex04OutputFormatRef,
    detail: {
      graphPathMarker: EX04_GRAPH_PATH_MARKER,
      exampleId: 'EX-04',
      role: 'output-format',
      outputExtension: ex04OutputFormatContribution.outputExtension,
    },
  },
  {
    id: ex04ProcessNodeId,
    kind: 'contribution',
    ref: ex04ProcessRef,
    detail: {
      graphPathMarker: EX04_GRAPH_PATH_MARKER,
      exampleId: 'EX-04',
      role: 'trusted-process',
      processId: ex04ProcessSpec.id,
      protocol: ex04ProcessSpec.protocol,
    },
  },
  {
    id: ex04ClipNodeId,
    kind: 'clip',
    detail: {
      graphPathMarker: EX04_GRAPH_PATH_MARKER,
      exampleId: 'EX-04',
      clipId: EX04_SOURCE_CLIP_ID,
      materialRefId: EX04_SOURCE_MATERIAL_ID,
    },
  },
] as const satisfies readonly CompositionGraphNode[]);

const ex04GraphEdges = Object.freeze([
  {
    id: `requires:${ex04OutputNodeId}:${ex04OutputNodeId}:route:sidecar-export`,
    kind: 'requires',
    sourceNodeId: ex04OutputNodeId,
    targetNodeId: ex04OutputNodeId,
    detail: {
      graphPathMarker: EX04_GRAPH_PATH_MARKER,
      outputFormatId: ex04OutputFormatContribution.id,
      outputLabel: ex04OutputFormatContribution.label,
      refKey: contributionRefKey(ex04OutputFormatRef),
      requirementKind: 'route',
      routes: EX04_ROUTE_CONSTRAINTS,
      routeScope: {
        source: 'output-format',
        mode: 'all',
        routes: EX04_ROUTE_CONSTRAINTS,
      },
      requiredCapabilities: ex04OutputFormatContribution.render.requiredCapabilities,
      determinism: ex04OutputFormatContribution.render.determinism,
      processId: ex04ProcessSpec.id,
      operationId: ex04ExportOperation.id,
      unavailableMessage: ex04OutputFormatContribution.render.unavailableMessage,
    },
  },
  {
    id: `requires:${ex04OutputNodeId}:${ex04ProcessNodeId}:process:${ex04ProcessSpec.id}:${ex04ExportOperation.id}`,
    kind: 'requires',
    sourceNodeId: ex04OutputNodeId,
    targetNodeId: ex04ProcessNodeId,
    detail: {
      graphPathMarker: EX04_GRAPH_PATH_MARKER,
      outputFormatId: ex04OutputFormatContribution.id,
      outputLabel: ex04OutputFormatContribution.label,
      refKey: contributionRefKey(ex04OutputFormatRef),
      requirementKind: 'process',
      processId: ex04ProcessSpec.id,
      operationId: ex04ExportOperation.id,
      routeScope: {
        source: 'process-requirement',
        mode: 'all',
        routes: EX04_ROUTE_CONSTRAINTS,
      },
      requiredCapabilities: ex04ExportOperation.requiredCapabilities,
    },
  },
  {
    id: `consumes:${ex04OutputNodeId}:${ex04ClipNodeId}:material:${EX04_SOURCE_MATERIAL_ID}`,
    kind: 'consumes',
    sourceNodeId: ex04OutputNodeId,
    targetNodeId: ex04ClipNodeId,
    detail: {
      graphPathMarker: EX04_GRAPH_PATH_MARKER,
      outputFormatId: ex04OutputFormatContribution.id,
      outputLabel: ex04OutputFormatContribution.label,
      refKey: contributionRefKey(ex04OutputFormatRef),
      consumedKind: 'material',
      materialRefId: EX04_SOURCE_MATERIAL_ID,
      materialMediaKind: 'video',
      determinism: 'deterministic',
      routeScopes: [{
        route: 'sidecar-export',
        fit: 'supported',
        sensitivity: 'route-category',
      }],
    },
  },
] as const satisfies readonly CompositionGraphEdge[]);

const ex04ReferenceStates = Object.freeze([
  {
    refKey: contributionRefKey(ex04OutputFormatRef),
    state: 'resolved',
    nodeIds: Object.freeze([ex04OutputNodeId]),
  },
  {
    refKey: contributionRefKey(ex04ProcessRef),
    state: 'resolved',
    nodeIds: Object.freeze([ex04ProcessNodeId]),
  },
] as const satisfies readonly CompositionReferenceStateEntry[]);

export const outputFormatSidecarComposedGraph: CompositionGraph = Object.freeze({
  nodes: ex04GraphNodes,
  edges: ex04GraphEdges,
  referenceStates: ex04ReferenceStates,
  diagnostics: Object.freeze([]),
});

const ex04SourceMaterial = Object.freeze({
  id: EX04_SOURCE_MATERIAL_ID,
  mediaKind: 'video',
  locator: {
    kind: 'artifact-store',
    uri: 'artifact://materials/ex04/source.mov',
    mimeType: 'video/quicktime',
    contentSha256: hash('d'),
  },
  producerExtensionId: 'com.reigh.host.capture',
  producerVersion: '1.0.0',
  determinism: 'deterministic',
  replacementPolicy: 'materialize-on-export',
  provenance: {
    graphPathMarker: EX04_GRAPH_PATH_MARKER,
    sourceAssetKey: 'asset://camera-a/source.mov',
    importedAt: '2026-07-05T03:24:00.000Z',
  },
} as const satisfies RenderMaterialRef);

const ex04MetadataManifest = Object.freeze({
  profile: 'sidecar',
  schemaVersion: 1,
  id: EX04_MANIFEST_ID,
  artifactId: EX04_ARTIFACT_ID,
  route: 'sidecar-export',
  determinism: 'process-dependent',
  producerExtensionId: EX04_EXTENSION_ID,
  producerVersion: '1.0.0',
  outputFormatId: ex04OutputFormatContribution.id,
  processId: ex04ProcessSpec.id,
  processVersion: ex04ProcessSpec.version,
  operationId: ex04ExportOperation.id,
  locator: {
    kind: 'artifact-store',
    uri: 'artifact://exports/ex04/metadata-export.json',
    mimeType: 'application/json',
    contentSha256: hash('a'),
  },
  consumedMaterialRefs: [ex04SourceMaterial],
  sidecars: ex04Sidecars,
  provenance: {
    graphPathMarker: EX04_GRAPH_PATH_MARKER,
    sourceExamples: EX04_SOURCE_EXAMPLES,
    processId: ex04ProcessSpec.id,
    operationId: ex04ExportOperation.id,
    routeConstraints: EX04_ROUTE_CONSTRAINTS,
    attachEvidence: {
      taskId: 'task.ex04.metadata-export',
      attachedAt: '2026-07-05T03:24:00.000Z',
      attachedBy: 'EX-04 fixture',
    },
  },
  inputHashes: {
    [EX04_SOURCE_MATERIAL_ID]: hash('d'),
    [ex04Sidecars[0].id!]: ex04Sidecars[0].locator!.contentSha256!,
    [ex04Sidecars[1].id!]: ex04Sidecars[1].locator!.contentSha256!,
  },
  createdAt: '2026-07-05T03:24:00.000Z',
  metadata: {
    graphPathMarker: EX04_GRAPH_PATH_MARKER,
    routeConstraints: EX04_ROUTE_CONSTRAINTS,
    sourceExamples: EX04_SOURCE_EXAMPLES,
  },
} as const satisfies SidecarArtifactManifestProfile);

const ex04MetadataArtifact = Object.freeze({
  id: EX04_ARTIFACT_ID,
  route: 'sidecar-export',
  locator: {
    kind: 'artifact-store',
    uri: 'artifact://exports/ex04/metadata-export.json',
    mimeType: 'application/json',
    contentSha256: hash('a'),
  },
  mediaKind: 'json',
  producerExtensionId: EX04_EXTENSION_ID,
  producerVersion: '1.0.0',
  consumedMaterialRefs: [ex04SourceMaterial],
  determinism: 'process-dependent',
  boundary: {
    source: 'sidecar-process',
    target: 'export-output',
    route: 'sidecar-export',
    failureBehavior: 'block-export',
  },
  sidecars: ex04Sidecars,
  manifest: ex04MetadataManifest,
} as const satisfies RenderArtifact);

const ex04TransitionSlotWitness: TransitionMaterialSlotDeclaration = Object.freeze({
  name: 'metadata-sidecar-slot',
  label: 'Metadata sidecar slot',
});

const ex04NodeKindWitness: CompositionNodeKind = COMPOSITION_NODE_KINDS[2];
const ex04EdgeKindWitness: CompositionEdgeKind = COMPOSITION_EDGE_KINDS[3];
const ex04ReferenceStateWitness: ReferenceState = REFERENCE_STATES[0];
const ex04ArtifactProfileKindWitness: ArtifactManifestProfileKind = ARTIFACT_MANIFEST_PROFILE_KINDS[2];
const ex04MaterialRefWitness: MaterialRef = ex04SourceMaterial;
const ex04AutomationSummaryWitness: TimelineAutomationSummary = Object.freeze({
  contributionId: String(ex04OutputFormatContribution.id),
  parameterPath: 'artifactCompletion.sidecar.status',
  targetPath: 'artifactCompletion.sidecar.status',
  keyframeCount: 2,
  enabled: true,
});

const ex04ArtifactProfileBase: ArtifactManifestProfileBase = Object.freeze({
  profile: 'sidecar',
  schemaVersion: 1,
  id: 'base.ex04.sidecar',
  artifactId: 'artifact.base.ex04.sidecar',
  route: 'sidecar-export',
  determinism: 'process-dependent',
  locator: {
    kind: 'artifact-store',
    uri: 'artifact://profiles/ex04/base-sidecar.json',
    mimeType: 'application/json',
    contentSha256: hash('e'),
  },
  consumedMaterialRefs: [ex04SourceMaterial],
  sidecars: [],
});

const ex04VideoProfileWitness: VideoArtifactManifestProfile = Object.freeze({
  ...ex04ArtifactProfileBase,
  profile: 'video',
  id: 'profile.ex04.video',
  artifactId: 'artifact.profile.ex04.video',
  route: 'browser-export',
  determinism: 'deterministic',
  mediaKind: 'video',
  outputFormatId: 'video-witness',
});

const ex04AudioProfileWitness: AudioArtifactManifestProfile = Object.freeze({
  ...ex04ArtifactProfileBase,
  profile: 'audio',
  id: 'profile.ex04.audio',
  artifactId: 'artifact.profile.ex04.audio',
  route: 'worker-export',
  determinism: 'deterministic',
  mediaKind: 'audio',
  outputFormatId: 'audio-witness',
});

const ex04PreviewProfileWitness: PreviewArtifactManifestProfile = Object.freeze({
  ...ex04ArtifactProfileBase,
  profile: 'preview',
  id: 'profile.ex04.preview',
  artifactId: 'artifact.profile.ex04.preview',
  route: 'preview',
  determinism: 'preview-only',
  outputFormatId: 'preview-witness',
});

const ex04MachinePathProfileWitness: MachinePathArtifactManifestProfile = Object.freeze({
  ...ex04ArtifactProfileBase,
  profile: 'machine-path',
  id: 'profile.ex04.machine-path',
  artifactId: 'artifact.profile.ex04.machine-path',
  locator: {
    kind: 'local-file',
    uri: 'file:///var/tmp/reigh/ex04/metadata.json',
    mimeType: 'application/json',
    contentSha256: hash('f'),
  },
  processId: ex04ProcessSpec.id,
  operationId: ex04ExportOperation.id,
});

const ex04ExecutablePackageProfileWitness: ExecutablePackageArtifactManifestProfile = Object.freeze({
  ...ex04ArtifactProfileBase,
  profile: 'executable-package',
  id: 'profile.ex04.executable-package',
  artifactId: 'artifact.profile.ex04.executable-package',
  locator: {
    kind: 'artifact-store',
    uri: 'artifact://packages/ex04/metadata-exporter.tar.gz',
    mimeType: 'application/gzip',
    contentSha256: hash('0'),
  },
  processId: ex04ProcessSpec.id,
  operationId: ex04ExportOperation.id,
});

const ex04ArtifactProfileWitnesses = Object.freeze([
  ex04MetadataManifest,
  ex04VideoProfileWitness,
  ex04AudioProfileWitness,
  ex04PreviewProfileWitness,
  ex04MachinePathProfileWitness,
  ex04ExecutablePackageProfileWitness,
] as const satisfies readonly ArtifactManifestProfile[]);

const ex04PreviewWitness: CompositionGraphPreviewResult = Object.freeze({
  nodes: ex04GraphNodes,
  edges: ex04GraphEdges,
  referenceStates: ex04ReferenceStates,
  diagnostics: Object.freeze([]),
});

export const outputFormatSidecarSdkCoverage = Object.freeze({
  transitionMaterialSlot: ex04TransitionSlotWitness,
  materialRef: ex04MaterialRefWitness,
  nodeKind: ex04NodeKindWitness,
  edgeKind: ex04EdgeKindWitness,
  referenceState: ex04ReferenceStateWitness,
  artifactProfileKind: ex04ArtifactProfileKindWitness,
  nodeKinds: COMPOSITION_NODE_KINDS,
  edgeKinds: COMPOSITION_EDGE_KINDS,
  referenceStates: REFERENCE_STATES,
  artifactProfileKinds: ARTIFACT_MANIFEST_PROFILE_KINDS,
  graphPreview: ex04PreviewWitness,
  artifactProfileBase: ex04ArtifactProfileBase,
  artifactProfiles: ex04ArtifactProfileWitnesses,
  automationSummary: ex04AutomationSummaryWitness,
});

interface OutputFormatSidecarArtifactEvidence {
  readonly artifact: RenderArtifact;
  readonly manifest: SidecarArtifactManifestProfile;
  readonly routeConstraints: readonly RenderRoute[];
  readonly artifactHash: string;
  readonly sidecarHashes: Readonly<Record<string, string>>;
  readonly inputHashes: Readonly<Record<string, string>>;
  readonly provenance: Readonly<Record<string, unknown>>;
}

interface OutputFormatSidecarRepairAction {
  readonly kind: 'start-process';
  readonly route: 'sidecar-export';
  readonly processId: string;
  readonly operationId: string;
  readonly label: string;
  readonly message: string;
  readonly detail: {
    readonly specificKind: 'start-process';
    readonly routeScope: 'sidecar-export';
    readonly targetState: 'ready';
  };
}

type OutputFormatSidecarCompletionStatus = 'complete' | 'incomplete' | 'blocked';

interface OutputFormatSidecarRequirementSource {
  readonly source:
    | 'output-format'
    | 'output-format-sidecar'
    | 'process-requirement'
    | 'process-attach-record';
  readonly outputFormatId?: string;
  readonly processId?: string;
  readonly operationId?: string;
  readonly detail?: Readonly<Record<string, unknown>>;
}

interface OutputFormatSidecarCompletionProfileRecord {
  readonly profile: 'sidecar';
  readonly status: OutputFormatSidecarCompletionStatus;
  readonly requiredBy: readonly OutputFormatSidecarRequirementSource[];
  readonly artifacts: readonly RenderArtifact[];
  readonly sidecars: readonly RenderArtifactSidecarDescriptor[];
  readonly issues: readonly string[];
}

interface OutputFormatSidecarCompletionRecord {
  readonly status: OutputFormatSidecarCompletionStatus;
  readonly requiredProfiles: readonly ['sidecar'];
  readonly completeProfiles: readonly ('sidecar')[];
  readonly incompleteProfiles: readonly ('sidecar')[];
  readonly blockedProfiles: readonly ('sidecar')[];
  readonly profiles: readonly OutputFormatSidecarCompletionProfileRecord[];
}

interface OutputFormatSidecarScenario {
  readonly processStatus: ProcessStatus;
  readonly blockers: readonly RenderBlocker[];
  readonly nextActions: readonly OutputFormatSidecarRepairAction[];
  readonly artifactCompletion: OutputFormatSidecarCompletionRecord;
}

function createArtifactEvidence(
  artifact: RenderArtifact,
  routeConstraints: readonly RenderRoute[],
): OutputFormatSidecarArtifactEvidence {
  const manifest = artifact.manifest;
  if (!manifest || manifest.profile !== 'sidecar') {
    throw new Error('EX-04 artifact evidence requires a typed sidecar manifest.');
  }
  if (artifact.route !== 'sidecar-export' || manifest.route !== 'sidecar-export') {
    throw new Error('EX-04 artifact evidence must stay route-scoped to sidecar-export.');
  }
  if (!artifact.locator.contentSha256) {
    throw new Error('EX-04 artifact evidence requires an artifact SHA-256 hash.');
  }
  if (routeConstraints.length === 0 || routeConstraints.some((route) => route !== artifact.route)) {
    throw new Error('EX-04 artifact evidence route constraints must match the sidecar-export route.');
  }
  if (!manifest.inputHashes || Object.keys(manifest.inputHashes).length === 0) {
    throw new Error('EX-04 artifact evidence requires manifest input hashes.');
  }
  const sidecarHashes: Record<string, string> = {};
  for (const sidecar of manifest.sidecars) {
    const key = sidecar.id ?? sidecar.filename;
    const sidecarHash = sidecar.locator?.contentSha256;
    if (!sidecarHash) {
      throw new Error(`EX-04 sidecar "${key}" is missing a SHA-256 hash.`);
    }
    sidecarHashes[key] = sidecarHash;
  }
  const provenance = manifest.provenance;
  if (!provenance || !Array.isArray(provenance.routeConstraints)) {
    throw new Error('EX-04 artifact evidence requires provenance route constraints.');
  }
  return Object.freeze({
    artifact,
    manifest,
    routeConstraints: Object.freeze([...routeConstraints]),
    artifactHash: artifact.locator.contentSha256,
    sidecarHashes: Object.freeze(sidecarHashes),
    inputHashes: Object.freeze({ ...manifest.inputHashes }),
    provenance: Object.freeze({ ...provenance }),
  });
}

export const outputFormatSidecarArtifactEvidence = Object.freeze([
  createArtifactEvidence(ex04MetadataArtifact, EX04_ROUTE_CONSTRAINTS),
] as const);

const ex04ReadyProcessStatus: ProcessStatus = Object.freeze({
  processId: ex04ProcessSpec.id,
  state: 'ready',
  label: ex04ProcessSpec.label,
  message: 'Example Analyzer Process is ready for metadata sidecar export.',
  updatedAt: '2026-07-05T03:24:00.000Z',
  pid: 4204,
  version: ex04ProcessSpec.version,
});

const ex04StartProcessAction = Object.freeze({
  kind: 'start-process',
  route: 'sidecar-export',
  processId: ex04ProcessSpec.id,
  operationId: ex04ExportOperation.id,
  label: 'Start Example Analyzer Process',
  message: 'Start the trusted local process before re-running metadata sidecar export.',
  detail: {
    specificKind: 'start-process',
    routeScope: 'sidecar-export',
    targetState: 'ready',
  },
} as const satisfies OutputFormatSidecarRepairAction);

const ex04StoppedBlocker = Object.freeze({
  id: 'planner.outputFormat.ex04.metadata-json-sidecar.sidecar-export.example-analyzer.exportMetadataJson.process-dependent',
  severity: 'error',
  route: 'sidecar-export',
  reason: 'process-dependent',
  message:
    'Metadata JSON Sidecar Export requires the Example Analyzer process before sidecar-export can complete.',
  extensionId: EX04_EXTENSION_ID,
  contributionId: ex04OutputFormatContribution.id,
  processId: ex04ProcessSpec.id,
  operationId: ex04ExportOperation.id,
  detail: {
    graphPathMarker: EX04_GRAPH_PATH_MARKER,
    routeScope: 'sidecar-export',
    lifecycleState: 'stopped',
    processProtocol: ex04ProcessSpec.protocol,
    nextAction: ex04StartProcessAction,
  },
} as const satisfies RenderBlocker);

const ex04RequiredBy = Object.freeze([
  {
    source: 'output-format',
    outputFormatId: ex04OutputFormatContribution.id,
    detail: {
      routeConstraints: EX04_ROUTE_CONSTRAINTS,
      graphPathMarker: EX04_GRAPH_PATH_MARKER,
    },
  },
  {
    source: 'output-format-sidecar',
    outputFormatId: ex04OutputFormatContribution.id,
    detail: {
      sidecarIds: ex04Sidecars.map((sidecar) => sidecar.id),
      routeConstraints: EX04_ROUTE_CONSTRAINTS,
    },
  },
  {
    source: 'process-requirement',
    processId: ex04ProcessSpec.id,
    operationId: ex04ExportOperation.id,
    detail: {
      requiredCapabilities: ex04ExportOperation.requiredCapabilities,
      routeConstraints: EX04_ROUTE_CONSTRAINTS,
    },
  },
  {
    source: 'process-attach-record',
    processId: ex04ProcessSpec.id,
    operationId: ex04ExportOperation.id,
    detail: {
      taskId: 'task.ex04.metadata-export',
      routeConstraints: EX04_ROUTE_CONSTRAINTS,
      manifestId: ex04MetadataManifest.id,
    },
  },
] as const satisfies readonly OutputFormatSidecarRequirementSource[]);

export const outputFormatSidecarReadyScenario: OutputFormatSidecarScenario = Object.freeze({
  processStatus: ex04ReadyProcessStatus,
  blockers: Object.freeze([]),
  nextActions: Object.freeze([]),
  artifactCompletion: {
    status: 'complete',
    requiredProfiles: ['sidecar'],
    completeProfiles: ['sidecar'],
    incompleteProfiles: [],
    blockedProfiles: [],
    profiles: [{
      profile: 'sidecar',
      status: 'complete',
      requiredBy: ex04RequiredBy,
      artifacts: [ex04MetadataArtifact],
      sidecars: ex04Sidecars,
      issues: [],
    }],
  },
});

export const outputFormatSidecarStoppedScenario: OutputFormatSidecarScenario = Object.freeze({
  processStatus: {
    processId: ex04ProcessSpec.id,
    state: 'stopped',
    label: ex04ProcessSpec.label,
    message: 'Example Analyzer Process is stopped.',
    updatedAt: '2026-07-05T03:24:00.000Z',
  },
  blockers: [ex04StoppedBlocker],
  nextActions: [ex04StartProcessAction],
  artifactCompletion: {
    status: 'blocked',
    requiredProfiles: ['sidecar'],
    completeProfiles: [],
    incompleteProfiles: ['sidecar'],
    blockedProfiles: ['sidecar'],
    profiles: [{
      profile: 'sidecar',
      status: 'blocked',
      requiredBy: ex04RequiredBy,
      artifacts: [],
      sidecars: [],
      issues: [
        'Process is stopped, so metadata JSON and sidecar evidence have not been attached.',
        'Route-scoped start-process repair is required before sidecar-export can complete.',
      ],
    }],
  },
});

export interface OutputFormatSidecarComposedContract {
  readonly exampleId: 'EX-04';
  readonly graphPathMarker: string;
  readonly sourceExamples: readonly string[];
  readonly routeConstraints: readonly RenderRoute[];
  readonly extension: ReighExtension;
  readonly outputFormat: RenderDependentOutputFormatContribution;
  readonly processContribution: ProcessContribution;
  readonly processSpec: ProcessManifestEntry;
  readonly graph: CompositionGraph;
  readonly consumedMaterial: RenderMaterialRef;
  readonly artifactEvidence: readonly OutputFormatSidecarArtifactEvidence[];
  readonly readyScenario: OutputFormatSidecarScenario;
  readonly stoppedScenario: OutputFormatSidecarScenario;
}

export const outputFormatSidecarComposedContract: OutputFormatSidecarComposedContract = Object.freeze({
  exampleId: 'EX-04',
  graphPathMarker: EX04_GRAPH_PATH_MARKER,
  sourceExamples: EX04_SOURCE_EXAMPLES,
  routeConstraints: EX04_ROUTE_CONSTRAINTS,
  extension: outputFormatSidecarComposedExample,
  outputFormat: ex04OutputFormatContribution,
  processContribution: ex04ProcessContribution,
  processSpec: ex04ProcessSpec,
  graph: outputFormatSidecarComposedGraph,
  consumedMaterial: ex04SourceMaterial,
  artifactEvidence: outputFormatSidecarArtifactEvidence,
  readyScenario: outputFormatSidecarReadyScenario,
  stoppedScenario: outputFormatSidecarStoppedScenario,
});
