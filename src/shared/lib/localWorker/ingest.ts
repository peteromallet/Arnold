import { getLocalWorkerConfig } from './config';

export interface IngestResult {
  fileUrl: string;
  cleanupPath: string;
}

export interface IngestOptions {
  generationId: string;
  signal?: AbortSignal;
}

export async function ingestFileToLocalWorker(
  file: File,
  { generationId, signal }: IngestOptions,
): Promise<IngestResult> {
  const { baseUrl } = getLocalWorkerConfig();
  const formData = new FormData();
  formData.append('generation_id', generationId);
  formData.append('file', file);

  const response = await fetch(`${baseUrl}/ingest`, {
    method: 'POST',
    body: formData,
    signal,
  });

  if (!response.ok) {
    throw new Error(`Local worker /ingest returned HTTP ${response.status}`);
  }

  const payload = (await response.json()) as { path?: unknown };
  if (typeof payload.path !== 'string' || payload.path.length === 0) {
    throw new Error('Local worker /ingest response missing string `path`');
  }

  return {
    fileUrl: `file://${payload.path}`,
    cleanupPath: payload.path,
  };
}

export async function requestLocalWorkerCleanup(path: string): Promise<void> {
  const { baseUrl } = getLocalWorkerConfig();
  try {
    await fetch(`${baseUrl}/cleanup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
  } catch (error) {
    console.error('[LocalWorkerCleanup] failed for path', path, error);
  }
}
