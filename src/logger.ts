import { config } from './config.js';

// Map local log levels to database log levels
const levelToDbLevel: Record<string, string> = {
  debug: 'DEBUG',
  info: 'INFO',
  warn: 'WARNING',
  error: 'ERROR',
};

// Current task context for associating logs with tasks
let currentTaskId: string | null = null;

// Lazy-loaded supabase module to avoid circular dependency
let supabaseModule: typeof import('./supabase.js') | null = null;
let supabaseLoadPromise: Promise<void> | null = null;

/**
 * Lazy load the supabase module to avoid circular dependency
 */
async function getSupabaseModule() {
  if (supabaseModule) return supabaseModule;
  if (supabaseLoadPromise) {
    await supabaseLoadPromise;
    return supabaseModule;
  }
  supabaseLoadPromise = import('./supabase.js').then((mod) => {
    supabaseModule = mod;
  });
  await supabaseLoadPromise;
  return supabaseModule;
}

/**
 * Set the current task context for log association
 */
export function setLogTaskContext(taskId: string | null): void {
  currentTaskId = taskId;
}

/**
 * Get the current task context
 */
export function getLogTaskContext(): string | null {
  return currentTaskId;
}

/**
 * Format a log entry for output
 */
function formatLog(
  level: string,
  message: string,
  meta?: Record<string, unknown>,
  error?: Error
): string {
  const timestamp = new Date().toISOString();

  if (config.isProd) {
    // JSON format for production (easy to parse in log aggregators)
    const entry: Record<string, unknown> = {
      timestamp,
      level,
      message,
      ...meta,
    };
    if (error) {
      entry.error = {
        name: error.name,
        message: error.message,
        stack: error.stack,
      };
    }
    return JSON.stringify(entry);
  }

  // Pretty format for development
  const levelIcons: Record<string, string> = {
    debug: '🔍',
    info: '📋',
    warn: '⚠️',
    error: '❌',
  };

  let output = `${levelIcons[level]} [${timestamp.substring(11, 19)}] ${message}`;
  if (meta && Object.keys(meta).length > 0) {
    output += ` ${JSON.stringify(meta)}`;
  }
  if (error) {
    output += `\n   ${error.stack || error.message}`;
  }
  return output;
}

/**
 * Write log to Supabase (fire-and-forget)
 */
function writeToSupabase(
  level: string,
  message: string,
  meta?: Record<string, unknown>,
  error?: Error
): void {
  const dbLevel = levelToDbLevel[level];

  // Build metadata including error info if present
  const metadata: Record<string, unknown> = { ...meta };
  if (error) {
    metadata.error = {
      name: error.name,
      message: error.message,
      stack: error.stack,
    };
  }

  // Fire and forget - don't await, don't let errors propagate
  getSupabaseModule()
    .then((mod) => mod?.insertSystemLog(dbLevel, message, currentTaskId, metadata))
    .catch(() => {
      // Silently ignore - we already log to console
    });
}

/**
 * Simple structured logger
 * - JSON output in production
 * - Pretty output in development
 * - Also writes to Supabase system_logs table
 */
export const logger = {
  debug(message: string, meta?: Record<string, unknown>): void {
    if (!config.isProd) {
      console.debug(formatLog('debug', message, meta));
    }
    // Only write debug to Supabase in development to avoid noise
    if (!config.isProd) {
      writeToSupabase('debug', message, meta);
    }
  },

  info(message: string, meta?: Record<string, unknown>): void {
    console.info(formatLog('info', message, meta));
    writeToSupabase('info', message, meta);
  },

  warn(message: string, meta?: Record<string, unknown>): void {
    console.warn(formatLog('warn', message, meta));
    writeToSupabase('warn', message, meta);
  },

  error(message: string, error?: Error | unknown, meta?: Record<string, unknown>): void {
    const err = error instanceof Error ? error : undefined;
    const extraMeta = error && !(error instanceof Error) ? { errorValue: error, ...meta } : meta;
    console.error(formatLog('error', message, extraMeta, err));
    writeToSupabase('error', message, extraMeta, err);
  },
};
