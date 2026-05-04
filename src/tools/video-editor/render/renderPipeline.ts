import type { TimelineRenderRequest } from '@/tools/video-editor/hooks/timeline-state-types';
import {
  RENDER_PROVIDER_REGISTRY,
  buildRenderTimelinePayload,
  enqueueBanodocoRenderTimeline,
  type RenderProviderId,
  type RenderRouteDecision,
} from '@/tools/video-editor/lib/renderRouter';

export type RenderPipelineEvent =
  | {
      type: 'beforeRender';
      decision: RenderRouteDecision;
      request: TimelineRenderRequest;
    }
  | {
      type: 'assetMaterialized';
      decision: RenderRouteDecision;
      request: TimelineRenderRequest;
      assetCount: number;
    }
  | {
      type: 'afterRender';
      decision: RenderRouteDecision;
      request: TimelineRenderRequest;
      providerId: RenderProviderId;
      message: string;
    }
  | {
      type: 'renderFailed';
      decision: RenderRouteDecision;
      request: TimelineRenderRequest;
      providerId: RenderProviderId;
      error: string;
    };

export type RenderPipelineMiddleware = (event: RenderPipelineEvent) => void | Promise<void>;

export interface BrowserRenderResult {
  status: 'done' | 'error';
  message: string;
}

export interface ExecuteRenderPipelineOptions {
  decision: RenderRouteDecision;
  request: TimelineRenderRequest;
  startBrowserRender: () => Promise<BrowserRenderResult>;
  middlewares?: readonly RenderPipelineMiddleware[];
}

export interface ExecuteRenderPipelineResult {
  status: 'done' | 'queued' | 'error';
  providerId: RenderProviderId;
  message: string;
  taskId?: string;
  correlationId?: string;
}

async function emitRenderPipelineEvent(
  middlewares: readonly RenderPipelineMiddleware[],
  event: RenderPipelineEvent,
): Promise<void> {
  for (const middleware of middlewares) {
    await middleware(event);
  }
}

async function executeProviderRoute({
  decision,
  request,
  startBrowserRender,
}: Pick<ExecuteRenderPipelineOptions, 'decision' | 'request' | 'startBrowserRender'>): Promise<ExecuteRenderPipelineResult> {
  switch (decision.route) {
    case 'browser-remotion': {
      const result = await startBrowserRender();
      return {
        status: result.status,
        providerId: 'browser-remotion',
        message: result.message,
      };
    }
    case 'worker-banodoco': {
      let workerJwt: string | null = null;
      try {
        workerJwt = await request.renderRuntime.getWorkerJwt();
      } catch (error) {
        return {
          status: 'error',
          providerId: 'worker-banodoco',
          message: `Worker render dispatch failed for route "${decision.reason}": ${error instanceof Error ? error.message : String(error)}`,
        };
      }

      if (!workerJwt) {
        return {
          status: 'error',
          providerId: 'worker-banodoco',
          message: `Worker render dispatch failed for route "${decision.reason}": missing worker session token.`,
        };
      }

      const { payload, error } = buildRenderTimelinePayload({
        request,
        userJwt: workerJwt,
      });

      if (!payload) {
        return {
          status: 'error',
          providerId: 'worker-banodoco',
          message: error ?? `Worker render dispatch failed for route "${decision.reason}".`,
        };
      }

      const enqueueResult = await enqueueBanodocoRenderTimeline(payload, {
        orchestratorBaseUrl: request.renderRuntime.orchestratorBaseUrl,
      });

      if (enqueueResult.status === 'error') {
        return {
          status: 'error',
          providerId: 'worker-banodoco',
          message: enqueueResult.message,
        };
      }

      return {
        status: 'queued',
        providerId: 'worker-banodoco',
        taskId: enqueueResult.task_id,
        correlationId: enqueueResult.correlation_id,
        message: enqueueResult.message,
      };
    }
    case 'external':
      return {
        status: 'error',
        providerId: 'external',
        message: `No external render provider is registered for route "${decision.reason}".`,
      };
    case 'preview-only':
      return {
        status: 'error',
        providerId: 'preview-only',
        message: `Render blocked: ${decision.reason}. Preview-only clips require a valid non-browser render provider.`,
      };
    default: {
      const unreachableRoute: never = decision.route;
      throw new Error(`Unknown render route: ${String(unreachableRoute)}`);
    }
  }
}

export async function executeRenderPipeline({
  decision,
  request,
  startBrowserRender,
  middlewares = [],
}: ExecuteRenderPipelineOptions): Promise<ExecuteRenderPipelineResult> {
  const provider = RENDER_PROVIDER_REGISTRY[decision.route];
  const baseEvent = {
    decision,
    request,
  } as const;

  await emitRenderPipelineEvent(middlewares, {
    type: 'beforeRender',
    ...baseEvent,
  });
  await emitRenderPipelineEvent(middlewares, {
    type: 'assetMaterialized',
    ...baseEvent,
    assetCount: Object.keys(request.assetRegistry?.assets ?? {}).length,
  });

  const result = await executeProviderRoute({
    decision: { ...decision, provider },
    request,
    startBrowserRender,
  });

  if (result.status === 'done' || result.status === 'queued') {
    await emitRenderPipelineEvent(middlewares, {
      type: 'afterRender',
      ...baseEvent,
      providerId: result.providerId,
      message: result.message,
    });
  } else {
    await emitRenderPipelineEvent(middlewares, {
      type: 'renderFailed',
      ...baseEvent,
      providerId: result.providerId,
      error: result.message,
    });
  }

  return result;
}
