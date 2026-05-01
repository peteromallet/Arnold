import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { __getServeHandler, __resetServeHandler } from '../_tests/mocks/denoHttpServer.ts';
import * as AiGenerateSequenceEntrypoint from './index.ts';

const mocks = vi.hoisted(() => ({
  bootstrapEdgeHandler: vi.fn(),
  enforceRateLimit: vi.fn(),
  toErrorMessage: vi.fn((error: unknown) => (error instanceof Error ? error.message : String(error))),
}));

vi.mock('../_shared/edgeHandler.ts', () => ({
  bootstrapEdgeHandler: (...args: unknown[]) => mocks.bootstrapEdgeHandler(...args),
  NO_SESSION_RUNTIME_OPTIONS: {},
}));

vi.mock('../_shared/rateLimit.ts', () => ({
  enforceRateLimit: (...args: unknown[]) => mocks.enforceRateLimit(...args),
  RATE_LIMITS: {
    expensive: { maxRequests: 10, windowSeconds: 60 },
  },
}));

vi.mock('../_shared/http.ts', () => ({
  jsonResponse: (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
}));

vi.mock('../_shared/errorMessage.ts', () => ({
  toErrorMessage: (...args: unknown[]) => mocks.toErrorMessage(...args),
}));

function stubDenoEnv(): void {
  vi.stubGlobal('Deno', {
    env: {
      get: (key: string) => {
        if (key === 'ANTHROPIC_API_KEY') return 'anthropic-test-key';
        return undefined;
      },
    },
  });
}

function createLogger() {
  return {
    info: vi.fn(),
    flush: vi.fn().mockResolvedValue(undefined),
  };
}

function createAnthropicSseResponse(content: string): Response {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({
          type: 'content_block_delta',
          delta: { type: 'text_delta', text: content },
        })}\n\n`));
        controller.close();
      },
    }),
    {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    },
  );
}

async function loadHandler() {
  await import('./index.ts');
  return __getServeHandler();
}

describe('ai-generate-sequence edge entrypoint', () => {
  it('imports entrypoint module directly', () => {
    expect(AiGenerateSequenceEntrypoint).toBeDefined();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    __resetServeHandler();
    stubDenoEnv();
    vi.stubGlobal('fetch', vi.fn(async () =>
      createAnthropicSseResponse(JSON.stringify({
        drafts: [
          {
            clipType: 'resource-card',
            hold: 3,
            params: {
              title: 'Leverage for creators',
              previewAssetKeys: ['asset-a'],
            },
          },
        ],
      }))
    ));

    mocks.enforceRateLimit.mockResolvedValue(null);
    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin: {},
        logger: createLogger(),
        auth: { userId: 'user-1' },
        body: {
          prompt: 'Create a resource beat',
          timeline: { clips: [] },
          selected_clips: [{ assetKey: 'asset-a' }],
          attached_clips: [],
          allowed_clip_types: ['resource-card'],
          allowed_assets: ['asset-a'],
          theme: '2rp',
          theme_overrides: { visual: { color: { accent: '#00ff88' } } },
        },
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('returns bootstrap failure response untouched', async () => {
    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: false,
      response: new Response('blocked', { status: 418 }),
    });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/ai-generate-sequence', { method: 'POST' }));

    expect(response.status).toBe(418);
    await expect(response.text()).resolves.toBe('blocked');
  });

  it('returns 401 when auth user is missing before rate limiting', async () => {
    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin: {},
        logger: createLogger(),
        auth: { userId: '' },
        body: { prompt: 'Generate a sequence' },
      },
    });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/ai-generate-sequence', { method: 'POST' }));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({ error: 'Authentication failed' });
    expect(mocks.enforceRateLimit).not.toHaveBeenCalled();
  });

  it('returns validated structured drafts from Anthropic output', async () => {
    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/ai-generate-sequence', { method: 'POST' }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      drafts: [
        {
          clipType: 'resource-card',
          hold: 3,
          params: {
            title: 'Leverage for creators',
            previewAssetKeys: ['asset-a'],
          },
        },
      ],
      invalid_drafts: [],
      model: 'claude-opus-4-6',
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'https://api.anthropic.com/v1/messages',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'x-api-key': 'anthropic-test-key',
        }),
      }),
    );
    const body = JSON.parse((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body as string);
    expect(body.model).toBe('claude-opus-4-6');
    expect(body.stream).toBe(true);
    expect(body.system).toContain('trusted structured timeline sequence drafts');
    expect(body.messages[0].content).toContain('allowed_asset_keys');
  });

  it('extracts valid drafts from prose-wrapped fenced JSON', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      createAnthropicSseResponse(`The prompt asks for a professional animation sequence.

\`\`\`json
${JSON.stringify({
  drafts: [
    {
      clipType: 'resource-card',
      hold: 3,
      params: {
        title: 'Use the attached reference',
        previewAssetKeys: ['asset-a'],
      },
    },
  ],
})}
\`\`\``)
    ));

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/ai-generate-sequence', { method: 'POST' }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      drafts: [
        {
          clipType: 'resource-card',
          hold: 3,
          params: {
            title: 'Use the attached reference',
            previewAssetKeys: ['asset-a'],
          },
        },
      ],
      invalid_drafts: [],
    });
  });

  it('repairs Anthropic output that contains no JSON before returning drafts', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(createAnthropicSseResponse('The prompt asks for an animated sequence, but I need more context.'))
      .mockResolvedValueOnce(createAnthropicSseResponse(JSON.stringify({
        drafts: [
          {
            clipType: 'resource-card',
            hold: 3,
            params: {
              title: 'Repaired draft',
              previewAssetKeys: ['asset-a'],
            },
          },
        ],
      }))));

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/ai-generate-sequence', { method: 'POST' }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      drafts: [
        {
          clipType: 'resource-card',
          hold: 3,
          params: {
            title: 'Repaired draft',
            previewAssetKeys: ['asset-a'],
          },
        },
      ],
      invalid_drafts: [],
    });
    expect(globalThis.fetch).toHaveBeenCalledTimes(2);
    const repairBody = JSON.parse((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[1][1].body as string);
    expect(repairBody.system).toContain('repair malformed Reigh sequence draft responses');
  });

  it('returns a stable 422 when repair output still contains no JSON', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(createAnthropicSseResponse('The prompt asks for an animated sequence, but I need more context.'))
      .mockResolvedValueOnce(createAnthropicSseResponse('I still cannot provide the JSON.')));

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/ai-generate-sequence', { method: 'POST' }));

    expect(response.status).toBe(422);
    await expect(response.json()).resolves.toEqual({
      error: 'Model response did not contain valid sequence JSON.',
    });
    expect(globalThis.fetch).toHaveBeenCalledTimes(2);
  });

  it('drops invalid model drafts and returns structured validation errors without raw draft values', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      createAnthropicSseResponse(JSON.stringify({
        drafts: [
          {
            clipType: 'resource-card',
            hold: 3,
            params: {
              title: 'https://evil.example/image.png',
              previews: ['https://evil.example/image.png'],
              code: 'function Bad() { return React.createElement("div"); }',
              entrance: 'fade',
            },
          },
        ],
      }))
    ));

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/ai-generate-sequence', { method: 'POST' }));
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.drafts).toEqual([]);
    expect(JSON.stringify(body)).not.toContain('https://evil.example');
    expect(JSON.stringify(body)).not.toContain('function Bad');
    expect(body.invalid_drafts[0].errors.map((error: { code: string }) => error.code)).toEqual(
      expect.arrayContaining(['raw_url', 'reserved_component_param', 'generated_code_field', 'animation_ref']),
    );
  });

  it('appears behind the same rate-limit convention as ai-generate-effect', async () => {
    mocks.enforceRateLimit.mockResolvedValue(
      new Response(JSON.stringify({ error: 'Rate limit service unavailable' }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/ai-generate-sequence', { method: 'POST' }));

    expect(response.status).toBe(503);
    expect(mocks.enforceRateLimit).toHaveBeenCalledWith(expect.objectContaining({
      functionName: 'ai-generate-sequence',
      userId: 'user-1',
    }));
  });
});
