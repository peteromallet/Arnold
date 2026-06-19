import React from 'react';
import { Sparkles } from 'lucide-react';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import { evaluatePredicate, type PredicateContext } from '@/tools/video-editor/runtime/commandPredicates.ts';
import type { CommandRegistry, ContextMenuItemEntry } from '@/tools/video-editor/runtime/commandRegistry.ts';
import type { ReighExtension, TargetContextPayload } from '@reigh/editor-sdk';

const menuItemClassName = 'relative flex w-full cursor-default select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground';

export function buildExtensionPredicateContext(
  extensionId: string,
  extensions: readonly ReighExtension[],
  target: TargetContextPayload,
): PredicateContext | null {
  const ext = extensions.find((candidate) => candidate.manifest.id === extensionId);
  if (!ext) return null;

  return {
    ext: {
      id: ext.manifest.id,
      version: ext.manifest.version,
      label: ext.manifest.label,
    },
    target,
    editor: undefined,
  };
}

export function getEligibleExtensionContextMenuItems({
  commandRegistry,
  extensions,
  target,
  items,
}: {
  commandRegistry?: CommandRegistry;
  extensions: readonly ReighExtension[];
  target: TargetContextPayload;
  items?: readonly ContextMenuItemEntry[];
}): Array<{ item: ContextMenuItemEntry; label: string }> {
  if (!commandRegistry) return [];

  const candidates = items ?? commandRegistry.getSnapshot().contextMenuItems;
  return candidates
    .filter((item) => item.target === target.target)
    .filter((item) => {
      if (!item.when) return true;
      const predicateContext = buildExtensionPredicateContext(item.extensionId, extensions, target);
      return predicateContext ? evaluatePredicate(item.when, predicateContext) : false;
    })
    .map((item) => {
      const command = commandRegistry.getCommand(item.commandId);
      if (!command) return null;
      return { item, label: item.label ?? command.label };
    })
    .filter((entry): entry is { item: ContextMenuItemEntry; label: string } => entry !== null)
    .sort((a, b) => {
      const orderCmp = a.item.order - b.item.order;
      if (orderCmp !== 0) return orderCmp;
      return a.label.localeCompare(b.label);
    });
}

export function hasEligibleExtensionContextMenuItems(
  commandRegistry: CommandRegistry | undefined,
  extensions: readonly ReighExtension[],
  target: TargetContextPayload,
): boolean {
  return getEligibleExtensionContextMenuItems({ commandRegistry, extensions, target }).length > 0;
}

export function ExtensionContextMenuItems({
  items,
  target,
  extensions,
  commandRegistry,
  closeMenu,
  validateTarget,
}: {
  items: readonly ContextMenuItemEntry[];
  target: TargetContextPayload;
  extensions: readonly ReighExtension[];
  commandRegistry?: CommandRegistry;
  closeMenu: () => void;
  validateTarget: (target: TargetContextPayload) => string | null;
}) {
  if (!commandRegistry) return null;

  const eligibleItems = getEligibleExtensionContextMenuItems({
    commandRegistry,
    extensions,
    target,
    items,
  });

  if (eligibleItems.length === 0) return null;

  return (
    <>
      <div className="my-1 h-px bg-border" />
      {eligibleItems.map(({ item, label }) => (
        <button
          key={`${item.extensionId}:${item.commandId}:${item.target}`}
          type="button"
          className={cn(menuItemClassName)}
          onClick={() => {
            const staleReason = validateTarget(target);
            if (staleReason) {
              commandRegistry.diagnoseContextMenuStaleTarget(item.commandId, item.extensionId, target, staleReason);
              closeMenu();
              return;
            }

            closeMenu();
            void commandRegistry.executeCommand(item.commandId, target);
          }}
        >
          <Sparkles className="h-4 w-4" />
          {label}
        </button>
      ))}
    </>
  );
}
