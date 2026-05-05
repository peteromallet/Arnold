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
  buildGenerateSequenceComponentMessages,
  extractSequenceComponentCodeAndMeta,
  type ExistingSequenceComponent,
} from "./templates.ts";

const ANTHROPIC_MODEL = "claude-opus-4-6";
const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
const ANTHROPIC_TIMEOUT_MS = 150_000;

const MAX_RETRY_DEPTH = 1;

interface LLMResponse {
  content: string;
  model: string;
}

const asStringArray = (value: unknown): string[] => {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];
};

const collectAssetKeys = (...sources: unknown[]): string[] => {
  const keys = new Set<string>();
  for (const source of sources) {
    if (!Array.isArray(source)) continue;
    for (const item of source) {
      if (typeof item === "string" && item.trim()) {
        keys.add(item);
      } else if (item && typeof item === "object") {
        const record = item as Record<string, unknown>;
        for (const field of ["assetKey", "asset_key", "asset", "id", "key"]) {
          const value = record[field];
          if (typeof value === "string" && value.trim()) {
            keys.add(value);
          }
        }
      }
    }
  }
  return [...keys];
};

function isExistingComponent(value: unknown): value is ExistingSequenceComponent {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.code === "string" &&
    record.schema !== null && typeof record.schema === "object" &&
    record.defaults !== null && typeof record.defaults === "object"
  );
}

async function callAnthropic(
  messages: Array<{ role: string; content: string }>,
  logger: { info: (msg: string) => void },
): Promise<LLMResponse> {
  const apiKey = Deno.env.get("ANTHROPIC_API_KEY");
  if (!apiKey) throw new Error("[ai-generate-sequence-component] Missing ANTHROPIC_API_KEY");

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), ANTHROPIC_TIMEOUT_MS);

  const systemContent = messages.find((m) => m.role === "system")?.content;
  const chatMessages = messages.filter((m) => m.role !== "system");

  try {
    const startedAt = Date.now();
    logger.info(`[AI-GENERATE-SEQUENCE-COMPONENT] Anthropic streaming request: model=${ANTHROPIC_MODEL}`);
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
    logger.info(
      `[AI-GENERATE-SEQUENCE-COMPONENT] Anthropic response in ${Date.now() - startedAt}ms, model=${ANTHROPIC_MODEL}, length=${content.length}`,
    );
    return { content, model: ANTHROPIC_MODEL };
  } finally {
    clearTimeout(timeout);
  }
}

serve(async (req) => {
  const bootstrap = await bootstrapEdgeHandler(req, {
    functionName: "ai-generate-sequence-component",
    logPrefix: "[AI-GENERATE-SEQUENCE-COMPONENT]",
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
    functionName: "ai-generate-sequence-component",
    userId: auth.userId,
    config: RATE_LIMITS.expensive,
    logger,
    logPrefix: "[AI-GENERATE-SEQUENCE-COMPONENT]",
    responses: {
      serviceUnavailable: () => jsonResponse({ error: "Rate limit service unavailable" }, 503),
    },
  });
  if (rateLimitDenied) {
    return rateLimitDenied;
  }

  const prompt = typeof body.prompt === "string" ? body.prompt.trim() : "";
  const componentName = typeof body.name === "string" ? body.name.trim() : "";
  const themeId = typeof body.themeId === "string" ? body.themeId.trim() : "";
  const existingComponent = isExistingComponent(body.existingComponent)
    ? body.existingComponent
    : undefined;

  if (!prompt) {
    return jsonResponse({ error: "prompt is required" }, 400);
  }

  // Asset keys come from explicit allowed_asset_keys OR are derived from the
  // selected/attached/allowed_assets payloads (mirroring ai-generate-sequence:54-79).
  const explicitAssetKeys = asStringArray(body.allowed_asset_keys);
  const allowedAssetKeys = explicitAssetKeys.length > 0
    ? explicitAssetKeys
    : collectAssetKeys(body.allowed_assets, body.selected_clips, body.attached_clips);

  const retryDepth = typeof body._retryDepth === "number" ? body._retryDepth : 0;
  const retryError = typeof body._retryError === "string" ? body._retryError : undefined;
  const retryFailedCode = typeof body._retryFailedCode === "string" ? body._retryFailedCode : undefined;

  try {
    let messages: Array<{ role: string; content: string }>;

    if (retryDepth > 0 && retryFailedCode && retryError) {
      logger.info(`[AI-GENERATE-SEQUENCE-COMPONENT] retry depth=${retryDepth} — fixing: ${retryError}`);
      // For retries, fold the failed code into existingComponent so the model has the
      // fence to fix without re-sending the original existingComponent payload.
      const retryExisting: ExistingSequenceComponent = existingComponent ?? {
        code: retryFailedCode,
        schema: {},
        defaults: {},
      };
      const retryInput = buildGenerateSequenceComponentMessages({
        prompt,
        name: componentName || undefined,
        themeId: themeId || undefined,
        existingComponent: { ...retryExisting, code: retryFailedCode },
        allowedAssetKeys,
        selectedClips: body.selected_clips,
        attachedClips: body.attached_clips,
        theme: body.theme,
        themeOverrides: body.theme_overrides,
        validationError: retryError,
      });
      messages = [
        { role: "system", content: retryInput.systemMsg },
        { role: "user", content: retryInput.userMsg },
      ];
    } else {
      const { systemMsg, userMsg } = buildGenerateSequenceComponentMessages({
        prompt,
        name: componentName || undefined,
        themeId: themeId || undefined,
        existingComponent,
        allowedAssetKeys,
        selectedClips: body.selected_clips,
        attachedClips: body.attached_clips,
        theme: body.theme,
        themeOverrides: body.theme_overrides,
      });
      messages = [
        { role: "system", content: systemMsg },
        { role: "user", content: userMsg },
      ];
    }

    const isEditMode = Boolean(existingComponent);
    logger.info(
      `[AI-GENERATE-SEQUENCE-COMPONENT] ${retryDepth > 0 ? `retry(${retryDepth})` : isEditMode ? "edit" : "create"} → ${ANTHROPIC_MODEL} (Anthropic)`,
    );
    await logger.flush();
    const llmResponse = await callAnthropic(messages, logger);

    logger.info(
      `[AI-GENERATE-SEQUENCE-COMPONENT] raw output length=${llmResponse.content.length}, first 200 chars: ${llmResponse.content.slice(0, 200)}`,
    );

    let extracted;
    try {
      extracted = extractSequenceComponentCodeAndMeta(llmResponse.content);
    } catch (parseErr: unknown) {
      const parseMsg = parseErr instanceof Error ? parseErr.message : String(parseErr);
      logger.info(`[AI-GENERATE-SEQUENCE-COMPONENT] extraction/validation failed: ${parseMsg}`);

      const retryResponse = await attemptSelfInvokeRetry({
        req,
        functionName: "ai-generate-sequence-component",
        retryDepth,
        maxDepth: MAX_RETRY_DEPTH,
        payload: {
          prompt,
          name: componentName || undefined,
          themeId: themeId || undefined,
          existingComponent,
          allowed_asset_keys: allowedAssetKeys,
          allowed_assets: body.allowed_assets,
          selected_clips: body.selected_clips,
          attached_clips: body.attached_clips,
          theme: body.theme,
          theme_overrides: body.theme_overrides,
        },
        parseError: parseMsg,
        rawOutput: llmResponse.content,
        logger,
      });
      if (retryResponse) {
        return retryResponse;
      }

      logger.info(`[AI-GENERATE-SEQUENCE-COMPONENT] max retry depth reached, returning error`);
      logger.info(`[AI-GENERATE-SEQUENCE-COMPONENT] final output: ${llmResponse.content.slice(0, 1000)}`);
      await logger.flush();
      return jsonResponse({ error: parseMsg, rawOutput: llmResponse.content.slice(0, 500) }, 422);
    }

    const { code, name: generatedName, description, schemaJson, defaultsJson, message } = extracted;

    if (retryDepth > 0) {
      logger.info(`[AI-GENERATE-SEQUENCE-COMPONENT] retry succeeded at depth ${retryDepth}`);
    }
    await logger.flush();
    return jsonResponse({
      code,
      name: generatedName,
      description,
      schemaJson,
      defaultsJson,
      message: message || undefined,
      model: llmResponse.model,
    });
  } catch (err: unknown) {
    const message = toErrorMessage(err);
    console.error("[ai-generate-sequence-component] Error generating sequence component:", message);
    logger.info(`[AI-GENERATE-SEQUENCE-COMPONENT] error: ${message}`);
    await logger.flush();
    return jsonResponse({ error: "Internal server error", details: message }, 500);
  }
});
