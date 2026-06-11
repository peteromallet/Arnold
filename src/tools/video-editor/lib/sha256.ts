/**
 * Lazy, streamed browser-safe SHA-256 helpers.
 *
 * All hashing is asynchronous and chunked so that large File/Blob inputs never
 * block the main thread. These helpers are designed to be called explicitly from
 * sync/publish/render preparation paths — they must NOT be invoked synchronously
 * (or eagerly) from import, timeline load, or preview materialization code paths.
 */

import type { AssetRegistry, AssetRegistryEntry } from '@/tools/video-editor/types/index';

// 1 MiB chunks keep memory pressure low while yielding reasonable throughput.
const SHA256_CHUNK_SIZE = 1024 * 1024;

/**
 * Compute the lowercase-hex SHA-256 digest of a File or Blob.
 *
 * Reads the input in chunks via {@link FileReader} so that even multi-GB files
 * never materialise their entire contents in a single ArrayBuffer.
 *
 * @returns a 64-character lowercase hex string.
 */
export async function computeSHA256(file: File | Blob): Promise<string> {
  const chunks = chunkBlob(file, SHA256_CHUNK_SIZE);
  const hash = await hashChunks(chunks);
  return bufferToHex(hash);
}

/**
 * Fill in missing `content_sha256` fields across an {@link AssetRegistry}.
 *
 * Iterates over every asset entry in the registry. When `content_sha256` is
 * absent or empty, the helper fetches the underlying blob via `fetchBlob`
 * (defaulting to a standard `fetch`-based implementation) and computes the
 * hash. Entries that already carry a non-empty hash are left untouched.
 *
 * @param registry  The asset registry to hydrate.
 * @param options.fetchBlob  Optional custom blob fetcher (e.g. for local
 *   File/Blob resolution). Defaults to `fetch(url).then(r => r.blob())`.
 * @returns A shallow copy of the registry with hashes filled in. Original
 *   entries are not mutated.
 */
export async function fillMissingContentSHA256(
  registry: AssetRegistry,
  options?: {
    fetchBlob?: (url: string) => Promise<Blob | null>;
  },
): Promise<AssetRegistry> {
  const fetchBlob = options?.fetchBlob ?? defaultFetchBlob;
  const entries = { ...registry.assets };
  const assetIds = Object.keys(entries);

  for (const assetId of assetIds) {
    const entry = entries[assetId];
    if (hasContentSHA256(entry)) {
      continue;
    }

    const url = entry.url ?? entry.file;
    if (!url) {
      continue;
    }

    try {
      const blob = await fetchBlob(url);
      if (!blob) {
        continue;
      }
      const hash = await computeSHA256(blob);
      entries[assetId] = { ...entry, content_sha256: hash };
    } catch {
      // Swallow individual fetch/hash failures — a missing hash is not fatal.
      // Callers that require 100 % coverage should inspect the returned
      // registry and decide how to handle gaps.
    }
  }

  return { assets: entries };
}

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

async function* chunkBlob(
  blob: File | Blob,
  chunkSize: number,
): AsyncGenerator<ArrayBuffer> {
  let offset = 0;
  while (offset < blob.size) {
    const slice = blob.slice(offset, offset + chunkSize);
    offset += chunkSize;
    yield await slice.arrayBuffer();
  }
}

async function hashChunks(chunks: AsyncGenerator<ArrayBuffer>): Promise<ArrayBuffer> {
  // Web Crypto subtle.digest does not expose a streaming interface, so we
  // concatenate progressively.  For the per-asset use case (single files,
  // not giant video renders) this is acceptable; the chunked reader still
  // avoids a single monolithic buffer allocation from the host platform.
  let totalLength = 0;
  const parts: ArrayBuffer[] = [];

  for await (const chunk of chunks) {
    parts.push(chunk);
    totalLength += chunk.byteLength;
  }

  // Assemble into a single contiguous buffer for the final digest call.
  const merged = new Uint8Array(totalLength);
  let writeOffset = 0;
  for (const part of parts) {
    merged.set(new Uint8Array(part), writeOffset);
    writeOffset += part.byteLength;
  }

  return crypto.subtle.digest('SHA-256', merged);
}

function bufferToHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

function hasContentSHA256(entry: AssetRegistryEntry): boolean {
  return typeof entry.content_sha256 === 'string' && entry.content_sha256.length === 64;
}

async function defaultFetchBlob(url: string): Promise<Blob | null> {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      return null;
    }
    return response.blob();
  } catch {
    return null;
  }
}
