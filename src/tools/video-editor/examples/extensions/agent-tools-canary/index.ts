/**
 * agent-tools-canary — Fake long-running generation canary extension.
 *
 * Demonstrates the full M10 agent tool SDK surface:
 *   - Contributed tool metadata (AgentToolContribution)
 *   - Progress reporting via GenerationSession callbacks
 *   - Cancellation support
 *   - Preview-only GenerationSession with placeholder sample channel
 *   - Proposal-ready output (mutation/proposal result family)
 *   - Fake baked asset/material refs (material/artifact result family)
 *   - Structured diagnostics
 *
 * This file must NOT import from editor internals (src/tools/video-editor/*).
 * It imports exclusively from @reigh/editor-sdk, the public SDK entrypoint.
 *
 * @publicContract
 * @milestone M10
 */

import { defineExtension } from '@reigh/editor-sdk';
import type {
  ReighExtension,
  ExtensionContext,
  DisposeHandle,
  AgentToolContribution,
  AgentToolHandler,
  AgentToolInvocationRequest,
  ToolResult,
  ToolGenerationSessionResult,
  ToolMutationProposalResult,
  ToolMaterialArtifactResult,
  ToolResultDiagnostic,
  GenerationSession,
  ToolArtifactRef,
  ToolSourceRef,
  TimelinePatch,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CANARY_EXTENSION_ID = 'com.reigh.examples.agent-tools-canary';
const GENERATION_TOOL_ID = 'canary.generation';
const MATERIAL_TOOL_ID = 'canary.material';
const PROPOSAL_TOOL_ID = 'canary.proposal';

// ---------------------------------------------------------------------------
// Fake GenerationSession factory
// ---------------------------------------------------------------------------

/**
 * Create a fake GenerationSession that simulates long-running generation.
 *
 * - Starts at progress 0 and auto-advances to 100 over a configurable duration.
 * - Supports cancellation (stops the interval and marks cancelled).
 * - Provides a preview-only sample channel placeholder.
 * - Emits progress callbacks so the host can render a progress bar.
 * - Completes with final result data (fake baked asset refs).
 */
function createFakeGenerationSession(
  toolId: string,
  extensionId: string,
  durationMs: number = 3000,
  onProgress?: (progress: number, label?: string) => void,
): GenerationSession {
  const sessionId = `${toolId}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  const progressListeners = new Set<(progress: number, label?: string) => void>();

  let _progress = 0;
  let _cancelled = false;
  let _done = false;
  let _progressLabel: string | undefined = 'Generating…';
  const _diagnostics: ToolResultDiagnostic[] = [];
  let _interval: ReturnType<typeof setInterval> | null = null;
  let _completeResult: Record<string, unknown> | undefined;

  const notifyProgress = (p: number, label?: string) => {
    for (const listener of progressListeners) {
      try {
        listener(p, label);
      } catch {
        // Listener errors must not break the session
      }
    }
    if (onProgress) {
      try {
        onProgress(p, label);
      } catch {
        // Callback errors must not break the session
      }
    }
  };

  // Start auto-advancing progress
  const stepCount = 20;
  const stepInterval = durationMs / stepCount;

  _interval = setInterval(() => {
    if (_cancelled || _done) return;

    _progress = Math.min(100, _progress + (100 / stepCount));
    _progressLabel =
      _progress < 100
        ? `Generating… (${Math.round(_progress)}%)`
        : 'Generation complete';

    notifyProgress(_progress, _progressLabel);

    if (_progress >= 100) {
      if (_interval) {
        clearInterval(_interval);
        _interval = null;
      }
      _done = true;
      _completeResult = {
        status: 'complete',
        sessionId,
        bakedAssets: [
          { ref: 'fake-asset-001', kind: 'asset', label: 'Generated texture A' },
          { ref: 'fake-material-001', kind: 'material', label: 'Generated material X' },
        ],
      };
    }
  }, stepInterval);

  return {
    get id(): string {
      return sessionId;
    },
    get progress(): number {
      return _progress;
    },
    get progressLabel(): string | undefined {
      return _progressLabel;
    },
    get cancelled(): boolean {
      return _cancelled;
    },
    get done(): boolean {
      return _done;
    },
    get diagnostics(): readonly ToolResultDiagnostic[] {
      return _diagnostics;
    },

    onProgress(listener: (progress: number, label?: string) => void): DisposeHandle {
      progressListeners.add(listener);
      return {
        dispose(): void {
          progressListeners.delete(listener);
        },
      };
    },

    cancel(): void {
      if (_cancelled || _done) return;
      _cancelled = true;
      if (_interval) {
        clearInterval(_interval);
        _interval = null;
      }
      _diagnostics.push({
        severity: 'info',
        code: 'agent-tool/generation-cancelled',
        message: `Generation session ${sessionId} was cancelled at ${Math.round(_progress)}%.`,
        detail: { sessionId, toolId, extensionId, cancelledAt: Date.now() },
      });
      notifyProgress(_progress, 'Cancelled');
    },

    getSampleChannel(): string {
      // Preview-only placeholder — no real media buffers in M10
      return `sample-channel:${sessionId}:preview-only`;
    },

    complete(result?: Record<string, unknown>): void {
      if (_done || _cancelled) return;
      if (_interval) {
        clearInterval(_interval);
        _interval = null;
      }
      _done = true;
      _progress = 100;
      _completeResult = result ?? { status: 'complete', sessionId };
      _progressLabel = 'Generation complete';
      notifyProgress(_progress, _progressLabel);
    },
  };
}

// ---------------------------------------------------------------------------
// Tool handlers
// ---------------------------------------------------------------------------

/**
 * Generation tool handler — returns a GenerationSession with progress,
 * cancellation, and a preview-only sample channel.
 */
const generationHandler: AgentToolHandler = (
  request: AgentToolInvocationRequest,
): ToolGenerationSessionResult => {
  const durationMs = (request.input?.durationMs as number) ?? 3000;
  const toolId = request.toolId;
  const extensionId = request.extensionId;

  const session = createFakeGenerationSession(toolId, extensionId, durationMs);

  const diagnostics: ToolResultDiagnostic[] = [
    {
      severity: 'info',
      code: 'agent-tool/generation-started',
      message: `Generation session ${session.id} started (duration: ${durationMs}ms).`,
      detail: {
        sessionId: session.id,
        toolId,
        extensionId,
        durationMs,
      },
    },
  ];

  return {
    family: 'generation/session',
    session,
    rationale:
      `Fake long-running generation canary. Simulates a ${durationMs}ms ` +
      `generation with progress, cancellation, and a preview-only sample channel.`,
    diagnostics,
  };
};

/**
 * Material/artifact tool handler — returns fake baked asset/material refs.
 */
const materialHandler: AgentToolHandler = (
  request: AgentToolInvocationRequest,
): ToolMaterialArtifactResult => {
  const refs: ToolArtifactRef[] = [
    {
      ref: `canary-baked-asset-${Date.now()}`,
      kind: 'asset',
      label: 'Canary baked texture (fake)',
      meta: {
        resolution: '1024x1024',
        format: 'png',
        generated: true,
        placeholder: true,
      },
    },
    {
      ref: `canary-baked-material-${Date.now()}`,
      kind: 'material',
      label: 'Canary baked material (fake)',
      meta: {
        shadingModel: 'pbr',
        roughness: 0.5,
        metallic: 0.0,
        generated: true,
        placeholder: true,
      },
    },
    {
      ref: `canary-placeholder-${Date.now()}`,
      kind: 'placeholder',
      label: 'Canary placeholder ref (fake)',
      meta: {
        note: 'This is a placeholder — no real bake occurred.',
        timestamp: Date.now(),
      },
    },
  ];

  const diagnostics: ToolResultDiagnostic[] = [
    {
      severity: 'info',
      code: 'agent-tool/fake-refs-generated',
      message: `Generated ${refs.length} fake baked asset/material/placeholder refs.`,
      detail: { refCount: refs.length },
    },
    {
      severity: 'warning',
      code: 'agent-tool/placeholder-refs',
      message:
        'These are placeholder refs — no real bake or asset generation occurred. ' +
        'Replace with real generation pipeline in M11/M12.',
      detail: { note: 'canary-only' },
    },
  ];

  return {
    family: 'material/artifact',
    refs,
    rationale:
      'Fake baked asset/material/placeholder refs demonstrating the material/artifact result family. ' +
      'No real generation or baking occurred.',
    diagnostics,
  };
};

/**
 * Proposal tool handler — returns a proposal-ready mutation/proposal result
 * with fake patches, affected objects, and source-to-output refs.
 */
const proposalHandler: AgentToolHandler = (
  request: AgentToolInvocationRequest,
): ToolMutationProposalResult => {
  const timeline = request.context?.timeline;
  const clipCount = timeline?.clips?.length ?? 0;
  const trackCount = timeline?.tracks?.length ?? 0;

  // Build fake patches based on timeline context
  const patches: TimelinePatch[] = [];
  const affectedObjectIds: string[] = [];

  if (timeline?.clips && timeline.clips.length > 0) {
    const firstClip = timeline.clips[0];
    affectedObjectIds.push(firstClip.id);

    patches.push({
      version: timeline.baseVersion,
      source: request.toolId,
      meta: { kind: 'canary-proposal', toolId: request.toolId },
      operations: [
        {
          op: 'project-data.write',
          target: request.extensionId,
          payload: {
            key: 'canary.lastProposal',
            value: {
              clipId: firstClip.id,
              clipType: firstClip.clipType ?? 'unknown',
              timestamp: Date.now(),
            },
            mode: 'replace',
          },
        },
      ],
    });
  }

  // Also add a track-level proposal
  if (timeline?.tracks && timeline.tracks.length > 0) {
    const firstTrack = timeline.tracks[0];
    affectedObjectIds.push(firstTrack.id);

    patches.push({
      version: timeline.baseVersion,
      source: request.toolId,
      meta: { kind: 'canary-track-proposal', toolId: request.toolId },
      operations: [
        {
          op: 'project-data.write',
          target: request.extensionId,
          payload: {
            key: 'canary.lastTrackProposal',
            value: {
              trackId: firstTrack.id,
              trackKind: firstTrack.kind,
              timestamp: Date.now(),
            },
            mode: 'replace',
          },
        },
      ],
    });
  }

  const sourceRefs: ToolSourceRef[] = affectedObjectIds.map((id, index) => ({
    sourceId: id,
    outputId: `canary-output-${id}-${index}`,
    description: `Canary source→output trace for ${id}`,
  }));

  return {
    family: 'mutation/proposal',
    rationale:
      `Canary proposal result based on timeline snapshot ` +
      `(${clipCount} clips, ${trackCount} tracks). ` +
      `Patches are fake but carry realistic metadata for proposal conversion testing.`,
    patches,
    affectedObjectIds,
    sourceRefs,
    diagnostics: [
      {
        severity: 'info',
        code: 'agent-tool/canary-proposal-generated',
        message: `Generated ${patches.length} proposal patches for ${affectedObjectIds.length} affected objects.`,
        detail: {
          patchCount: patches.length,
          affectedCount: affectedObjectIds.length,
          clipCount,
          trackCount,
        },
      },
    ],
  };
};

// ---------------------------------------------------------------------------
// Extension definition
// ---------------------------------------------------------------------------

export const agentToolsCanaryExtension: ReighExtension = defineExtension({
  manifest: {
    id: CANARY_EXTENSION_ID as any,
    version: '1.0.0',
    label: 'Agent Tools Canary',
    description:
      'Fake long-running generation canary demonstrating the M10 agent tool SDK surface: ' +
      'progress reporting, cancellation, preview-only GenerationSession, placeholder ' +
      'sample channel, proposal-ready output, fake baked asset/material refs, and diagnostics.',
    apiVersion: 1,

    contributions: [
      {
        id: 'canary-generation-contribution' as any,
        kind: 'agentTool',
        toolId: GENERATION_TOOL_ID,
        label: 'Canary Generation Tool',
        description:
          'Fake long-running generation tool that exercises progress reporting, ' +
          'cancellation, and preview-only sample channels through GenerationSession.',
        resultFamilies: ['generation/session'],
        order: 10,
      } satisfies AgentToolContribution,

      {
        id: 'canary-material-contribution' as any,
        kind: 'agentTool',
        toolId: MATERIAL_TOOL_ID,
        label: 'Canary Material Tool',
        description:
          'Fake material/artifact tool returning placeholder baked asset and material refs.',
        resultFamilies: ['material/artifact'],
        order: 20,
      } satisfies AgentToolContribution,

      {
        id: 'canary-proposal-contribution' as any,
        kind: 'agentTool',
        toolId: PROPOSAL_TOOL_ID,
        label: 'Canary Proposal Tool',
        description:
          'Fake proposal tool returning mutation/proposal results with patches, ' +
          'affected object IDs, and source-to-output refs.',
        resultFamilies: ['mutation/proposal'],
        order: 30,
      } satisfies AgentToolContribution,
    ],

    messages: {
      'activation.started': 'Agent Tools Canary activating…',
      'activation.ready': 'Agent Tools Canary ready with 3 fake tools registered.',
      'activation.disposed': 'Agent Tools Canary disposed.',
    },
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    // Activation diagnostic
    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'canary/activation-started',
      message: ctx.services.i18n.t('activation.started'),
    });

    // Register generation tool handler
    const genHandle = ctx.agentTools!.registerTool(GENERATION_TOOL_ID, generationHandler);

    // Register material tool handler
    const matHandle = ctx.agentTools!.registerTool(MATERIAL_TOOL_ID, materialHandler);

    // Register proposal tool handler
    const propHandle = ctx.agentTools!.registerTool(PROPOSAL_TOOL_ID, proposalHandler);

    // Activation-ready diagnostic
    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'canary/activation-ready',
      message: ctx.services.i18n.t('activation.ready'),
    });
    ctx.chrome.toast(ctx.services.i18n.t('activation.ready'), 'info');

    return {
      dispose(): void {
        genHandle.dispose();
        matHandle.dispose();
        propHandle.dispose();
        ctx.services.diagnostics.report({
          severity: 'info',
          code: 'canary/activation-disposed',
          message: ctx.services.i18n.t('activation.disposed'),
        });
      },
    };
  },
});
