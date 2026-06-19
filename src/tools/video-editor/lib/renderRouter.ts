// Sprint 8 (SD-027 + SD-034): render-button routing.
//
// Decides whether the user's "Render" click should:
//   * stay in the existing client-side WebCodecs path (`useClientRender`),
//     which handles pure-media + Reigh-native clipTypes ("text",
//     "effect-layer", "media", "hold").
//   * delegate to the new orchestrator `banodoco_render_timeline` task,
//     which the banodoco-worker pool services with Node + Chromium +
//     Remotion + the @banodoco/timeline-theme-* packages.
//
// Decision rule (per sprint brief):
//   * If ANY clip's clipType is in THEME_PACKAGE_REGISTRY → orchestrator.
//   * Mixed timelines (themed + media) → orchestrator (option (a)
//     in the architecture doc; uniform composition end-to-end inside
//     the worker, no cross-task ffmpeg-join).
//   * Pure-Reigh-native timelines → client-side render (untouched).
//
// The router is shape-driven — it inspects the resolved TimelineConfig
// and returns a tagged decision. The caller (UI hook) translates that
// decision into either a `useClientRender` invocation or an
// `enqueueBanodocoRenderTimeline` POST.
//
// We intentionally do NOT inspect `timeline.theme` — a timeline can
// declare a theme but only contain pure-media clips, and the existing
// client renderer can still handle that. The trigger is the clipType
// dispatch, not theme presence.

import type { TimelineRenderRequest } from '@/tools/video-editor/hooks/timeline-state-types.ts';
import { getRegisteredClipTypeDescriptor } from '@/tools/video-editor/clip-types/runtime.ts';
import {
  getGeneratedRemotionModuleStatus,
  type GeneratedRemotionModuleBlockReason,
  type GeneratedLaneClipShape,
} from '@/tools/video-editor/lib/generated-lanes.ts';
import { materializeSequenceConfig } from '@/tools/video-editor/sequences/materialize.ts';
import type { ContributionRenderability } from '@/tools/video-editor/runtime/renderability.ts';

/** Minimal clip shape we need from the resolved timeline. */
export interface RouterClipShape extends GeneratedLaneClipShape {
  clipType?: string;
}

/** Minimal timeline shape we need from the resolved config. */
export interface RouterTimelineShape {
  clips?: ReadonlyArray<RouterClipShape> | null;
}

/**
 * Minimal contributed clip record the router needs to check dynamic
 * capability declarations. Consumers pass a subset of
 * ClipTypeRegistryRecord or an equivalent shape extracted from the
 * provider-scoped registry snapshot.
 */
export interface ContributedClipRecord {
  readonly clipTypeId: string;
  readonly renderability: ContributionRenderability;
}

/**
 * Sprint 8 (final): provider-id taxonomy used by the render pipeline +
 * `renderPipeline.ts`. Each route maps 1:1 onto a provider id so middleware
 * can dispatch on the route without a separate lookup table.
 *
 *   * `browser-remotion`  — client-side WebCodecs / Remotion path
 *                          (`useClientRender`, native + media clips).
 *   * `worker-banodoco`   — orchestrator `banodoco_render_timeline`
 *                          (themed + generated-remotion-module clips).
 *   * `preview-only`      — generated remotion_module clips with invalid /
 *                          missing artifact metadata. Cannot be rendered;
 *                          surfaces a hard "render blocked" message.
 *   * `external`          — reserved for future external render providers.
 *                          Currently unreachable from `decideRenderRoute`.
 */
export type RenderRoute =
  | 'browser-remotion'
  | 'worker-banodoco'
  | 'preview-only'
  | 'external';

export type RenderProviderId = RenderRoute;

export const RENDER_PROVIDER_REGISTRY: Readonly<Record<RenderRoute, RenderProviderId>> = {
  'browser-remotion': 'browser-remotion',
  'worker-banodoco': 'worker-banodoco',
  'preview-only': 'preview-only',
  external: 'external',
};

export interface RenderRouteDecision {
  route: RenderRoute;
  /** True iff at least one clip is themed (i.e. uses the registry). */
  hasThemedClip: boolean;
  /** True iff at least one clip is pure-media / Reigh-native. */
  hasMediaClip: boolean;
  /** True iff at least one clip is a contributed extension clip. */
  hasContributedClip: boolean;
  reason:
    | 'no_clips'
    | 'pure_native_clips'
    | 'themed_only'
    | 'mixed_themed_and_media'
    | 'generated_remotion_module'
    | 'mixed_generated_module_and_other'
    | 'browser_capable_contributed'
    | 'mixed_browser_capable_contributed_and_native'
    | 'contributed_blocked_no_browser_capability'
    | 'contributed_blocked_worker_route_conflict'
    | GeneratedRemotionModuleBlockReason;
}

const NATIVE_BUILTIN_CLIP_TYPES: ReadonlySet<string> = new Set([
  'media',
  'text',
  'effect-layer',
  'hold',
  'automation',
]);

const isNativeBuiltinClipType = (value: unknown): boolean => {
  // Treat undefined/null clipType as media-equivalent (pre-clipType
  // legacy clips). They route to the client renderer.
  if (typeof value !== 'string') return true;
  return NATIVE_BUILTIN_CLIP_TYPES.has(value);
};

const isCustomRenderClipType = (value: unknown): boolean => {
  if (typeof value !== 'string') {
    return false;
  }
  const descriptor = getRegisteredClipTypeDescriptor(value);
  return descriptor?.renderCapabilities.exportRoute === 'custom';
};

/**
 * Map contributed clip records by clipTypeId for O(1) lookup during the
 * routing loop.
 */
function indexContributedRecords(
  records: ReadonlyArray<ContributedClipRecord> | undefined,
): ReadonlyMap<string, ContributedClipRecord> {
  if (!records || records.length === 0) return new Map();
  const map = new Map<string, ContributedClipRecord>();
  for (const record of records) {
    if (!map.has(record.clipTypeId)) {
      map.set(record.clipTypeId, record);
    }
  }
  return map;
}

/**
 * Check whether a contributed clip record explicitly declares a supported
 * browser-export capability.
 */
function hasBrowserExportCapability(
  record: ContributedClipRecord,
): boolean {
  return record.renderability.capabilities.some(
    (c) => c.route === 'browser-export' && c.status === 'supported',
  );
}

/** Pure-decision routing — call this from a hook or test. */
export function decideRenderRoute(
  timeline: RouterTimelineShape | null | undefined,
  contributedClipRecords?: ReadonlyArray<ContributedClipRecord>,
): RenderRouteDecision {
  const clips = (timeline?.clips ?? []) as ReadonlyArray<RouterClipShape>;
  const contributedIndex = indexContributedRecords(contributedClipRecords);

  if (clips.length === 0) {
    return {
      route: 'browser-remotion',
      hasThemedClip: false,
      hasMediaClip: false,
      hasContributedClip: false,
      reason: 'no_clips',
    };
  }

  let hasThemedClip = false;
  let hasMediaClip = false;
  let hasContributedClip = false;
  let hasBrowserCapableContributedClip = false;
  let hasNativeOrMediaClip = false;
  let hasGeneratedModuleClip = false;
  let hasOtherClip = false;
  for (const clip of clips) {
    const moduleStatus = getGeneratedRemotionModuleStatus(clip);
    if (moduleStatus.kind === 'blocked_module') {
      return {
        route: 'preview-only',
        hasThemedClip: false,
        hasMediaClip: false,
        hasContributedClip: false,
        reason: moduleStatus.reason,
      };
    }
    if (moduleStatus.kind === 'valid_module') {
      hasGeneratedModuleClip = true;
      continue;
    }

    hasOtherClip = true;

    // M9 T11: Check contributed clip records first. Contributed clip
    // code is only allowed in browser-remotion when it explicitly
    // declares browser-export capability. Worker routes are always
    // blocked for contributed code (SD1).
    const clipType = clip?.clipType;
    if (typeof clipType === 'string') {
      const contributedRecord = contributedIndex.get(clipType);
      if (contributedRecord) {
        hasContributedClip = true;
        if (hasBrowserExportCapability(contributedRecord)) {
          hasBrowserCapableContributedClip = true;
        } else {
          // Contributed clip without browser-export capability is
          // immediately blocked — worker routes are out of scope
          // for contributed code and no other route is available.
          return {
            route: 'preview-only',
            hasThemedClip: false,
            hasMediaClip: false,
            hasContributedClip: true,
            reason: 'contributed_blocked_no_browser_capability',
          };
        }
        continue;
      }
    }

    // Non-contributed clips follow existing routing.
    if (isCustomRenderClipType(clip?.clipType)) {
      hasThemedClip = true;
      // A themed clip mixed with browser-capable contributed clips
      // creates a conflict: themed clips need worker, contributed
      // clips can't go to worker.
      if (hasBrowserCapableContributedClip) {
        return {
          route: 'preview-only',
          hasThemedClip: true,
          hasMediaClip: true,
          hasContributedClip: true,
          reason: 'contributed_blocked_worker_route_conflict',
        };
      }
    } else if (isNativeBuiltinClipType(clip?.clipType)) {
      hasMediaClip = true;
      hasNativeOrMediaClip = true;
    } else {
      // Unknown clipType (theme package not installed, typo). Treat as
      // media so the existing render path's loud-placeholder fallback
      // surfaces — orchestrator wouldn't be able to render it either
      // without the theme package, and the sprint scopes us to
      // registered themes.
      hasMediaClip = true;
      hasNativeOrMediaClip = true;
    }
  }

  // Generated Remotion module clips always go to the worker pool if
  // they survived the blocked_module short-circuit above. Mixed
  // generated + browser-capable contributed clips create an
  // unresolvable conflict because contributed code cannot execute in
  // the worker.
  if (hasGeneratedModuleClip) {
    if (hasBrowserCapableContributedClip) {
      return {
        route: 'preview-only',
        hasThemedClip,
        hasMediaClip,
        hasContributedClip: true,
        reason: 'contributed_blocked_worker_route_conflict',
      };
    }
    return {
      route: 'worker-banodoco',
      hasThemedClip,
      hasMediaClip,
      hasContributedClip: false,
      reason: hasOtherClip ? 'mixed_generated_module_and_other' : 'generated_remotion_module',
    };
  }

  // Browser-capable contributed clips mixed with themed clips already
  // short-circuit above (contributed_blocked_worker_route_conflict).
  // Here we handle the remaining combinations.

  if (hasBrowserCapableContributedClip) {
    if (hasThemedClip) {
      // Should not reach here (caught above), but defensive.
      return {
        route: 'preview-only',
        hasThemedClip: true,
        hasMediaClip: true,
        hasContributedClip: true,
        reason: 'contributed_blocked_worker_route_conflict',
      };
    }
    if (hasNativeOrMediaClip) {
      // Mixed browser-capable contributed + native → browser-remotion
      // handles both.
      return {
        route: 'browser-remotion',
        hasThemedClip: false,
        hasMediaClip: true,
        hasContributedClip: true,
        reason: 'mixed_browser_capable_contributed_and_native',
      };
    }
    // Pure browser-capable contributed clips
    return {
      route: 'browser-remotion',
      hasThemedClip: false,
      hasMediaClip: false,
      hasContributedClip: true,
      reason: 'browser_capable_contributed',
    };
  }

  if (hasThemedClip && hasMediaClip) {
    return {
      route: 'worker-banodoco',
      hasThemedClip,
      hasMediaClip,
      hasContributedClip: false,
      reason: 'mixed_themed_and_media',
    };
  }
  if (hasThemedClip) {
    return {
      route: 'worker-banodoco',
      hasThemedClip,
      hasMediaClip,
      hasContributedClip: false,
      reason: 'themed_only',
    };
  }
  return {
    route: 'browser-remotion',
    hasThemedClip,
    hasMediaClip,
    hasContributedClip: false,
    reason: 'pure_native_clips',
  };
}

// ---------------------------------------------------------------------------
// Orchestrator dispatch (banodoco_render_timeline)
// ---------------------------------------------------------------------------

export interface BanodocoRenderTimelinePayload {
  timeline_id: string;
  timeline: unknown;
  assets: unknown;
  theme_id: string;
  output_filename: string;
  user_jwt: string;
  project_id: string;
  correlation_id: string;
}

export interface BuildRenderPayloadInput {
  /**
   * The TimelineRenderRequest the UI/hook composed for this render.
   * `renderRuntime.projectId` and `assetRegistry` are read from here,
   * keeping caller call-sites aligned with the rest of the pipeline.
   */
  request: Pick<TimelineRenderRequest, 'timelineId' | 'assetRegistry' | 'resolvedConfig' | 'renderRuntime'> & {
    outputFilename?: string;
  };
  userJwt: string;
  /** Tests inject a deterministic UUID; production uses crypto.randomUUID. */
  correlationId?: string;
}

const FALLBACK_THEME_ID = '2rp';

function defaultThemeId(config: { theme?: string } | null | undefined): string {
  const value = config?.theme;
  return typeof value === 'string' && value.trim() ? value : FALLBACK_THEME_ID;
}

function defaultOutputFilename(timelineId: string): string {
  // Suggested filename — the worker may suffix with task_id.
  return `timeline-${timelineId}.mp4`;
}

function newCorrelationId(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return globalThis.crypto.randomUUID();
  }
  // Defensive non-prod fallback (e.g. test envs without the crypto API);
  // the sprint's prod path has crypto everywhere.
  return `corr-${Math.random().toString(16).slice(2)}-${Date.now().toString(16)}`;
}

export function buildRenderTimelinePayload(
  input: BuildRenderPayloadInput,
): { payload?: BanodocoRenderTimelinePayload; error?: string } {
  const { request } = input;
  if (!request?.timelineId) return { error: 'timelineId is required' };
  if (!request?.renderRuntime?.projectId) return { error: 'projectId is required' };
  if (!input.userJwt) return { error: 'user JWT is required (SD-022)' };
  if (!request.resolvedConfig) return { error: 'resolved timeline config is required' };

  return {
    payload: {
      timeline_id: request.timelineId,
      timeline: materializeSequenceConfig(request.resolvedConfig as Parameters<typeof materializeSequenceConfig>[0]),
      assets: request.assetRegistry ?? { assets: {} },
      theme_id: defaultThemeId(request.resolvedConfig),
      output_filename: request.outputFilename ?? defaultOutputFilename(request.timelineId),
      user_jwt: input.userJwt,
      project_id: request.renderRuntime.projectId,
      correlation_id: input.correlationId ?? newCorrelationId(),
    },
  };
}

export interface EnqueueRenderResult {
  status: 'queued' | 'error';
  task_id?: string;
  correlation_id?: string;
  message: string;
}

interface OrchestratorEnqueueResponse {
  task_id?: string;
}

/** POST `banodoco_render_timeline` to the orchestrator's enqueue endpoint.
 *
 * Mirrors `delegateToBanodocoAgent.enqueueBanodocoTask` to keep the
 * agent + UI dispatch on one paper trail.
 */
export async function enqueueBanodocoRenderTimeline(
  payload: BanodocoRenderTimelinePayload,
  options: {
    fetchImpl?: typeof fetch;
    orchestratorBaseUrl: string;
  },
): Promise<EnqueueRenderResult> {
  if (!options.orchestratorBaseUrl) {
    return {
      status: 'error',
      message: 'orchestratorBaseUrl is required for banodoco_render_timeline.',
    };
  }
  const base = options.orchestratorBaseUrl.replace(/\/$/, '');
  const enqueueUrl = base.includes('/functions/v1/')
    ? base
    : `${base}/functions/v1/enqueue-task`;

  const fetchImpl = options.fetchImpl ?? fetch;

  const body = {
    task_type: 'banodoco_render_timeline',
    params: payload,
    project_id: payload.project_id,
    run_type: 'banodoco-worker',
    worker_pool: 'banodoco',
  };

  let resp: Response;
  try {
    resp = await fetchImpl(enqueueUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${payload.user_jwt}`,
      },
      body: JSON.stringify(body),
    });
  } catch (err) {
    return {
      status: 'error',
      message: `Failed to reach orchestrator: ${err instanceof Error ? err.message : String(err)}`,
    };
  }

  if (resp.status >= 400) {
    let errBody = '';
    try {
      errBody = (await resp.text()).slice(0, 500);
    } catch {
      // ignore
    }
    return {
      status: 'error',
      message: `Orchestrator rejected enqueue (HTTP ${resp.status}): ${errBody}`,
    };
  }

  let parsed: OrchestratorEnqueueResponse | null = null;
  try {
    parsed = (await resp.json()) as OrchestratorEnqueueResponse;
  } catch {
    // 2xx with no body is acceptable.
  }

  return {
    status: 'queued',
    task_id: parsed?.task_id,
    correlation_id: payload.correlation_id,
    message:
      'Themed render queued — the editor will surface the download URL when the worker finishes.',
  };
}
