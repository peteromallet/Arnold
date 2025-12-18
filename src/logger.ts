import { config } from './config.js';

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogMeta {
  [key: string]: unknown;
}

/**
 * Format a log entry for output
 */
function formatLog(level: LogLevel, message: string, meta?: LogMeta, error?: Error): string {
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
  const levelIcons: Record<LogLevel, string> = {
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
 * Simple structured logger
 * - JSON output in production
 * - Pretty output in development
 */
export const logger = {
  debug(message: string, meta?: LogMeta): void {
    if (!config.isProd) {
      console.debug(formatLog('debug', message, meta));
    }
  },
  
  info(message: string, meta?: LogMeta): void {
    console.info(formatLog('info', message, meta));
  },
  
  warn(message: string, meta?: LogMeta): void {
    console.warn(formatLog('warn', message, meta));
  },
  
  error(message: string, error?: Error | unknown, meta?: LogMeta): void {
    const err = error instanceof Error ? error : undefined;
    const extraMeta = error && !(error instanceof Error) ? { errorValue: error, ...meta } : meta;
    console.error(formatLog('error', message, extraMeta, err));
  },
};
