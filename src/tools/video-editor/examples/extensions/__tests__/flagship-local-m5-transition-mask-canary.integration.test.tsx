import { describe, expect, it, vi } from 'vitest';
import type {
  AgentToolInvocationRequest,
  ProposalRuntime,
  RenderMaterialRef,
  TimelineSnapshot,
  ToolMaterialArtifactResult,
} from '@reigh/editor-sdk';
import { flagshipLocalExtension } from '@/tools/video-editor/examples/extensions/flagship-local';
import { projectHostMaterialRuntime } from '@/tools/video-editor/runtime/composition/materialRuntime.ts';
import { applyGraphPreviewOperations } from '@/tools/video-editor/runtime/composition/patchPreview.ts';
import { normalizeExtensionRuntime } from '@/tools/video-editor/runtime/extensionSurface.ts';
import { createAgentToolInvocationService } from '@/tools/video-editor/runtime/agentToolInvocationService';

const FLAGSHIP_EXTENSION_ID = 'com.reigh.examples.flagship-local';
const FLAGSHIP_WIPE_CONTRIBUTION_ID = 'flagship-transition-wipe';
const FLAGSHIP_WIPE_TRANSITION_ID = 'com.reigh.flagship.transition.wipe';
const FLAGSHIP_WIPE_REF_KEY = `transition:${FLAGSHIP_EXTENSION_ID}:${FLAGSHIP_WIPE_CONTRIBUTION_ID}`;
const FLAGSHIP_WIPE_NODE_ID = `contribution:${FLAGSHIP_WIPE_REF_KEY}`;
const CLIP_ID = 'clip-flagship-wipe-mask';
const MASK_SLOT_NAME = 'transition-mask';
const MASK_MATERIAL_REF_ID = 'mat-flagship-transition-mask';

function makeSnapshot(): TimelineSnapshot {
  const transition = {
    id: `${CLIP_ID}.transition.${FLAGSHIP_WIPE_TRANSITION_ID}`,
    clipId: CLIP_ID,
    transitionType: FLAGSHIP_WIPE_TRANSITION_ID,
    duration: 0.75,
    managed: true,
    managedBy: FLAGSHIP_EXTENSION_ID,
    params: {
      direction: 'right',
      softness: 0.2,
    },
  };

  return {
    projectId: 'flagship-transition-mask-canary',
    baseVersion: 1,
    currentVersion: 1,
    extensionRequirements: [],
    clips: [{
      id: CLIP_ID,
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

async function promoteMaskMaterial(): Promise<RenderMaterialRef> {
  const registry = {
    invokeTool: vi.fn().mockResolvedValue({
      family: 'material/artifact',
      refs: [
        {
          ref: MASK_MATERIAL_REF_ID,
          kind: 'material',
          meta: {
            promotion: {
              schemaVersion: 1,
              mediaKind: 'image',
              locator: {
                kind: 'artifact-store',
                uri: 'artifact://materials/flagship-transition-mask.png',
                contentSha256: 'c'.repeat(64),
                mimeType: 'image/png',
              },
              determinism: 'deterministic',
              replacementPolicy: 'materialize-on-export',
              routeConstraints: ['preview', 'browser-export'],
              provenance: {
                capture: 'agent-mask',
                model: 'deterministic-masker',
              },
              consumedRefs: [CLIP_ID],
              inputHashes: {
                [CLIP_ID]: 'mask-input-hash',
              },
              producedAt: '2026-07-04T13:10:00.000Z',
            },
          },
        },
      ],
    } satisfies ToolMaterialArtifactResult),
  };
  const proposalRuntime = {
    currentVersion: 1,
    create: vi.fn(),
  } as ProposalRuntime;
  const service = createAgentToolInvocationService({
    registry: registry as any,
    proposalRuntime,
  });
  const request: AgentToolInvocationRequest = {
    toolId: 'mask-materializer',
    extensionId: FLAGSHIP_EXTENSION_ID,
    contributionId: 'flagship-agent-mask-tool' as any,
    context: {
      projectId: 'flagship-transition-mask-canary',
    },
  };

  const result = await service.invokeTool(request);
  expect(result?.family).toBe('material/artifact');
  expect(proposalRuntime.create).not.toHaveBeenCalled();

  const durableRecord = (result as ToolMaterialArtifactResult).refs[0]?.durableRecord;
  expect(durableRecord).toEqual(expect.objectContaining({
    durableKind: 'material',
    id: MASK_MATERIAL_REF_ID,
    determinism: 'deterministic',
    producer: expect.objectContaining({
      extensionId: FLAGSHIP_EXTENSION_ID,
      toolId: 'mask-materializer',
    }),
  }));

  return durableRecord as RenderMaterialRef;
}

describe('flagship-local M5 transition/mask canary', () => {
  it('proves EX-03 transition consumes and transition-mask mask-material consumes with the attached promoted material ref id', async () => {
    const runtime = normalizeExtensionRuntime([flagshipLocalExtension]);
    const snapshot = makeSnapshot();
    const transition = snapshot.clips[0]?.transition;
    expect(transition).toBeDefined();
    const transitionId = transition!.id;

    const transitionDescriptor = runtime.transitions.find((descriptor) => (
      descriptor.id === FLAGSHIP_WIPE_CONTRIBUTION_ID
      && descriptor.transitionId === FLAGSHIP_WIPE_TRANSITION_ID
    ));
    expect(transitionDescriptor).toBeDefined();
    expect(transitionDescriptor!.materialSlots).toEqual([
      expect.objectContaining({
        name: MASK_SLOT_NAME,
        label: 'Transition Mask',
      }),
    ]);

    const promotedMaskMaterial = await promoteMaskMaterial();
    const preview = applyGraphPreviewOperations({
      snapshot,
      contributionIndex: runtime.contributionIndex,
      materialRuntime: projectHostMaterialRuntime({
        materialRefs: [promotedMaskMaterial],
      }),
      materialSlotDeclarations: transitionDescriptor!.materialSlots.map((slot) => ({
        owner: {
          kind: 'transition',
          clipId: CLIP_ID,
          ownerId: transitionId,
        },
        slotName: slot.name,
      })),
    }, [
      {
        kind: 'material.attach',
        owner: {
          kind: 'transition',
          clipId: CLIP_ID,
          ownerId: transitionId,
        },
        slotName: MASK_SLOT_NAME,
        materialRefId: promotedMaskMaterial.id,
      },
    ]);

    expect(preview?.diagnostics).toEqual([]);
    expect(preview?.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'consumes',
        sourceNodeId: `clip:${CLIP_ID}`,
        targetNodeId: FLAGSHIP_WIPE_NODE_ID,
        detail: expect.objectContaining({
          transitionId,
          clipId: CLIP_ID,
          transitionType: FLAGSHIP_WIPE_TRANSITION_ID,
          refKey: FLAGSHIP_WIPE_REF_KEY,
          consumedKind: 'transition',
          ownerKind: 'transition',
          ownerId: transitionId,
        }),
      }),
      expect.objectContaining({
        kind: 'consumes',
        sourceNodeId: `clip:${CLIP_ID}`,
        targetNodeId: FLAGSHIP_WIPE_NODE_ID,
        detail: expect.objectContaining({
          transitionId,
          clipId: CLIP_ID,
          transitionType: FLAGSHIP_WIPE_TRANSITION_ID,
          refKey: FLAGSHIP_WIPE_REF_KEY,
          consumedKind: 'mask-material',
          targetSlot: MASK_SLOT_NAME,
          materialRefId: promotedMaskMaterial.id,
          ownerKind: 'transition',
          ownerId: transitionId,
        }),
      }),
    ]));
  });
});
