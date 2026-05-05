export interface LocalWorkerConfig {
  baseUrl: string;
  healthcheckTimeoutMs: number;
}

const DEFAULT_BASE_URL = 'http://localhost:8765';

export function getLocalWorkerConfig(): LocalWorkerConfig {
  const fromEnv = import.meta.env.VITE_LOCAL_WORKER_BASE_URL;
  const baseUrl = typeof fromEnv === 'string' && fromEnv.length > 0 ? fromEnv : DEFAULT_BASE_URL;
  return {
    baseUrl: baseUrl.replace(/\/$/, ''),
    healthcheckTimeoutMs: 250,
  };
}
