import type { AssetRegistryEntry } from '@/tools/video-editor/types/index.ts';

export interface OptimisticAssetRegistryWriteOptions {
  assetId: string;
  entry: AssetRegistryEntry;
  patchRegistry: (assetId: string, entry: AssetRegistryEntry, src?: string) => void;
  persistAsset: (assetId: string, entry: AssetRegistryEntry) => Promise<void>;
  src?: string;
  rollback:
    | {
        mode: 'remove';
        unpatchRegistry: (assetId: string) => void;
      }
    | {
        mode: 'restore';
        previousEntry: AssetRegistryEntry;
        previousSrc?: string;
      };
}

export function optimisticallyPersistAssetRegistryEntry({
  assetId,
  entry,
  patchRegistry,
  persistAsset,
  src,
  rollback,
}: OptimisticAssetRegistryWriteOptions): Promise<void> {
  patchRegistry(assetId, entry, src);

  return persistAsset(assetId, entry).catch((error) => {
    if (rollback.mode === 'remove') {
      rollback.unpatchRegistry(assetId);
    } else {
      patchRegistry(assetId, rollback.previousEntry, rollback.previousSrc);
    }

    throw error;
  });
}
