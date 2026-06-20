export type RealtimeFetchErrorType =
  | 'CONNECTION_CLOSED'
  | 'NETWORK_ERROR'
  | 'TIMEOUT'
  | 'ABORTED'
  | 'AUTH_ERROR'
  | 'RATE_LIMITED'
  | 'SERVICE_UNAVAILABLE'
  | 'UNKNOWN';

export function classifyRealtimeFetchError(error: Error): RealtimeFetchErrorType {
  const message = error.message?.toLowerCase() || '';

  if (message.includes('connection_closed') || message.includes('err_connection_closed')) {
    return 'CONNECTION_CLOSED';
  }
  if (message.includes('failed to fetch') || message.includes('network')) {
    return 'NETWORK_ERROR';
  }
  if (message.includes('timeout') || message.includes('timed out')) {
    return 'TIMEOUT';
  }
  if (message.includes('abort')) {
    return 'ABORTED';
  }
  if (message.includes('401') || message.includes('unauthorized')) {
    return 'AUTH_ERROR';
  }
  if (message.includes('429') || message.includes('rate limit')) {
    return 'RATE_LIMITED';
  }
  if (message.includes('503') || message.includes('service unavailable')) {
    return 'SERVICE_UNAVAILABLE';
  }
  return 'UNKNOWN';
}

export function toUserFriendlyRealtimeErrorMessage(
  errorType: RealtimeFetchErrorType,
  failureCount: number,
): string {
  switch (errorType) {
    case 'CONNECTION_CLOSED':
    case 'NETWORK_ERROR':
      return 'Connection issue detected';
    case 'TIMEOUT':
      return 'Server is slow to respond';
    case 'RATE_LIMITED':
      return 'Too many requests - slowing down';
    case 'SERVICE_UNAVAILABLE':
      return 'Service temporarily unavailable';
    case 'AUTH_ERROR':
      return 'Authentication issue - try refreshing';
    default:
      return `Connection issues (${failureCount} failures)`;
  }
}
