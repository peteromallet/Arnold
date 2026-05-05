import { getSupabaseClient as supabase } from '@/integrations/supabase/client';
import { getSupabaseUrl } from '@/integrations/supabase/config/env';
import {
  storagePaths,
  getFileExtension,
  generateUniqueFilename,
  MEDIA_BUCKET,
} from '../storagePaths';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import {
  attachUploadProgressListener,
  createUploadXhrLifecycle,
} from './uploadXhrLifecycle';
export type { VideoMetadata } from './videoMetadata';
export { extractVideoMetadata, extractVideoMetadataFromUrl } from './videoMetadata';

const DEFAULT_VIDEO_TIMEOUT_MS = 300000;
const STALL_TIMEOUT_MS = 30000;

interface VideoUploadOptions {
  onProgress?: (progress: number) => void;
  maxRetries?: number;
  signal?: AbortSignal;
  timeoutMs?: number;
}

interface ResolvedVideoUploadOptions {
  onProgress?: (progress: number) => void;
  maxRetries: number;
  signal?: AbortSignal;
  timeoutMs: number;
}

interface UploadRequestOptions {
  file: File;
  bucketUrl: string;
  accessToken: string;
  signal?: AbortSignal;
  timeoutMs: number;
  onProgress?: (progress: number) => void;
}

function resolveVideoUploadOptions(
  maxRetriesOrOptions?: number | VideoUploadOptions,
  onProgress?: (progress: number) => void,
): ResolvedVideoUploadOptions {
  if (maxRetriesOrOptions && typeof maxRetriesOrOptions === 'object') {
    return {
      onProgress: maxRetriesOrOptions.onProgress,
      maxRetries: maxRetriesOrOptions.maxRetries ?? 3,
      signal: maxRetriesOrOptions.signal,
      timeoutMs: maxRetriesOrOptions.timeoutMs ?? DEFAULT_VIDEO_TIMEOUT_MS,
    };
  }

  return {
    onProgress,
    maxRetries: typeof maxRetriesOrOptions === 'number' ? maxRetriesOrOptions : 3,
    signal: undefined,
    timeoutMs: DEFAULT_VIDEO_TIMEOUT_MS,
  };
}

function assertNotAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new Error('Upload cancelled');
  }
}

async function getRequiredUploadUserId(): Promise<string> {
  const { data: initialSessionData } = await supabase().auth.getSession();
  const session = initialSessionData?.session;
  if (!session?.access_token || !session.user?.id) {
    throw new Error('No active session');
  }
  return session.user.id;
}

async function getRequiredUploadAccessToken(): Promise<string> {
  const { data: sessionData } = await supabase().auth.getSession();
  const accessToken = sessionData?.session?.access_token;
  if (!accessToken) {
    throw new Error('Session expired - please sign in again');
  }
  return accessToken;
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getRetryDelayMs(attempt: number): number {
  return Math.pow(2, attempt) * 1000;
}

function shouldAbortRetries(error: Error): boolean {
  return error.message.includes('cancelled');
}

function formatFinalUploadError(lastError: Error | null, fileName: string, fileSizeMB: string): Error {
  if (lastError?.message.includes('cancelled')) {
    return new Error('Upload cancelled');
  }
  if (lastError?.message.includes('timed out') || lastError?.message.includes('stalled')) {
    return new Error(
      `Video upload failed: ${fileName} (${fileSizeMB}MB) - connection too slow or unstable. Please check your connection and try again.`,
    );
  }
  return lastError || new Error('Failed to upload video after multiple attempts');
}

function executeVideoUploadRequest(options: UploadRequestOptions): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const lifecycle = createUploadXhrLifecycle();

    const rejectAndAbort = (error: Error) => {
      lifecycle.cleanup();
      xhr.abort();
      reject(error);
    };

    const abortHandler = () => {
      rejectAndAbort(new Error('Upload cancelled'));
    };

    lifecycle.overallTimeout = setTimeout(() => {
      rejectAndAbort(new Error(`Upload timed out after ${options.timeoutMs}ms`));
    }, options.timeoutMs);

    lifecycle.stallCheckInterval = setInterval(() => {
      const timeSinceLastProgress = lifecycle.millisecondsSinceProgress();
      if (timeSinceLastProgress > STALL_TIMEOUT_MS) {
        rejectAndAbort(new Error(`Upload stalled - no progress for ${STALL_TIMEOUT_MS}ms`));
      }
    }, 10000);

    options.signal?.addEventListener('abort', abortHandler);
    attachUploadProgressListener(xhr, options.onProgress, lifecycle.markProgress);

    xhr.addEventListener('load', () => {
      lifecycle.cleanup();
      options.signal?.removeEventListener('abort', abortHandler);
      if (xhr.status >= 200 && xhr.status < 300) {
        options.onProgress?.(100);
        resolve();
        return;
      }
      reject(new Error(`Upload failed with status ${xhr.status}: ${xhr.responseText}`));
    });

    xhr.addEventListener('error', () => {
      lifecycle.cleanup();
      options.signal?.removeEventListener('abort', abortHandler);
      reject(new Error('Network error during upload'));
    });

    xhr.addEventListener('abort', () => {
      lifecycle.cleanup();
      options.signal?.removeEventListener('abort', abortHandler);
      reject(new Error('Upload aborted'));
    });

    xhr.open('POST', options.bucketUrl);
    xhr.setRequestHeader('Authorization', `Bearer ${options.accessToken}`);
    xhr.setRequestHeader('Content-Type', options.file.type || 'video/mp4');
    xhr.setRequestHeader('Cache-Control', '3600');
    xhr.send(options.file);
  });
}

function buildStorageTarget(file: File, userId: string): { fileName: string; fileSizeMB: string } {
  const fileExt = getFileExtension(file.name, file.type, 'mp4');
  const filename = generateUniqueFilename(fileExt);
  return {
    fileName: storagePaths.upload(userId, filename),
    fileSizeMB: (file.size / (1024 * 1024)).toFixed(2),
  };
}

export async function uploadVideoToStorageWithPath(
  file: File,
  maxRetriesOrOptions?: number | VideoUploadOptions,
  onProgress?: (progress: number) => void,
): Promise<{ publicUrl: string; path: string }> {
  const { onProgress: progressCallback, maxRetries, signal, timeoutMs } =
    resolveVideoUploadOptions(maxRetriesOrOptions, onProgress);

  assertNotAborted(signal);

  const userId = await getRequiredUploadUserId();
  const { fileName, fileSizeMB } = buildStorageTarget(file, userId);
  let lastError: Error | null = null;

  for (let attempt = 0; attempt < maxRetries; attempt += 1) {
    assertNotAborted(signal);

    try {
      const accessToken = await getRequiredUploadAccessToken();
      const bucketUrl = `${getSupabaseUrl()}/storage/v1/object/${MEDIA_BUCKET}/${fileName}`;

      await executeVideoUploadRequest({
        file,
        bucketUrl,
        accessToken,
        signal,
        timeoutMs,
        onProgress: progressCallback,
      });

      const {
        data: { publicUrl },
      } = supabase().storage.from(MEDIA_BUCKET).getPublicUrl(fileName);

      return { publicUrl, path: fileName };
    } catch (error) {
      lastError = error instanceof Error ? error : new Error('Unknown upload error');
      normalizeAndPresentError(lastError, { context: 'VideoUploader', showToast: false });

      if (shouldAbortRetries(lastError)) {
        throw lastError;
      }

      if (attempt < maxRetries - 1) {
        await wait(getRetryDelayMs(attempt));
      }
    }
  }

  throw formatFinalUploadError(lastError, file.name, fileSizeMB);
}

/**
 * Uploads a video file to Supabase storage with real progress tracking,
 * timeout, abort support, and stall detection.
 */
export async function uploadVideoToStorage(
  file: File,
  maxRetriesOrOptions?: number | VideoUploadOptions,
  onProgress?: (progress: number) => void,
): Promise<string> {
  const { publicUrl } = await uploadVideoToStorageWithPath(file, maxRetriesOrOptions, onProgress);
  return publicUrl;
}
