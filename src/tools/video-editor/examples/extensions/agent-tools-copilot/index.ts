/**
 * agent-tools-copilot — Copilot proposal canary extension.
 *
 * Demonstrates M10 copilot-style agent tools that:
 *   - Read TimelineSnapshot from request context
 *   - Return proposal rationale/explanation with affected objects
 *   - Include source-to-output refs for traceability
 *   - Demonstrate replaceForSource by using a stable source identifier,
 *     which causes ProposalRuntime.create() to atomically replace
 *     prior pending proposals from the same tool source.
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
  ToolMutationProposalResult,
  ToolUISummaryResult,
  ToolResultDiagnostic,
  ToolSourceRef,
  TimelinePatch,
  TimelineSnapshot,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COPILOT_EXTENSION_ID = 'com.reigh.examples.agent-tools-copilot';
const COPILOT_ANALYZE_TOOL_ID = 'canary.copilot.analyze';
const COPILOT_SUGGEST_TOOL_ID = 'canary.copilot.suggest';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Build a stable source identifier for replaceForSource semantics.
 *
 * When the same tool ID + extension ID produces multiple mutation/proposal
 * results with the same source identifier, ProposalRuntime.create() will
 * atomically replace the previous pending proposal from that source.
 *
 * By using a fixed source string, each subsequent call to the copilot
 * suggestion tool replaces the prior pending suggestion.
 */
function copilotSource(toolId: string): string {
  return `${toolId}`;
}

/**
 * Build source-to-output refs from a timeline snapshot.
 * Maps each clip to a synthetic output ID for traceability.
 */
function buildSourceRefsFromSnapshot(
  snapshot: TimelineSnapshot,
): ToolSourceRef[] {
  const refs: ToolSourceRef[] = [];

  for (const clip of snapshot.clips) {
    refs.push({
      sourceId: clip.id,
      outputId: `copilot-output-${clip.id}`,
      description: `Copilot trace: clip ${clip.id} (${clip.clipType ?? 'unknown'}) → analysis output`,
    });
  }

  for (const track of snapshot.tracks) {
    refs.push({
      sourceId: track.id,
      outputId: `copilot-output-${track.id}`,
      description: `Copilot trace: track ${track.id} (${track.kind}) → analysis output`,
    });
  }

  return refs;
}

/**
 * Build a copilot analysis summary from the timeline snapshot.
 */
function buildAnalysisSummary(snapshot: TimelineSnapshot): {
  summary: string;
  detail: Record<string, unknown>;
} {
  const clipCount = snapshot.clips.length;
  const trackCount = snapshot.tracks.length;
  const managedCount = snapshot.clips.filter((c) => c.managed).length;
  const visualTrackCount = snapshot.tracks.filter((t) => t.kind === 'visual').length;
  const audioTrackCount = snapshot.tracks.filter((t) => t.kind === 'audio').length;
  const assetCount = snapshot.assetKeys.length;

  const clipTypes = new Set(snapshot.clips.map((c) => c.clipType ?? 'unknown'));
  const totalDuration = snapshot.clips.reduce((sum, c) => sum + (c.duration ?? 0), 0);

  const summaryLines: string[] = [];
  summaryLines.push(`Timeline analysis: ${clipCount} clips across ${trackCount} tracks.`);
  summaryLines.push(
    `${visualTrackCount} visual tracks, ${audioTrackCount} audio tracks.`,
  );
  summaryLines.push(
    `${managedCount} clips are extension-managed, ${clipCount - managedCount} are host-owned.`,
  );
  if (assetCount > 0) {
    summaryLines.push(`${assetCount} assets referenced.`);
  }
  summaryLines.push(`Total clip duration: ${totalDuration} frames.`);
  summaryLines.push(`Clip types present: ${[...clipTypes].join(', ')}.`);

  return {
    summary: summaryLines.join('\n'),
    detail: {
      clipCount,
      trackCount,
      visualTrackCount,
      audioTrackCount,
      managedCount,
      assetCount,
      totalDuration,
      clipTypes: [...clipTypes],
      clipIds: snapshot.clips.map((c) => c.id),
      trackIds: snapshot.tracks.map((t) => t.id),
      baseVersion: snapshot.baseVersion,
      currentVersion: snapshot.currentVersion,
    },
  };
}

// ---------------------------------------------------------------------------
// Tool handlers
// ---------------------------------------------------------------------------

/**
 * Analyze tool handler — reads TimelineSnapshot and returns a UI summary
 * with detailed analysis, source-to-output refs, and diagnostics.
 */
const analyzeHandler: AgentToolHandler = (
  request: AgentToolInvocationRequest,
): ToolUISummaryResult => {
  const snapshot = request.context?.timeline;

  if (!snapshot) {
    return {
      family: 'ui/summary',
      summary: 'No timeline snapshot available for analysis.',
      diagnostics: [
        {
          severity: 'warning',
          code: 'agent-tool/missing-timeline-context',
          message:
            'Copilot analyze tool was invoked without a timeline snapshot. ' +
            'Provide a timeline context for richer analysis.',
        },
      ],
      detail: { missingContext: 'timeline' },
    };
  }

  const { summary, detail } = buildAnalysisSummary(snapshot);
  const sourceRefs = buildSourceRefsFromSnapshot(snapshot);

  return {
    family: 'ui/summary',
    summary,
    detail: {
      ...detail,
      sourceRefs,
    },
    diagnostics: [
      {
        severity: 'info',
        code: 'agent-tool/copilot-analysis-complete',
        message: `Copilot analysis complete: ${snapshot.clips.length} clips, ${snapshot.tracks.length} tracks.`,
        detail: {
          clipCount: snapshot.clips.length,
          trackCount: snapshot.tracks.length,
          sourceRefCount: sourceRefs.length,
        },
      },
    ],
  };
};

/**
 * Suggest tool handler — reads TimelineSnapshot and returns a
 * mutation/proposal result with patches derived from timeline analysis.
 *
 * Uses a stable source identifier so that repeated calls replace
 * prior pending suggestions from this tool (replaceForSource semantics).
 */
const suggestHandler: AgentToolHandler = (
  request: AgentToolInvocationRequest,
): ToolMutationProposalResult => {
  const snapshot = request.context?.timeline;

  if (!snapshot) {
    // Return a proposal with empty patches but with diagnostics
    return {
      family: 'mutation/proposal',
      rationale:
        'Copilot suggestion could not be generated: no timeline snapshot available.',
      patches: [],
      affectedObjectIds: [],
      sourceRefs: [],
      diagnostics: [
        {
          severity: 'warning',
          code: 'agent-tool/missing-timeline-context',
          message:
            'Copilot suggest tool was invoked without a timeline snapshot. ' +
            'No suggestions can be generated.',
        },
      ],
    };
  }

  const patches: TimelinePatch[] = [];
  const affectedObjectIds: string[] = [];

  // Build a copilot-authored project-data patch to demonstrate proposal output
  // Using the stable source identifier for replaceForSource semantics
  patches.push({
    version: snapshot.baseVersion,
    source: copilotSource(request.toolId),
    meta: {
      kind: 'copilot-suggestion',
      toolId: request.toolId,
      suggestionIndex: Date.now(),
    },
    operations: [
      {
        op: 'project-data.write',
        target: request.extensionId,
        payload: {
          key: 'copilot.lastSuggestion',
          value: {
            timestamp: Date.now(),
            clipCount: snapshot.clips.length,
            trackCount: snapshot.tracks.length,
            baseVersion: snapshot.baseVersion,
            suggestedClips: snapshot.clips.slice(0, 10).map((c) => ({
              id: c.id,
              track: c.track,
              clipType: c.clipType,
              at: c.at,
            })),
          },
          mode: 'replace',
        },
      },
    ],
  });

  // Add affected object IDs from the timeline
  for (const clip of snapshot.clips.slice(0, 5)) {
    affectedObjectIds.push(clip.id);
  }
  for (const track of snapshot.tracks.slice(0, 2)) {
    affectedObjectIds.push(track.id);
  }

  // Build source-to-output refs
  const sourceRefs = buildSourceRefsFromSnapshot(snapshot);

  // Build rationale explaining the suggestion
  const rationaleLines: string[] = [];
  rationaleLines.push(
    `Copilot suggestion based on timeline analysis: ${snapshot.clips.length} clips, ` +
      `${snapshot.tracks.length} tracks, base version ${snapshot.baseVersion}.`,
  );

  const managedCount = snapshot.clips.filter((c) => c.managed).length;
  if (managedCount > 0) {
    rationaleLines.push(
      `${managedCount} extension-managed clips detected — review managed objects ` +
        `before accepting any automation proposals.`,
    );
  }

  if (snapshot.assetKeys.length === 0) {
    rationaleLines.push(
      'Note: No assets are referenced in the timeline. Consider adding media assets.',
    );
  }

  return {
    family: 'mutation/proposal',
    rationale: rationaleLines.join('\n'),
    patches,
    affectedObjectIds,
    sourceRefs,
    diagnostics: [
      {
        severity: 'info',
        code: 'agent-tool/copilot-suggestion-generated',
        message:
          `Copilot suggestion generated with ${patches.length} patches, ` +
          `${affectedObjectIds.length} affected objects, ` +
          `${sourceRefs.length} source→output refs.`,
        detail: {
          patchCount: patches.length,
          affectedCount: affectedObjectIds.length,
          sourceRefCount: sourceRefs.length,
          clipCount: snapshot.clips.length,
          trackCount: snapshot.tracks.length,
          baseVersion: snapshot.baseVersion,
        },
      },
    ],
  };
};

// ---------------------------------------------------------------------------
// Extension definition
// ---------------------------------------------------------------------------

export const agentToolsCopilotExtension: ReighExtension = defineExtension({
  manifest: {
    id: COPILOT_EXTENSION_ID as any,
    version: '1.0.0',
    label: 'Agent Tools Copilot Canary',
    description:
      'Copilot proposal canary demonstrating M10 agent tools that read TimelineSnapshot, ' +
      'return proposal rationale/explanation with affected objects and source-to-output refs, ' +
      'and demonstrate replaceForSource by replacing prior pending suggestions from the same tool source.',
    apiVersion: 1,

    contributions: [
      {
        id: 'copilot-analyze-contribution' as any,
        kind: 'agentTool',
        toolId: COPILOT_ANALYZE_TOOL_ID,
        label: 'Copilot Analyze',
        description:
          'Reads TimelineSnapshot and returns a detailed analysis with source-to-output refs.',
        resultFamilies: ['ui/summary'],
        order: 10,
      } satisfies AgentToolContribution,

      {
        id: 'copilot-suggest-contribution' as any,
        kind: 'agentTool',
        toolId: COPILOT_SUGGEST_TOOL_ID,
        label: 'Copilot Suggest',
        description:
          'Reads TimelineSnapshot and returns mutation/proposal results with patches, ' +
          'affected object IDs, and source-to-output refs. Uses a stable source identifier ' +
          'so repeated calls replace prior pending proposals (replaceForSource).',
        resultFamilies: ['mutation/proposal'],
        order: 20,
      } satisfies AgentToolContribution,
    ],

    messages: {
      'activation.started': 'Agent Tools Copilot Canary activating…',
      'activation.ready':
        'Agent Tools Copilot Canary ready with analyze and suggest tools registered.',
      'activation.disposed': 'Agent Tools Copilot Canary disposed.',
    },
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    // Activation diagnostic
    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'copilot/activation-started',
      message: ctx.services.i18n.t('activation.started'),
    });

    // Register analyze tool handler
    const analyzeHandle = ctx.agentTools!.registerTool(
      COPILOT_ANALYZE_TOOL_ID,
      analyzeHandler,
    );

    // Register suggest tool handler
    const suggestHandle = ctx.agentTools!.registerTool(
      COPILOT_SUGGEST_TOOL_ID,
      suggestHandler,
    );

    // Activation-ready diagnostic
    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'copilot/activation-ready',
      message: ctx.services.i18n.t('activation.ready'),
    });
    ctx.chrome.toast(ctx.services.i18n.t('activation.ready'), 'info');

    return {
      dispose(): void {
        analyzeHandle.dispose();
        suggestHandle.dispose();
        ctx.services.diagnostics.report({
          severity: 'info',
          code: 'copilot/activation-disposed',
          message: ctx.services.i18n.t('activation.disposed'),
        });
      },
    };
  },
});
