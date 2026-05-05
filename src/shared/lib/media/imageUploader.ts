import { getSupabaseClient as supabase } from '@/integrations/supabase/client';
import { getSupabaseUrl } from '@/integrations/supabase/config/env';
import { storagePaths, getFileExtension, generateUniqueFilename, MEDIA_BUCKET } from '../storagePaths';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import {
  attachUploadProgressListener,
  createUploadXhrLifecycle,
} from './uploadXhrLifecycle';

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const DEFAULT_TIMEOUT_MS = 60000;
const STALL_TIMEOUT_MS = 15000;

interface UploadOptions {
  maxRetries?: number;
  onProgress?: (progress: number) => void;
  signal?: AbortSignal;
  timeoutMs?: number;
}

interface ResolvedUploadOptions {
  maxRetries: number;
  onProgress?: (progress: number) => void;
  signal?: AbortSignal;
  timeoutMs: number;
}

function resolveUploadOptions(
  maxRetriesOrOptions?: number | UploadOptions,
  onProgress?: (progress: number) => void,
): ResolvedUploadOptions {
  if (typeof maxRetriesOrOptions === 'object') {
    return {
      maxRetries: maxRetriesOrOptions.maxRetries ?? 3,
      onProgress: maxRetriesOrOptions.onProgress,
      signal: maxRetriesOrOptions.signal,
      timeoutMs: maxRetriesOrOptions.timeoutMs ?? DEFAULT_TIMEOUT_MS,
    };
  }

  return {
    maxRetries: maxRetriesOrOptions ?? 3,
    onProgress,
    signal: undefined,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  };
}

function isCancelledError(message: string): boolean {
  return message.includes('cancelled');
}

function isFileTooLargeError(message: string): boolean {
  return message.includes('413') || message.includes('too large');
}

function getRetryDelay(attempt: number): number {
  return 1000 * Math.pow(2, attempt - 1);
}

async function requireSessionUserId(): Promise<string> {
  const {
    data: { session },
  } = await supabase().auth.getSession();

  if (!session?.user?.id) {
    throw new Error('User not authenticated');
  }

  return session.user.id;
}

async function requireAccessToken(): Promise<string> {
  const {
    data: { session },
  } = await supabase().auth.getSession();

  if (!session?.access_token) {
    throw new Error('Session expired - please sign in again');
  }

  return session.access_token;
}

async function uploadFileWithXhr(input: {
  file: File;
  filePath: string;
  accessToken: string;
  timeoutMs: number;
  signal?: AbortSignal;
  onProgress?: (progress: number) => void;
}): Promise<void> {
  const { file, filePath, accessToken, timeoutMs, signal, onProgress } = input;
  const bucketUrl = `${getSupabaseUrl()}/storage/v1/object/${MEDIA_BUCKET}/${filePath}`;

  await new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const lifecycle = createUploadXhrLifecycle();

    const fail = (error: Error) => {
      lifecycle.cleanup();
      signal?.removeEventListener('abort', abortHandler);
      reject(error);
    };

    const abortHandler = () => {
      xhr.abort();
      fail(new Error('Upload cancelled'));
    };

    lifecycle.overallTimeout = setTimeout(() => {
      xhr.abort();
      fail(new Error(`Upload timed out after ${timeoutMs}ms`));
    }, timeoutMs);

    lifecycle.stallCheckInterval = setInterval(() => {
      const timeSinceLastProgress = lifecycle.millisecondsSinceProgress();
      if (timeSinceLastProgress > STALL_TIMEOUT_MS) {
        xhr.abort();
        fail(new Error(`Upload stalled - no progress for ${STALL_TIMEOUT_MS}ms`));
      }
    }, 5000);

    signal?.addEventListener('abort', abortHandler);
    attachUploadProgressListener(xhr, onProgress, lifecycle.markProgress);

    xhr.addEventListener('load', () => {
      lifecycle.cleanup();
      signal?.removeEventListener('abort', abortHandler);
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress?.(100);
        resolve();
      } else {
        reject(new Error(`Upload failed with status ${xhr.status}: ${xhr.responseText}`));
      }
    });

    xhr.addEventListener('error', () => {
      fail(new Error('Network error'));
    });

    xhr.addEventListener('abort', () => {
      fail(new Error('Upload aborted'));
    });

    xhr.open('POST', bucketUrl);
    xhr.setRequestHeader('Authorization', `Bearer ${accessToken}`);
    xhr.setRequestHeader('Content-Type', file.type);
    xhr.setRequestHeader('Cache-Control', '3600');
    xhr.send(file);
  });
}

function getPublicUrlFromPath(path: string): string {
  const {
    data: { publicUrl },
  } = supabase().storage.from(MEDIA_BUCKET).getPublicUrl(path);

  if (!publicUrl) {
    throw new Error('Failed to obtain a public URL for the uploaded image.');
  }

  return publicUrl;
}

function buildUploadFailureMessage(
  lastError: unknown,
  fileName: string,
  fileSizeMB: string,
  maxRetries: number,
): string {
  const lastErrorMsg = lastError instanceof Error ? lastError.message : String(lastError);
  if (isCancelledError(lastErrorMsg)) {
    return 'Upload cancelled';
  }

  if (lastErrorMsg.includes('timed out') || lastErrorMsg.includes('stalled')) {
    return `Upload failed: ${fileName} (${fileSizeMB}MB) - connection too slow or unstable. Please check your connection and try again.`;
  }

  return `Failed to upload image after ${maxRetries} attempts: ${lastErrorMsg || 'Unknown error'}`;
}

export const uploadImageToStorageWithPath = async (
  file: File,
  maxRetriesOrOptions?: number | UploadOptions,
  onProgress?: (progress: number) => void,
): Promise<{ publicUrl: string; path: string }> => {
  const options = resolveUploadOptions(maxRetriesOrOptions, onProgress);
  const { maxRetries, onProgress: progressCallback, signal, timeoutMs } = options;

  if (!file) {
    throw new Error('No file provided');
  }

  if (signal?.aborted) {
    throw new Error('Upload cancelled');
  }

  const userId = await requireSessionUserId();
  const fileExtension = getFileExtension(file.name, file.type);
  const filename = generateUniqueFilename(fileExtension);
  const filePath = storagePaths.upload(userId, filename);
  const fileSizeMB = (file.size / (1024 * 1024)).toFixed(2);

  let lastError: unknown;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    if (signal?.aborted) {
      throw new Error('Upload cancelled');
    }

    try {
      const accessToken = await requireAccessToken();
      await uploadFileWithXhr({
        file,
        filePath,
        accessToken,
        timeoutMs,
        signal,
        onProgress: progressCallback,
      });

      return { publicUrl: getPublicUrlFromPath(filePath), path: filePath };
    } catch (error) {
      lastError = error;
      const errorMsg = error instanceof Error ? error.message : String(error);

      if (isFileTooLargeError(errorMsg)) {
        throw new Error(`File too large: ${file.name} (${fileSizeMB}MB) exceeds the maximum allowed size.`);
      }
      if (isCancelledError(errorMsg)) {
        throw error;
      }

      if (attempt < maxRetries) {
        await wait(getRetryDelay(attempt));
      }
    }
  }

  normalizeAndPresentError(lastError, { context: `ImageUpload:allRetriesFailed:${file.name}`, showToast: false });
  throw new Error(buildUploadFailureMessage(lastError, file.name, fileSizeMB, maxRetries));
};

/**
 * Uploads an image file with retry mechanism, timeout, abort support, and optional progress tracking.
 * Returns the public URL of the uploaded image.
 */
export const uploadImageToStorage = async (
  file: File,
  maxRetriesOrOptions?: number | UploadOptions,
  onProgress?: (progress: number) => void,
): Promise<string> => {
  const { publicUrl } = await uploadImageToStorageWithPath(file, maxRetriesOrOptions, onProgress);
  return publicUrl;
};

/**
 * Upload a Blob (e.g., thumbnail) to storage with same timeout/retry support
 */
export const uploadBlobToStorage = (
  blob: Blob,
  filename: string,
  contentType: string,
  options: UploadOptions = {},
): Promise<string> => {
  const file = new File([blob], filename, { type: contentType });
  return uploadImageToStorage(file, options);
};

export const uploadThumbnailBlobToStorage = async (
  blob: Blob,
  fileName: string,
  contentType: string = 'image/jpeg',
): Promise<string> => {
  const userId = await requireSessionUserId();
  const filePath = storagePaths.thumbnail(userId, fileName);

  const { error } = await supabase().storage
    .from(MEDIA_BUCKET)
    .upload(filePath, blob, {
      contentType,
      upsert: true,
    });

  if (error) {
    throw error;
  }

  return getPublicUrlFromPath(filePath);
};
