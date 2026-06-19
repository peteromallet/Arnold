import { useCallback, useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandShortcut,
} from '@/shared/components/ui/command.tsx';
import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import type { CommandEntry, CommandRunStatus } from '@/tools/video-editor/runtime/commandRegistry.ts';

export interface CommandPaletteProps {
  /** Whether the palette is open. */
  open: boolean;
  /** Called when the palette open state changes (e.g. Escape close, item select). */
  onOpenChange: (open: boolean) => void;
}

interface CommandPaletteItem {
  entry: CommandEntry;
  /** Normalized keybinding bound to this command, if any. */
  keybinding: string | null;
  /** Last-run status from the registry. */
  status: CommandRunStatus;
  /** True when the handler has been registered (not just the contribution). */
  hasHandler: boolean;
}

/**
 * Group commands by category. Commands without a category are placed under
 * a default "Other" heading when there is at least one categorized command;
 * otherwise they appear without a group label.
 */
function groupCommands(items: CommandPaletteItem[]): Map<string, CommandPaletteItem[]> {
  const grouped = new Map<string, CommandPaletteItem[]>();
  for (const item of items) {
    const category = item.entry.category || '__ungrouped__';
    let group = grouped.get(category);
    if (!group) {
      group = [];
      grouped.set(category, group);
    }
    group.push(item);
  }
  return grouped;
}

function formatKeybinding(key: string): string {
  return key
    .replace(/ctrlOrCmd/g, navigator.platform.includes('Mac') ? '⌘' : 'Ctrl')
    .replace(/ctrl/g, 'Ctrl')
    .replace(/alt/g, 'Alt')
    .replace(/shift/g, 'Shift')
    .replace(/\+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const runtime = useVideoEditorRuntime();
  const commandRegistry = runtime.commandRegistry;
  const [search, setSearch] = useState('');

  // Build the full command list from the registry snapshot
  const allItems = useMemo<CommandPaletteItem[]>(() => {
    if (!commandRegistry) return [];

    const snapshot = commandRegistry.getSnapshot();
    const commands = snapshot.commands;

    return commands.map((entry) => {
      // Find any keybinding bound to this command
      const kb = snapshot.keybindings.find((k) => k.commandId === entry.commandId);
      const status = snapshot.getStatus(entry.commandId);
      // A command has a handler when getCommand returns it AND the internal
      // handler is non-null. We use executeCommand's behavior: if there's no
      // handler, it will emit invoke-no-handler. But we can't directly check
      // handler presence from the snapshot. We'll infer: a command is enabled
      // if getCommand finds it and the registry has a handler registered.
      // For now, we use the status: commands that have never been run AND
      // have no keybinding are likely disabled, but that's heuristic.
      // Better: commands are always visible in palette; handler-presence is
      // only validated on invocation. The registry emits diagnostics when
      // a handler is missing. We show all commands and let the registry
      // surface errors on invocation.
      const hasHandler = true; // Will be validated on execute; show all as available
      return {
        entry,
        keybinding: kb?.key ?? null,
        status,
        hasHandler,
      };
    });
  }, [commandRegistry]);

  // Filter items by search query
  const filteredItems = useMemo(() => {
    if (!search.trim()) return allItems;
    const q = search.toLowerCase();
    return allItems.filter(
      (item) =>
        item.entry.label.toLowerCase().includes(q) ||
        item.entry.commandId.toLowerCase().includes(q) ||
        (item.entry.category?.toLowerCase().includes(q) ?? false) ||
        (item.keybinding?.toLowerCase().includes(q) ?? false),
    );
  }, [allItems, search]);

  // Group filtered items
  const grouped = useMemo(() => groupCommands(filteredItems), [filteredItems]);
  const hasCategorizedItems = grouped.size > 1 || !grouped.has('__ungrouped__');

  // Invoke a command through the central registry
  const handleSelect = useCallback(
    (commandId: string) => {
      if (!commandRegistry) return;
      void commandRegistry.executeCommand(commandId);
      onOpenChange(false);
    },
    [commandRegistry, onOpenChange],
  );

  // Whether to show "No commands found"
  const isEmpty = filteredItems.length === 0;
  const showSearch = allItems.length > 0;

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      {showSearch && (
        <CommandInput
          placeholder="Type a command…"
          value={search}
          onValueChange={setSearch}
        />
      )}

      <CommandList>
        {isEmpty && (
          <CommandEmpty>
            {allItems.length === 0
              ? 'No commands registered. Extensions contribute commands when activated.'
              : 'No matching commands.'}
          </CommandEmpty>
        )}

        {!isEmpty &&
          Array.from(grouped.entries()).map(([category, items]) => {
            const label =
              category === '__ungrouped__'
                ? hasCategorizedItems
                  ? 'Other'
                  : undefined
                : category;

            return (
              <CommandGroup key={category} heading={label}>
                {items.map((item) => {
                  const statusText = item.status.lastRunOk === false
                    ? `⚠ ${item.status.lastError ?? 'Last run failed'}`
                    : item.status.invocationCount > 0
                      ? `✓ Run ${item.status.invocationCount} time${item.status.invocationCount === 1 ? '' : 's'}`
                      : undefined;

                  return (
                    <CommandItem
                      key={item.entry.commandId}
                      value={item.entry.commandId}
                      onSelect={() => handleSelect(item.entry.commandId)}
                      data-command-palette-item="true"
                      data-command-id={item.entry.commandId}
                      data-extension-id={item.entry.extensionId}
                    >
                      <div className="flex flex-1 items-center gap-2 overflow-hidden">
                        <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50" />
                        <span className="truncate">{item.entry.label}</span>
                        {statusText && (
                          <span className="ml-1 shrink-0 text-[10px] text-muted-foreground/60">
                            {statusText}
                          </span>
                        )}
                      </div>
                      {item.keybinding && (
                        <CommandShortcut>
                          {formatKeybinding(item.keybinding)}
                        </CommandShortcut>
                      )}
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            );
          })}
      </CommandList>

      {/* Footer with hint */}
      {!isEmpty && (
        <div className="border-t border-border px-3 py-2 text-[10px] text-muted-foreground/70">
          <kbd className="rounded border border-border px-1 py-0.5 font-mono text-[10px]">Enter</kbd>{' '}
          to invoke ·{' '}
          <kbd className="rounded border border-border px-1 py-0.5 font-mono text-[10px]">Esc</kbd>{' '}
          to close ·{' '}
          <kbd className="rounded border border-border px-1 py-0.5 font-mono text-[10px]">↑↓</kbd>{' '}
          to navigate
        </div>
      )}
    </CommandDialog>
  );
}

export default CommandPalette;
