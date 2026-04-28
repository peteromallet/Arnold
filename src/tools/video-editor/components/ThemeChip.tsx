import { useMemo, useState, type FC } from 'react';
import { resolveTheme, type ThemeRegistry } from '@banodoco/timeline-schema';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Badge } from '@/shared/components/ui/badge';
import { cn } from '@/shared/components/ui/contracts/cn';
import type { TimelineConfig } from '@/tools/video-editor/types';

/**
 * Read-only Theme chip (SD-018, SD-019). Renders:
 *
 *   - `Theme: <id>` when the timeline has a theme and the theme registry
 *     contains it.
 *   - `Theme: <id> (not installed)` when a theme slug is set but no
 *     `@banodoco/timeline-theme-<id>` peer-dep is registered.
 *   - Nothing when `timeline.theme` is undefined.
 *
 * Click expands a JSON view of the resolved theme (overrides + base when
 * installed; raw `theme_overrides` only when not installed). NO picker, NO
 * edit form, NO theme switching — those are agent-via-chat surfaces only
 * (SD-018).
 *
 * Sprint 3 ships an empty registry; the not-installed branch is the live
 * one. Sprint 5 wires `@banodoco/timeline-theme-<id>` peer-dep packages.
 */

interface ThemeChipProps {
  timeline: Pick<TimelineConfig, 'theme' | 'theme_overrides'> | null | undefined;
  /**
   * Theme registry. Sprint 3 default is empty — when Sprint 5 ships
   * `@banodoco/timeline-theme-<id>` peer-deps, the host will pass them in
   * here.
   */
  registry?: ThemeRegistry;
  className?: string;
}

const EMPTY_REGISTRY: ThemeRegistry = {};

interface ResolvedView {
  installed: boolean;
  json: string;
  fallbackMessage?: string;
}

function resolveView(
  themeId: string,
  themeOverrides: TimelineConfig['theme_overrides'],
  registry: ThemeRegistry,
): ResolvedView {
  const installed = Object.prototype.hasOwnProperty.call(registry, themeId);
  if (!installed) {
    if (themeOverrides && Object.keys(themeOverrides).length > 0) {
      return {
        installed: false,
        json: JSON.stringify({ theme: themeId, theme_overrides: themeOverrides }, null, 2),
      };
    }
    return {
      installed: false,
      json: '',
      fallbackMessage: `No theme data available — install @banodoco/timeline-theme-${themeId}.`,
    };
  }
  try {
    const merged = resolveTheme({ theme: themeId, theme_overrides: themeOverrides ?? undefined }, registry);
    return { installed: true, json: JSON.stringify(merged, null, 2) };
  } catch (err) {
    return {
      installed: true,
      json: '',
      fallbackMessage: `Failed to resolve theme: ${(err as Error).message}`,
    };
  }
}

export const ThemeChip: FC<ThemeChipProps> = ({ timeline, registry = EMPTY_REGISTRY, className }) => {
  const [isOpen, setIsOpen] = useState(false);
  const themeId = timeline?.theme;
  const themeOverrides = timeline?.theme_overrides;

  const view = useMemo<ResolvedView | null>(() => {
    if (typeof themeId !== 'string' || themeId.length === 0) {
      return null;
    }
    return resolveView(themeId, themeOverrides, registry);
  }, [themeId, themeOverrides, registry]);

  if (!view || typeof themeId !== 'string' || themeId.length === 0) {
    return null;
  }

  const label = view.installed ? `Theme: ${themeId}` : `Theme: ${themeId} (not installed)`;

  return (
    <>
      <button
        type="button"
        data-testid="theme-chip"
        data-theme-id={themeId}
        data-theme-installed={view.installed ? 'true' : 'false'}
        onClick={() => setIsOpen(true)}
        className={cn(
          'pointer-events-auto inline-flex items-center gap-1 rounded bg-background/70 px-1.5 py-0.5 font-mono text-[11px] tracking-[0.08em] backdrop-blur-sm transition-colors hover:bg-background/85 motion-reduce:transition-none',
          view.installed ? 'text-muted-foreground' : 'text-amber-200',
          className,
        )}
        title={view.installed ? `Click to view resolved theme JSON` : `Theme '${themeId}' is not installed in this build`}
      >
        <span>{label}</span>
        {!view.installed && (
          <Badge variant="outline" className="ml-1 h-4 px-1 py-0 text-[9px] uppercase tracking-[0.12em]">
            stub
          </Badge>
        )}
      </button>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="font-mono text-sm">{label}</DialogTitle>
            <DialogDescription>
              Read-only resolved theme view. Theme switching happens via the agent chat (SD-018).
            </DialogDescription>
          </DialogHeader>
          {view.fallbackMessage ? (
            <div className="rounded border border-border/50 bg-muted/40 p-3 text-xs text-muted-foreground">
              {view.fallbackMessage}
            </div>
          ) : (
            <pre
              data-testid="theme-chip-json"
              className="max-h-[60vh] overflow-auto rounded border border-border/50 bg-muted/40 p-3 font-mono text-[11px] leading-relaxed"
            >
              {view.json}
            </pre>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
};
