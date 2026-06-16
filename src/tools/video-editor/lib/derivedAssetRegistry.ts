import type { AssetRegistry, AssetRegistryEntry } from '@/tools/video-editor/types/index.ts';
import { cloneAssetRegistry, sanitizeAssetRegistryEntry } from '@/tools/video-editor/lib/timeline-domain.ts';

type DerivedAssetRole = NonNullable<AssetRegistryEntry['derivedFrom']>['role'];

type DerivedAssetBaseInput = Omit<AssetRegistryEntry, 'derivedFrom'>;

type DerivedAssetLinkInput = {
  sourceAssetId: string;
  sourceEntry?: AssetRegistryEntry | null;
  parentContentSha256?: string | null;
  role: DerivedAssetRole;
};

type UpsertDerivedAssetInput = DerivedAssetLinkInput & {
  derivedAssetId: string;
  entry: DerivedAssetBaseInput;
  displayUrl?: string | null;
};

const trimToUndefined = (value: string | null | undefined): string | undefined => {
  if (typeof value !== 'string') {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
};

const resolveParentContentSha256 = (
  sourceEntry?: AssetRegistryEntry | null,
  parentContentSha256?: string | null,
): string | undefined => {
  return trimToUndefined(parentContentSha256) ?? trimToUndefined(sourceEntry?.content_sha256);
};

export const buildDerivedFromLink = ({
  sourceAssetId,
  sourceEntry,
  parentContentSha256,
  role,
}: DerivedAssetLinkInput): NonNullable<AssetRegistryEntry['derivedFrom']> => {
  const resolvedParentContentSha256 = resolveParentContentSha256(sourceEntry, parentContentSha256);
  return {
    assetId: sourceAssetId,
    ...(resolvedParentContentSha256 ? { content_sha256: resolvedParentContentSha256 } : {}),
    role,
  };
};

export const buildDerivedAssetEntry = ({
  sourceAssetId,
  sourceEntry,
  parentContentSha256,
  role,
  entry,
}: DerivedAssetLinkInput & { entry: DerivedAssetBaseInput }): AssetRegistryEntry => {
  return sanitizeAssetRegistryEntry({
    ...entry,
    derivedFrom: buildDerivedFromLink({
      sourceAssetId,
      sourceEntry,
      parentContentSha256,
      role,
    }),
  });
};

export const buildDerivedThumbnailAssetEntry = (
  input: Omit<DerivedAssetLinkInput, 'role'> & { entry: DerivedAssetBaseInput },
): AssetRegistryEntry => buildDerivedAssetEntry({ ...input, role: 'thumbnail' });

export const buildDerivedProxyAssetEntry = (
  input: Omit<DerivedAssetLinkInput, 'role'> & { entry: DerivedAssetBaseInput },
): AssetRegistryEntry => buildDerivedAssetEntry({ ...input, role: 'proxy' });

export const buildRenderOutputAssetEntry = (
  input: Omit<DerivedAssetLinkInput, 'role'> & { entry: DerivedAssetBaseInput },
): AssetRegistryEntry => buildDerivedAssetEntry({ ...input, role: 'render-output' });

export const upsertDerivedAsset = (
  registry: AssetRegistry,
  {
    derivedAssetId,
    sourceAssetId,
    parentContentSha256,
    role,
    entry,
    displayUrl,
  }: UpsertDerivedAssetInput,
): AssetRegistry => {
  const nextRegistry = cloneAssetRegistry(registry);
  const currentSourceEntry = nextRegistry.assets[sourceAssetId];
  if (!currentSourceEntry) {
    throw new Error(`Cannot register derived asset '${derivedAssetId}' without source asset '${sourceAssetId}'`);
  }

  nextRegistry.assets[derivedAssetId] = buildDerivedAssetEntry({
    sourceAssetId,
    sourceEntry: currentSourceEntry,
    parentContentSha256,
    role,
    entry,
  });

  if (role === 'thumbnail') {
    const resolvedDisplayUrl = trimToUndefined(displayUrl) ?? trimToUndefined(entry.url);
    if (resolvedDisplayUrl) {
      nextRegistry.assets[sourceAssetId] = sanitizeAssetRegistryEntry({
        ...currentSourceEntry,
        thumbnailUrl: resolvedDisplayUrl,
      });
    }
  }

  return nextRegistry;
};
