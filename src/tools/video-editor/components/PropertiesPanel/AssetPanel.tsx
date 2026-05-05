import { useMemo, useRef, useState } from 'react';
import { useQueries } from '@tanstack/react-query';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import { getGenerationDropData, getDragType } from '@/shared/lib/dnd/dragDrop.ts';
import { Button } from '@/shared/components/ui/button.tsx';
import { Input } from '@/shared/components/ui/input.tsx';
import { ScrollArea } from '@/shared/components/ui/scroll-area.tsx';
import { ExternalLink, Film, ImageIcon, Music2, Upload } from 'lucide-react';
import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import { useTimelineEditorOps } from '@/tools/video-editor/hooks/timelineStore.ts';
import type { ClipMeta } from '@/tools/video-editor/lib/timeline-data.ts';
import type { AssetRegistryEntry } from '@/tools/video-editor/types/index.ts';

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
}: AssetPanelProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isGenerationDragOver, setIsGenerationDragOver] = useState(false);
  const [lightboxAssetId, setLightboxAssetId] = useState<string | null>(null);
  const { mediaLightbox } = useVideoEditorRuntime();
  const { registerGenerationAsset } = useTimelineEditorOps();

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

  const visibleAssets = useMemo(() => {
    return Object.entries(assetMap).filter(([assetKey]) => {
      if (!showAll && !usedAssets.has(assetKey)) {
        return false;
      }

      if (!showHidden && hidden.includes(assetKey)) {
        return false;
      }

      return true;
    });
  }, [assetMap, hidden, showAll, showHidden, usedAssets]);

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
              const generationQuery = generationMap[assetKey];
              const canOpenSource = Boolean(entry?.generationId) && Boolean(generationQuery?.data);
              const sourceUnavailable = Boolean(entry?.generationId) && !generationQuery?.isLoading && !generationQuery?.data;
              const icon = kind === 'audio'
                ? <Music2 className="h-3.5 w-3.5" />
                : entry?.type?.startsWith('image')
                  ? <ImageIcon className="h-3.5 w-3.5" />
                  : <Film className="h-3.5 w-3.5" />;

              return (
                <div
                  key={assetKey}
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
                    <div className="truncate">{file.split('/').pop() ?? file}</div>
                    <div className="mt-0.5 text-[10px] text-muted-foreground">
                      {isUsed ? 'In timeline' : 'Not used'}{isHidden ? ' · Hidden' : ''}
                    </div>
                  </div>
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
              );
            })}
            {visibleAssets.length === 0 && (
              <div className="rounded-md border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
                No assets match the current filters.
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
