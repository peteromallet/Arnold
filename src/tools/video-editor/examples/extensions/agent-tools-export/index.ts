/**
 * agent-tools-export — Export-adjacent canary extension.
 *
 * Demonstrates M10 agent tools for export-planning that:
 *   - Read only explicit request context (timeline, assets, export context)
 *   - Return exportPlanFindings (CapabilityFinding-shaped records)
 *     via the 'export' ToolResult family
 *   - Represent missing contribution/export blocker context
 *     as findings or diagnostics
 *   - Never access raw provider internals — everything comes from
 *     the explicit serializable request context
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
  ToolExportResult,
  ToolResultDiagnostic,
  AgentToolExportContext,
  TimelineSnapshot,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const EXPORT_EXTENSION_ID = 'com.reigh.examples.agent-tools-export';
const EXPORT_PLAN_TOOL_ID = 'canary.export.plan';
const EXPORT_VALIDATE_TOOL_ID = 'canary.export.validate';

// ---------------------------------------------------------------------------
// Finding shape (compatible with CapabilityFinding from renderability.ts)
// ---------------------------------------------------------------------------

interface ExportPlanFinding {
  readonly id: string;
  readonly severity: 'error' | 'warning' | 'info';
  readonly route?: string;
  readonly reason?: string;
  readonly message: string;
  readonly extensionId?: string;
  readonly contributionId?: string;
  readonly clipId?: string;
  readonly materialRefId?: string;
  readonly detail?: Record<string, unknown>;
}

/**
 * Build an export plan finding from an export context analysis.
 */
function buildFinding(
  id: string,
  severity: 'error' | 'warning' | 'info',
  message: string,
  detail?: Record<string, unknown>,
): ExportPlanFinding {
  return {
    id,
    severity,
    message,
    ...(detail ? { detail } : {}),
  };
}

// ---------------------------------------------------------------------------
// Export context analysis
// ---------------------------------------------------------------------------

interface ExportContextAnalysis {
  hasExportContext: boolean;
  hasOutputFormat: boolean;
  hasTimeline: boolean;
  hasAssets: boolean;
  hasBlockers: boolean;
  hasContributions: boolean;
  missingFields: string[];
}

function analyzeExportContext(
  exportCtx?: AgentToolExportContext,
  timeline?: TimelineSnapshot,
  assets?: readonly { key: string; metadata?: Record<string, unknown> }[],
): ExportContextAnalysis {
  const analysis: ExportContextAnalysis = {
    hasExportContext: !!exportCtx,
    hasOutputFormat: !!exportCtx?.outputFormatId,
    hasTimeline: !!timeline,
    hasAssets: !!(assets && assets.length > 0),
    hasBlockers: !!(exportCtx?.blockers && exportCtx.blockers.length > 0),
    hasContributions: !!(
      exportCtx?.contributionIds && exportCtx.contributionIds.length > 0
    ),
    missingFields: [],
  };

  if (!exportCtx) {
    analysis.missingFields.push('export context (entirely missing)');
  } else {
    if (!exportCtx.outputFormatId) {
      analysis.missingFields.push('outputFormatId');
    }
    if (!exportCtx.blockers || exportCtx.blockers.length === 0) {
      analysis.missingFields.push('blockers list (empty or missing)');
    }
    if (!exportCtx.contributionIds || exportCtx.contributionIds.length === 0) {
      analysis.missingFields.push('contributionIds (empty or missing)');
    }
  }

  if (!timeline) {
    analysis.missingFields.push('timeline snapshot');
  }

  if (!assets || assets.length === 0) {
    analysis.missingFields.push('assets list (empty or missing)');
  }

  return analysis;
}

/**
 * Build diagnostic findings from export context analysis.
 */
function buildExportFindings(
  analysis: ExportContextAnalysis,
  toolId: string,
  extensionId: string,
): {
  findings: ExportPlanFinding[];
  diagnostics: ToolResultDiagnostic[];
} {
  const findings: ExportPlanFinding[] = [];
  const diagnostics: ToolResultDiagnostic[] = [];

  // ---- Presence findings ----

  if (analysis.hasExportContext) {
    findings.push(
      buildFinding(
        `${toolId}.export-context-present`,
        'info',
        'Export context is present and will be analyzed.',
        { toolId, extensionId },
      ),
    );
  } else {
    findings.push(
      buildFinding(
        `${toolId}.export-context-missing`,
        'warning',
        'No export context provided. Export planning is limited without format, blocker, and contribution information.',
        {
          toolId,
          extensionId,
          recommendation:
            'Include AgentToolExportContext in the request payload for richer analysis.',
        },
      ),
    );
    diagnostics.push({
      severity: 'warning',
      code: 'agent-tool/missing-export-context',
      message:
        'Export tool invoked without export context. Provide outputFormatId, blockers, and contributionIds for complete planning.',
    });
  }

  if (analysis.hasOutputFormat) {
    findings.push(
      buildFinding(
        `${toolId}.output-format-present`,
        'info',
        'Output format is selected — export plan can target a specific format.',
        { toolId, extensionId },
      ),
    );
  } else {
    findings.push(
      buildFinding(
        `${toolId}.output-format-missing`,
        'warning',
        'No output format selected. The export plan cannot tailor recommendations to a specific format.',
        {
          toolId,
          extensionId,
          recommendation: 'Select an output format before invoking export planning.',
        },
      ),
    );
  }

  if (analysis.hasBlockers) {
    findings.push(
      buildFinding(
        `${toolId}.blockers-present`,
        'info',
        'Render blockers are reported in the export context. These will be included in the plan.',
        { toolId, extensionId },
      ),
    );
  } else {
    findings.push(
      buildFinding(
        `${toolId}.blockers-missing`,
        'info',
        'No render blockers reported. If blockers exist, include them in the export context for accurate planning.',
        { toolId, extensionId },
      ),
    );
  }

  if (analysis.hasContributions) {
    findings.push(
      buildFinding(
        `${toolId}.contributions-present`,
        'info',
        'Contribution IDs are available for export. Export plan can assess contribution renderability.',
        { toolId, extensionId },
      ),
    );
  } else {
    findings.push(
      buildFinding(
        `${toolId}.contributions-missing`,
        'warning',
        'No contribution IDs provided. The export plan cannot assess per-contribution renderability or export readiness.',
        {
          toolId,
          extensionId,
          recommendation:
            'Include contributionIds in the export context for per-contribution renderability analysis.',
        },
      ),
    );
  }

  // ---- Cross-reference findings ----

  if (analysis.hasTimeline && analysis.hasAssets) {
    findings.push(
      buildFinding(
        `${toolId}.full-context-available`,
        'info',
        'Both timeline snapshot and asset list are available — full export planning is possible.',
        { toolId, extensionId },
      ),
    );
  } else if (analysis.hasTimeline && !analysis.hasAssets) {
    findings.push(
      buildFinding(
        `${toolId}.assets-missing`,
        'warning',
        'Timeline snapshot is available but no asset metadata was provided. Asset-referencing clips may produce export errors.',
        {
          toolId,
          extensionId,
          recommendation:
            'Include asset metadata in the request context for complete export readiness analysis.',
        },
      ),
    );
  } else if (!analysis.hasTimeline && analysis.hasAssets) {
    findings.push(
      buildFinding(
        `${toolId}.timeline-missing`,
        'warning',
        'Asset metadata is available but no timeline snapshot was provided. Export planning is limited to asset-level checks.',
        {
          toolId,
          extensionId,
          recommendation:
            'Include a timeline snapshot in the request context for clip-level export planning.',
        },
      ),
    );
  } else {
    findings.push(
      buildFinding(
        `${toolId}.minimal-context`,
        'error',
        'Neither timeline snapshot nor asset metadata provided. Export planning cannot proceed meaningfully.',
        {
          toolId,
          extensionId,
          missingFields: analysis.missingFields,
          recommendation:
            'Provide at minimum a timeline snapshot or asset metadata in the request context.',
        },
      ),
    );
    diagnostics.push({
      severity: 'error',
      code: 'agent-tool/insufficient-export-context',
      message:
        `Export planning requires at minimum a timeline snapshot or asset metadata. ` +
        `Missing: ${analysis.missingFields.join(', ')}.`,
      detail: { missingFields: analysis.missingFields },
    });
  }

  // ---- Summary diagnostic ----

  diagnostics.push({
    severity: 'info',
    code: 'agent-tool/export-plan-complete',
    message:
      `Export plan analysis complete: ${findings.length} findings, ` +
      `${analysis.missingFields.length} missing fields.`,
    detail: {
      findingCount: findings.length,
      missingFieldCount: analysis.missingFields.length,
      missingFields: analysis.missingFields,
      hasExportContext: analysis.hasExportContext,
      hasOutputFormat: analysis.hasOutputFormat,
      hasTimeline: analysis.hasTimeline,
      hasAssets: analysis.hasAssets,
      hasBlockers: analysis.hasBlockers,
      hasContributions: analysis.hasContributions,
    },
  });

  return { findings, diagnostics };
}

// ---------------------------------------------------------------------------
// Tool handlers
// ---------------------------------------------------------------------------

/**
 * Export plan tool handler — reads explicit request context and returns
 * export plan findings.
 *
 * Reads ONLY the declared context fields:
 *   - context.export (AgentToolExportContext)
 *   - context.timeline (TimelineSnapshot)
 *   - context.assets (asset metadata)
 *
 * Never touches raw provider internals.
 */
const exportPlanHandler: AgentToolHandler = (
  request: AgentToolInvocationRequest,
): ToolExportResult => {
  const exportCtx = request.context?.export;
  const timeline = request.context?.timeline;
  const assets = request.context?.assets;

  const analysis = analyzeExportContext(exportCtx, timeline, assets);
  const { findings, diagnostics } = buildExportFindings(
    analysis,
    request.toolId,
    request.extensionId,
  );

  // Convert findings to plain records (CapabilityFinding-compatible shape)
  const findingsRecords: readonly Record<string, unknown>[] = findings.map(
    (f) => ({
      id: f.id,
      severity: f.severity,
      message: f.message,
      ...(f.route ? { route: f.route } : {}),
      ...(f.reason ? { reason: f.reason } : {}),
      ...(f.extensionId ? { extensionId: f.extensionId } : {}),
      ...(f.contributionId ? { contributionId: f.contributionId } : {}),
      ...(f.clipId ? { clipId: f.clipId } : {}),
      ...(f.materialRefId ? { materialRefId: f.materialRefId } : {}),
      ...(f.detail ? { detail: f.detail } : {}),
    }),
  );

  return {
    family: 'export',
    findings: findingsRecords,
    diagnostics,
    rationale:
      `Export plan analysis based on explicit request context. ` +
      `Context completeness: export=${analysis.hasExportContext}, ` +
      `format=${analysis.hasOutputFormat}, timeline=${analysis.hasTimeline}, ` +
      `assets=${analysis.hasAssets}, blockers=${analysis.hasBlockers}, ` +
      `contributions=${analysis.hasContributions}.`,
  };
};

/**
 * Export validate tool handler — reads explicit request context and returns
 * export findings focused on validation/blocker detection.
 *
 * This tool focuses on identifying blockers and missing contributions
 * rather than general planning. It represents missing contribution or
 * export blocker context as findings and diagnostics.
 */
const exportValidateHandler: AgentToolHandler = (
  request: AgentToolInvocationRequest,
): ToolExportResult => {
  const exportCtx = request.context?.export;
  const timeline = request.context?.timeline;
  const assets = request.context?.assets;

  const findings: ExportPlanFinding[] = [];
  const diagnostics: ToolResultDiagnostic[] = [];

  // ---- Blocker analysis ----

  if (exportCtx?.blockers && exportCtx.blockers.length > 0) {
    // Report existing blockers as error findings
    for (const blocker of exportCtx.blockers) {
      const blockerId = (blocker as Record<string, unknown>).id as string | undefined;
      const blockerMessage =
        (blocker as Record<string, unknown>).message as string | undefined;

      findings.push(
        buildFinding(
          blockerId ?? `${request.toolId}.blocker-${findings.length}`,
          'error',
          blockerMessage ?? 'Unidentified render blocker detected.',
          {
            blocker,
            toolId: request.toolId,
            extensionId: request.extensionId,
            recommendation:
              'Resolve this render blocker before attempting export.',
          },
        ),
      );
    }

    diagnostics.push({
      severity: 'warning',
      code: 'agent-tool/export-blockers-detected',
      message: `${exportCtx.blockers.length} render blocker(s) detected in export context.`,
      detail: {
        blockerCount: exportCtx.blockers.length,
        blockerIds: exportCtx.blockers.map(
          (b) => (b as Record<string, unknown>).id,
        ),
      },
    });
  } else {
    findings.push(
      buildFinding(
        `${request.toolId}.no-blockers`,
        'info',
        'No render blockers detected in export context.',
        { toolId: request.toolId, extensionId: request.extensionId },
      ),
    );
  }

  // ---- Contribution analysis ----

  if (exportCtx?.contributionIds && exportCtx.contributionIds.length > 0) {
    const contributingExtCount = new Set(
      exportCtx.contributionIds.map(
        (c) => c.split('.')[0] ?? c,
      ),
    ).size;

    findings.push(
      buildFinding(
        `${request.toolId}.contributions-available`,
        'info',
        `${exportCtx.contributionIds.length} contribution(s) available from ${contributingExtCount} extension(s).`,
        {
          contributionCount: exportCtx.contributionIds.length,
          extensionCount: contributingExtCount,
          toolId: request.toolId,
          extensionId: request.extensionId,
        },
      ),
    );
  } else {
    findings.push(
      buildFinding(
        `${request.toolId}.contributions-missing`,
        'error',
        'No contributions declared for export. Export cannot proceed without at least one exportable contribution.',
        {
          toolId: request.toolId,
          extensionId: request.extensionId,
          recommendation:
            'Declare contributions via AgentToolExportContext.contributionIds.',
        },
      ),
    );
    diagnostics.push({
      severity: 'error',
      code: 'agent-tool/missing-export-contributions',
      message:
        'No contributions declared for export. Add contributionIds to the export context.',
    });
  }

  // ---- Timeline validation ----

  if (timeline) {
    const emptyClips = timeline.clips.filter(
      (c) => !c.clipType || c.clipType === 'unknown',
    );

    if (emptyClips.length > 0) {
      findings.push(
        buildFinding(
          `${request.toolId}.clips-without-type`,
          'warning',
          `${emptyClips.length} clip(s) have unknown or missing clip types — these may cause export errors.`,
          {
            count: emptyClips.length,
            clipIds: emptyClips.map((c) => c.id),
            toolId: request.toolId,
            extensionId: request.extensionId,
            recommendation:
              'Assign clip types to all timeline clips before export.',
          },
        ),
      );
    }

    if (timeline.tracks.length === 0) {
      findings.push(
        buildFinding(
          `${request.toolId}.empty-timeline`,
          'error',
          'Timeline has no tracks. Export cannot produce meaningful output.',
          {
            toolId: request.toolId,
            extensionId: request.extensionId,
            recommendation: 'Add at least one track to the timeline.',
          },
        ),
      );
    }
  }

  // ---- Asset validation ----

  if (assets && assets.length > 0) {
    const assetsWithoutMetadata = assets.filter(
      (a) => !a.metadata || Object.keys(a.metadata).length === 0,
    );

    if (assetsWithoutMetadata.length > 0) {
      findings.push(
        buildFinding(
          `${request.toolId}.assets-without-metadata`,
          'warning',
          `${assetsWithoutMetadata.length} asset(s) have no metadata — export may produce incomplete artifacts.`,
          {
            count: assetsWithoutMetadata.length,
            assetKeys: assetsWithoutMetadata.map((a) => a.key),
            toolId: request.toolId,
            extensionId: request.extensionId,
            recommendation:
              'Enrich assets with metadata before export for complete artifact generation.',
          },
        ),
      );
    }
  }

  // ---- Summary diagnostic ----

  diagnostics.push({
    severity: 'info',
    code: 'agent-tool/export-validation-complete',
    message:
      `Export validation complete: ${findings.length} findings.`,
    detail: {
      findingCount: findings.length,
      hasBlockers: !!(exportCtx?.blockers && exportCtx.blockers.length > 0),
      hasContributions: !!(
        exportCtx?.contributionIds && exportCtx.contributionIds.length > 0
      ),
      hasTimeline: !!timeline,
      hasAssets: !!(assets && assets.length > 0),
    },
  });

  // Convert findings to plain records
  const findingsRecords: readonly Record<string, unknown>[] = findings.map(
    (f) => ({
      id: f.id,
      severity: f.severity,
      message: f.message,
      ...(f.route ? { route: f.route } : {}),
      ...(f.reason ? { reason: f.reason } : {}),
      ...(f.extensionId ? { extensionId: f.extensionId } : {}),
      ...(f.contributionId ? { contributionId: f.contributionId } : {}),
      ...(f.clipId ? { clipId: f.clipId } : {}),
      ...(f.materialRefId ? { materialRefId: f.materialRefId } : {}),
      ...(f.detail ? { detail: f.detail } : {}),
    }),
  );

  return {
    family: 'export',
    findings: findingsRecords,
    diagnostics,
    rationale:
      `Export validation based on explicit request context: ` +
      `${findingsRecords.length} findings covering blockers, contributions, timeline, and assets.`,
  };
};

// ---------------------------------------------------------------------------
// Extension definition
// ---------------------------------------------------------------------------

export const agentToolsExportExtension: ReighExtension = defineExtension({
  manifest: {
    id: EXPORT_EXTENSION_ID as any,
    version: '1.0.0',
    label: 'Agent Tools Export Canary',
    description:
      'Export-adjacent canary demonstrating M10 agent tools that read only explicit ' +
      'request context (timeline, assets, export) and return exportPlanFindings plus ' +
      'proposal/diagnostic metadata. Represents missing contribution/export blocker ' +
      'context as findings or diagnostics without raw provider internals.',
    apiVersion: 1,

    contributions: [
      {
        id: 'export-plan-contribution' as any,
        kind: 'agentTool',
        toolId: EXPORT_PLAN_TOOL_ID,
        label: 'Export Plan',
        description:
          'Reads explicit export context and returns export plan findings ' +
          'with diagnostic metadata. Never accesses raw provider internals.',
        resultFamilies: ['export'],
        order: 10,
      } satisfies AgentToolContribution,

      {
        id: 'export-validate-contribution' as any,
        kind: 'agentTool',
        toolId: EXPORT_VALIDATE_TOOL_ID,
        label: 'Export Validate',
        description:
          'Reads explicit export context (blockers, contributions, timeline, assets) ' +
          'and returns validation findings. Missing contribution/export blocker context ' +
          'is represented as findings and diagnostics.',
        resultFamilies: ['export'],
        order: 20,
      } satisfies AgentToolContribution,
    ],

    messages: {
      'activation.started': 'Agent Tools Export Canary activating…',
      'activation.ready':
        'Agent Tools Export Canary ready with export plan and validate tools registered.',
      'activation.disposed': 'Agent Tools Export Canary disposed.',
    },
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    // Activation diagnostic
    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'export-canary/activation-started',
      message: ctx.services.i18n.t('activation.started'),
    });

    // Register export plan tool handler
    const planHandle = ctx.agentTools!.registerTool(
      EXPORT_PLAN_TOOL_ID,
      exportPlanHandler,
    );

    // Register export validate tool handler
    const validateHandle = ctx.agentTools!.registerTool(
      EXPORT_VALIDATE_TOOL_ID,
      exportValidateHandler,
    );

    // Activation-ready diagnostic
    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'export-canary/activation-ready',
      message: ctx.services.i18n.t('activation.ready'),
    });
    ctx.chrome.toast(ctx.services.i18n.t('activation.ready'), 'info');

    return {
      dispose(): void {
        planHandle.dispose();
        validateHandle.dispose();
        ctx.services.diagnostics.report({
          severity: 'info',
          code: 'export-canary/activation-disposed',
          message: ctx.services.i18n.t('activation.disposed'),
        });
      },
    };
  },
});
