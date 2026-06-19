import { useMemo, useRef, useState } from 'react';
import { useQueries } from '@tanstack/react-query';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import { getGenerationDropData, getDragType } from '@/shared/lib/dnd/dragDrop.ts';
import { Button } from '@/shared/components/ui/button.tsx';
import { Input } from '@/shared/components/ui/input.tsx';
import { ScrollArea } from '@/shared/components/ui/scroll-area.tsx';
import {
  ExternalLink,
  Film,
  ImageIcon,
  Music2,
  Search,
  Upload,
  AlertTriangle,
  Clock,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import { useTimelineEditorOps } from '@/tools/video-editor/hooks/timelineStore.ts';
import type { ClipMeta } from '@/tools/video-editor/lib/timeline-data.ts';
import type { AssetRegistryEntry } from '@/tools/video-editor/types/index.ts';
import {
  hasSearchableMetadata,
  shouldShowMetadataSearch,
  matchMetadataText,
  hasMetadataFacetValues,
  getMetadataFacetValues,
  getSourceBadge,
  getEnrichmentStatus,
  getEnrichmentClaimDetails,
  getProvenanceChainDetails,
  hasRelatedMaterials,
  getRelatedMaterialIds,
  getVisibleExtensionDetailSections,
  mergeSearchProviderResults,
  getSearchProviderMatchedAssetKeys,
  getSearchProviderSourceLabels,
} from '@/tools/video-editor/lib/assetMetadataUIHelpers';
import type {
  SearchProviderResultEnvelope,
  MergedSearchResults,
} from '@/tools/video-editor/lib/assetMetadataUIHelpers';

interface AssetPanelProps {
  assetMap: Record<string, string>;
  rows: Array<{ id: string; actions: Array<{ id: string }> }>;
  meta: Record<string, ClipMeta>;
  backgroundAsset?: string;
  showAll: boolean;
  showHidden: boolean;
  hidden: string[];
  setPanelState: (patch: { showAll?: boolean; showHidden?: boolean; hidden?: string[] }) => void;
  onUploadFiles: (files: File[]) => Promise<void>;
  registry?: Record<string, AssetRegistryEntry>;
  /** M6: Pre-computed search provider results for merging with built-in metadata filtering. */
  searchResults?: readonly SearchProviderResultEnvelope[] | null;
}

const inferKind = (entry: AssetRegistryEntry | undefined, assetKey: string): 'visual' | 'audio' => {
  if (entry?.type?.startsWith('audio')) {
    return 'audio';
  }

  if (/\.(mp3|wav|aac|m4a)$/i.test(assetKey) || entry?.type?.startsWith('audio')) {
    return 'audio';
  }

  return 'visual';
};

/** Source badge color and icon mapping. */
const SOURCE_BADGE_STYLES: Record<string, string> = {
  generation: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
  upload: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  'external-url': 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  unknown: 'bg-muted text-muted-foreground',
};

export default function AssetPanel({
  assetMap,
  rows,
  meta,
  backgroundAsset,
  showAll,
  showHidden,
  hidden,
  setPanelState,
  onUploadFiles,
  registry,
  searchResults,
}: AssetPanelProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isGenerationDragOver, setIsGenerationDragOver] = useState(false);
  const [lightboxAssetId, setLightboxAssetId] = useState<string | null>(null);
  const [metadataSearchText, setMetadataSearchText] = useState('');
  const [expandedAssets, setExpandedAssets] = useState<Set<string>>(new Set());
  const { mediaLightbox } = useVideoEditorRuntime();
  const { registerGenerationAsset } = useTimelineEditorOps();

  // M6: Access extension runtime config for metadata facets, search providers,
  // and asset detail sections.
  const runtime = useVideoEditorRuntime();
  const extensionConfig = runtime.extensions;
  const metadataFacets = extensionConfig?.metadataFacets ?? [];
  const searchProviders = extensionConfig?.searchProviders ?? [];
  const assetDetailSections = extensionConfig?.assetDetailSections ?? [];

  const usedAssets = useMemo(() => {
    const used = new Set<string>();
    rows.forEach((row) => {
      row.actions.forEach((action) => {
        const assetKey = meta[action.id]?.asset;
        if (assetKey) {
          used.add(assetKey);
        }
      });
    });

    if (backgroundAsset) {
      used.add(backgroundAsset);
    }

    return used;
  }, [backgroundAsset, meta, rows]);

  // M6: Determine whether to show metadata search
  const showMetadataSearch = useMemo(
    () => shouldShowMetadataSearch(registry, searchProviders),
    [registry, searchProviders],
  );

  // M6: Metadata-text-filtered registry subset, merged with search provider results
  const metadataFilteredKeys = useMemo(() => {
    if (!metadataSearchText || metadataSearchText.trim().length === 0) return null;

    const matchingKeys = new Set<string>();

    // Built-in host-owned metadata text filtering
    if (registry) {
      const keys = Object.keys(registry);
      for (let i = 0; i < keys.length; i++) {
        const key = keys[i];
        const matches = matchMetadataText(registry[key], metadataSearchText);
        if (matches.length > 0) {
          matchingKeys.add(key);
        }
      }
    }

    // Search provider results: merge with built-in filtering and add matching asset keys
    const effectiveSearchResults = searchResults ?? [];
    if (effectiveSearchResults.length > 0) {
      const merged = mergeSearchProviderResults(
        registry,
        metadataSearchText,
        effectiveSearchResults,
      );
      const providerKeys = getSearchProviderMatchedAssetKeys(merged);
      for (const key of providerKeys) {
        matchingKeys.add(key);
      }
    }

    return matchingKeys;
  }, [metadataSearchText, registry, searchResults]);

  // M6: Merged search results for source labeling (recomputed for display)
  const mergedSearchResults: MergedSearchResults | null = useMemo(() => {
    const effectiveSearchResults = searchResults ?? [];
    if (!metadataSearchText || metadataSearchText.trim().length === 0 || effectiveSearchResults.length === 0) {
      return null;
    }
    return mergeSearchProviderResults(registry, metadataSearchText, effectiveSearchResults);
  }, [metadataSearchText, registry, searchResults]);

  // M6: Search provider source labels for the active query
  const searchProviderSourceLabels = useMemo(() => {
    if (!mergedSearchResults) return [];
    return getSearchProviderSourceLabels(mergedSearchResults);
  }, [mergedSearchResults]);

  const visibleAssets = useMemo(() => {
    return Object.entries(assetMap).filter(([assetKey]) => {
      if (!showAll && !usedAssets.has(assetKey)) {
        return false;
      }

      if (!showHidden && hidden.includes(assetKey)) {
        return false;
      }

      // M6: Apply metadata text filter when active
      if (metadataFilteredKeys && !metadataFilteredKeys.has(assetKey)) {
        return false;
      }

      return true;
    });
  }, [assetMap, hidden, showAll, showHidden, usedAssets, metadataFilteredKeys]);

  const generationAssets = useMemo(() => {
    return visibleAssets.flatMap(([assetKey]) => {
      const generationId = registry?.[assetKey]?.generationId;
      return generationId ? [{ assetKey, generationId }] : [];
    });
  }, [registry, visibleAssets]);

  const uniqueGenerationAssets = useMemo(() => {
    const seen = new Set<string>();
    return generationAssets.filter(({ generationId }) => {
      if (seen.has(generationId)) {
        return false;
      }

      seen.add(generationId);
      return true;
    });
  }, [generationAssets]);

  const generationQueries = useQueries({
    queries: uniqueGenerationAssets.map(({ generationId }) => ({
      queryKey: ['video-editor', 'generation-lightbox', generationId],
      queryFn: () => mediaLightbox.loadGenerationForLightbox(generationId),
      staleTime: 60_000,
    })),
  });

  const generationMap = useMemo(() => {
    const queryByGenerationId = new Map(
      uniqueGenerationAssets.map(({ generationId }, index) => [generationId, generationQueries[index]]),
    );

    return Object.fromEntries(
      generationAssets.map(({ assetKey, generationId }) => [assetKey, queryByGenerationId.get(generationId)]),
    );
  }, [generationAssets, generationQueries, uniqueGenerationAssets]);

  const lightboxAsset = lightboxAssetId ? registry?.[lightboxAssetId] : undefined;
  const lightboxQuery = lightboxAssetId ? generationMap[lightboxAssetId] : undefined;

  const toggleExpanded = (assetKey: string) => {
    setExpandedAssets((prev) => {
      const next = new Set(prev);
      if (next.has(assetKey)) {
        next.delete(assetKey);
      } else {
        next.add(assetKey);
      }
      return next;
    });
  };

  return (
    <>
      <div
        className={cn(
          'space-y-3 rounded-lg p-2 transition-colors',
          isGenerationDragOver && 'bg-accent/10 ring-1 ring-inset ring-accent',
        )}
        onDragOver={(event) => {
          if (getDragType(event) !== 'generation') {
            return;
          }
          event.preventDefault();
          event.stopPropagation();
          setIsGenerationDragOver(true);
        }}
        onDragLeave={() => setIsGenerationDragOver(false)}
        onDrop={(event) => {
          const generationData = getGenerationDropData(event);
          if (!generationData) {
            return;
          }
          event.preventDefault();
          event.stopPropagation();
          setIsGenerationDragOver(false);
          registerGenerationAsset(generationData);
        }}
      >
        <div className="rounded-lg border border-dashed border-border bg-muted/30 p-3">
          <div className="flex items-center justify-between gap-2">
            <div>
              <div className="text-xs font-medium text-foreground">Upload assets</div>
              <div className="text-[11px] text-muted-foreground">Videos, audio, and images land in the private timeline bucket.</div>
            </div>
            <Button
              type="button"
              size="sm"
              className="gap-1"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="h-3.5 w-3.5" />
              Upload
            </Button>
          </div>
          <Input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(event) => {
              const files = Array.from(event.target.files ?? []);
              if (files.length === 0) {
                return;
              }

              void onUploadFiles(files);
              event.target.value = '';
            }}
          />
        </div>

        {/* M6: Metadata search input (conditional) */}
        {showMetadataSearch && (
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search metadata..."
              value={metadataSearchText}
              onChange={(event) => setMetadataSearchText(event.target.value)}
              className="h-8 pl-8 text-xs"
            />
          </div>
        )}
        {/* M6: Search provider source summary */}
        {metadataSearchText && searchProviderSourceLabels.length > 0 && (
          <div className="text-[10px] text-muted-foreground flex items-center gap-1">
            <span>Results from:</span>
            {searchProviderSourceLabels.map((label, idx) => (
              <span key={label} className="inline-flex items-center rounded bg-accent/50 px-1 py-0 text-[9px] font-medium">
                {label}
              </span>
            ))}
          </div>
        )}

        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <label className="inline-flex items-center gap-1">
            <input type="checkbox" checked={showAll} onChange={(event) => setPanelState({ showAll: event.target.checked })} />
            Show all
          </label>
          <label className="inline-flex items-center gap-1">
            <input type="checkbox" checked={showHidden} onChange={(event) => setPanelState({ showHidden: event.target.checked })} />
            Show hidden
          </label>
        </div>

        <ScrollArea className="h-[260px] rounded-lg border border-border">
          <div className="space-y-1 p-2">
            {visibleAssets.map(([assetKey, file]) => {
              const entry = registry?.[assetKey];
              const kind = inferKind(entry, file);
              const isUsed = usedAssets.has(assetKey);
              const isHidden = hidden.includes(assetKey);
              const isExpanded = expandedAssets.has(assetKey);
              const generationQuery = generationMap[assetKey];
              const canOpenSource = Boolean(entry?.generationId) && Boolean(generationQuery?.data);
              const sourceUnavailable = Boolean(entry?.generationId) && !generationQuery?.isLoading && !generationQuery?.data;
              const icon = kind === 'audio'
                ? <Music2 className="h-3.5 w-3.5" />
                : entry?.type?.startsWith('image')
                  ? <ImageIcon className="h-3.5 w-3.5" />
                  : <Film className="h-3.5 w-3.5" />;

              // M6: Source badge, enrichment status, and metadata details
              const sourceBadge = getSourceBadge(entry);
              // M6: Search provider match info for this asset (if any)
              const searchProviderMatch = mergedSearchResults?.matches.find(
                (m) => m.kind === 'asset' && m.ref === assetKey && m.matchSource === 'search-provider',
              ) ?? null;
              const enrichmentStatus = getEnrichmentStatus(entry);
              const provenanceDetail = getProvenanceChainDetails(entry);
              const enrichmentClaims = getEnrichmentClaimDetails(entry);
              const relatedIds = getRelatedMaterialIds(entry);
              const hasFacets = hasMetadataFacetValues(entry, metadataFacets);
              const detailSections = getVisibleExtensionDetailSections(entry, assetDetailSections);
              const hasMetadataDetails = Boolean(
                sourceBadge.kind !== 'unknown' ||
                enrichmentStatus.hasEnrichment ||
                provenanceDetail ||
                enrichmentClaims.length > 0 ||
                relatedIds.length > 0 ||
                hasFacets ||
                detailSections.length > 0
              );

              return (
                <div key={assetKey}>
                  <div
                    className="flex items-center gap-2 rounded-md border border-border bg-card/70 px-2 py-2 text-xs text-foreground"
                    draggable
                    onDragStart={(event) => {
                      event.dataTransfer.setData('asset-key', assetKey);
                      event.dataTransfer.setData('asset-kind', kind);
                      // Encode kind into type key so it's readable during dragover
                      // (getData() returns empty during dragover due to browser security)
                      event.dataTransfer.setData(`asset-kind:${kind}`, '');
                    }}
                  >
                    <div className="flex h-8 w-8 items-center justify-center rounded bg-muted text-muted-foreground">
                      {icon}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5 truncate">
                        <span className="truncate">{file.split('/').pop() ?? file}</span>
                        {/* M6: Source/provider badge */}
                        {sourceBadge.kind !== 'unknown' && (
                          <span
                            className={cn(
                              'inline-flex items-center rounded px-1 py-0 text-[9px] font-medium leading-tight',
                              SOURCE_BADGE_STYLES[sourceBadge.kind] ?? SOURCE_BADGE_STYLES.unknown,
                            )}
                            title={sourceBadge.detail}
                          >
                            {sourceBadge.label}
                          </span>
                        )}
                        {/* M6: Search provider match indicator */}
                        {searchProviderMatch && (
                          <span
                            className="inline-flex items-center rounded px-1 py-0 text-[9px] font-medium leading-tight bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300"
                            title={`Matched by: ${searchProviderMatch.sourceProviderLabel} (score: ${searchProviderMatch.score.toFixed(2)})`}
                          >
                            {searchProviderMatch.excerpt
                              ? searchProviderMatch.excerpt.slice(0, 30)
                              : searchProviderMatch.sourceProviderLabel}
                          </span>
                        )}
                      </div>
                      <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-muted-foreground">
                        <span>{isUsed ? 'In timeline' : 'Not used'}{isHidden ? ' · Hidden' : ''}</span>
                        {/* M6: Enrichment status indicators */}
                        {enrichmentStatus.hasEnrichment && (
                          <>
                            {enrichmentStatus.pending > 0 && (
                              <span className="inline-flex items-center gap-0.5 text-amber-600 dark:text-amber-400" title={`${enrichmentStatus.pending} pending`}>
                                <Clock className="h-3 w-3" />
                                {enrichmentStatus.pending}
                              </span>
                            )}
                            {enrichmentStatus.failed > 0 && (
                              <span className="inline-flex items-center gap-0.5 text-red-600 dark:text-red-400" title={`${enrichmentStatus.failed} failed`}>
                                <AlertTriangle className="h-3 w-3" />
                                {enrichmentStatus.failed}
                              </span>
                            )}
                            {enrichmentStatus.pending === 0 && enrichmentStatus.failed === 0 && enrichmentStatus.totalClaims > 0 && (
                              <span className="inline-flex items-center gap-0.5 text-green-600 dark:text-green-400" title={`${enrichmentStatus.totalClaims} claims`}>
                                <CheckCircle2 className="h-3 w-3" />
                                {enrichmentStatus.totalClaims}
                              </span>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                    {/* M6: Expand/collapse metadata details button */}
                    {hasMetadataDetails && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        title={isExpanded ? 'Hide metadata details' : 'Show metadata details'}
                        onClick={() => toggleExpanded(assetKey)}
                      >
                        {isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                      </Button>
                    )}
                    {entry?.generationId && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        disabled={!canOpenSource}
                        title={sourceUnavailable ? 'Source generation unavailable' : 'Open source generation'}
                        onClick={() => setLightboxAssetId(assetKey)}
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </Button>
                    )}
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-[10px] hover:bg-accent"
                      onClick={() => {
                        const nextHidden = isHidden
                          ? hidden.filter((value) => value !== assetKey)
                          : [...hidden, assetKey];
                        setPanelState({ hidden: nextHidden });
                      }}
                    >
                      {isHidden ? 'Show' : 'Hide'}
                    </Button>
                  </div>

                  {/* M6: Expanded metadata details */}
                  {isExpanded && hasMetadataDetails && (
                    <div className="ml-4 mt-1 rounded-md border border-border bg-card/50 p-2 text-[10px]">
                      {/* Host-owned provenance details */}
                      {provenanceDetail && (
                        <div className="mb-2 space-y-1">
                          <div className="font-medium text-foreground">Provenance</div>
                          <div className="space-y-0.5 text-muted-foreground">
                            {provenanceDetail.importTimestamp && (
                              <div>Imported: {new Date(provenanceDetail.importTimestamp).toLocaleString()}</div>
                            )}
                            {provenanceDetail.sourceProvider && (
                              <div>Provider: {provenanceDetail.sourceProvider}</div>
                            )}
                            {provenanceDetail.sourceUrl && (
                              <div className="truncate">Source: {provenanceDetail.sourceUrl}</div>
                            )}
                            {provenanceDetail.importedBy && (
                              <div>By: {provenanceDetail.importedBy}</div>
                            )}
                            {provenanceDetail.originalFilename && (
                              <div>File: {provenanceDetail.originalFilename}</div>
                            )}
                            {provenanceDetail.integrityHash && (
                              <div className="truncate">
                                {provenanceDetail.integrityAlgorithm}: {provenanceDetail.integrityHash.slice(0, 16)}...
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Host-owned enrichment claim details */}
                      {enrichmentClaims.length > 0 && (
                        <div className="mb-2 space-y-1">
                          <div className="font-medium text-foreground">
                            Enrichment Claims ({enrichmentClaims.length})
                            {enrichmentStatus.pending > 0 && (
                              <span className="ml-1 text-amber-600 dark:text-amber-400">· {enrichmentStatus.pending} pending</span>
                            )}
                            {enrichmentStatus.failed > 0 && (
                              <span className="ml-1 text-red-600 dark:text-red-400">· {enrichmentStatus.failed} failed</span>
                            )}
                          </div>
                          <div className="space-y-0.5">
                            {enrichmentClaims.slice(0, 5).map((claim) => (
                              <div key={claim.claimId} className="flex items-center gap-1 text-muted-foreground">
                                <span className="font-medium text-foreground">{claim.parserId}</span>
                                {claim.field && <span>→ {claim.field}</span>}
                                {claim.summary && (
                                  <span className="truncate">: {claim.summary}</span>
                                )}
                                <span className="ml-auto shrink-0 text-[9px]">
                                  {new Date(claim.timestamp).toLocaleDateString()}
                                </span>
                              </div>
                            ))}
                            {enrichmentClaims.length > 5 && (
                              <div className="text-muted-foreground">
                                +{enrichmentClaims.length - 5} more claims
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Host-owned related materials */}
                      {relatedIds.length > 0 && (
                        <div className="mb-2 space-y-1">
                          <div className="font-medium text-foreground">Related Materials</div>
                          <div className="space-y-0.5 text-muted-foreground">
                            {relatedIds.map((id) => (
                              <div key={id} className="truncate">{id}</div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Host-owned metadata facets */}
                      {hasFacets && metadataFacets.length > 0 && (
                        <div className="mb-2 space-y-1">
                          <div className="font-medium text-foreground">Metadata</div>
                          <div className="space-y-0.5 text-muted-foreground">
                            {metadataFacets.map((facet) => {
                              const facetValues = getMetadataFacetValues(entry, [facet]);
                              const value = facetValues.get(facet.id);
                              if (value === undefined) return null;
                              return (
                                <div key={facet.id} className="flex items-center gap-1">
                                  <span>{facet.displayName}:</span>
                                  <span className="font-medium text-foreground">
                                    {typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value)}
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Extension-declared asset detail sections (bounded) */}
                      {detailSections.length > 0 && (
                        <div className="space-y-1">
                          <div className="font-medium text-foreground">Extension Details</div>
                          {detailSections.map((section) => (
                            <div
                              key={section.id}
                              className={cn(
                                'rounded border px-2 py-1',
                                section.hasData
                                  ? 'border-border bg-card/70'
                                  : 'border-dashed border-muted text-muted-foreground',
                              )}
                            >
                              <div className="flex items-center gap-1">
                                <span className="font-medium text-foreground">{section.title}</span>
                                <span className="text-[9px] text-muted-foreground">
                                  ({section.extensionId})
                                </span>
                              </div>
                              {!section.hasData && (
                                <div className="text-[9px] text-muted-foreground">No data available</div>
                              )}
                              {/* Extension sections are bounded — content is rendered
                                  by the extension during activate(), not by the host.
                                  The host owns only the section container, title, and empty state. */}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
            {visibleAssets.length === 0 && (
              <div className="rounded-md border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
                {metadataSearchText
                  ? 'No assets match the current metadata search.'
                  : 'No assets match the current filters.'}
              </div>
            )}
          </div>
        </ScrollArea>
      </div>

      {lightboxAssetId && lightboxQuery?.data && (
        <mediaLightbox.Lightbox
          media={lightboxQuery.data}
          initialVariantId={lightboxAsset?.variantId ?? lightboxQuery.data.primary_variant_id ?? undefined}
          onClose={() => setLightboxAssetId(null)}
          features={{ showTaskDetails: true }}
        />
      )}
    </>
  );
}
