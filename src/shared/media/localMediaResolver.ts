import { useEffect, useMemo, useState } from 'react';
import { loadHandle, type PersistedLocalMediaHandle } from '@/shared/lib/media/localHandleStore';

type LocalMediaStorageMode = 'remote' | 'local' | 'uploading' | null | undefined;

interface LocalMediaGenerationLike {
  id: string;
  location?: string | null;
  url?: string | null;
  storage_mode?: LocalMediaStorageMode;
  local_handle_id?: string | null;
}

type LocalMediaState = 'ready' | 'needs-permission' | 'missing' | 'resolving';

interface LocalMediaRegistryEntry {
  refs: number;
  url: string | null;
  promise: Promise<string> | null;
}

interface LocalMediaHandleWithFile extends PersistedLocalMediaHandle {
  getFile: () => Promise<File>;
}

interface UseLocalMediaUrlOptions {
  refreshToken?: number;
}

const objectUrlRegistry = new Map<string, LocalMediaRegistryEntry>();

function hasReadableFile(handle: PersistedLocalMediaHandle | null): handle is LocalMediaHandleWithFile {
  return !!handle && typeof handle.getFile === 'function';
}

function releaseObjectUrl(generationId: string): void {
  const entry = objectUrlRegistry.get(generationId);
  if (!entry) {
    return;
  }

  entry.refs -= 1;
  if (entry.refs > 0) {
    return;
  }

  if (entry.url) {
    URL.revokeObjectURL(entry.url);
    objectUrlRegistry.delete(generationId);
  }
}

async function acquireObjectUrl(
  generationId: string,
  handle: LocalMediaHandleWithFile,
): Promise<string> {
  const existing = objectUrlRegistry.get(generationId);
  if (existing) {
    existing.refs += 1;
    if (existing.url) {
      return existing.url;
    }
    if (existing.promise) {
      return existing.promise;
    }
  }

  const entry: LocalMediaRegistryEntry = existing ?? {
    refs: 1,
    url: null,
    promise: null,
  };

  entry.promise = handle.getFile().then((file) => {
    const current = objectUrlRegistry.get(generationId);
    const blobUrl = URL.createObjectURL(file);

    if (!current) {
      URL.revokeObjectURL(blobUrl);
      throw new Error('Local media registry entry disappeared');
    }

    current.url = blobUrl;
    current.promise = null;

    if (current.refs <= 0) {
      URL.revokeObjectURL(blobUrl);
      objectUrlRegistry.delete(generationId);
    }

    return blobUrl;
  }).catch((error) => {
    const current = objectUrlRegistry.get(generationId);
    if (current) {
      current.promise = null;
      if (current.refs <= 0 || !current.url) {
        objectUrlRegistry.delete(generationId);
      }
    }
    throw error;
  });

  objectUrlRegistry.set(generationId, entry);
  return entry.promise;
}

export function useLocalMediaUrl(
  generation: LocalMediaGenerationLike | null | undefined,
  options?: UseLocalMediaUrlOptions,
): {
  url: string | null;
  state: LocalMediaState;
} {
  const remoteUrl = useMemo(
    () => generation?.location ?? generation?.url ?? null,
    [generation?.location, generation?.url],
  );

  const [resolved, setResolved] = useState<{ url: string | null; state: LocalMediaState }>(() => {
    if (!generation || generation.storage_mode !== 'local') {
      return { url: remoteUrl, state: 'ready' };
    }

    return { url: null, state: 'resolving' };
  });

  useEffect(() => {
    if (!generation || generation.storage_mode !== 'local') {
      setResolved({ url: remoteUrl, state: 'ready' });
      return;
    }

    if (!generation.local_handle_id) {
      setResolved({ url: null, state: 'missing' });
      return;
    }

    let released = false;
    let acquired = false;
    const generationId = generation.id;

    setResolved({ url: null, state: 'resolving' });

    void (async () => {
      const handle = await loadHandle(generation.local_handle_id!);

      if (released) {
        return;
      }

      if (!hasReadableFile(handle)) {
        setResolved({ url: null, state: 'missing' });
        return;
      }

      const permission = await handle.queryPermission({ mode: 'read' });
      if (released) {
        return;
      }

      if (permission !== 'granted') {
        setResolved({ url: null, state: 'needs-permission' });
        return;
      }

      try {
        const url = await acquireObjectUrl(generationId, handle);
        acquired = true;

        if (released) {
          releaseObjectUrl(generationId);
          return;
        }

        setResolved({ url, state: 'ready' });
      } catch {
        if (!released) {
          setResolved({ url: null, state: 'missing' });
        }
      }
    })();

    return () => {
      released = true;
      if (acquired) {
        releaseObjectUrl(generationId);
      }
    };
  }, [generation?.id, generation?.local_handle_id, generation?.storage_mode, options?.refreshToken, remoteUrl]);

  return resolved;
}
