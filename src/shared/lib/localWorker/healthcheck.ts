import { getLocalWorkerConfig } from './config';

export async function probeLocalWorker(): Promise<boolean> {
  const { baseUrl, healthcheckTimeoutMs } = getLocalWorkerConfig();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), healthcheckTimeoutMs);
  try {
    const response = await fetch(`${baseUrl}/health`, {
      method: 'GET',
      signal: controller.signal,
    });
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}
