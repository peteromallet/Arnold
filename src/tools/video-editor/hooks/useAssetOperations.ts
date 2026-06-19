import type { QueryClient } from '@tanstack/react-query';
import { useCallback, type MutableRefObject } from 'react';
import { assetRegistryQueryKey, timelineQueryKey } from '@/tools/video-editor/hooks/useTimeline.ts';
import {
  transcodeAssetWithResolver,
  uploadAssetWithResolver,
  type AssetResolver,
} from '@/tools/video-editor/data/AssetResolver.ts';
import type { AssetRegistryEntry } from '@/tools/video-editor/types/index.ts';
import type { RegisteredParser } from '../lib/assetParserRuntime';
import { enrichRegistryEntryWithParsers } from '../lib/mediaMetadata';

export function useAssetOperations(
  provider: AssetResolver,
  timelineId: string,
  userId: string | null,
  queryClient: QueryClient,
  pendingOpsRef: MutableRefObject<number>,
  registeredParsers?: readonly RegisteredParser[],
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

      const result = await uploadAssetWithResolver(provider, {
        file: preparedFile,
        options: { timelineId, userId: userId! },
      });

      // If parsers are registered, enrich the entry after upload
      if (registeredParsers && registeredParsers.length > 0) {
        const enriched = await enrichRegistryEntryWithParsers(
          preparedFile,
          result.entry,
          result.assetId,
          registeredParsers,
        );
        // Update the provider-registered entry with parser-enriched metadata
        if (provider.registerAsset) {
          await provider.registerAsset(timelineId, result.assetId, enriched.entry);
        }
        return { assetId: result.assetId, entry: enriched.entry };
      }

      return result;
    } finally {
      pendingOpsRef.current -= 1;
    }
    }, [pendingOpsRef, provider, timelineId, userId, registeredParsers]);

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
