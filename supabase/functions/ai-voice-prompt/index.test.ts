import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { __getServeHandler, __resetServeHandler } from '../_tests/mocks/denoHttpServer.ts';
import * as AiVoicePromptEntrypoint from './index.ts';

const mocks = vi.hoisted(() => ({
  bootstrapEdgeHandler: vi.fn(),
  groqTranscriptionsCreate: vi.fn(),
  groqChatCreate: vi.fn(),
}));

vi.mock('../_shared/edgeHandler.ts', () => ({
  bootstrapEdgeHandler: (...args: unknown[]) => mocks.bootstrapEdgeHandler(...args),
  NO_SESSION_RUNTIME_OPTIONS: {},
}));

vi.mock('../_shared/http.ts', () => ({
  jsonResponse: (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
}));

vi.mock('npm:groq-sdk@0.26.0', () => ({
  default: class GroqMock {
    chat = {
      completions: {
        create: (payload: unknown) => mocks.groqChatCreate(payload),
      },
    };

    audio = {
      transcriptions: {
        create: (payload: unknown) => mocks.groqTranscriptionsCreate(payload),
      },
    };

    constructor(_options?: unknown) {}
  },
}));

function stubDenoEnv(): void {
  vi.stubGlobal('Deno', {
    env: {
      get: (key: string) => {
        if (key === 'GROQ_API_KEY') return 'groq-test-key';
        return undefined;
      },
    },
  });
}

function createLogger() {
  return {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    flush: vi.fn().mockResolvedValue(undefined),
  };
}

async function loadHandler() {
  await import('./index.ts');
  return __getServeHandler();
}

describe('ai-voice-prompt edge entrypoint', () => {
  it('imports entrypoint module directly', () => {
    expect(AiVoicePromptEntrypoint).toBeDefined();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    __resetServeHandler();
    stubDenoEnv();

    mocks.groqTranscriptionsCreate.mockResolvedValue({ text: 'transcribed text' });
    mocks.groqChatCreate.mockResolvedValue({
      choices: [{ message: { content: 'enhanced prompt' } }],
      usage: { total_tokens: 22 },
    });

    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: {
        logger: createLogger(),
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('handles OPTIONS preflight without bootstrapping', async () => {
    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/ai-voice-prompt', { method: 'OPTIONS' }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ ok: true });
    expect(mocks.bootstrapEdgeHandler).not.toHaveBeenCalled();
  });

  it('returns bootstrap failure response untouched', async () => {
    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: false,
      response: new Response('denied', { status: 403 }),
    });

    const handler = await loadHandler();
    const response = await handler(new Request('https://edge.test/ai-voice-prompt', { method: 'POST' }));

    expect(response.status).toBe(403);
    await expect(response.text()).resolves.toBe('denied');
  });

  it('rejects JSON requests without textInstructions', async () => {
    const logger = createLogger();
    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: { logger },
    });

    const handler = await loadHandler();
    const response = await handler(
      new Request('https://edge.test/ai-voice-prompt', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ task: 'transcribe_and_write' }),
      }),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({
      error: 'textInstructions is required for JSON requests',
    });
    expect(mocks.groqTranscriptionsCreate).not.toHaveBeenCalled();
    expect(mocks.groqChatCreate).not.toHaveBeenCalled();
  });

  it('transforms textInstructions into an enhanced prompt', async () => {
    const logger = createLogger();
    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: { logger },
    });

    const handler = await loadHandler();
    const response = await handler(
      new Request('https://edge.test/ai-voice-prompt', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          textInstructions: 'make this scene more dramatic',
          context: 'Image generation prompt field',
          example: 'cinematic shot of a mountain at sunset',
        }),
      }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      success: true,
      transcription: 'make this scene more dramatic',
      prompt: 'enhanced prompt',
      intent: 'rewrite',
      usage: { total_tokens: 22 },
    });
    expect(mocks.groqTranscriptionsCreate).not.toHaveBeenCalled();
    expect(mocks.groqChatCreate).toHaveBeenCalled();
    expect(logger.flush).toHaveBeenCalled();
  });

  it('falls back to raw transcription when enhancement fails', async () => {
    const logger = createLogger();
    mocks.bootstrapEdgeHandler.mockResolvedValue({
      ok: true,
      value: { logger },
    });
    mocks.groqChatCreate.mockRejectedValue(new Error('kimi unavailable'));

    const handler = await loadHandler();
    const response = await handler(
      new Request('https://edge.test/ai-voice-prompt', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          textInstructions: 'use exactly this sentence',
        }),
      }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      success: true,
      transcription: 'use exactly this sentence',
      prompt: 'use exactly this sentence',
      intent: 'rewrite',
      usage: null,
    });
  });
});
