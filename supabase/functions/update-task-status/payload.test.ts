import { describe, expect, it } from 'vitest';

import { buildTaskUpdatePayload } from './payload.ts';

describe('buildTaskUpdatePayload', () => {
  it('maps common request fields', () => {
    const payload = buildTaskUpdatePayload({
      task_id: 'task-1',
      status: 'Failed',
      output_location: '/tmp/out.png',
      attempts: 3,
      error_details: 'worker crashed',
    });

    expect(payload.status).toBe('Failed');
    expect(typeof payload.updated_at).toBe('string');
    expect(payload.output_location).toBe('/tmp/out.png');
    expect(payload.attempts).toBe(3);
    expect(payload.error_message).toBe('worker crashed');
  });

  it('sets completion timestamp for Complete', () => {
    const payload = buildTaskUpdatePayload({
      task_id: 'task-1',
      status: 'Complete',
    });

    expect(typeof payload.generation_processed_at).toBe('string');
  });

  it('clears worker assignment for requeue', () => {
    const payload = buildTaskUpdatePayload({
      task_id: 'task-1',
      status: 'Queued',
      clear_worker: true,
    });

    expect(payload.worker_id).toBeNull();
    expect(payload.generation_started_at).toBeNull();
  });

  it('persists result_data when provided', () => {
    const payload = buildTaskUpdatePayload({
      task_id: 'task-1',
      status: 'Complete',
      result_data: { correlation_id: 'corr-1', config_version: 4 },
    });

    expect(payload.result_data).toEqual({ correlation_id: 'corr-1', config_version: 4 });
  });

  it('omits result_data when not provided', () => {
    const payload = buildTaskUpdatePayload({
      task_id: 'task-1',
      status: 'Complete',
    });

    expect(Object.prototype.hasOwnProperty.call(payload, 'result_data')).toBe(false);
  });
});
