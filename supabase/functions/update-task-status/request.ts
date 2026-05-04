import type { SystemLogger } from '../_shared/systemLogger.ts';

import { isTaskStatus } from './transitions.ts';
import { VALID_TASK_STATUSES, type UpdateTaskStatusRequest } from './types.ts';

type ParseResult =
  | { ok: true; data: UpdateTaskStatusRequest }
  | { ok: false; response: Response };

function jsonResponse(body: Record<string, unknown>, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

async function rejectValidation(
  logger: SystemLogger,
  logMessage: string,
  response: Response,
  context?: Record<string, unknown>,
): Promise<ParseResult> {
  logger.error(logMessage, context);
  await logger.flush();
  return { ok: false, response };
}

export async function parseAndValidateRequest(
  req: Request,
  logger: SystemLogger,
): Promise<ParseResult> {
  let requestBody: Record<string, unknown> = {};

  try {
    const bodyText = await req.text();
    if (bodyText) {
      const parsed = JSON.parse(bodyText);
      if (parsed && typeof parsed === 'object') {
        requestBody = parsed as Record<string, unknown>;
      }
    }
  } catch {
    return rejectValidation(
      logger,
      'Invalid JSON body',
      new Response('Invalid JSON body', { status: 400 }),
    );
  }

  const taskId = requestBody.task_id;
  const status = requestBody.status;

  if (!taskId || !status || typeof taskId !== 'string') {
    return rejectValidation(
      logger,
      'Missing required fields',
      new Response('Missing required fields: task_id and status', { status: 400 }),
      { has_task_id: !!taskId, has_status: !!status },
    );
  }

  if (!isTaskStatus(status)) {
    return rejectValidation(
      logger,
      'Invalid status value',
      new Response(
        `Invalid status. Must be one of: ${VALID_TASK_STATUSES.join(', ')}`,
        { status: 400 },
      ),
      { status, valid_statuses: VALID_TASK_STATUSES },
    );
  }

  const attempts = requestBody.attempts;
  if (attempts !== undefined && typeof attempts !== 'number') {
    return rejectValidation(
      logger,
      'Invalid attempts value',
      jsonResponse({ success: false, message: 'attempts must be a number' }, 400),
      { attempts },
    );
  }

  const outputLocation = requestBody.output_location;
  const errorDetails = requestBody.error_details;
  const clearWorker = requestBody.clear_worker;
  const resetGenerationStartedAt = requestBody.reset_generation_started_at;

  if (outputLocation !== undefined && typeof outputLocation !== 'string') {
    return rejectValidation(
      logger,
      'Invalid output_location value',
      jsonResponse({ success: false, message: 'output_location must be a string' }, 400),
      { output_location: outputLocation },
    );
  }

  if (errorDetails !== undefined && typeof errorDetails !== 'string') {
    return rejectValidation(
      logger,
      'Invalid error_details value',
      jsonResponse({ success: false, message: 'error_details must be a string' }, 400),
      { error_details: errorDetails },
    );
  }

  if (clearWorker !== undefined && typeof clearWorker !== 'boolean') {
    return rejectValidation(
      logger,
      'Invalid clear_worker value',
      jsonResponse({ success: false, message: 'clear_worker must be a boolean' }, 400),
      { clear_worker: clearWorker },
    );
  }

  if (resetGenerationStartedAt !== undefined && typeof resetGenerationStartedAt !== 'boolean') {
    return rejectValidation(
      logger,
      'Invalid reset_generation_started_at value',
      jsonResponse({ success: false, message: 'reset_generation_started_at must be a boolean' }, 400),
      { reset_generation_started_at: resetGenerationStartedAt },
    );
  }

  const resultData = requestBody.result_data;
  if (
    resultData !== undefined &&
    (typeof resultData !== 'object' || resultData === null || Array.isArray(resultData))
  ) {
    return rejectValidation(
      logger,
      'Invalid result_data value',
      jsonResponse({ success: false, message: 'result_data must be a JSON object' }, 400),
      { result_data: resultData },
    );
  }

  return {
    ok: true,
    data: {
      task_id: taskId,
      status,
      output_location: outputLocation as string | undefined,
      attempts: attempts as number | undefined,
      error_details: errorDetails as string | undefined,
      clear_worker: clearWorker as boolean | undefined,
      reset_generation_started_at: resetGenerationStartedAt as boolean | undefined,
      result_data: resultData as Record<string, unknown> | undefined,
    },
  };
}
