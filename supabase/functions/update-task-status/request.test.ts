import { describe, expect, it, vi } from 'vitest';

import { parseAndValidateRequest } from './request.ts';

function createLoggerStub() {
  return {
    error: vi.fn(),
    flush: vi.fn(async () => {}),
  };
}

describe('parseAndValidateRequest', () => {
  it('parses a valid request', async () => {
    const logger = createLoggerStub();
    const req = new Request('http://localhost/update-task-status', {
      method: 'POST',
      body: JSON.stringify({ task_id: 'task-1', status: 'Queued' }),
    });

    const result = await parseAndValidateRequest(req, logger);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.task_id).toBe('task-1');
      expect(result.data.status).toBe('Queued');
    }
  });

  it('rejects invalid JSON', async () => {
    const logger = createLoggerStub();
    const req = new Request('http://localhost/update-task-status', {
      method: 'POST',
      body: '{bad-json',
    });

    const result = await parseAndValidateRequest(req, logger);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.response.status).toBe(400);
    }
    expect(logger.error).toHaveBeenCalledWith('Invalid JSON body', undefined);
    expect(logger.flush).toHaveBeenCalledTimes(1);
  });

  it('rejects invalid status values', async () => {
    const logger = createLoggerStub();
    const req = new Request('http://localhost/update-task-status', {
      method: 'POST',
      body: JSON.stringify({ task_id: 'task-1', status: 'pending' }),
    });

    const result = await parseAndValidateRequest(req, logger);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.response.status).toBe(400);
    }
    expect(logger.error).toHaveBeenCalledWith('Invalid status value', {
      status: 'pending',
      valid_statuses: expect.any(Array),
    });
    expect(logger.flush).toHaveBeenCalledTimes(1);
  });

  it('rejects malformed attempts type', async () => {
    const logger = createLoggerStub();
    const req = new Request('http://localhost/update-task-status', {
      method: 'POST',
      body: JSON.stringify({ task_id: 'task-1', status: 'Queued', attempts: '3' }),
    });

    const result = await parseAndValidateRequest(req, logger);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.response.status).toBe(400);
      const body = JSON.parse(await result.response.text()) as Record<string, unknown>;
      expect(body.message).toBe('attempts must be a number');
    }
    expect(logger.error).toHaveBeenCalledWith('Invalid attempts value', { attempts: '3' });
    expect(logger.flush).toHaveBeenCalledTimes(1);
  });

  it('rejects malformed reset_generation_started_at values through the shared validation helper', async () => {
    const logger = createLoggerStub();
    const req = new Request('http://localhost/update-task-status', {
      method: 'POST',
      body: JSON.stringify({
        task_id: 'task-1',
        status: 'Queued',
        reset_generation_started_at: 'yes',
      }),
    });

    const result = await parseAndValidateRequest(req, logger);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.response.status).toBe(400);
      const body = JSON.parse(await result.response.text()) as Record<string, unknown>;
      expect(body.message).toBe('reset_generation_started_at must be a boolean');
    }
    expect(logger.error).toHaveBeenCalledWith('Invalid reset_generation_started_at value', {
      reset_generation_started_at: 'yes',
    });
    expect(logger.flush).toHaveBeenCalledTimes(1);
  });

  it('accepts a result_data object', async () => {
    const logger = createLoggerStub();
    const req = new Request('http://localhost/update-task-status', {
      method: 'POST',
      body: JSON.stringify({
        task_id: 'task-1',
        status: 'Complete',
        result_data: {
          correlation_id: 'corr-9',
          config_version: 12,
          timeline_id: '55555555-5555-5555-5555-555555555555',
        },
      }),
    });

    const result = await parseAndValidateRequest(req, logger);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.result_data).toEqual({
        correlation_id: 'corr-9',
        config_version: 12,
        timeline_id: '55555555-5555-5555-5555-555555555555',
      });
    }
  });

  it('rejects non-object result_data', async () => {
    const logger = createLoggerStub();
    const req = new Request('http://localhost/update-task-status', {
      method: 'POST',
      body: JSON.stringify({
        task_id: 'task-1',
        status: 'Queued',
        result_data: 'oops',
      }),
    });

    const result = await parseAndValidateRequest(req, logger);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.response.status).toBe(400);
      const body = JSON.parse(await result.response.text()) as Record<string, unknown>;
      expect(body.message).toBe('result_data must be a JSON object');
    }
  });

  it('rejects array result_data', async () => {
    const logger = createLoggerStub();
    const req = new Request('http://localhost/update-task-status', {
      method: 'POST',
      body: JSON.stringify({
        task_id: 'task-1',
        status: 'Queued',
        result_data: [1, 2, 3],
      }),
    });

    const result = await parseAndValidateRequest(req, logger);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.response.status).toBe(400);
    }
  });
});
