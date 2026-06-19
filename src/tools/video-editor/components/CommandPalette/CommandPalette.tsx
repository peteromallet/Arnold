import { useCallback, useMemo, useState } from 'react';
import { Search, Wrench } from 'lucide-react';
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
import type { AgentToolEntry, AgentToolRunStatus } from '@/tools/video-editor/runtime/agentToolRegistry.ts';

export interface CommandPaletteProps {
  /** Whether the palette is open. */
  open: boolean;
  /** Called when the palette open state changes (e.g. Escape close, item select). */
  onOpenChange: (open: boolean) => void;
}

/** Discriminated union: a palette item is either a command or an agent tool. */
type PaletteItemKind = 'command' | 'agentTool';

interface CommandPaletteCommandItem {
  kind: 'command';
  entry: CommandEntry;
  /** Normalized keybinding bound to this command, if any. */
  keybinding: string | null;
  /** Last-run status from the registry. */
  status: CommandRunStatus;
  /** True when the handler has been registered (not just the contribution). */
  hasHandler: boolean;
}

interface CommandPaletteAgentToolItem {
  kind: 'agentTool';
  entry: AgentToolEntry;
  /** Last-run status from the agent tool registry. */
  status: AgentToolRunStatus;
}

type CommandPaletteItem = CommandPaletteCommandItem | CommandPaletteAgentToolItem;

/**
 * Group items by category. Commands without a category are placed under
 * a default "Other" heading when there is at least one categorized command;
 * otherwise they appear without a group label. Agent tools always appear
 * under "Agent Tools".
 */
function groupCommands(items: CommandPaletteItem[]): Map<string, CommandPaletteItem[]> {
  const grouped = new Map<string, CommandPaletteItem[]>();
  for (const item of items) {
    let category: string;
    if (item.kind === 'agentTool') {
      category = 'Agent Tools';
    } else {
      category = item.entry.category || '__ungrouped__';
    }
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
  const agentToolRegistry = runtime.agentToolRegistry;
  const [search, setSearch] = useState('');

  // Build the full item list from command registry + agent tool registry snapshots
  const allItems = useMemo<CommandPaletteItem[]>(() => {
    const items: CommandPaletteItem[] = [];

    // ---- Commands --------------------------------------------------------
    if (commandRegistry) {
      const snapshot = commandRegistry.getSnapshot();
      const commands = snapshot.commands;

      for (const entry of commands) {
        const kb = snapshot.keybindings.find((k) => k.commandId === entry.commandId);
        const status = snapshot.getStatus(entry.commandId);
        const hasHandler = true; // Validated on invocation; show all as available
        items.push({
          kind: 'command',
          entry,
          keybinding: kb?.key ?? null,
          status,
          hasHandler,
        });
      }
    }

    // ---- Agent Tools -----------------------------------------------------
    if (agentToolRegistry) {
      const toolSnapshot = agentToolRegistry.getSnapshot();
      for (const toolEntry of toolSnapshot.tools) {
        const toolStatus = toolSnapshot.getStatus(toolEntry.toolId);
        items.push({
          kind: 'agentTool',
          entry: toolEntry,
          status: toolStatus,
        });
      }
    }

    return items;
  }, [commandRegistry, agentToolRegistry]);

  // Filter items by search query
  const filteredItems = useMemo(() => {
    if (!search.trim()) return allItems;
    const q = search.toLowerCase();
    return allItems.filter((item) => {
      if (item.kind === 'agentTool') {
        return (
          item.entry.label.toLowerCase().includes(q) ||
          item.entry.toolId.toLowerCase().includes(q) ||
          (item.entry.description?.toLowerCase().includes(q) ?? false) ||
          item.entry.extensionId.toLowerCase().includes(q) ||
          item.entry.resultFamilies.some((f) => f.toLowerCase().includes(q))
        );
      }
      return (
        item.entry.label.toLowerCase().includes(q) ||
        item.entry.commandId.toLowerCase().includes(q) ||
        (item.entry.category?.toLowerCase().includes(q) ?? false) ||
        (item.keybinding?.toLowerCase().includes(q) ?? false)
      );
    });
  }, [allItems, search]);

  // Group filtered items
  const grouped = useMemo(() => groupCommands(filteredItems), [filteredItems]);
  const hasCategorizedItems = grouped.size > 1 || !grouped.has('__ungrouped__');

  // Invoke a command or agent tool through the appropriate registry
  const handleSelect = useCallback(
    (item: CommandPaletteItem) => {
      if (item.kind === 'agentTool') {
        if (!agentToolRegistry) return;
        void agentToolRegistry.invokeTool({
          toolId: item.entry.toolId,
          extensionId: item.entry.extensionId,
          contributionId: item.entry.contributionId,
        });
        onOpenChange(false);
      } else {
        if (!commandRegistry) return;
        void commandRegistry.executeCommand(item.entry.commandId);
        onOpenChange(false);
      }
    },
    [commandRegistry, agentToolRegistry, onOpenChange],
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
              ? 'No commands or agent tools registered. Extensions contribute commands and agent tools when activated.'
              : 'No matching commands or agent tools.'}
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
                  const isAgentTool = item.kind === 'agentTool';

                  // Status text
                  let statusText: string | undefined;
                  if (isAgentTool) {
                    statusText = item.status.lastRunOk === false
                      ? `⚠ ${item.status.lastError ?? 'Last run failed'}`
                      : item.status.invocationCount > 0
                        ? `✓ Run ${item.status.invocationCount} time${item.status.invocationCount === 1 ? '' : 's'}`
                        : item.entry.hasHandler
                          ? undefined
                          : 'No handler';
                  } else {
                    statusText = item.status.lastRunOk === false
                      ? `⚠ ${item.status.lastError ?? 'Last run failed'}`
                      : item.status.invocationCount > 0
                        ? `✓ Run ${item.status.invocationCount} time${item.status.invocationCount === 1 ? '' : 's'}`
                        : undefined;
                  }

                  // Unique key
                  const itemKey = isAgentTool
                    ? `tool:${item.entry.toolId}`
                    : item.entry.commandId;

                  // Search value
                  const searchValue = isAgentTool
                    ? item.entry.toolId
                    : item.entry.commandId;

                  return (
                    <CommandItem
                      key={itemKey}
                      value={searchValue}
                      onSelect={() => handleSelect(item)}
                      data-command-palette-item="true"
                      data-item-kind={isAgentTool ? 'agentTool' : 'command'}
                      {...(isAgentTool
                        ? {
                            'data-tool-id': item.entry.toolId,
                            'data-extension-id': item.entry.extensionId,
                          }
                        : {
                            'data-command-id': item.entry.commandId,
                            'data-extension-id': item.entry.extensionId,
                          })
                      }
                    >
                      <div className="flex flex-1 items-center gap-2 overflow-hidden">
                        {isAgentTool ? (
                          <Wrench className="h-3.5 w-3.5 shrink-0 text-blue-400/70" />
                        ) : (
                          <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50" />
                        )}
                        <span className="truncate">{item.entry.label}</span>
                        {isAgentTool && item.entry.resultFamilies.length > 0 && (
                          <span className="ml-0.5 shrink-0 rounded bg-blue-500/10 px-1 py-px text-[9px] text-blue-400/80">
                            {item.entry.resultFamilies[0]}{item.entry.resultFamilies.length > 1 ? ` +${item.entry.resultFamilies.length - 1}` : ''}
                          </span>
                        )}
                        {statusText && (
                          <span className={`ml-1 shrink-0 text-[10px] ${
                            isAgentTool && !item.entry.hasHandler
                              ? 'text-yellow-400/80'
                              : 'text-muted-foreground/60'
                          }`}>
                            {statusText}
                          </span>
                        )}
                      </div>
                      {!isAgentTool && item.keybinding && (
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
