import React from 'react';
import {
  getRenderBudgetTelemetrySnapshot,
  subscribeRenderBudgetTelemetry,
  type RenderBudgetTelemetryEntry,
} from '@/shared/dev/useRenderBudget';

const OVERLAY_STORAGE_KEY = 'dev.renderTelemetryOverlay.open';

function readStoredPreference(): boolean {
  try {
    return window.localStorage.getItem(OVERLAY_STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

function writeStoredPreference(isOpen: boolean): void {
  try {
    window.localStorage.setItem(OVERLAY_STORAGE_KEY, isOpen ? '1' : '0');
  } catch {
    // Ignore persistence issues in restricted browser contexts.
  }
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }

  return target.isContentEditable || Boolean(target.closest('input, textarea, select, [contenteditable="true"]'));
}

export function RenderTelemetryOverlay(): React.ReactElement | null {
  if (!import.meta.env.DEV) {
    return null;
  }

  const [isOpen, setIsOpen] = React.useState<boolean>(() => readStoredPreference());
  const [entries, setEntries] = React.useState<RenderBudgetTelemetryEntry[]>(
    () => getRenderBudgetTelemetrySnapshot(),
  );

  React.useEffect(() => {
    const unsubscribe = subscribeRenderBudgetTelemetry(() => {
      setEntries(getRenderBudgetTelemetrySnapshot());
    });

    return unsubscribe;
  }, []);

  React.useEffect(() => {
    writeStoredPreference(isOpen);
  }, [isOpen]);

  React.useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (isEditableTarget(event.target)) {
        return;
      }

      if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === 'y') {
        event.preventDefault();
        setIsOpen((previous) => !previous);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  if (!isOpen) {
    return null;
  }

  return (
    <aside className="fixed bottom-4 right-4 z-[120000] flex w-[22rem] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-lg border border-border bg-background/95 text-foreground shadow-2xl backdrop-blur">
      <header className="flex items-center justify-between border-b border-border px-3 py-2">
        <h2 className="text-xs font-semibold tracking-wide">Render Telemetry</h2>
        <span className="text-[10px] text-muted-foreground">Cmd/Ctrl+Shift+Y</span>
      </header>
      <div className="max-h-[50vh] overflow-y-auto p-2">
        {entries.length === 0 ? (
          <p className="px-2 py-3 text-xs text-muted-foreground">No render telemetry captured yet.</p>
        ) : (
          <ul className="space-y-1">
            {entries.map((entry) => (
              <li
                key={entry.name}
                className="rounded-md border border-border/60 bg-card/80 px-2 py-1.5 text-xs"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-medium">{entry.name}</span>
                  <span
                    className={
                      entry.status === 'over'
                        ? 'shrink-0 font-semibold text-destructive'
                        : 'shrink-0 font-semibold text-[hsl(var(--chart-2))]'
                    }
                  >
                    {entry.status === 'over' ? 'OVER' : 'UNDER'}
                  </span>
                </div>
                <div className="mt-1 flex items-center justify-between text-[11px] text-muted-foreground">
                  <span>{entry.maxCount} renders</span>
                  <span>budget {entry.budget}</span>
                  <span>{entry.mounts} mounts</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
