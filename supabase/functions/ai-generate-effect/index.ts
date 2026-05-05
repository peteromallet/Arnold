// deno-lint-ignore-file
import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import {
  enforceRateLimit,
  RATE_LIMITS,
} from "../_shared/rateLimit.ts";
import { bootstrapEdgeHandler, NO_SESSION_RUNTIME_OPTIONS } from "../_shared/edgeHandler.ts";
import { jsonResponse } from "../_shared/http.ts";
import { toErrorMessage } from "../_shared/errorMessage.ts";
import { attemptSelfInvokeRetry } from "../_shared/aiCodegenRetry.ts";
import {
  buildGenerateEffectMessages,
  extractEffectCodeAndMeta,
  extractQuestionResponse,
  type EffectCategory,
} from "./templates.ts";

// ── Models ───────────────────────────────────────────────────────────
// All generation (create + edit + retry) uses Claude Opus 4.6 via Anthropic
const ANTHROPIC_MODEL = "claude-opus-4-6";
const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
const ANTHROPIC_TIMEOUT_MS = 150_000; // max out to edge function wall-clock limit

const MAX_RETRY_DEPTH = 1; // max number of self-invocation retries

const EFFECT_CATEGORIES: EffectCategory[] = ["entrance", "exit", "continuous"];

function isEffectCategory(value: unknown): value is EffectCategory {
  return typeof value === "string" && EFFECT_CATEGORIES.includes(value as EffectCategory);
}

// ── Response types ───────────────────────────────────────────────────

interface LLMResponse {
  content: string;
  model: string;
}

// ── Anthropic generation (Claude Opus 4.6) ──────────────────────────

async function callAnthropic(
  messages: Array<{ role: string; content: string }>,
  logger: { info: (msg: string) => void },
): Promise<LLMResponse> {
  const apiKey = Deno.env.get("ANTHROPIC_API_KEY");
  if (!apiKey) throw new Error("[ai-generate-effect] Missing ANTHROPIC_API_KEY");

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), ANTHROPIC_TIMEOUT_MS);

  // Separate system message from user/assistant messages (Anthropic API uses top-level system param)
  const systemContent = messages.find(m => m.role === "system")?.content;
  const chatMessages = messages.filter(m => m.role !== "system");

  try {
    const startedAt = Date.now();
    logger.info(`[AI-GENERATE-EFFECT] Anthropic streaming request: model=${ANTHROPIC_MODEL}`);
    const response = await fetch(ANTHROPIC_URL, {
      method: "POST",
      headers: {
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: ANTHROPIC_MODEL,
        max_tokens: 16384,
        temperature: 0.4,
        ...(systemContent ? { system: systemContent } : {}),
        messages: chatMessages,
        stream: true,
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new Error(`Anthropic ${response.status}: ${text.slice(0, 500)}`);
    }

    // Collect streamed SSE chunks into full content
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let content = "";
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6).trim();
        try {
          const chunk = JSON.parse(data);
          if (chunk.type === "content_block_delta" && chunk.delta?.type === "text_delta") {
            content += chunk.delta.text;
          }
        } catch {
          // skip malformed chunks
        }
      }
    }

    content = content.trim();
    logger.info(`[AI-GENERATE-EFFECT] Anthropic response in ${Date.now() - startedAt}ms, model=${ANTHROPIC_MODEL}, length=${content.length}`);
    return { content, model: ANTHROPIC_MODEL };
  } finally {
    clearTimeout(timeout);
  }
}

// ── Main handler ─────────────────────────────────────────────────────

serve(async (req) => {
  const bootstrap = await bootstrapEdgeHandler(req, {
    functionName: "ai-generate-effect",
    logPrefix: "[AI-GENERATE-EFFECT]",
    parseBody: "strict",
    auth: {
      required: true,
      options: { allowJwtUserAuth: true },
    },
    ...NO_SESSION_RUNTIME_OPTIONS,
  });
  if (!bootstrap.ok) {
    return bootstrap.response;
  }

  const { supabaseAdmin, logger, auth, body } = bootstrap.value;
  if (!auth?.userId) {
    return jsonResponse({ error: "Authentication failed" }, 401);
  }

  const rateLimitDenied = await enforceRateLimit({
    supabaseAdmin,
    functionName: "ai-generate-effect",
    userId: auth.userId,
    config: RATE_LIMITS.expensive,
    logger,
    logPrefix: "[AI-GENERATE-EFFECT]",
    responses: {
      serviceUnavailable: () => jsonResponse({ error: "Rate limit service unavailable" }, 503),
    },
  });
  if (rateLimitDenied) {
    return rateLimitDenied;
  }

  const prompt = typeof body.prompt === "string" ? body.prompt.trim() : "";
  const effectName = typeof body.name === "string" ? body.name.trim() : "";
  const category = body.category;
  const existingCode = typeof body.existingCode === "string" && body.existingCode.trim()
    ? body.existingCode
    : undefined;

  if (!prompt) {
    return jsonResponse({ error: "prompt is required" }, 400);
  }

  if (!isEffectCategory(category)) {
    return jsonResponse({ error: `category must be one of: ${EFFECT_CATEGORIES.join(", ")}` }, 400);
  }

  const isEditMode = Boolean(existingCode);
  const retryDepth = typeof body._retryDepth === "number" ? body._retryDepth : 0;
  const retryError = typeof body._retryError === "string" ? body._retryError : undefined;
  const retryFailedCode = typeof body._retryFailedCode === "string" ? body._retryFailedCode : undefined;

  try {
    // If this is a retry invocation, build edit-mode messages to fix the failed code
    let messages: Array<{ role: string; content: string }>;

    if (retryDepth > 0 && retryFailedCode && retryError) {
      logger.info(`[AI-GENERATE-EFFECT] retry depth=${retryDepth} — fixing: ${retryError}`);
      const retryInput = buildGenerateEffectMessages({
        prompt,
        name: effectName || undefined,
        category,
        existingCode: retryFailedCode,
        validationError: retryError,
      });
      messages = [
        { role: "system", content: retryInput.systemMsg },
        { role: "user", content: retryInput.userMsg },
      ];
    } else {
      const { systemMsg, userMsg } = buildGenerateEffectMessages({
        prompt,
        name: effectName || undefined,
        category,
        existingCode,
      });
      messages = [
        { role: "system", content: systemMsg },
        { role: "user", content: userMsg },
      ];
    }

    // All generation uses Claude Opus 4.6 via Anthropic
    logger.info(`[AI-GENERATE-EFFECT] ${retryDepth > 0 ? `retry(${retryDepth})` : isEditMode ? "edit" : "create"} → ${ANTHROPIC_MODEL} (Anthropic)`);
    await logger.flush();
    const llmResponse = await callAnthropic(messages, logger);

    logger.info(`[AI-GENERATE-EFFECT] raw output length=${llmResponse.content.length}, first 200 chars: ${llmResponse.content.slice(0, 200)}`);

    const questionResponse = extractQuestionResponse(llmResponse.content);
    if (questionResponse) {
      logger.info(`[AI-GENERATE-EFFECT] question response detected, returning conversational reply (length=${questionResponse.message.length})`);
      await logger.flush();
      return jsonResponse({
        message: questionResponse.message,
        isQuestionResponse: true,
        model: llmResponse.model,
      });
    }

    let extracted;
    try {
      extracted = extractEffectCodeAndMeta(llmResponse.content);
    } catch (parseErr: unknown) {
      const parseMsg = parseErr instanceof Error ? parseErr.message : String(parseErr);
      logger.info(`[AI-GENERATE-EFFECT] extraction/validation failed: ${parseMsg}`);

      const retryResponse = await attemptSelfInvokeRetry({
        req,
        functionName: "ai-generate-effect",
        retryDepth,
        maxDepth: MAX_RETRY_DEPTH,
        payload: {
          prompt,
          name: effectName || undefined,
          category,
        },
        parseError: parseMsg,
        rawOutput: llmResponse.content,
        logger,
      });
      if (retryResponse) {
        return retryResponse;
      }

      logger.info(`[AI-GENERATE-EFFECT] max retry depth reached, returning error`);
      logger.info(`[AI-GENERATE-EFFECT] final output: ${llmResponse.content.slice(0, 1000)}`);
      await logger.flush();
      return jsonResponse({ error: parseMsg, rawOutput: llmResponse.content.slice(0, 500) }, 422);
    }

    const { code, name: generatedName, description, parameterSchema, message } = extracted;

    if (retryDepth > 0) {
      logger.info(`[AI-GENERATE-EFFECT] retry succeeded at depth ${retryDepth}`);
    }
    await logger.flush();
    return jsonResponse({
      code,
      name: generatedName,
      description,
      parameterSchema,
      message: message || undefined,
      model: llmResponse.model,
    });
  } catch (err: unknown) {
    const message = toErrorMessage(err);
    console.error("[ai-generate-effect] Error generating effect:", message);
    logger.info(`[AI-GENERATE-EFFECT] error: ${message}`);
    await logger.flush();
    return jsonResponse({ error: "Internal server error", details: message }, 500);
  }
});
