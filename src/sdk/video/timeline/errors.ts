/**
 * Canonical timeline persistence conflict helpers shared by the SDK and host.
 *
 * Host providers must throw this exact class so SDK consumers can rely on
 * `instanceof` and the exported type guard across the boundary.
 *
 * @publicContract
 */

export class TimelineVersionConflictError extends Error {
  code = 'timeline_version_conflict' as const;

  constructor(
    message = 'Timeline version conflict',
    readonly expectedVersion?: number,
    readonly actualVersion?: number,
  ) {
    super(message);
    this.name = 'TimelineVersionConflictError';
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export function isTimelineVersionConflictError(error: unknown): error is TimelineVersionConflictError {
  return error instanceof TimelineVersionConflictError
    || (error instanceof Error && error.name === 'TimelineVersionConflictError');
}
