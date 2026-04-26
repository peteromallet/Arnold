import React, { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Loader2, Plus } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { cn } from '@/shared/components/ui/contracts/cn';
import { useVariants, type GenerationVariant } from '@/shared/hooks/variants/useVariants';
import { hasVideoExtension } from '@/shared/lib/typeGuards';

const PAGE_SIZE = 9;

interface MediaVariantPickerProps {
  generationId: string;
  /** Variant id of the asset's currently-displayed variant (highlighted in grid). */
  currentVariantId?: string | null;
  /** Called after the user clicks a variant. The picker has already set it as primary in DB. */
  onVariantApplied?: (variant: GenerationVariant) => void | Promise<void>;
  /** Optional: clone the variant into a new generation and place it after the source clip. */
  onAddVariantAsGeneration?: (variant: GenerationVariant) => void | Promise<void>;
  /** Whether a specific variant's add-as-generation action is currently in flight. */
  isAddingVariantAsGeneration?: (variantId: string) => boolean;
  /** Override badge styling/positioning. Default is an absolute pill anchored top-right. */
  className?: string;
  /** Stop the trigger badge from absolute-positioning (use inline in a flex row). */
  inline?: boolean;
  /** Optional hint to render thumbnails as videos when no thumbnail_url is present. */
  defaultMediaKind?: 'image' | 'video';
}

function isVideoVariant(variant: GenerationVariant, defaultKind?: 'image' | 'video'): boolean {
  if (variant.thumbnail_url) return false;
  if (hasVideoExtension(variant.location)) return true;
  return defaultKind === 'video';
}

export const MediaVariantPicker: React.FC<MediaVariantPickerProps> = ({
  generationId,
  currentVariantId,
  onVariantApplied,
  onAddVariantAsGeneration,
  isAddingVariantAsGeneration,
  className,
  inline = false,
  defaultMediaKind,
}) => {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(0);
  const { variants, setPrimaryVariant } = useVariants({ generationId });

  const totalPages = useMemo(() => Math.ceil(variants.length / PAGE_SIZE), [variants.length]);
  const pagedVariants = useMemo(
    () => variants.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE),
    [variants, page],
  );

  if (variants.length <= 1) {
    return null;
  }

  const handleVariantClick = async (variant: GenerationVariant) => {
    setOpen(false);
    await onVariantApplied?.(variant);
    await setPrimaryVariant(variant.id);
  };

  const tooltip = `Click to see ${variants.length} variant${variants.length === 1 ? '' : 's'}`;

  return (
    <Popover open={open} onOpenChange={(next) => { setOpen(next); if (!next) setPage(0); }}>
      <PopoverTrigger asChild>
        <span
          role="button"
          tabIndex={0}
          className={cn(
            'z-10 inline-flex min-w-[1.1rem] items-center justify-center rounded-full bg-black/40 px-1.5 text-[10px] font-medium leading-none text-white/80 backdrop-blur-sm transition-colors hover:bg-black/70 hover:text-white cursor-pointer',
            !inline && 'absolute top-0.5 right-1',
            className,
          )}
          style={{ height: '1rem' }}
          onClick={(e) => { e.stopPropagation(); }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              e.stopPropagation();
              setOpen((v) => !v);
            }
          }}
          aria-label={tooltip}
          title={tooltip}
        >
          {variants.length}
        </span>
      </PopoverTrigger>
      <PopoverContent
        side="bottom"
        align="end"
        sideOffset={6}
        className="w-72 p-2"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="grid grid-cols-3 gap-2">
          {pagedVariants.map((variant) => {
            const previewUrl = variant.thumbnail_url || variant.location;
            if (!previewUrl) return null;

            const isPrimary = variant.is_primary;
            const isCurrent = currentVariantId === variant.id;
            const showAsVideo = isVideoVariant(variant, defaultMediaKind);

            const isAdding = isAddingVariantAsGeneration?.(variant.id) ?? false;

            const tileTooltip = isPrimary ? 'Primary variant' : 'Make primary';
            const addTooltip = isAdding ? 'Adding…' : 'Add as new generation';

            return (
              <div key={variant.id} className="relative">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      className={cn(
                        'group relative block aspect-video w-full overflow-hidden rounded-md bg-muted transition-opacity hover:opacity-100',
                        isPrimary && 'ring-2 ring-green-500',
                        !isPrimary && isCurrent && 'ring-1 ring-border',
                      )}
                      onClick={(e) => {
                        e.stopPropagation();
                        void handleVariantClick(variant);
                      }}
                      aria-label={tileTooltip}
                    >
                      {showAsVideo ? (
                        <video
                          src={previewUrl}
                          className="h-full w-full object-cover"
                          muted
                          playsInline
                          preload="metadata"
                        />
                      ) : (
                        <img
                          src={previewUrl}
                          alt={variant.name ?? 'Variant thumbnail'}
                          className="h-full w-full object-cover"
                        />
                      )}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="max-w-[14rem] text-xs">
                    {tileTooltip}
                  </TooltipContent>
                </Tooltip>
                {onAddVariantAsGeneration && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        disabled={isAdding}
                        onClick={(e) => {
                          e.stopPropagation();
                          void onAddVariantAsGeneration(variant);
                        }}
                        aria-label={addTooltip}
                        className={cn(
                          'absolute bottom-1 right-1 z-10 flex h-5 w-5 items-center justify-center rounded-full bg-black/60 text-white/90 backdrop-blur-sm transition-colors hover:bg-black/85 hover:text-white disabled:cursor-wait disabled:opacity-60',
                        )}
                      >
                        {isAdding ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <Plus className="h-3 w-3" />
                        )}
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-[14rem] text-xs">
                      {addTooltip}
                    </TooltipContent>
                  </Tooltip>
                )}
              </div>
            );
          })}
        </div>

        {totalPages > 1 && (
          <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
            <button
              type="button"
              disabled={page === 0}
              onClick={(e) => { e.stopPropagation(); setPage((p) => p - 1); }}
              className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 hover:bg-muted disabled:opacity-30"
            >
              <ChevronLeft className="h-3 w-3" />
              Prev
            </button>
            <span>{page + 1} / {totalPages}</span>
            <button
              type="button"
              disabled={page >= totalPages - 1}
              onClick={(e) => { e.stopPropagation(); setPage((p) => p + 1); }}
              className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 hover:bg-muted disabled:opacity-30"
            >
              Next
              <ChevronRight className="h-3 w-3" />
            </button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
};
