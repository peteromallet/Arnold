import { getSupabasePublishableKey, getSupabaseUrl } from '@/integrations/supabase/config/env';
import { fetchGenerationRecordById } from '@/integrations/supabase/repositories/generationRepository';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { isAbortError } from '@/shared/lib/errorHandling/errorUtils';
import { normalizeAndPresentAndRethrow } from '@/shared/lib/errorHandling/runtimeError';
import { AuthError, NetworkError, ServerError } from '@/shared/lib/errorHandling/errors';
import { materializeLocalGeneration } from '@/shared/lib/media/materializeLocalGeneration';
import { readAccessTokenFromStorage } from '@/shared/lib/supabaseSession';
import { generateUUID } from './ids';
import { parseTaskCreationResponse } from './parseTaskCreationResponse';
import type { BaseTaskParams, TaskCreationResult } from './types';

const ATTEMPT_TIMEOUT_MS = 15_000;
const MAX_ATTEMPTS = 2;
const DIRECT_GENERATION_ID_KEYS = new Set([
  'based_on',
  'source_generation_id',
  'generation_id',
  'input_generation_id',
  'parent_generation_id',
  'start_image_generation_id',
  'end_image_generation_id',
  'pair_shot_generation_id',
]);
const ARRAY_GENERATION_ID_KEYS = new Set([
  'input_image_generation_ids',
  'pair_shot_generation_ids',
]);

interface CreateTaskOptions {
  signal?: AbortSignal;
  onMaterializeProgress?: (event: {
    generationId: string;
    progress: number;
    index: number;
    total: number;
  }) => void;
}

function getNetworkDiagnostics(): Record<string, unknown> {
  const diag: Record<string, unknown> = {
    online: navigator.onLine,
  };
  const conn = (navigator as Navigator & { connection?: { effectiveType?: string; downlink?: number; rtt?: number } }).connection;
  if (conn) {
    diag.effectiveType = conn.effectiveType;
    diag.downlink = conn.downlink;
    diag.rtt = conn.rtt;
  }
  return diag;
}

async function attemptCreateTask(
  url: string,
  headers: Record<string, string>,
  body: string,
  timeoutMs: number,
  signal?: AbortSignal,
): Promise<Response> {
  const controller = new AbortController();
  const handleAbort = () => controller.abort();
  if (signal?.aborted) {
    controller.abort();
  }
  signal?.addEventListener('abort', handleAbort);
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, {
      method: 'POST',
      headers,
      body,
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', handleAbort);
  }
}

function addGenerationId(target: Set<string>, value: unknown): void {
  if (typeof value !== 'string') {
    return;
  }

  const trimmed = value.trim();
  if (trimmed) {
    target.add(trimmed);
  }
}

function addGenerationIdsFromArray(target: Set<string>, value: unknown): void {
  if (!Array.isArray(value)) {
    return;
  }

  value.forEach((item) => addGenerationId(target, item));
}

function collectGenerationIds(value: unknown, target: Set<string>): void {
  if (!value) {
    return;
  }

  if (Array.isArray(value)) {
    value.forEach((item) => collectGenerationIds(item, target));
    return;
  }

  if (typeof value !== 'object') {
    return;
  }

  const record = value as Record<string, unknown>;
  for (const [key, nestedValue] of Object.entries(record)) {
    if (DIRECT_GENERATION_ID_KEYS.has(key)) {
      addGenerationId(target, nestedValue);
      continue;
    }

    if (ARRAY_GENERATION_ID_KEYS.has(key)) {
      addGenerationIdsFromArray(target, nestedValue);
      continue;
    }

    collectGenerationIds(nestedValue, target);
  }
}

async function materializeTaskInputGenerations(
  input: Record<string, unknown>,
  options?: CreateTaskOptions,
): Promise<void> {
  const generationIds = new Set<string>();
  collectGenerationIds(input, generationIds);

  if (generationIds.size === 0) {
    return;
  }

  let announcedUpload = false;
  const ids = Array.from(generationIds);

  for (const [index, generationId] of ids.entries()) {
    const record = await fetchGenerationRecordById(generationId) as Record<string, unknown> | null;
    if (record?.storage_mode === 'remote' || !record?.storage_mode) {
      continue;
    }

    if (!announcedUpload) {
      toast.info('Uploading original before sending to worker…');
      announcedUpload = true;
    }

    await materializeLocalGeneration(generationId, {
      signal: options?.signal,
      onProgress: (progress) => options?.onMaterializeProgress?.({
        generationId,
        progress,
        index,
        total: ids.length,
      }),
    });
  }
}

/**
 * Creates a task using the unified create-task edge function.
 * Retries once on timeout since the server typically responds in <2s.
 */
export async function createTask(
  taskParams: BaseTaskParams,
  options?: CreateTaskOptions,
): Promise<TaskCreationResult> {
  const accessToken = readAccessTokenFromStorage();

  if (!accessToken) {
    throw new AuthError('Please log in to create tasks', { needsLogin: true });
  }

  const startTime = Date.now();
  const requestId = `${startTime}-${Math.random().toString(36).slice(2, 8)}`;
  const taskIdentifier = taskParams.family;
  const requestContext = {
    requestId,
    taskType: taskIdentifier,
    projectId: taskParams.project_id,
  };

  // Idempotency key stays the same across retries so the server
  // deduplicates if the first attempt actually landed.
  const idempotency_key = generateUUID();
  const url = `${getSupabaseUrl()}/functions/v1/create-task`;
  await materializeTaskInputGenerations(taskParams.input, options);
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${accessToken}`,
    apikey: getSupabasePublishableKey(),
  };
  const body = JSON.stringify({
    family: taskParams.family,
    project_id: taskParams.project_id,
    input: taskParams.input,
    idempotency_key,
  });

  let lastError: unknown;

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    try {
      const response = await attemptCreateTask(url, headers, body, ATTEMPT_TIMEOUT_MS, options?.signal);

      if (!response.ok) {
        const errorText = await response.text().catch(() => '');
        throw new ServerError(errorText || 'Failed to create task', {
          context: requestContext,
        });
      }

      const data = await response.json() as unknown;
      return parseTaskCreationResponse(data, requestContext);
    } catch (err: unknown) {
      lastError = err;
      const durationMs = Date.now() - startTime;
      const isTimeout = isAbortError(err);

      if (isTimeout && attempt < MAX_ATTEMPTS) {
        console.error('[createTask] attempt %d/%d timed out after %dms, retrying', attempt, MAX_ATTEMPTS, durationMs, {
          ...requestContext,
          network: getNetworkDiagnostics(),
        });
        continue;
      }

      const context = {
        ...requestContext,
        attempt,
        durationMs,
        network: getNetworkDiagnostics(),
        errorType: err instanceof Error ? err.name : typeof err,
        errorMessage: err instanceof Error ? err.message : String(err),
      };

      console.error('[createTask] FAILED after %d attempt(s), %dms', attempt, durationMs, context);

      if (isTimeout) {
        throw new NetworkError('Task creation timed out. Please try again.', {
          isTimeout: true,
          context,
          cause: err instanceof Error ? err : undefined,
        });
      }

      normalizeAndPresentAndRethrow(err, {
        context: 'TaskCreation',
        showToast: false,
        logData: context,
      });
    }
  }

  // Unreachable, but TypeScript needs it
  throw lastError;
}
