import type { QueryClient } from '@tanstack/react-query';
import { useCallback, type MutableRefObject } from 'react';
import { assetRegistryQueryKey, timelineQueryKey } from '@/tools/video-editor/hooks/useTimeline';
import {
  transcodeAssetWithResolver,
  uploadAssetWithResolver,
  type AssetResolver,
} from '@/tools/video-editor/data/AssetResolver';
import type { AssetRegistryEntry } from '@/tools/video-editor/types';

export function useAssetOperations(
  provider: AssetResolver,
  timelineId: string,
  userId: string | null,
  queryClient: QueryClient,
  pendingOpsRef: MutableRefObject<number>,
) {
  const uploadAsset = useCallback(async (file: File) => {
    pendingOpsRef.current += 1;
    try {
      const preparedFile = await transcodeAssetWithResolver(provider, {
        file,
        timelineId,
        userId: userId!,
        intent: 'asset-upload',
      });
      return await uploadAssetWithResolver(provider, {
        file: preparedFile,
        options: { timelineId, userId: userId! },
      });
    } finally {
      pendingOpsRef.current -= 1;
    }
  }, [pendingOpsRef, provider, timelineId, userId]);

  const registerAsset = useCallback(async (assetId: string, entry: AssetRegistryEntry) => {
    if (!provider.registerAsset) {
      throw new Error('This editor backend does not support asset registration');
    }

    pendingOpsRef.current += 1;
    try {
      await provider.registerAsset(timelineId, assetId, entry);
      await queryClient.invalidateQueries({ queryKey: assetRegistryQueryKey(timelineId) });
    } finally {
      pendingOpsRef.current -= 1;
    }
  }, [pendingOpsRef, provider, queryClient, timelineId]);

  const uploadFiles = useCallback(async (files: File[]) => {
    await Promise.all(files.map(uploadAsset));
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: timelineQueryKey(timelineId) }),
      queryClient.invalidateQueries({ queryKey: assetRegistryQueryKey(timelineId) }),
    ]);
  }, [queryClient, timelineId, uploadAsset]);

  const invalidateAssetRegistry = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: assetRegistryQueryKey(timelineId) });
  }, [queryClient, timelineId]);

  return {
    uploadAsset,
    registerAsset,
    uploadFiles,
    invalidateAssetRegistry,
  };
}
