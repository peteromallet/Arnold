import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import {
  useKeyboardShortcuts,
  normalizeKeyboardEvent,
} from '@/tools/video-editor/hooks/useKeyboardShortcuts.ts';
import {
  DataProviderContext,
  type VideoEditorRuntimeContextValue,
} from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import {
  createCommandRegistry,
  type CommandRegistry,
} from '@/tools/video-editor/runtime/commandRegistry.ts';
import type { ReighExtension } from '@reigh/editor-sdk';

function makeExtension(id = 'shortcut.ext'): ReighExtension {
  return {
    manifest: {
      id,
      version: '1.0.0',
      label: 'Shortcut Extension',
      contributes: [],
    },
  } as ReighExtension;
}

function makeOptions(overrides: Partial<Parameters<typeof useKeyboardShortcuts>[0]> = {}) {
  return {
    hasSelectedClip: false,
    canMoveSelectedClipToTrack: false,
    precisionEnabled: false,
    selectedClipIds: new Set<string>(),
    timelineFps: 30,
    moveSelectedClipsToTrack: vi.fn(),
    undo: vi.fn(),
    redo: vi.fn(),
    selectAllClips: vi.fn(),
    togglePlayPause: vi.fn(),
    seekRelative: vi.fn(),
    toggleMute: vi.fn(),
    splitSelectedClip: vi.fn(),
    deleteSelectedClip: vi.fn(),
    clearSelection: vi.fn(),
    ...overrides,
  };
}

function mountShortcuts({
  registry,
  extensions = [makeExtension()],
  options = makeOptions(),
}: {
  registry?: CommandRegistry;
  extensions?: readonly ReighExtension[];
  options?: Parameters<typeof useKeyboardShortcuts>[0];
}) {
  const runtime = {
    commandRegistry: registry,
    extensionRuntime: { extensions },
  } as VideoEditorRuntimeContextValue;

  return renderHook(() => useKeyboardShortcuts(options), {
    wrapper: ({ children }) => (
      <DataProviderContext.Provider value={runtime}>
        {children}
      </DataProviderContext.Provider>
    ),
  });
}

function registerShortcutCommand({
  registry,
  extensionId = 'shortcut.ext',
  commandId = 'shortcut.ext.run',
  key = 'CtrlOrCmd+K',
  when,
  handler = vi.fn(),
}: {
  registry: CommandRegistry;
  extensionId?: string;
  commandId?: string;
  key?: string;
  when?: string;
  handler?: ReturnType<typeof vi.fn>;
}) {
  registry.ingestCommandContribution(extensionId, {
    kind: 'command',
    command: commandId,
    label: 'Run command',
  });
  registry.ingestKeybindingContribution(extensionId, {
    kind: 'keybinding',
    command: commandId,
    key,
    ...(when ? { when } : {}),
  });
  registry.registerCommand(extensionId, commandId, handler);
  return handler;
}

function dispatchKey(target: EventTarget, init: KeyboardEventInit) {
  const event = new KeyboardEvent('keydown', {
    bubbles: true,
    cancelable: true,
    ...init,
  });
  target.dispatchEvent(event);
  return event;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('normalizeKeyboardEvent', () => {
  it('normalizes keyboard events into registry keybinding notation', () => {
    const event = new KeyboardEvent('keydown', {
      key: 'K',
      ctrlKey: true,
      shiftKey: true,
    });

    expect(normalizeKeyboardEvent(event)).toBe('ctrlOrCmd+shift+k');
  });

  it('returns null for pure modifier keys', () => {
    const event = new KeyboardEvent('keydown', { key: 'Shift', shiftKey: true });

    expect(normalizeKeyboardEvent(event)).toBeNull();
  });
});

describe('useKeyboardShortcuts extension keybindings', () => {
  it('invokes a matching extension command once after built-ins decline', async () => {
    const registry = createCommandRegistry();
    const handler = registerShortcutCommand({ registry });
    const undo = vi.fn();

    mountShortcuts({ registry, options: makeOptions({ undo }) });

    const event = dispatchKey(window, { key: 'k', ctrlKey: true });

    expect(event.defaultPrevented).toBe(true);
    expect(undo).not.toHaveBeenCalled();
    await waitFor(() => expect(handler).toHaveBeenCalledTimes(1));
  });

  it('keeps built-in shortcuts ahead of extension keybinding dispatch', async () => {
    const registry = createCommandRegistry();
    const handler = registerShortcutCommand({
      registry,
      commandId: 'shortcut.ext.other',
      key: 'CtrlOrCmd+K',
    });
    const undo = vi.fn();

    mountShortcuts({ registry, options: makeOptions({ undo }) });

    dispatchKey(window, { key: 'z', ctrlKey: true });

    expect(undo).toHaveBeenCalledTimes(1);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(handler).not.toHaveBeenCalled();
  });

  it('skips extension keybindings from editable targets', async () => {
    const registry = createCommandRegistry();
    const handler = registerShortcutCommand({ registry });
    const input = document.createElement('input');
    document.body.appendChild(input);

    try {
      mountShortcuts({ registry });

      const event = dispatchKey(input, { key: 'k', ctrlKey: true });

      expect(event.defaultPrevented).toBe(false);
      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(handler).not.toHaveBeenCalled();
    } finally {
      input.remove();
    }
  });

  it('reserves CtrlOrCmd+Shift+P for the command palette path', async () => {
    const registry = createCommandRegistry();
    const handler = registerShortcutCommand({
      registry,
      commandId: 'shortcut.ext.palette',
      key: 'CtrlOrCmd+Shift+P',
    });

    mountShortcuts({ registry });

    const event = dispatchKey(window, { key: 'p', ctrlKey: true, shiftKey: true });

    expect(event.defaultPrevented).toBe(false);
    expect(registry.diagnostics.some((d) => d.code === 'command-registry/reserved-keybinding')).toBe(true);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(handler).not.toHaveBeenCalled();
  });

  it('surfaces invalid extension keybindings through registry diagnostics and skips invocation', async () => {
    const registry = createCommandRegistry();
    const handler = registerShortcutCommand({
      registry,
      key: 'Ctrl++K',
    });

    mountShortcuts({ registry });

    dispatchKey(window, { key: 'k', ctrlKey: true });

    expect(registry.diagnostics.some((d) => d.code === 'command-registry/invalid-keybinding')).toBe(true);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(handler).not.toHaveBeenCalled();
  });

  it('keeps first-registered extension keybinding winner and diagnoses duplicates', async () => {
    const registry = createCommandRegistry();
    const firstHandler = registerShortcutCommand({
      registry,
      extensionId: 'shortcut.ext',
      commandId: 'shortcut.ext.first',
      key: 'CtrlOrCmd+K',
    });
    const secondHandler = registerShortcutCommand({
      registry,
      extensionId: 'shortcut.second',
      commandId: 'shortcut.second.run',
      key: 'CtrlOrCmd+K',
    });

    mountShortcuts({
      registry,
      extensions: [makeExtension('shortcut.ext'), makeExtension('shortcut.second')],
    });

    const event = dispatchKey(window, { key: 'k', ctrlKey: true });

    expect(event.defaultPrevented).toBe(true);
    expect(registry.diagnostics.some((d) => d.code === 'command-registry/keybinding-conflict')).toBe(true);
    await waitFor(() => expect(firstHandler).toHaveBeenCalledTimes(1));
    expect(secondHandler).not.toHaveBeenCalled();
  });

  it('honors when predicates against the current selection target', async () => {
    const registry = createCommandRegistry();
    const clipHandler = registerShortcutCommand({
      registry,
      commandId: 'shortcut.ext.clip',
      key: 'CtrlOrCmd+K',
      when: 'target.target == "clip" && target.clipId == "clip-1"',
    });

    mountShortcuts({
      registry,
      options: makeOptions({
        hasSelectedClip: true,
        selectedClipIds: new Set(['clip-1']),
      }),
    });

    dispatchKey(window, { key: 'k', ctrlKey: true });

    await waitFor(() => expect(clipHandler).toHaveBeenCalledTimes(1));
  });

  it('does not invoke when predicates that decline', async () => {
    const registry = createCommandRegistry();
    const handler = registerShortcutCommand({
      registry,
      when: 'target.target == "clip-selection"',
    });

    mountShortcuts({
      registry,
      options: makeOptions({
        hasSelectedClip: true,
        selectedClipIds: new Set(['clip-1']),
      }),
    });

    const event = dispatchKey(window, { key: 'k', ctrlKey: true });

    expect(event.defaultPrevented).toBe(false);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(handler).not.toHaveBeenCalled();
  });
});
