import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@testing-library/react';
import { useEffect, useMemo, useState } from 'react';
import { describe, expect, it } from 'vitest';
import type {
  CapabilityFinding,
  RenderMaterialRef,
  TimelineSnapshot,
} from '@reigh/editor-sdk';
import { BlockerActionCard } from '@/tools/video-editor/components/BlockerActionCard.tsx';
import { MaterialBrowser } from '@/tools/video-editor/components/MaterialBrowser.tsx';
import { RouteCompletionDashboard } from '@/tools/video-editor/components/RouteCompletionDashboard/index.ts';
import {
  outputFormatSidecarComposedContract,
  outputFormatSidecarComposedExample,
} from '@/examples/output-format-sidecar-composed-example.ts';
import { flagshipLocalExtension } from '@/tools/video-editor/examples/extensions/flagship-local';
import { buildTimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
import { serializeTimelineConfigSnapshot } from '@/tools/video-editor/lib/timeline-domain.ts';
import { createTimelineReader } from '@/tools/video-editor/lib/timeline-reader.ts';
import {
  collectBuiltInKnownIds,
  collectExtensionDeclaredIds,
  scanExportConfig,
} from '@/tools/video-editor/runtime/exportGuard.ts';
import {
  applyGraphPreviewOperations,
} from '@/tools/video-editor/runtime/composition/patchPreview.ts';
import {
  projectHostMaterialRuntime,
  resolveMaterialAttachEntry,
} from '@/tools/video-editor/runtime/composition/materialRuntime.ts';
import {
  createProcessResultAttachRecord,
  type ProcessResultAttachRecord,
} from '@/tools/video-editor/runtime/composition/processResultAttach.ts';
import { projectCompositionGraph } from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import { createLiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry.ts';
import { normalizeExtensionRuntime } from '@/tools/video-editor/runtime/extensionSurface.ts';
import {
  buildExportReadinessPlan,
  type RenderPlannerResult,
} from '@/tools/video-editor/runtime/renderPlanner.ts';
import type {
  ResolvedTimelineConfig,
  TimelineLiveBinding,
  TimelineLiveDeterministicRef,
} from '@/tools/video-editor/types/index.ts';

const FLAGSHIP_EXTENSION_ID = 'com.reigh.examples.flagship-local';

const EX02_CLIP_ID = 'clip-flagship-glow-live';
const EX02_SOURCE_ID = 'source-flagship-glow-live';
const EX02_BINDING_ID = 'binding-flagship-glow-intensity';
const EX02_CAPTURE_REF_ID = 'capture-flagship-glow-intensity';
const EX02_EFFECT_CONTRIBUTION_ID = 'flagship-effect-glow';
const EX02_EFFECT_ID = 'com.reigh.flagship.effect.glow';
const EX02_EFFECT_REF_KEY = `effect:${FLAGSHIP_EXTENSION_ID}:${EX02_EFFECT_CONTRIBUTION_ID}`;
const EX02_EFFECT_NODE_ID = `contribution:${EX02_EFFECT_REF_KEY}`;

const EX03_CLIP_ID = 'clip-flagship-wipe-mask';
const EX03_TRANSITION_CONTRIBUTION_ID = 'flagship-transition-wipe';
const EX03_TRANSITION_ID = 'com.reigh.flagship.transition.wipe';
const EX03_TRANSITION_REF_KEY = `transition:${FLAGSHIP_EXTENSION_ID}:${EX03_TRANSITION_CONTRIBUTION_ID}`;
const EX03_TRANSITION_NODE_ID = `contribution:${EX03_TRANSITION_REF_KEY}`;
const EX03_MASK_SLOT = 'transition-mask';
const EX03_MASK_MATERIAL_REF_ID = 'mat-flagship-transition-mask';
const EX04_ROUTE = 'sidecar-export';

const EMPTY_ASSET_REGISTRY = { assets: {} };
const FLAGSHIP_RUNTIME = normalizeExtensionRuntime([flagshipLocalExtension]);
const EX04_RUNTIME = normalizeExtensionRuntime([outputFormatSidecarComposedExample]);
const FLAGSHIP_DECLARED_IDS = collectExtensionDeclaredIds(
  flagshipLocalExtension.manifest.contributions ?? [],
);
const EX04_PROCESS_DESCRIPTOR = EX04_RUNTIME.processes.find((descriptor) => (
  descriptor.processId === outputFormatSidecarComposedContract.processSpec.id
));
const EX04_OUTPUT_DESCRIPTOR = EX04_RUNTIME.outputFormats.find((descriptor) => (
  descriptor.id === outputFormatSidecarComposedContract.outputFormat.id
));

if (!EX04_PROCESS_DESCRIPTOR) {
  throw new Error('EX-04 browser acceptance requires a normalized process descriptor.');
}
if (!EX04_OUTPUT_DESCRIPTOR) {
  throw new Error('EX-04 browser acceptance requires a normalized output format descriptor.');
}

const EX04_ARTIFACT_EVIDENCE = outputFormatSidecarComposedContract.artifactEvidence[0];

if (!EX04_ARTIFACT_EVIDENCE) {
  throw new Error('EX-04 browser acceptance requires artifact evidence.');
}
const EX04_OPERATION_ID = EX04_ARTIFACT_EVIDENCE.manifest.operationId;

if (!EX04_OPERATION_ID) {
  throw new Error('EX-04 browser acceptance requires a manifest operation ID.');
}

function makeEffectBinding(
  overrides: Partial<TimelineLiveBinding> = {},
): TimelineLiveBinding {
  return {
    bindingId: EX02_BINDING_ID,
    sourceId: EX02_SOURCE_ID,
    sourceKind: 'generated',
    sourceStatus: 'active',
    targetEffectId: EX02_EFFECT_CONTRIBUTION_ID,
    targetParamName: 'params.intensity',
    targetPath: 'params.intensity',
    ownerExtensionId: FLAGSHIP_EXTENSION_ID,
    ...overrides,
  };
}

function makeEffectConfig(binding: TimelineLiveBinding): ResolvedTimelineConfig {
  return {
    output: { resolution: '1280x720', fps: 30, file: 'flagship-glow-live.mp4' },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips: [{
      id: EX02_CLIP_ID,
      track: 'V1',
      at: 0,
      hold: 60,
      clipType: 'media',
      effects: [{
        type: EX02_EFFECT_ID,
        managedBy: FLAGSHIP_EXTENSION_ID,
        params: {
          intensity: 0.35,
          color: '#ff6b6b',
          style: 'glow',
          animate: true,
        },
      }],
      params: {
        liveBindings: [binding],
      },
    }],
    registry: {},
  } as ResolvedTimelineConfig;
}

function makeTransitionSnapshot(): TimelineSnapshot {
  const transition = {
    id: `${EX03_CLIP_ID}.transition.${EX03_TRANSITION_ID}`,
    clipId: EX03_CLIP_ID,
    transitionType: EX03_TRANSITION_ID,
    duration: 0.75,
    managed: true,
    managedBy: FLAGSHIP_EXTENSION_ID,
    params: {
      direction: 'right',
      softness: 0.2,
    },
  };

  return {
    projectId: 'flagship-transition-mask-browser',
    baseVersion: 1,
    currentVersion: 1,
    extensionRequirements: [],
    clips: [{
      id: EX03_CLIP_ID,
      track: 'V1',
      at: 0,
      duration: 60,
      clipType: 'media',
      managed: false,
      transition,
    }],
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1', muted: false }],
    assetKeys: [],
    app: {},
    transitions: [transition],
    outputMetadata: { resolution: '1280x720', fps: 30, file: 'flagship-wipe-mask.mp4' },
  };
}

async function roundTripSnapshot(config: ResolvedTimelineConfig): Promise<TimelineSnapshot> {
  const serialized = serializeTimelineConfigSnapshot(config).config;
  const data = await buildTimelineData(serialized, EMPTY_ASSET_REGISTRY);
  return createTimelineReader({ data }).snapshot();
}

function bakeDeterministicCapture(): TimelineLiveDeterministicRef {
  const registry = createLiveDataRegistry({ emitLifecycleDiagnostics: false });
  const handle = registry.registerSource({ id: EX02_SOURCE_ID, kind: 'generated' });
  const channelId = registry.openChannel(EX02_SOURCE_ID, 'control', { label: 'Flagship Glow Intensity' });

  registry.pushSample(channelId, {
    timestamp: 0,
    format: 'json',
    data: { value: 0.82 },
  });

  const result = registry.bake({
    sourceId: EX02_SOURCE_ID,
    channelIds: [channelId],
    targets: [{
      kind: 'deterministic-capture',
      ref: EX02_CAPTURE_REF_ID,
      params: {
        captureId: EX02_CAPTURE_REF_ID,
        profile: 'event',
        contentHash: 'a'.repeat(64),
        provenanceHash: 'b'.repeat(64),
        routeConstraints: ['preview', 'browser-export'],
        determinism: 'deterministic',
      },
    }],
  });

  handle.dispose();
  if (!result.success || result.replacements.length === 0) {
    throw new Error('Failed to bake deterministic EX-02 capture for browser acceptance.');
  }

  return result.replacements[0]!.deterministicRef;
}

function makeMaskMaterialRef(): RenderMaterialRef {
  return {
    id: EX03_MASK_MATERIAL_REF_ID,
    mediaKind: 'image',
    producerExtensionId: FLAGSHIP_EXTENSION_ID,
    determinism: 'deterministic',
    replacementPolicy: 'materialize-on-export',
    locator: {
      kind: 'artifact-store',
      uri: 'artifact://materials/flagship-transition-mask.png',
      contentSha256: 'c'.repeat(64),
      mimeType: 'image/png',
    },
    provenance: {
      capture: 'agent-mask',
      model: 'deterministic-masker',
    },
  } as RenderMaterialRef;
}

function createEx04AttachRecord(): ProcessResultAttachRecord {
  return createProcessResultAttachRecord({
    processDescriptor: EX04_PROCESS_DESCRIPTOR,
    attachedAt: '2026-07-05T03:24:00.000Z',
    result: {
      requestId: 'task.ex04.metadata-export',
      processId: EX04_PROCESS_DESCRIPTOR.processId,
      operationId: EX04_OPERATION_ID,
      status: 'completed',
      returnedMaterials: [],
      artifacts: [EX04_ARTIFACT_EVIDENCE.artifact],
      sidecars: EX04_ARTIFACT_EVIDENCE.manifest.sidecars,
      diagnostics: [],
      logs: [{
        level: 'info',
        message: 'Metadata JSON sidecar export attached.',
      }],
      availableActions: [],
      metadata: {
        graphPathMarker: outputFormatSidecarComposedContract.graphPathMarker,
      },
    },
  });
}

function buildEx04RoutePlan(
  scenario: typeof outputFormatSidecarComposedContract.readyScenario,
): RenderPlannerResult['routePlans'][number] {
  return {
    route: EX04_ROUTE,
    blockerCount: scenario.blockers.length,
    findingCount: scenario.blockers.length,
    blocked: scenario.blockers.length > 0,
    requiredCapabilities: EX04_OUTPUT_DESCRIPTOR.processRequirements[0]?.requiredCapabilities
      ?? outputFormatSidecarComposedContract.outputFormat.render.requiredCapabilities,
    determinism: outputFormatSidecarComposedContract.outputFormat.render.determinism,
    blockers: scenario.blockers,
    diagnostics: scenario.blockers,
    outputFormatIds: [outputFormatSidecarComposedContract.outputFormat.id],
    processRequirements: EX04_OUTPUT_DESCRIPTOR.processRequirements,
    nextActions: scenario.nextActions,
    artifactCompletion: scenario.artifactCompletion,
  };
}

interface EffectShellState {
  loading: boolean;
  hasConsumesEdge: boolean;
  hasBindsLiveEdge: boolean;
  exportBlocked: boolean;
  scannerDiagnosticCode: string | null;
  blockerMessage: string | null;
}

function EffectLiveAcceptanceShell({
  initialConfig,
}: {
  initialConfig: ResolvedTimelineConfig;
}) {
  const [config, setConfig] = useState(initialConfig);
  const [state, setState] = useState<EffectShellState>({
    loading: true,
    hasConsumesEdge: false,
    hasBindsLiveEdge: false,
    exportBlocked: false,
    scannerDiagnosticCode: null,
    blockerMessage: null,
  });

  useEffect(() => {
    let cancelled = false;

    async function project() {
      const snapshot = await roundTripSnapshot(config);
      const graph = projectCompositionGraph({
        snapshot,
        contributionIndex: FLAGSHIP_RUNTIME.contributionIndex,
      });
      const exportResult = scanExportConfig(
        config,
        collectBuiltInKnownIds(),
        FLAGSHIP_DECLARED_IDS,
        undefined,
        undefined,
        undefined,
        graph,
      );
      const exportReadiness = buildExportReadinessPlan({
        snapshot,
        compositionGraph: graph,
        extensionRuntime: FLAGSHIP_RUNTIME,
        guard: exportResult,
      });
      const liveBindingDiagnostic = exportResult.diagnostics.find((diagnostic) => (
        diagnostic.code === 'export/live-binding-unresolved'
      ));

      if (cancelled) {
        return;
      }

      setState({
        loading: false,
        hasConsumesEdge: graph.edges.some((edge) => (
          edge.kind === 'consumes'
          && edge.sourceNodeId === `clip:${EX02_CLIP_ID}`
          && edge.targetNodeId === EX02_EFFECT_NODE_ID
          && edge.detail?.consumedKind === 'effect'
          && edge.detail?.refKey === EX02_EFFECT_REF_KEY
        )),
        hasBindsLiveEdge: graph.edges.some((edge) => (
          edge.kind === 'binds-live'
          && edge.sourceNodeId === `clip:${EX02_CLIP_ID}`
          && edge.targetNodeId === EX02_EFFECT_NODE_ID
          && edge.detail?.targetKind === 'effect-param'
          && edge.detail?.targetPath === 'intensity'
        )),
        exportBlocked: !exportReadiness.canBrowserExport,
        scannerDiagnosticCode: liveBindingDiagnostic?.code ?? null,
        blockerMessage: exportReadiness.blockers.find((blocker) => (
          blocker.route === 'browser-export'
          && blocker.reason === 'live-unbaked'
        ))?.message ?? null,
      });
    }

    void project();
    return () => {
      cancelled = true;
    };
  }, [config]);

  const bakeBinding = () => {
    setConfig(
      makeEffectConfig(makeEffectBinding({
        bake: {
          status: 'complete',
          deterministicRefs: [bakeDeterministicCapture()],
        },
      })),
    );
  };

  return (
    <section aria-label="EX-02 browser shell">
      <div data-testid="ex02-loading">{String(state.loading)}</div>
      <div data-testid="ex02-consumes">{String(state.hasConsumesEdge)}</div>
      <div data-testid="ex02-binds-live">{String(state.hasBindsLiveEdge)}</div>
      <div data-testid="ex02-export-blocked">{String(state.exportBlocked)}</div>
      {state.blockerMessage && state.scannerDiagnosticCode ? (
        <BlockerActionCard
          severity="error"
          code={state.scannerDiagnosticCode}
          message={state.blockerMessage}
          nextAction={{
            kind: 'bake',
            label: 'Bake live binding',
            message: 'Bake the Flagship Glow live binding before browser export.',
          }}
          onAction={bakeBinding}
        />
      ) : null}
    </section>
  );
}

interface TransitionShellState {
  loading: boolean;
  hasTransitionConsumes: boolean;
  hasMaskConsumes: boolean;
  materialStatuses: readonly {
    materialRefId: string;
    state: 'missing' | 'pending' | 'resolved' | 'stale' | 'failed';
    message?: string;
    detail?: Record<string, unknown>;
  }[];
  plannerResult: {
    nextActions: readonly {
      kind: 'materialize';
      label: string;
      message: string;
    }[];
    blockers: readonly CapabilityFinding[];
    diagnostics: readonly CapabilityFinding[];
  };
}

function TransitionMaskAcceptanceShell({
  initialMaterialState,
}: {
  initialMaterialState: 'missing' | 'resolved';
}) {
  const [materialState, setMaterialState] = useState<'missing' | 'resolved'>(initialMaterialState);
  const materialRef = useMemo(() => makeMaskMaterialRef(), []);
  const [state, setState] = useState<TransitionShellState>({
    loading: true,
    hasTransitionConsumes: false,
    hasMaskConsumes: false,
    materialStatuses: [],
    plannerResult: {
      nextActions: [],
      blockers: [],
      diagnostics: [],
    },
  });

  useEffect(() => {
    let cancelled = false;

    async function project() {
      const snapshot = makeTransitionSnapshot();
      const transition = snapshot.clips[0]?.transition;
      const transitionDescriptor = FLAGSHIP_RUNTIME.transitions.find((descriptor) => (
        descriptor.id === EX03_TRANSITION_CONTRIBUTION_ID
        && descriptor.transitionId === EX03_TRANSITION_ID
      ));

      if (!transition || !transitionDescriptor) {
        return;
      }

      const materialRuntime = projectHostMaterialRuntime({
        materialRefs: [materialRef],
        materialStatuses: [{
          materialRefId: materialRef.id,
          state: materialState,
          ...(materialState === 'missing' ? { message: 'Missing bytes' } : {}),
        }],
      });
      const baseGraph = projectCompositionGraph({
        snapshot,
        contributionIndex: FLAGSHIP_RUNTIME.contributionIndex,
      });
      const transitionConsumes = baseGraph.edges.some((edge) => (
        edge.kind === 'consumes'
        && edge.sourceNodeId === `clip:${EX03_CLIP_ID}`
        && edge.targetNodeId === EX03_TRANSITION_NODE_ID
        && edge.detail?.consumedKind === 'transition'
        && edge.detail?.refKey === EX03_TRANSITION_REF_KEY
      ));

      let maskConsumes = false;
      let plannerResult: TransitionShellState['plannerResult'] = {
        nextActions: [],
        blockers: [],
        diagnostics: [],
      };

      if (materialState === 'resolved') {
        const preview = applyGraphPreviewOperations({
          snapshot,
          contributionIndex: FLAGSHIP_RUNTIME.contributionIndex,
          materialRuntime,
          materialSlotDeclarations: transitionDescriptor.materialSlots.map((slot) => ({
            owner: {
              kind: 'transition',
              clipId: EX03_CLIP_ID,
              ownerId: transition.id,
            },
            slotName: slot.name,
          })),
        }, [{
          kind: 'material.attach',
          owner: {
            kind: 'transition',
            clipId: EX03_CLIP_ID,
            ownerId: transition.id,
          },
          slotName: EX03_MASK_SLOT,
          materialRefId: materialRef.id,
        }]);

        maskConsumes = Boolean(preview?.edges.some((edge) => (
          edge.kind === 'consumes'
          && edge.sourceNodeId === `clip:${EX03_CLIP_ID}`
          && edge.targetNodeId === EX03_TRANSITION_NODE_ID
          && edge.detail?.consumedKind === 'mask-material'
          && edge.detail?.targetSlot === EX03_MASK_SLOT
          && edge.detail?.materialRefId === materialRef.id
        )));
      } else {
        const resolution = resolveMaterialAttachEntry(materialRuntime, materialRef.id, {
          clipId: EX03_CLIP_ID,
          transitionId: transition.id,
          transitionType: EX03_TRANSITION_ID,
          scope: 'clip',
          ownerKind: 'transition',
          ownerId: transition.id,
          materialSlot: EX03_MASK_SLOT,
          refKey: EX03_TRANSITION_REF_KEY,
          extensionId: FLAGSHIP_EXTENSION_ID,
          contributionId: EX03_TRANSITION_CONTRIBUTION_ID,
          resolverState: 'resolved',
          packageState: 'loaded',
        });

        if (!resolution.ok) {
          plannerResult = {
            nextActions: [{
              kind: 'materialize',
              label: 'Materialize transition mask',
              message: `Materialize ${materialRef.id} for ${EX03_MASK_SLOT}.`,
            }],
            blockers: [{
              id: `browser:${resolution.diagnostic.code}`,
              severity: resolution.diagnostic.severity,
              route: 'browser-export',
              reason: 'missing-material',
              message: resolution.diagnostic.message,
              materialRefId: materialRef.id,
              detail: {
                code: resolution.diagnostic.code,
                repairAction: resolution.diagnostic.detail?.repairAction,
                materialRefId: materialRef.id,
              },
            }],
            diagnostics: [],
          };
        }
      }

      if (cancelled) {
        return;
      }

      setState({
        loading: false,
        hasTransitionConsumes: transitionConsumes,
        hasMaskConsumes: maskConsumes,
        materialStatuses: materialRuntime.materials.map((entry) => entry.status),
        plannerResult,
      });
    }

    void project();
    return () => {
      cancelled = true;
    };
  }, [materialRef, materialState]);

  return (
    <section aria-label="EX-03 browser shell">
      <div data-testid="ex03-loading">{String(state.loading)}</div>
      <div data-testid="ex03-transition-consumes">{String(state.hasTransitionConsumes)}</div>
      <div data-testid="ex03-mask-consumes">{String(state.hasMaskConsumes)}</div>
      <MaterialBrowser
        materials={[materialRef]}
        materialStatuses={state.materialStatuses}
        plannerResult={state.plannerResult}
        onAction={() => setMaterialState('resolved')}
      />
    </section>
  );
}

interface Ex04RouteCompletionShellState {
  loading: boolean;
  hasRequiresProcessEdge: boolean;
  hasConsumesMaterialEdge: boolean;
  routePlan: RenderPlannerResult['routePlans'][number] | null;
  plannerSurface: Pick<RenderPlannerResult, 'blockers' | 'nextActions'>;
}

function OutputFormatSidecarAcceptanceShell({
  initialScenario,
}: {
  initialScenario: 'ready' | 'stopped';
}) {
  const [scenario, setScenario] = useState<'ready' | 'stopped'>(initialScenario);
  const [state, setState] = useState<Ex04RouteCompletionShellState>({
    loading: true,
    hasRequiresProcessEdge: false,
    hasConsumesMaterialEdge: false,
    routePlan: null,
    plannerSurface: {
      blockers: [],
      nextActions: [],
    },
  });

  useEffect(() => {
    let cancelled = false;
    const contract = outputFormatSidecarComposedContract;
    const activeScenario = scenario === 'ready'
      ? contract.readyScenario
      : contract.stoppedScenario;
    const routePlan = buildEx04RoutePlan(activeScenario);
    const unrelatedBrowserBlocker = {
      id: 'planner.ex04.browser-export.unrelated',
      severity: 'error',
      route: 'browser-export',
      reason: 'route-unsupported',
      message: 'Unrelated browser blocker',
    } as const;
    const unrelatedBrowserAction = {
      kind: 'select-route',
      route: 'browser-export',
      label: 'Select browser export',
      message: 'Unrelated browser action',
    } as const;

    if (cancelled) {
      return;
    }

    setState({
      loading: false,
      hasRequiresProcessEdge: contract.graph.edges.some((edge) => (
        edge.kind === 'requires'
        && edge.detail?.graphPathMarker === contract.graphPathMarker
        && edge.detail?.requirementKind === 'process'
        && edge.detail?.processId === contract.processSpec.id
      )),
      hasConsumesMaterialEdge: contract.graph.edges.some((edge) => (
        edge.kind === 'consumes'
        && edge.detail?.graphPathMarker === contract.graphPathMarker
        && edge.detail?.consumedKind === 'material'
        && edge.detail?.materialRefId === contract.consumedMaterial.id
      )),
      routePlan,
      plannerSurface: {
        blockers: [...activeScenario.blockers, unrelatedBrowserBlocker],
        nextActions: [...activeScenario.nextActions, unrelatedBrowserAction],
      },
    });

    return () => {
      cancelled = true;
    };
  }, [scenario]);

  const activeScenario = scenario === 'ready'
    ? outputFormatSidecarComposedContract.readyScenario
    : outputFormatSidecarComposedContract.stoppedScenario;
  const attachRecords = scenario === 'ready'
    ? [createEx04AttachRecord()]
    : [];

  return (
    <section aria-label="EX-04 browser shell">
      <div data-testid="ex04-loading">{String(state.loading)}</div>
      <div data-testid="ex04-requires-process">{String(state.hasRequiresProcessEdge)}</div>
      <div data-testid="ex04-consumes-material">{String(state.hasConsumesMaterialEdge)}</div>
      {state.routePlan ? (
        <RouteCompletionDashboard
          routePlan={state.routePlan}
          plannerResult={state.plannerSurface}
          extensionRuntime={EX04_RUNTIME}
          processStatuses={[activeScenario.processStatus]}
          processResultAttachRecords={attachRecords}
          onAction={(action) => {
            if (action.kind === 'start-process') {
              setScenario('ready');
            }
          }}
        />
      ) : null}
    </section>
  );
}

describe('M5 composed examples browser acceptance', () => {
  it('covers the EX-02 happy path through the browser provider with graph-backed readiness', async () => {
    render(
      <EffectLiveAcceptanceShell
        initialConfig={makeEffectConfig(makeEffectBinding({
        bake: {
          status: 'complete',
          deterministicRefs: [bakeDeterministicCapture()],
        },
        }))}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId('ex02-loading')).toHaveTextContent('false');
    });

    expect(screen.getByTestId('ex02-consumes')).toHaveTextContent('true');
    expect(screen.getByTestId('ex02-binds-live')).toHaveTextContent('true');
    expect(screen.getByTestId('ex02-export-blocked')).toHaveTextContent('false');
    expect(screen.queryByText('export/live-binding-unresolved')).toBeNull();
  });

  it('covers the EX-02 blocker and repair path through a blocker action card', async () => {
    const user = userEvent.setup();

    render(
      <EffectLiveAcceptanceShell
        initialConfig={makeEffectConfig(makeEffectBinding())}
      />,
    );

    expect(await screen.findByText('export/live-binding-unresolved')).toBeInTheDocument();
    expect(screen.getByTestId('ex02-export-blocked')).toHaveTextContent('true');

    await user.click(screen.getByRole('button', { name: 'Bake live binding' }));

    await waitFor(() => {
      expect(screen.getByTestId('ex02-export-blocked')).toHaveTextContent('false');
    });

    expect(screen.getByTestId('ex02-consumes')).toHaveTextContent('true');
    expect(screen.getByTestId('ex02-binds-live')).toHaveTextContent('true');
    expect(screen.queryByText('export/live-binding-unresolved')).toBeNull();
  });

  it('covers the EX-03 happy path through the browser provider with transition-mask consumption', async () => {
    render(
      <TransitionMaskAcceptanceShell initialMaterialState="resolved" />,
    );

    await waitFor(() => {
      expect(screen.getByTestId('ex03-loading')).toHaveTextContent('false');
    });

    expect(screen.getByTestId('ex03-transition-consumes')).toHaveTextContent('true');
    expect(screen.getByTestId('ex03-mask-consumes')).toHaveTextContent('true');
    expect(screen.queryByText('composition/material-not-resolved')).toBeNull();
  });

  it('covers the EX-03 blocker and repair path through the material browser action surface', async () => {
    const user = userEvent.setup();

    render(
      <TransitionMaskAcceptanceShell initialMaterialState="missing" />,
    );

    expect(await screen.findByText('composition/material-not-resolved')).toBeInTheDocument();
    expect(screen.getByTestId('ex03-transition-consumes')).toHaveTextContent('true');
    expect(screen.getByTestId('ex03-mask-consumes')).toHaveTextContent('false');

    await user.click(screen.getByRole('button', { name: 'Materialize transition mask' }));

    await waitFor(() => {
      expect(screen.getByTestId('ex03-mask-consumes')).toHaveTextContent('true');
    });

    expect(screen.queryByText('composition/material-not-resolved')).toBeNull();
  });

  it('covers the EX-04 happy path through the route completion dashboard with graph-backed artifact evidence', async () => {
    render(
      <OutputFormatSidecarAcceptanceShell initialScenario="ready" />,
    );

    await waitFor(() => {
      expect(screen.getByTestId('ex04-loading')).toHaveTextContent('false');
    });

    expect(screen.getByTestId('ex04-requires-process')).toHaveTextContent('true');
    expect(screen.getByTestId('ex04-consumes-material')).toHaveTextContent('true');
    expect(screen.getByTestId(`route-completion-status-${EX04_ROUTE}`)).toHaveTextContent('complete');
    expect(screen.getByTestId('route-completion-profile-sidecar')).toHaveTextContent('complete');
    expect(screen.getByTestId(`route-completion-process-status-${EX04_PROCESS_DESCRIPTOR.processId}`)).toHaveTextContent('ready');
    expect(screen.getByTestId(`route-completion-artifact-${EX04_ARTIFACT_EVIDENCE.artifact.id}`)).toHaveTextContent('metadata-export.json');
    expect(screen.queryByText('Unrelated browser blocker')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Select browser export' })).toBeNull();
  });

  it('covers the EX-04 stopped-process repair path through the route completion dashboard action surface', async () => {
    const user = userEvent.setup();

    render(
      <OutputFormatSidecarAcceptanceShell initialScenario="stopped" />,
    );

    expect(await screen.findByText(/requires the Example Analyzer process/i)).toBeInTheDocument();
    expect(screen.getByTestId(`route-completion-status-${EX04_ROUTE}`)).toHaveTextContent('blocked');
    expect(screen.getByTestId(`route-completion-process-status-${EX04_PROCESS_DESCRIPTOR.processId}`)).toHaveTextContent('stopped');

    await user.click(screen.getByRole('button', { name: 'Start Example Analyzer Process' }));

    await waitFor(() => {
      expect(screen.getByTestId(`route-completion-status-${EX04_ROUTE}`)).toHaveTextContent('complete');
    });

    expect(screen.getByTestId(`route-completion-process-status-${EX04_PROCESS_DESCRIPTOR.processId}`)).toHaveTextContent('ready');
    expect(screen.queryByText(/requires the Example Analyzer process/i)).toBeNull();
    expect(screen.getByTestId(`route-completion-sidecar-${EX04_ARTIFACT_EVIDENCE.manifest.sidecars[0]!.id}`)).toHaveTextContent('metadata-export.manifest.json');
    expect(screen.queryByText('Unrelated browser blocker')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Select browser export' })).toBeNull();
  });
});
