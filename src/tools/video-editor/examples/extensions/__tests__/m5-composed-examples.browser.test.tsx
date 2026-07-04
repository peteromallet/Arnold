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
import { projectCompositionGraph } from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import { createLiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry.ts';
import { normalizeExtensionRuntime } from '@/tools/video-editor/runtime/extensionSurface.ts';
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

const EMPTY_ASSET_REGISTRY = { assets: {} };
const FLAGSHIP_RUNTIME = normalizeExtensionRuntime([flagshipLocalExtension]);
const FLAGSHIP_DECLARED_IDS = collectExtensionDeclaredIds(
  flagshipLocalExtension.manifest.contributions ?? [],
);

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

interface EffectShellState {
  loading: boolean;
  hasConsumesEdge: boolean;
  hasBindsLiveEdge: boolean;
  exportBlocked: boolean;
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
        exportBlocked: exportResult.hasBlockingErrors,
        blockerMessage: exportResult.diagnostics.find((diagnostic) => diagnostic.code === 'export/live-binding-unresolved')?.message ?? null,
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
      {state.blockerMessage ? (
        <BlockerActionCard
          severity="error"
          code="export/live-binding-unresolved"
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
});
