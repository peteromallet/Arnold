/**
 * Base error class for Arnold
 * All custom errors extend this for consistent handling
 */
export class ArnoldError extends Error {
  constructor(
    message: string,
    /** Error code for categorization */
    public readonly code: string,
    /** Whether this error is recoverable (task can be retried) */
    public readonly recoverable: boolean = true,
  ) {
    super(message);
    this.name = 'ArnoldError';
  }
}

/**
 * Task not found in database
 */
export class TaskNotFoundError extends ArnoldError {
  constructor(taskId: string) {
    super(`Task not found: ${taskId}`, 'TASK_NOT_FOUND', false);
    this.name = 'TaskNotFoundError';
  }
}

/**
 * Executor is already running
 */
export class ExecutorBusyError extends ArnoldError {
  constructor() {
    super('Executor is already running', 'EXECUTOR_BUSY', false);
    this.name = 'ExecutorBusyError';
  }
}

/**
 * Executor is not running
 */
export class ExecutorNotRunningError extends ArnoldError {
  constructor() {
    super('Executor is not running', 'EXECUTOR_NOT_RUNNING', false);
    this.name = 'ExecutorNotRunningError';
  }
}

/**
 * External service error (Supabase, Anthropic, Groq, GitHub)
 */
export class ExternalServiceError extends ArnoldError {
  constructor(
    service: 'supabase' | 'anthropic' | 'groq' | 'github' | 'claude-code',
    message: string,
    recoverable: boolean = true,
  ) {
    super(`${service}: ${message}`, `EXTERNAL_${service.toUpperCase().replace('-', '_')}`, recoverable);
    this.name = 'ExternalServiceError';
  }
}

/**
 * Configuration error (missing or invalid config)
 */
export class ConfigError extends ArnoldError {
  constructor(message: string) {
    super(message, 'CONFIG_ERROR', false);
    this.name = 'ConfigError';
  }
}

/**
 * Voice transcription error
 */
export class TranscriptionError extends ArnoldError {
  constructor(message: string) {
    super(message, 'TRANSCRIPTION_ERROR', true);
    this.name = 'TranscriptionError';
  }
}

/**
 * Git operation error
 */
export class GitError extends ArnoldError {
  constructor(operation: string, message: string) {
    super(`Git ${operation} failed: ${message}`, 'GIT_ERROR', true);
    this.name = 'GitError';
  }
}

/**
 * Check if an error is an ArnoldError
 */
export function isArnoldError(error: unknown): error is ArnoldError {
  return error instanceof ArnoldError;
}

/**
 * Convert any error to a user-friendly message
 */
export function toUserMessage(error: unknown): string {
  if (error instanceof ArnoldError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}
