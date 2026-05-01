import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { __getServeHandler, __resetServeHandler } from '../_tests/mocks/denoHttpServer.ts';
import * as AiGenerateEffectEntrypoint from './index.ts';

const mocks = vi.hoisted(() => ({
  bootstrapEdgeHandler: vi.fn(),
  enforceRateLimit: vi.fn(),
  buildGenerateEffectMessages: vi.fn(),
  toErrorMessage: vi.fn((error: unknown) => (error instanceof Error ? error.message : String(error))),
  groqChatCreate: vi.fn(),
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

vi.mock('./templates.ts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./templates.ts')>();
  return {
    ...actual,
    buildGenerateEffectMessages: (...args: unknown[]) => mocks.buildGenerateEffectMessages(...args),
  };
});

vi.mock('npm:groq-sdk@0.26.0', () => ({
  default: class GroqMock {
    chat = {
      completions: {
        create: (payload: unknown) => mocks.groqChatCreate(payload),
      },
    };

    constructor(_options?: unknown) {}
  },
}));

function stubDenoEnv(): void {
  vi.stubGlobal('Deno', {
    env: {
      get: (key: string) => {
        if (key === 'ANTHROPIC_API_KEY') return 'anthropic-test-key';
        if (key === 'GROQ_API_KEY') return 'groq-test-key';
        if (key === 'FIREWORKS_API_KEY') return 'fireworks-test-key';
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

function createFireworksSseResponse(content: string): Response {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({
          choices: [{ delta: { content } }],
        })}\n\n`));
        controller.enqueue(encoder.encode('data: [DONE]\n\n'));
        controller.close();
      },
    }),
    {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    },
  );
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

describe('ai-generate-effect edge entrypoint', () => {
  it('imports entrypoint module directly', () => {
    expect(AiGenerateEffectEntrypoint).toBeDefined();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    __resetServeHandler();
    stubDenoEnv();
    vi.stubGlobal('fetch', vi.fn(async () =>
      createAnthropicSseResponse(
        '```ts\n// DESCRIPTION: Slides the clip in from the left with a soft easing finish.\n// PARAMS: [{"name":"direction","label":"Direction","description":"Controls which side the clip enters from.","type":"select","default":"left","options":[{"label":"Left","value":"left"},{"label":"Right","value":"right"}]}]\nfunction Example(props){ return React.createElement(AbsoluteFill, null, props.children); }\nexports.default = Example;\n```',
      )
    ));

    mocks.enforceRateLimit.mockResolvedValue(null);
    mocks.buildGenerateEffectMessages.mockReturnValue({
      systemMsg: 'system message',
      userMsg: 'user message',
    });
    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin: {},
        logger: createLogger(),
        auth: { userId: 'user-1' },
        body: {
          prompt: 'Slide the clip in from the left',
          category: 'entrance',
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
    const response = await handler(new Request('https://edge.test/ai-generate-effect', { method: 'POST' }));

    expect(response.status).toBe(418);
    await expect(response.text()).resolves.toBe('blocked');
  });

  it('returns 401 when auth user is missing', async () => {
    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin: {},
        logger: createLogger(),
        auth: { userId: '' },
        body: { prompt: 'Generate an effect', category: 'entrance' },
      },
    });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/ai-generate-effect', { method: 'POST' }));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({ error: 'Authentication failed' });
    expect(mocks.enforceRateLimit).not.toHaveBeenCalled();
  });

  it('returns 503 when rate limit service is unavailable', async () => {
    mocks.enforceRateLimit.mockResolvedValue(
      new Response(JSON.stringify({ error: 'Rate limit service unavailable' }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/ai-generate-effect', { method: 'POST' }));

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({ error: 'Rate limit service unavailable' });
  });

  it('generates an effect and returns code plus extracted metadata', async () => {
    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/ai-generate-effect', { method: 'POST' }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      code: 'function Example(props){ return React.createElement(AbsoluteFill, null, props.children); }\nexports.default = Example;',
      name: '',
      description: 'Slides the clip in from the left with a soft easing finish.',
      parameterSchema: [
        {
          name: 'direction',
          label: 'Direction',
          description: 'Controls which side the clip enters from.',
          type: 'select',
          default: 'left',
          options: [
            { label: 'Left', value: 'left' },
            { label: 'Right', value: 'right' },
          ],
        },
      ],
      model: 'claude-opus-4-6',
    });
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'https://api.anthropic.com/v1/messages',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'x-api-key': 'anthropic-test-key',
          'anthropic-version': '2023-06-01',
        }),
      }),
    );
    expect(mocks.buildGenerateEffectMessages).toHaveBeenCalledWith({
      prompt: 'Slide the clip in from the left',
      category: 'entrance',
      existingCode: undefined,
    });
  });

  it('returns 400 for an invalid category before calling Groq', async () => {
    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        supabaseAdmin: {},
        logger: createLogger(),
        auth: { userId: 'user-1' },
        body: { prompt: 'Generate an effect', category: 'spin-up' },
      },
    });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/ai-generate-effect', { method: 'POST' }));

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({
      error: 'category must be one of: entrance, exit, continuous',
    });
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });
});
