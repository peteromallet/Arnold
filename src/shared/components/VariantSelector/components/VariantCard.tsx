/**
 * VariantCard Component
 *
 * Renders an individual variant thumbnail with:
 * - Clickable thumbnail with status rings (active, primary, parent, child)
 * - NEW badge or time-ago indicator
 * - Desktop: Info button in bottom-right corner (appears on card hover) with HoverCard showing
 *   full details and actions (Make Primary, Load Settings, Delete, Copy ID, Lineage GIF)
 * - Mobile: plain button (info shown via MobileInfoModal on re-tap)
 */

import React, { useState } from 'react';
import { Check, ArrowDown, ArrowUp, Info, Loader2, Trash2, GitBranch, Star, Download, Image } from 'lucide-react';
import { cn } from '@/shared/components/ui/contracts/cn';
import { Button } from '@/shared/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { HoverCard, HoverCardTrigger, HoverCardContent } from '@/shared/components/ui/hover-card';
import type { GenerationVariant } from '@/shared/hooks/variants/useVariants';
import { getVariantIcon, getVariantLabel, isNewVariant, getTimeAgo, hasLoadableSettings } from '../variantPresentation';
import { hasDifferentSourceImages } from '../variantSourceImages';
import { VariantDetails } from './VariantDetails';
import type { VariantCardSharedProps } from './variantCardSharedTypes';

// --- VariantCard ---

interface VariantCardProps extends VariantCardSharedProps {
  variant: GenerationVariant;
  isActive: boolean;
  isPrimary: boolean;
  isParent: boolean;
  isChild: boolean;
  /** Lineage depth for this variant (show GIF button when >= 5) */
  lineageDepth: number;
  /** Whether a delete operation is loading for this variant */
  isDeleteLoading: boolean;
}

export const VariantCard: React.FC<VariantCardProps> = ({
  variant,
  isActive,
  isPrimary,
  isParent,
  isChild,
  activeVariantId,
  isMobile,
  readOnly,
  availableLoras,
  lineageDepth,
  isDeleteLoading,
  copiedVariantId,
  loadedSettingsVariantId,
  onVariantSelect,
  onMakePrimary,
  onDeleteVariant,
  onLoadVariantSettings,
  onToggleStar,
  onMouseEnter,
  onShowMobileInfo,
  onShowLineageGif,
  onCopyId,
  onLoadSettings,
  onLoadImages,
  currentSegmentImages,
  loadedImagesVariantId,
}) => {
  const [infoOpen, setInfoOpen] = useState(false);
  const Icon = getVariantIcon(variant.variant_type);
  const label = getVariantLabel(variant);

  const buttonContent = (
    <div
      role="button"
      tabIndex={0}
      onClick={(e) => {
        e.stopPropagation();
        if (isMobile && isActive) {
          onShowMobileInfo(variant.id);
          return;
        }
        onVariantSelect(variant.id);
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onVariantSelect(variant.id);
        }
      }}
      onTouchEnd={(e) => {
        if (isMobile) {
          e.stopPropagation();
          if (isActive) {
            onShowMobileInfo(variant.id);
            return;
          }
          onVariantSelect(variant.id);
        }
      }}
      onMouseEnter={() => onMouseEnter(variant)}
      className={cn(
        'relative p-0.5 rounded transition-all w-full touch-manipulation group/variant overflow-hidden cursor-pointer',
        'hover:bg-muted/80',
        isPrimary && !isActive && 'ring-2 ring-green-500 bg-green-500/10',
        isActive
          ? 'ring-2 ring-orange-500 bg-orange-500/10'
          : 'opacity-70 hover:opacity-100',
        isParent && !isActive && !isPrimary && 'ring-1 ring-blue-500/50',
        isChild && !isActive && !isPrimary && 'ring-1 ring-purple-500/50'
      )}
    >
      {/* Thumbnail */}
      <div className="relative w-full rounded overflow-hidden bg-muted" style={{ paddingBottom: '56.25%' }}>
        {(variant.thumbnail_url || variant.location) ? (
          <img
            src={variant.thumbnail_url || variant.location}
            alt={label}
            className="absolute inset-0 w-full h-full object-cover pointer-events-none"
          />
        ) : (
          <div className="absolute inset-0 w-full h-full flex items-center justify-center">
            <Icon className="w-4 h-4 text-muted-foreground" />
          </div>
        )}

        {/* Top-right: primary badge first, then relationship badges */}
        <div className="absolute top-0.5 right-0.5 flex items-center gap-0.5 pointer-events-auto">
          {/* Primary/make-main button - leftmost */}
          {!readOnly && onMakePrimary ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <div
                  className={cn(
                    'rounded-full p-0.5 transition-opacity',
                    isPrimary
                      ? 'opacity-100 bg-green-500/80 cursor-default'
                      : 'opacity-0 group-hover/variant:opacity-100 bg-black/50 hover:bg-black/70 cursor-pointer'
                  )}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (!isPrimary) {
                      onVariantSelect(variant.id);
                      onMakePrimary(variant.id);
                    }
                  }}
                >
                  <Check className="w-2 h-2 text-white" />
                </div>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="text-xs">
                {isPrimary ? 'Main variant' : 'Set as main'}
              </TooltipContent>
            </Tooltip>
          ) : isPrimary ? (
            <div className="bg-green-500 rounded-full p-0.5 pointer-events-none">
              <Check className="w-2 h-2 text-white" />
            </div>
          ) : null}

          {/* Parent relationship badge */}
          {isParent && !isActive && (
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="bg-blue-500 rounded-full p-0.5 cursor-default">
                  <ArrowUp className="w-2 h-2 text-white" />
                </div>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="text-xs">
                Current variant is based on this one
              </TooltipContent>
            </Tooltip>
          )}

          {/* Child relationship badge */}
          {isChild && !isActive && (
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="bg-purple-500 rounded-full p-0.5 cursor-default">
                  <ArrowDown className="w-2 h-2 text-white" />
                </div>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="text-xs">
                Based on the current variant
              </TooltipContent>
            </Tooltip>
          )}
        </div>

        {/* Top-left: star button */}
        {onToggleStar && (
          <div
            className={cn(
              'absolute top-0.5 left-0.5 rounded-full p-0.5 transition-opacity cursor-pointer pointer-events-auto',
              variant.starred
                ? 'opacity-100 bg-yellow-500/80'
                : 'opacity-0 group-hover/variant:opacity-100 bg-black/50 hover:bg-black/70'
            )}
            onClick={(e) => {
              e.stopPropagation();
              onToggleStar(variant.id, !variant.starred);
            }}
          >
            <Star className={cn('w-2 h-2', variant.starred ? 'text-white fill-white' : 'text-white')} />
          </div>
        )}

        {/* Bottom-left: NEW badge or time ago */}
        {isNewVariant(variant, activeVariantId) ? (
          <div className="absolute bottom-0.5 left-0.5 bg-yellow-500 text-black text-[8px] font-bold px-1 rounded pointer-events-none">
            NEW
          </div>
        ) : (
          <div className="absolute bottom-0.5 left-0.5 bg-black/70 text-white text-[8px] px-1 rounded pointer-events-none">
            {getTimeAgo(variant.created_at)}
          </div>
        )}

        {/* Info button - bottom right, shows on hover (desktop only) */}
        {!isMobile && (
          <div className="absolute bottom-0.5 right-0.5 opacity-0 group-hover/variant:opacity-100 transition-opacity pointer-events-auto">
            <HoverCard
              open={infoOpen}
              onOpenChange={setInfoOpen}
            >
              <HoverCardTrigger asChild>
                <div
                  className="h-5 w-5 rounded-full bg-black/50 flex items-center justify-center cursor-pointer hover:bg-black/70"
                  onClick={(e) => {
                    e.stopPropagation();
                    setInfoOpen(true);
                  }}
                >
                  <Info className="h-3 w-3 text-white" strokeWidth={2.5} />
                </div>
              </HoverCardTrigger>
              <HoverCardContent
                side="top"
                align="end"
                usePortal
                className="max-w-md p-0 w-auto"
                sideOffset={4}
              >
                <div className="flex flex-col max-h-[85vh]">
                  {/* Header - pinned at top */}
                  <div className="flex items-center justify-between gap-2 p-2 pb-1.5 shrink-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-sm">{label}</p>
                      {isPrimary && (
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-green-500/20 text-green-400 border border-green-500/30">
                          Primary
                        </span>
                      )}
                      {isActive && !isPrimary && (
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-orange-500/20 text-orange-400 border border-orange-500/30">
                          Viewing
                        </span>
                      )}
                      {isParent && (
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-blue-500/20 text-blue-400 border border-blue-500/30">
                          Parent of current
                        </span>
                      )}
                      {isChild && (
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-purple-500/20 text-purple-400 border border-purple-500/30">
                          Child of current
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-0.5">
                      {/* Copy ID button */}
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onCopyId(variant.id);
                            }}
                            className={cn(
                              "px-1.5 py-0.5 rounded text-[10px] transition-all duration-150",
                              copiedVariantId === variant.id
                                ? "text-green-400 bg-green-400/10"
                                : "text-muted-foreground hover:text-foreground hover:bg-muted/80 active:scale-95"
                            )}
                          >
                            {copiedVariantId === variant.id ? 'copied' : 'id'}
                          </button>
                        </TooltipTrigger>
                        <TooltipContent side="bottom" className="text-xs">
                          Copy ID
                        </TooltipContent>
                      </Tooltip>
                      {/* Lineage GIF button */}
                      {lineageDepth >= 5 && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onShowLineageGif(variant.id);
                              }}
                              className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted/80 transition-all duration-150 active:scale-95 animate-in fade-in slide-in-from-left-1 duration-300"
                            >
                              <GitBranch className="w-3.5 h-3.5" />
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="bottom" className="text-xs">
                            View evolution ({lineageDepth} generations)
                          </TooltipContent>
                        </Tooltip>
                      )}
                      {/* Delete button */}
                      {!readOnly && onDeleteVariant && !isPrimary && variant.variant_type !== 'original' && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onDeleteVariant(variant.id);
                              }}
                              disabled={isDeleteLoading}
                              className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-all duration-150 active:scale-95 disabled:opacity-50"
                            >
                              {isDeleteLoading ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <Trash2 className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="bottom" className="text-xs">
                            Delete
                          </TooltipContent>
                        </Tooltip>
                      )}
                    </div>
                  </div>

                  {/* Scrollable area: task details only */}
                  {variant.params && (
                    <div className="relative min-h-0 flex-1">
                      <div
                        className="px-2 pb-2 overflow-y-auto max-h-[calc(85vh-5rem)]"
                        onScroll={(e) => {
                          const el = e.currentTarget;
                          const fade = el.nextElementSibling as HTMLElement | null;
                          if (fade) {
                            const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 8;
                            fade.style.opacity = isAtBottom ? '0' : '1';
                          }
                        }}
                        ref={(el) => {
                          if (!el) return;
                          const fade = el.nextElementSibling as HTMLElement | null;
                          if (fade) {
                            const isScrollable = el.scrollHeight > el.clientHeight;
                            fade.style.opacity = isScrollable ? '1' : '0';
                          }
                        }}
                      >
                        <div className="border-t border-border/50 pt-2">
                          <VariantDetails
                            variant={variant}
                            availableLoras={availableLoras}
                          />
                        </div>
                      </div>
                      <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-popover to-transparent transition-opacity duration-150" />
                    </div>
                  )}

                  {/* Action buttons row - pinned at bottom */}
                  {!readOnly && ((!isPrimary && onMakePrimary) || (onLoadVariantSettings && hasLoadableSettings(variant)) || (onLoadImages && hasDifferentSourceImages(variant, currentSegmentImages))) && (
                    <div className="flex flex-wrap gap-1.5 px-2 py-1.5 border-t border-border/50 shrink-0">
                      {!isPrimary && onMakePrimary && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            onVariantSelect(variant.id);
                            setTimeout(() => onMakePrimary(variant.id), 50);
                          }}
                          className="h-6 text-xs gap-1 flex-1"
                        >
                          <Star className="w-3 h-3" />
                          Make Primary
                        </Button>
                      )}
                      {onLoadVariantSettings && hasLoadableSettings(variant) && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            onLoadSettings(variant);
                          }}
                          className={cn(
                            "h-6 text-xs gap-1 flex-1",
                            loadedSettingsVariantId === variant.id && "bg-green-500/20 border-green-500/50 text-green-400"
                          )}
                        >
                          {loadedSettingsVariantId === variant.id ? (
                            <>
                              <Check className="w-3 h-3" />
                              Loaded!
                            </>
                          ) : (
                            <>
                              <Download className="w-3 h-3" />
                              Load Settings
                            </>
                          )}
                        </Button>
                      )}
                      {onLoadImages && hasDifferentSourceImages(variant, currentSegmentImages) && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            onLoadImages(variant);
                          }}
                          className={cn(
                            "h-6 text-xs gap-1 flex-1",
                            loadedImagesVariantId === variant.id && "bg-green-500/20 border-green-500/50 text-green-400"
                          )}
                        >
                          {loadedImagesVariantId === variant.id ? (
                            <>
                              <Check className="w-3 h-3" />
                              Loaded!
                            </>
                          ) : (
                            <>
                              <Image className="w-3 h-3" />
                              Load Images
                            </>
                          )}
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              </HoverCardContent>
            </HoverCard>
          </div>
        )}
      </div>
    </div>
  );

  // Both mobile and desktop now render the same buttonContent
  // Desktop has the info button inside with tooltip on hover
  return <React.Fragment key={variant.id}>{buttonContent}</React.Fragment>;
};
