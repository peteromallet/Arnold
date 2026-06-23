import { describe, expect, it, vi, beforeEach } from 'vitest';
import {
  createCommandRegistry,
  normalizeKeybinding,
  isReservedCommandId,
  isReservedKeybinding,
  BUILT_IN_RESERVED_KEYBINDINGS,
  type CommandRegistry,
  type CommandRegistrySnapshot,
  type CommandRegistryCallbacks,
} from '@/tools/video-editor/runtime/commandRegistry';
import type {
  CommandContribution,
  KeybindingContribution,
  ContextMenuItemContribution,
  CommandHandler,
  CommandRunContext,
  TargetContextPayload,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeCommandContribution(overrides?: Partial<CommandContribution>): CommandContribution {
  return {
    id: 'cmd.test' as any,
    kind: 'command',
    command: 'test.doSomething',
    label: 'Test Command',
    ...overrides,
  };
}

function makeKeybindingContribution(overrides?: Partial<KeybindingContribution>): KeybindingContribution {
  return {
    id: 'kb.test' as any,
    kind: 'keybinding',
    command: 'test.doSomething',
    key: 'ctrl+shift+t',
    ...overrides,
  };
}

function makeContextMenuContribution(overrides?: Partial<ContextMenuItemContribution>): ContextMenuItemContribution {
  return {
    id: 'cm.test' as any,
    kind: 'contextMenuItem',
    command: 'test.doSomething',
    target: 'clip',
    ...overrides,
  };
}

function createFreshRegistry(): CommandRegistry {
  return createCommandRegistry();
}

function createCallbacks(): Required<CommandRegistryCallbacks> & { calls: Map<string, any[]> } {
  const calls = new Map<string, any[]>();
  const record = (key: string, ...args: any[]) => {
    if (!calls.has(key)) calls.set(key, []);
    calls.get(key)!.push(args);
  };
  return {
    calls,
    onCommandFailure: vi.fn((commandId, error, extensionId) => record('onCommandFailure', commandId, error, extensionId)),
    onReservedCommand: vi.fn((commandId, extensionId) => record('onReservedCommand', commandId, extensionId)),
    onReservedKeybinding: vi.fn((key, extensionId, commandId) => record('onReservedKeybinding', key, extensionId, commandId)),
    onDuplicateCommand: vi.fn((commandId, originalExtension, conflictingExtension) => record('onDuplicateCommand', commandId, originalExtension, conflictingExtension)),
    onKeybindingConflict: vi.fn((key, originalExtension, conflictingExtension) => record('onKeybindingConflict', key, originalExtension, conflictingExtension)),
    onContextMenuStaleTarget: vi.fn((commandId, extensionId, reason) => record('onContextMenuStaleTarget', commandId, extensionId, reason)),
  };
}

// Helper to register a command + handler in one step
function registerTestCommand(registry: CommandRegistry, extensionId: string, commandId: string, handler?: CommandHandler) {
  registry.ingestCommandContribution(extensionId, makeCommandContribution({ command: commandId }));
  if (handler) {
    return registry.registerCommand(extensionId, commandId, handler);
  }
  return undefined;
}

// ---------------------------------------------------------------------------
// normalizeKeybinding
// ---------------------------------------------------------------------------

describe('normalizeKeybinding', () => {
  it('normalizes a simple modifier+key combination', () => {
    expect(normalizeKeybinding('Ctrl+Shift+K')).toBe('ctrl+shift+k');
  });

  it('sorts modifiers into canonical order (alt < ctrl < ctrlOrCmd < shift)', () => {
    expect(normalizeKeybinding('Shift+Alt+K')).toBe('alt+shift+k');
    expect(normalizeKeybinding('Shift+Ctrl+K')).toBe('ctrl+shift+k');
    expect(normalizeKeybinding('CtrlOrCmd+Shift+K')).toBe('ctrlOrCmd+shift+k');
  });

  it('normalizes CtrlOrCmd case-insensitively', () => {
    expect(normalizeKeybinding('ctrlorcmd+k')).toBe('ctrlOrCmd+k');
    expect(normalizeKeybinding('CTRLORCMD+K')).toBe('ctrlOrCmd+k');
    expect(normalizeKeybinding('CtrlOrCmd+K')).toBe('ctrlOrCmd+k');
  });

  it('returns null for empty string', () => {
    expect(normalizeKeybinding('')).toBeNull();
    expect(normalizeKeybinding('   ')).toBeNull();
  });

  it('returns null for non-string input', () => {
    expect(normalizeKeybinding(null as any)).toBeNull();
    expect(normalizeKeybinding(undefined as any)).toBeNull();
    expect(normalizeKeybinding(123 as any)).toBeNull();
  });

  it('returns null for invalid notation (starts with non-alpha)', () => {
    expect(normalizeKeybinding('123+K')).toBeNull();
  });

  it('returns null for malformed notation with empty segments', () => {
    expect(normalizeKeybinding('Ctrl++K')).toBeNull();
  });

  it('preserves non-modifier key parts in original order', () => {
    expect(normalizeKeybinding('Ctrl+K+Delete')).toBe('ctrl+k+delete');
  });

  it('handles single-key bindings (no modifiers)', () => {
    expect(normalizeKeybinding('Enter')).toBe('enter');
    expect(normalizeKeybinding('Space')).toBe('space');
  });

  it('trims whitespace', () => {
    expect(normalizeKeybinding('  Ctrl+K  ')).toBe('ctrl+k');
  });
});

// ---------------------------------------------------------------------------
// isReservedCommandId
// ---------------------------------------------------------------------------

describe('isReservedCommandId', () => {
  it('returns true for reigh.* prefixed commands', () => {
    expect(isReservedCommandId('reigh.test')).toBe(true);
    expect(isReservedCommandId('reigh.editor.palette')).toBe(true);
    expect(isReservedCommandId('reigh.internal')).toBe(true);
  });

  it('returns false for non-reigh prefixed commands', () => {
    expect(isReservedCommandId('test.doSomething')).toBe(false);
    expect(isReservedCommandId('com.ext.custom')).toBe(false);
    expect(isReservedCommandId('Reigh.test')).toBe(false); // case-sensitive
  });

  it('returns false for commands that contain reigh elsewhere', () => {
    expect(isReservedCommandId('com.reighSomething.do')).toBe(false);
    expect(isReservedCommandId('reighSomething.do')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// isReservedKeybinding / BUILT_IN_RESERVED_KEYBINDINGS
// ---------------------------------------------------------------------------

describe('isReservedKeybinding', () => {
  it('returns true for built-in reserved shortcuts', () => {
    expect(isReservedKeybinding('ctrl+z')).toBe(true);
    expect(isReservedKeybinding('ctrl+shift+z')).toBe(true);
    expect(isReservedKeybinding('ctrl+a')).toBe(true);
    expect(isReservedKeybinding(' ')).toBe(true);
    expect(isReservedKeybinding('escape')).toBe(true);
    expect(isReservedKeybinding('alt+w')).toBe(true);
    expect(isReservedKeybinding('ctrl+shift+p')).toBe(true);
  });

  it('handles ctrlOrCmd canonicalization for reserved check', () => {
    // CtrlOrCmd normalizes to ctrlOrCmd, but reserved check should canonicalize to ctrl
    expect(isReservedKeybinding('ctrlOrCmd+z')).toBe(true);
    expect(isReservedKeybinding('ctrlOrCmd+shift+p')).toBe(true);
    expect(isReservedKeybinding('ctrlOrCmd+a')).toBe(true);
  });

  it('returns false for non-reserved shortcuts', () => {
    expect(isReservedKeybinding('ctrl+k')).toBe(false);
    expect(isReservedKeybinding('alt+shift+m')).toBe(false);
    expect(isReservedKeybinding('ctrl+shift+x')).toBe(false);
  });

  it('BUILT_IN_RESERVED_KEYBINDINGS is a non-empty set', () => {
    expect(BUILT_IN_RESERVED_KEYBINDINGS.size).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// Reserved command rejection
// ---------------------------------------------------------------------------

describe('CommandRegistry — reserved command rejection', () => {
  it('rejects reigh.* command contributions with an error diagnostic', () => {
    const registry = createFreshRegistry();
    registry.ingestCommandContribution('test.ext', makeCommandContribution({ command: 'reigh.internal' }));

    const diags = registry.diagnostics;
    const reservedDiag = diags.find((d) => d.code === 'command-registry/reserved-command');
    expect(reservedDiag).toBeDefined();
    expect(reservedDiag!.severity).toBe('error');
    expect(reservedDiag!.extensionId).toBe('test.ext');
    expect(reservedDiag!.message).toContain('reigh.internal');
  });

  it('does not add reserved commands to the registry', () => {
    const registry = createFreshRegistry();
    registry.ingestCommandContribution('test.ext', makeCommandContribution({ command: 'reigh.internal' }));

    expect(registry.getCommand('reigh.internal')).toBeUndefined();
  });

  it('calls onReservedCommand callback when callbacks are set', () => {
    const registry = createFreshRegistry();
    const cbs = createCallbacks();
    registry.setCallbacks(cbs);

    registry.ingestCommandContribution('test.ext', makeCommandContribution({ command: 'reigh.internal' }));

    expect(cbs.onReservedCommand).toHaveBeenCalledWith('reigh.internal', 'test.ext');
  });
});

// ---------------------------------------------------------------------------
// Duplicate command IDs — first-registered-wins
// ---------------------------------------------------------------------------

describe('CommandRegistry — duplicate command IDs', () => {
  it('first extension wins: second extension cannot claim the same command ID', () => {
    const registry = createFreshRegistry();
    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'shared.cmd', label: 'Ext1 Cmd' }));
    registry.ingestCommandContribution('ext2', makeCommandContribution({ command: 'shared.cmd', label: 'Ext2 Cmd' }));

    const cmd = registry.getCommand('shared.cmd');
    expect(cmd).toBeDefined();
    expect(cmd!.extensionId).toBe('ext1');
    expect(cmd!.label).toBe('Ext1 Cmd');
  });

  it('emits warning diagnostic for cross-extension duplicate', () => {
    const registry = createFreshRegistry();
    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'shared.cmd' }));
    registry.ingestCommandContribution('ext2', makeCommandContribution({ command: 'shared.cmd' }));

    const dupDiag = registry.diagnostics.find((d) => d.code === 'command-registry/duplicate-command');
    expect(dupDiag).toBeDefined();
    expect(dupDiag!.severity).toBe('warning');
    expect(dupDiag!.extensionId).toBe('ext2');
    expect(dupDiag!.message).toContain('ext1');
  });

  it('calls onDuplicateCommand callback', () => {
    const registry = createFreshRegistry();
    const cbs = createCallbacks();
    registry.setCallbacks(cbs);
    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'shared.cmd' }));
    registry.ingestCommandContribution('ext2', makeCommandContribution({ command: 'shared.cmd' }));

    expect(cbs.onDuplicateCommand).toHaveBeenCalledWith('shared.cmd', 'ext1', 'ext2');
  });

  it('same extension can overwrite its own command contribution metadata', () => {
    const registry = createFreshRegistry();
    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'own.cmd', label: 'First' }));
    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'own.cmd', label: 'Second' }));

    const cmd = registry.getCommand('own.cmd');
    expect(cmd).toBeDefined();
    expect(cmd!.extensionId).toBe('ext1');
    expect(cmd!.label).toBe('Second');
  });

  it('same-extension overwrite preserves previously registered handler', () => {
    const registry = createFreshRegistry();
    const handler = vi.fn();
    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'own.cmd' }));
    registry.registerCommand('ext1', 'own.cmd', handler);
    // Re-ingest without re-registering — handler should survive
    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'own.cmd', label: 'Updated' }));

    const status = registry.getStatus('own.cmd');
    expect(registry.getCommand('own.cmd')!.label).toBe('Updated');
    // executeCommand still works because handler was preserved
    return registry.executeCommand('own.cmd').then((ok) => {
      expect(ok).toBe(true);
      expect(handler).toHaveBeenCalled();
    });
  });
});

// ---------------------------------------------------------------------------
// Invalid keybinding grammar
// ---------------------------------------------------------------------------

describe('CommandRegistry — invalid keybinding grammar', () => {
  it('rejects keybinding contributions with invalid notation', () => {
    const registry = createFreshRegistry();
    registry.ingestKeybindingContribution('test.ext', makeKeybindingContribution({ key: '+++invalid+++' }));

    const diag = registry.diagnostics.find((d) => d.code === 'command-registry/invalid-keybinding');
    expect(diag).toBeDefined();
    expect(diag!.severity).toBe('error');
    expect(diag!.extensionId).toBe('test.ext');
  });

  it('does not register keybindings with invalid notation', () => {
    const registry = createFreshRegistry();
    registry.ingestKeybindingContribution('test.ext', makeKeybindingContribution({ key: '+++invalid+++' }));

    expect(registry.getKeybinding('+++invalid+++')).toBeUndefined();
  });

  it('rejects empty keybinding notation', () => {
    const registry = createFreshRegistry();
    registry.ingestKeybindingContribution('test.ext', makeKeybindingContribution({ key: '' }));

    const diag = registry.diagnostics.find((d) => d.code === 'command-registry/invalid-keybinding');
    expect(diag).toBeDefined();
  });

  it('accepts valid keybinding notation', () => {
    const registry = createFreshRegistry();
    registry.ingestKeybindingContribution('test.ext', makeKeybindingContribution({ key: 'Alt+Shift+M' }));

    const kb = registry.getKeybinding('alt+shift+m');
    expect(kb).toBeDefined();
    expect(kb!.commandId).toBe('test.doSomething');
    expect(kb!.extensionId).toBe('test.ext');
  });
});

// ---------------------------------------------------------------------------
// Reserved built-in shortcut precedence
// ---------------------------------------------------------------------------

describe('CommandRegistry — reserved built-in shortcuts', () => {
  it('rejects keybindings that match built-in reserved shortcuts', () => {
    const registry = createFreshRegistry();
    // Ctrl+Z (cross-platform undo) is reserved
    registry.ingestKeybindingContribution('test.ext', makeKeybindingContribution({ key: 'Ctrl+Z' }));

    const diag = registry.diagnostics.find((d) => d.code === 'command-registry/reserved-keybinding');
    expect(diag).toBeDefined();
    expect(diag!.severity).toBe('error');
    expect(diag!.extensionId).toBe('test.ext');
  });

  it('rejects CtrlOrCmd+Z as reserved (canonicalized to ctrl+z)', () => {
    const registry = createFreshRegistry();
    registry.ingestKeybindingContribution('test.ext', makeKeybindingContribution({ key: 'CtrlOrCmd+Z' }));

    const diag = registry.diagnostics.find((d) => d.code === 'command-registry/reserved-keybinding');
    expect(diag).toBeDefined();
  });

  it('rejects single-space keybinding as invalid grammar (space is reserved but fails KEYBINDING_RE)', () => {
    const registry = createFreshRegistry();
    registry.ingestKeybindingContribution('test.ext', makeKeybindingContribution({ key: ' ' }));

    // Space fails the KEYBINDING_RE regex (must start with [a-zA-Z]),
    // so it gets invalid-keybinding rather than reserved-keybinding.
    // The space character IS in BUILT_IN_RESERVED_KEYBINDINGS, but the
    // normalizer rejects it before the reserved check runs.
    const diag = registry.diagnostics.find((d) => d.code === 'command-registry/invalid-keybinding');
    expect(diag).toBeDefined();
  });

  it('rejects Escape keybinding as reserved', () => {
    const registry = createFreshRegistry();
    registry.ingestKeybindingContribution('test.ext', makeKeybindingContribution({ key: 'Escape' }));

    const diag = registry.diagnostics.find((d) => d.code === 'command-registry/reserved-keybinding');
    expect(diag).toBeDefined();
  });

  it('calls onReservedKeybinding callback', () => {
    const registry = createFreshRegistry();
    const cbs = createCallbacks();
    registry.setCallbacks(cbs);
    registry.ingestKeybindingContribution('test.ext', makeKeybindingContribution({ key: 'Alt+W' }));

    expect(cbs.onReservedKeybinding).toHaveBeenCalledWith('alt+w', 'test.ext', 'test.doSomething');
  });

  it('does not register reserved keybindings', () => {
    const registry = createFreshRegistry();
    registry.ingestKeybindingContribution('test.ext', makeKeybindingContribution({ key: 'Ctrl+Z' }));

    expect(registry.getKeybinding('ctrl+z')).toBeUndefined();
  });

  it('accepts non-reserved keybindings', () => {
    const registry = createFreshRegistry();
    registry.ingestKeybindingContribution('test.ext', makeKeybindingContribution({ key: 'Ctrl+K' }));

    expect(registry.getKeybinding('ctrl+k')).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// Extension-vs-extension first-registered-wins keybindings
// ---------------------------------------------------------------------------

describe('CommandRegistry — keybinding first-registered-wins', () => {
  it('first extension to register a keybinding wins', () => {
    const registry = createFreshRegistry();
    registry.ingestKeybindingContribution('ext1', makeKeybindingContribution({ key: 'Ctrl+K', command: 'ext1.cmd' }));
    registry.ingestKeybindingContribution('ext2', makeKeybindingContribution({ key: 'Ctrl+K', command: 'ext2.cmd' }));

    const kb = registry.getKeybinding('ctrl+k');
    expect(kb).toBeDefined();
    expect(kb!.extensionId).toBe('ext1');
    expect(kb!.commandId).toBe('ext1.cmd');
  });

  it('emits warning diagnostic for keybinding conflict', () => {
    const registry = createFreshRegistry();
    registry.ingestKeybindingContribution('ext1', makeKeybindingContribution({ key: 'Ctrl+K', command: 'ext1.cmd' }));
    registry.ingestKeybindingContribution('ext2', makeKeybindingContribution({ key: 'Ctrl+K', command: 'ext2.cmd' }));

    const diag = registry.diagnostics.find((d) => d.code === 'command-registry/keybinding-conflict');
    expect(diag).toBeDefined();
    expect(diag!.severity).toBe('warning');
    expect(diag!.extensionId).toBe('ext2');
    expect(diag!.message).toContain('ext1');
  });

  it('calls onKeybindingConflict callback', () => {
    const registry = createFreshRegistry();
    const cbs = createCallbacks();
    registry.setCallbacks(cbs);
    registry.ingestKeybindingContribution('ext1', makeKeybindingContribution({ key: 'Ctrl+K', command: 'ext1.cmd' }));
    registry.ingestKeybindingContribution('ext2', makeKeybindingContribution({ key: 'Ctrl+K', command: 'ext2.cmd' }));

    expect(cbs.onKeybindingConflict).toHaveBeenCalledWith('ctrl+k', 'ext1', 'ext2');
  });

  it('same extension can overwrite its own keybinding (last-wins)', () => {
    const registry = createFreshRegistry();
    registry.ingestKeybindingContribution('ext1', makeKeybindingContribution({ key: 'Ctrl+K', command: 'ext1.cmd' }));
    registry.ingestKeybindingContribution('ext1', makeKeybindingContribution({ key: 'Ctrl+K', command: 'ext1.otherCmd' }));

    const kb = registry.getKeybinding('ctrl+k');
    expect(kb).toBeDefined();
    expect(kb!.extensionId).toBe('ext1');
    expect(kb!.commandId).toBe('ext1.otherCmd');
  });

  it('different extensions can use different keybindings without conflict', () => {
    const registry = createFreshRegistry();
    registry.ingestKeybindingContribution('ext1', makeKeybindingContribution({ key: 'Ctrl+K', command: 'ext1.cmd' }));
    registry.ingestKeybindingContribution('ext2', makeKeybindingContribution({ key: 'Ctrl+J', command: 'ext2.cmd' }));

    expect(registry.getKeybinding('ctrl+k')).toBeDefined();
    expect(registry.getKeybinding('ctrl+j')).toBeDefined();
    expect(registry.diagnostics.filter((d) => d.code === 'command-registry/keybinding-conflict')).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// Unregister cleanup
// ---------------------------------------------------------------------------

describe('CommandRegistry — unregisterAll cleanup', () => {
  it('removes all commands for an extension', () => {
    const registry = createFreshRegistry();
    registerTestCommand(registry, 'ext1', 'ext1.cmd1', vi.fn());
    registerTestCommand(registry, 'ext1', 'ext1.cmd2', vi.fn());
    registerTestCommand(registry, 'ext2', 'ext2.cmd', vi.fn());

    expect(registry.getCommand('ext1.cmd1')).toBeDefined();
    expect(registry.getCommand('ext1.cmd2')).toBeDefined();

    registry.unregisterAll('ext1');

    expect(registry.getCommand('ext1.cmd1')).toBeUndefined();
    expect(registry.getCommand('ext1.cmd2')).toBeUndefined();
    // ext2 should be untouched
    expect(registry.getCommand('ext2.cmd')).toBeDefined();
  });

  it('removes all keybindings for an extension', () => {
    const registry = createFreshRegistry();
    registry.ingestKeybindingContribution('ext1', makeKeybindingContribution({ key: 'Ctrl+K', command: 'ext1.cmd1' }));
    registry.ingestKeybindingContribution('ext2', makeKeybindingContribution({ key: 'Ctrl+J', command: 'ext2.cmd' }));

    registry.unregisterAll('ext1');

    expect(registry.getKeybinding('ctrl+k')).toBeUndefined();
    expect(registry.getKeybinding('ctrl+j')).toBeDefined();
  });

  it('removes all context menu items for an extension', () => {
    const registry = createFreshRegistry();
    registry.ingestContextMenuItemContribution('ext1', makeContextMenuContribution({ target: 'clip', command: 'ext1.cmd' }));
    registry.ingestContextMenuItemContribution('ext2', makeContextMenuContribution({ target: 'clip', command: 'ext2.cmd' }));

    registry.unregisterAll('ext1');

    const snap = registry.getSnapshot();
    const ext1Items = snap.contextMenuItems.filter((i) => i.extensionId === 'ext1');
    const ext2Items = snap.contextMenuItems.filter((i) => i.extensionId === 'ext2');
    expect(ext1Items).toHaveLength(0);
    expect(ext2Items).toHaveLength(1);
  });

  it('unregisterAll is idempotent for the same extension', () => {
    const registry = createFreshRegistry();
    registry.ingestKeybindingContribution('ext1', makeKeybindingContribution({ key: 'Ctrl+K', command: 'ext1.cmd1' }));

    registry.unregisterAll('ext1');
    expect(registry.getKeybinding('ctrl+k')).toBeUndefined();

    // Second unregister should not throw
    expect(() => registry.unregisterAll('ext1')).not.toThrow();
  });

  it('unregistering an unknown extension does nothing', () => {
    const registry = createFreshRegistry();
    registerTestCommand(registry, 'ext1', 'ext1.cmd', vi.fn());

    expect(() => registry.unregisterAll('nonexistent')).not.toThrow();
    expect(registry.getCommand('ext1.cmd')).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// Handler disposal
// ---------------------------------------------------------------------------

describe('CommandRegistry — handler disposal', () => {
  it('dispose handle nullifies the handler so it cannot be executed', async () => {
    const registry = createFreshRegistry();
    const handler = vi.fn();
    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'ext1.cmd' }));
    const handle = registry.registerCommand('ext1', 'ext1.cmd', handler);

    // Should work before disposal
    const ok1 = await registry.executeCommand('ext1.cmd');
    expect(ok1).toBe(true);
    expect(handler).toHaveBeenCalledTimes(1);

    handle.dispose();

    // Should fail after disposal (no handler)
    const ok2 = await registry.executeCommand('ext1.cmd');
    expect(ok2).toBe(false);
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('dispose handle is idempotent', () => {
    const registry = createFreshRegistry();
    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'ext1.cmd' }));
    const handler = vi.fn();
    const handle = registry.registerCommand('ext1', 'ext1.cmd', handler);

    handle.dispose();
    expect(() => handle.dispose()).not.toThrow();
    expect(() => handle.dispose()).not.toThrow();
  });

  it('dispose handle does not remove the command entry, only the handler', () => {
    const registry = createFreshRegistry();
    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'ext1.cmd' }));
    const handle = registry.registerCommand('ext1', 'ext1.cmd', vi.fn());

    handle.dispose();

    // Command entry still exists but has no handler
    const cmd = registry.getCommand('ext1.cmd');
    expect(cmd).toBeDefined();
  });

  it('disposing a handler for one extension does not affect another extension', async () => {
    const registry = createFreshRegistry();
    const handler1 = vi.fn();
    const handler2 = vi.fn();
    registerTestCommand(registry, 'ext1', 'ext1.cmd', handler1);
    const handle2 = registerTestCommand(registry, 'ext2', 'ext2.cmd', handler2);

    handle2!.dispose();

    // ext1 handler still works
    const ok1 = await registry.executeCommand('ext1.cmd');
    expect(ok1).toBe(true);
    expect(handler1).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// Invocation status
// ---------------------------------------------------------------------------

describe('CommandRegistry — invocation status', () => {
  it('returns default zero-state status for unregistered commands', () => {
    const registry = createFreshRegistry();
    const status = registry.getStatus('nonexistent.cmd');

    expect(status.invocationCount).toBe(0);
    expect(status.lastRunAt).toBe(0);
    expect(status.lastRunOk).toBe(true);
    expect(status.lastError).toBeNull();
  });

  it('tracks successful invocations', async () => {
    const registry = createFreshRegistry();
    const handler = vi.fn();
    registerTestCommand(registry, 'ext1', 'ext1.cmd', handler);

    await registry.executeCommand('ext1.cmd');
    await registry.executeCommand('ext1.cmd');

    const status = registry.getStatus('ext1.cmd');
    expect(status.invocationCount).toBe(2);
    expect(status.lastRunOk).toBe(true);
    expect(status.lastError).toBeNull();
    expect(status.lastRunAt).toBeGreaterThan(0);
  });

  it('tracks failed invocations', async () => {
    const registry = createFreshRegistry();
    const handler = vi.fn().mockRejectedValue(new Error('Test failure'));
    registerTestCommand(registry, 'ext1', 'ext1.cmd', handler);

    await registry.executeCommand('ext1.cmd');

    const status = registry.getStatus('ext1.cmd');
    expect(status.invocationCount).toBe(1);
    expect(status.lastRunOk).toBe(false);
    expect(status.lastError).toBe('Test failure');
  });

  it('resets lastError after a subsequent successful invocation', async () => {
    const registry = createFreshRegistry();
    let fail = true;
    const handler = vi.fn().mockImplementation(() => {
      if (fail) {
        fail = false;
        return Promise.reject(new Error('First fail'));
      }
      return Promise.resolve();
    });
    registerTestCommand(registry, 'ext1', 'ext1.cmd', handler);

    await registry.executeCommand('ext1.cmd'); // fails
    await registry.executeCommand('ext1.cmd'); // succeeds

    const status = registry.getStatus('ext1.cmd');
    expect(status.invocationCount).toBe(2);
    expect(status.lastRunOk).toBe(true);
    expect(status.lastError).toBeNull();
  });

  it('getStatus returns a frozen snapshot', () => {
    const registry = createFreshRegistry();
    const status = registry.getStatus('any.cmd');

    expect(() => {
      (status as any).invocationCount = 99;
    }).toThrow();
  });
});

// ---------------------------------------------------------------------------
// Rejected/thrown handler diagnostics
// ---------------------------------------------------------------------------

describe('CommandRegistry — rejected/thrown handler diagnostics', () => {
  it('notifies subscribers when diagnostics are emitted and stops after subscription disposal', async () => {
    const registry = createFreshRegistry();
    const listener = vi.fn();
    const subscription = registry.subscribe(listener);

    await registry.executeCommand('missing.command');
    expect(listener).toHaveBeenCalledTimes(1);

    subscription.dispose();
    await registry.executeCommand('still.missing');
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('emits error diagnostic when handler throws', async () => {
    const registry = createFreshRegistry();
    const handler = vi.fn().mockImplementation(() => {
      throw new Error('Kaboom!');
    });
    registerTestCommand(registry, 'ext1', 'ext1.cmd', handler);

    const ok = await registry.executeCommand('ext1.cmd');
    expect(ok).toBe(false);

    const diag = registry.diagnostics.find((d) => d.code === 'command-registry/invoke-error');
    expect(diag).toBeDefined();
    expect(diag!.severity).toBe('error');
    expect(diag!.message).toContain('Kaboom!');
    expect(diag!.extensionId).toBe('ext1');
  });

  it('emits error diagnostic when handler rejects', async () => {
    const registry = createFreshRegistry();
    const handler = vi.fn().mockRejectedValue(new Error('Async boom'));
    registerTestCommand(registry, 'ext1', 'ext1.cmd', handler);

    const ok = await registry.executeCommand('ext1.cmd');
    expect(ok).toBe(false);

    const diag = registry.diagnostics.find((d) => d.code === 'command-registry/invoke-error');
    expect(diag).toBeDefined();
    expect(diag!.message).toContain('Async boom');
  });

  it('handles non-Error rejections (wraps in Error)', async () => {
    const registry = createFreshRegistry();
    const handler = vi.fn().mockRejectedValue('string error');
    registerTestCommand(registry, 'ext1', 'ext1.cmd', handler);

    const ok = await registry.executeCommand('ext1.cmd');
    expect(ok).toBe(false);

    const diag = registry.diagnostics.find((d) => d.code === 'command-registry/invoke-error');
    expect(diag).toBeDefined();
    expect(diag!.message).toContain('string error');
  });

  it('emits diagnostic for unknown command invocation', async () => {
    const registry = createFreshRegistry();
    const ok = await registry.executeCommand('nonexistent.cmd');
    expect(ok).toBe(false);

    const diag = registry.diagnostics.find((d) => d.code === 'command-registry/invoke-unknown-command');
    expect(diag).toBeDefined();
    expect(diag!.severity).toBe('warning');
  });

  it('emits diagnostic when command has no handler', async () => {
    const registry = createFreshRegistry();
    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'ext1.cmd' }));
    // No handler registered

    const ok = await registry.executeCommand('ext1.cmd');
    expect(ok).toBe(false);

    const diag = registry.diagnostics.find((d) => d.code === 'command-registry/invoke-no-handler');
    expect(diag).toBeDefined();
  });

  it('emits diagnostic when registering handler for non-existent command', () => {
    const registry = createFreshRegistry();
    registry.registerCommand('ext1', 'nonexistent.cmd', vi.fn());

    const diag = registry.diagnostics.find((d) => d.code === 'command-registry/handler-no-command');
    expect(diag).toBeDefined();
    expect(diag!.severity).toBe('warning');
  });

  it('emits diagnostic when registering handler for another extension\'s command', () => {
    const registry = createFreshRegistry();
    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'ext1.cmd' }));
    registry.registerCommand('ext2', 'ext1.cmd', vi.fn());

    const diag = registry.diagnostics.find((d) => d.code === 'command-registry/handler-wrong-extension');
    expect(diag).toBeDefined();
    expect(diag!.severity).toBe('error');
  });
});

// ---------------------------------------------------------------------------
// Toast callback behavior
// ---------------------------------------------------------------------------

describe('CommandRegistry — toast callback behavior', () => {
  it('onCommandFailure is called when handler throws', async () => {
    const registry = createFreshRegistry();
    const cbs = createCallbacks();
    registry.setCallbacks(cbs);

    registerTestCommand(registry, 'ext1', 'ext1.cmd', vi.fn().mockRejectedValue(new Error('Toast me')));

    await registry.executeCommand('ext1.cmd');

    expect(cbs.onCommandFailure).toHaveBeenCalled();
    const [commandId, error, extensionId] = cbs.onCommandFailure.mock.calls[0];
    expect(commandId).toBe('ext1.cmd');
    expect(error).toBeInstanceOf(Error);
    expect(error.message).toBe('Toast me');
    expect(extensionId).toBe('ext1');
  });

  it('onCommandFailure is NOT called on successful invocation', async () => {
    const registry = createFreshRegistry();
    const cbs = createCallbacks();
    registry.setCallbacks(cbs);

    registerTestCommand(registry, 'ext1', 'ext1.cmd', vi.fn().mockResolvedValue(undefined));

    await registry.executeCommand('ext1.cmd');

    expect(cbs.onCommandFailure).not.toHaveBeenCalled();
  });

  it('onReservedCommand callback is called for reigh.* commands', () => {
    const registry = createFreshRegistry();
    const cbs = createCallbacks();
    registry.setCallbacks(cbs);

    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'reigh.test' }));

    expect(cbs.onReservedCommand).toHaveBeenCalledWith('reigh.test', 'ext1');
  });

  it('onReservedKeybinding callback is called for reserved shortcuts', () => {
    const registry = createFreshRegistry();
    const cbs = createCallbacks();
    registry.setCallbacks(cbs);

    registry.ingestKeybindingContribution('ext1', makeKeybindingContribution({ key: 'Ctrl+Z' }));

    expect(cbs.onReservedKeybinding).toHaveBeenCalledWith('ctrl+z', 'ext1', 'test.doSomething');
  });

  it('onDuplicateCommand callback is called for cross-extension duplicates', () => {
    const registry = createFreshRegistry();
    const cbs = createCallbacks();
    registry.setCallbacks(cbs);

    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'shared.cmd' }));
    registry.ingestCommandContribution('ext2', makeCommandContribution({ command: 'shared.cmd' }));

    expect(cbs.onDuplicateCommand).toHaveBeenCalledWith('shared.cmd', 'ext1', 'ext2');
  });

  it('onDuplicateCommand is NOT called for same-extension overwrites', () => {
    const registry = createFreshRegistry();
    const cbs = createCallbacks();
    registry.setCallbacks(cbs);

    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'own.cmd' }));
    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'own.cmd' }));

    expect(cbs.onDuplicateCommand).not.toHaveBeenCalled();
  });

  it('onKeybindingConflict callback is called for cross-extension keybinding conflicts', () => {
    const registry = createFreshRegistry();
    const cbs = createCallbacks();
    registry.setCallbacks(cbs);

    registry.ingestKeybindingContribution('ext1', makeKeybindingContribution({ key: 'Ctrl+K', command: 'ext1.cmd' }));
    registry.ingestKeybindingContribution('ext2', makeKeybindingContribution({ key: 'Ctrl+K', command: 'ext2.cmd' }));

    expect(cbs.onKeybindingConflict).toHaveBeenCalledWith('ctrl+k', 'ext1', 'ext2');
  });

  it('setCallbacks overrides previous callbacks', () => {
    const registry = createFreshRegistry();
    const cbs1 = createCallbacks();
    const cbs2 = createCallbacks();
    registry.setCallbacks(cbs1);
    registry.setCallbacks(cbs2);

    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'reigh.test' }));

    expect(cbs1.onReservedCommand).not.toHaveBeenCalled();
    expect(cbs2.onReservedCommand).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Snapshot
// ---------------------------------------------------------------------------

describe('CommandRegistry — snapshot', () => {
  it('returns a snapshot with commands, keybindings, contextMenuItems, and diagnostics', () => {
    const registry = createFreshRegistry();
    registerTestCommand(registry, 'ext1', 'ext1.cmd', vi.fn());
    registry.ingestKeybindingContribution('ext1', makeKeybindingContribution({ key: 'Ctrl+K', command: 'ext1.cmd' }));
    registry.ingestContextMenuItemContribution('ext1', makeContextMenuContribution({ target: 'clip', command: 'ext1.cmd' }));

    const snap = registry.getSnapshot();

    expect(snap.commands).toHaveLength(1);
    expect(snap.commands[0].commandId).toBe('ext1.cmd');
    expect(snap.keybindings).toHaveLength(1);
    expect(snap.contextMenuItems).toHaveLength(1);
    expect(Array.isArray(snap.diagnostics)).toBe(true);
  });

  it('snapshot is frozen', () => {
    const registry = createFreshRegistry();
    registerTestCommand(registry, 'ext1', 'ext1.cmd', vi.fn());
    const snap = registry.getSnapshot();

    expect(() => {
      (snap as any).commands = [];
    }).toThrow();
  });

  it('snapshot getCommand/getKeybinding/getStatus methods work', () => {
    const registry = createFreshRegistry();
    registerTestCommand(registry, 'ext1', 'ext1.cmd', vi.fn());
    registry.ingestKeybindingContribution('ext1', makeKeybindingContribution({ key: 'Ctrl+K', command: 'ext1.cmd' }));

    const snap = registry.getSnapshot();

    expect(snap.getCommand('ext1.cmd')).toBeDefined();
    expect(snap.getCommand('ext1.cmd')!.commandId).toBe('ext1.cmd');
    expect(snap.getKeybinding('ctrl+k')).toBeDefined();
    expect(snap.getStatus('ext1.cmd').invocationCount).toBe(0);
  });

  it('returns same frozen snapshot reference on repeated calls (memoized)', () => {
    const registry = createFreshRegistry();
    registerTestCommand(registry, 'ext1', 'ext1.cmd', vi.fn());

    const snap1 = registry.getSnapshot();
    const snap2 = registry.getSnapshot();

    expect(snap1).toBe(snap2);
  });

  it('invalidates snapshot after mutation', () => {
    const registry = createFreshRegistry();
    const snap1 = registry.getSnapshot();

    registerTestCommand(registry, 'ext1', 'ext1.cmd', vi.fn());
    const snap2 = registry.getSnapshot();

    expect(snap1).not.toBe(snap2);
    expect(snap2.commands).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// Context menu contributions
// ---------------------------------------------------------------------------

describe('CommandRegistry — context menu contributions', () => {
  it('ingests context menu items scoped by target', () => {
    const registry = createFreshRegistry();
    registry.ingestContextMenuItemContribution('ext1', makeContextMenuContribution({ target: 'clip', command: 'ext1.cmd' }));
    registry.ingestContextMenuItemContribution('ext1', makeContextMenuContribution({ target: 'track', command: 'ext1.trackCmd' }));

    const snap = registry.getSnapshot();
    expect(snap.contextMenuItems).toHaveLength(2);

    const clipItems = snap.contextMenuItems.filter((i) => i.target === 'clip');
    const trackItems = snap.contextMenuItems.filter((i) => i.target === 'track');
    expect(clipItems).toHaveLength(1);
    expect(trackItems).toHaveLength(1);
  });

  it('diagnoses shot-group context-menu targets as reserved instead of registering them', () => {
    const registry = createFreshRegistry();

    registry.ingestContextMenuItemContribution('ext1', makeContextMenuContribution({
      id: 'cm.shotGroup' as any,
      target: 'shot-group' as any,
      command: 'ext1.shotGroup',
    }));

    expect(registry.getSnapshot().contextMenuItems).toHaveLength(0);
    expect(registry.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        severity: 'error',
        code: 'command-registry/reserved-context-menu-target',
        extensionId: 'ext1',
        contributionId: 'cm.shotGroup',
        message: expect.stringContaining('shot-group'),
      }),
    ]));
  });

  it('same-extension duplicate target+command overwrites previous', () => {
    const registry = createFreshRegistry();
    registry.ingestContextMenuItemContribution('ext1', makeContextMenuContribution({ target: 'clip', command: 'ext1.cmd', label: 'First' }));
    registry.ingestContextMenuItemContribution('ext1', makeContextMenuContribution({ target: 'clip', command: 'ext1.cmd', label: 'Second' }));

    const snap = registry.getSnapshot();
    const items = snap.contextMenuItems.filter((i) => i.target === 'clip' && i.extensionId === 'ext1');
    expect(items).toHaveLength(1);
    expect(items[0].label).toBe('Second');
  });

  it('different extensions can have same target+command (no conflict)', () => {
    const registry = createFreshRegistry();
    registry.ingestContextMenuItemContribution('ext1', makeContextMenuContribution({ target: 'clip', command: 'shared.cmd' }));
    registry.ingestContextMenuItemContribution('ext2', makeContextMenuContribution({ target: 'clip', command: 'shared.cmd' }));

    const snap = registry.getSnapshot();
    const clipItems = snap.contextMenuItems.filter((i) => i.target === 'clip');
    expect(clipItems).toHaveLength(2);
  });

  it('context menu items preserve optional fields (icon, when, order)', () => {
    const registry = createFreshRegistry();
    registry.ingestContextMenuItemContribution('ext1', makeContextMenuContribution({
      target: 'clip',
      command: 'ext1.cmd',
      label: 'My Item',
      when: 'target.clipId != null',
      order: 10,
      icon: 'star',
    }));

    const snap = registry.getSnapshot();
    const item = snap.contextMenuItems[0];
    expect(item.label).toBe('My Item');
    expect(item.when).toBe('target.clipId != null');
    expect(item.order).toBe(10);
    expect(item.icon).toBe('star');
  });
});

// ---------------------------------------------------------------------------
// Execute command with target context
// ---------------------------------------------------------------------------

describe('CommandRegistry — execute with target context', () => {
  it('passes target payload to the handler', async () => {
    const registry = createFreshRegistry();
    const handler = vi.fn();
    registerTestCommand(registry, 'ext1', 'ext1.cmd', handler);

    const target: TargetContextPayload = { target: 'clip', clipId: 'clip-1', trackId: 'track-1' };
    await registry.executeCommand('ext1.cmd', target);

    expect(handler).toHaveBeenCalled();
    const ctx = handler.mock.calls[0][0] as CommandRunContext;
    expect(ctx.commandId).toBe('ext1.cmd');
    expect(ctx.extensionId).toBe('ext1');
    expect(ctx.target).toEqual(target);
  });

  it('handler can be called without target', async () => {
    const registry = createFreshRegistry();
    const handler = vi.fn();
    registerTestCommand(registry, 'ext1', 'ext1.cmd', handler);

    await registry.executeCommand('ext1.cmd');

    const ctx = handler.mock.calls[0][0] as CommandRunContext;
    expect(ctx.commandId).toBe('ext1.cmd');
    expect(ctx.target).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// registerCommand with options
// ---------------------------------------------------------------------------

describe('CommandRegistry — registerCommand options', () => {
  it('updates label from registration options', () => {
    const registry = createFreshRegistry();
    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'ext1.cmd', label: 'Original' }));
    registry.registerCommand('ext1', 'ext1.cmd', vi.fn(), { label: 'Updated' });

    const cmd = registry.getCommand('ext1.cmd');
    expect(cmd!.label).toBe('Updated');
  });

  it('updates category from registration options', () => {
    const registry = createFreshRegistry();
    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'ext1.cmd' }));
    registry.registerCommand('ext1', 'ext1.cmd', vi.fn(), { category: 'MyCategory' });

    const cmd = registry.getCommand('ext1.cmd');
    expect(cmd!.category).toBe('MyCategory');
  });
});

// ---------------------------------------------------------------------------
// Dispose lifecycle
// ---------------------------------------------------------------------------

describe('CommandRegistry — dispose lifecycle', () => {
  it('after dispose, all operations become no-ops with diagnostics', () => {
    const registry = createFreshRegistry();
    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'ext1.cmd' }));
    registry.registerCommand('ext1', 'ext1.cmd', vi.fn());

    registry.dispose();

    // Operations after dispose should no-op
    registry.ingestCommandContribution('ext2', makeCommandContribution({ command: 'ext2.cmd' }));
    expect(registry.getCommand('ext2.cmd')).toBeUndefined();

    // Ingest after dispose emits diagnostic
    const disposedDiags = registry.diagnostics.filter((d) => d.code === 'command-registry/disposed');
    expect(disposedDiags.length).toBeGreaterThanOrEqual(1);
  });

  it('executeCommand returns false after dispose', async () => {
    const registry = createFreshRegistry();
    registerTestCommand(registry, 'ext1', 'ext1.cmd', vi.fn());
    registry.dispose();

    const ok = await registry.executeCommand('ext1.cmd');
    expect(ok).toBe(false);
  });

  it('registerCommand returns a no-op DisposeHandle after dispose', () => {
    const registry = createFreshRegistry();
    registry.ingestCommandContribution('ext1', makeCommandContribution({ command: 'ext1.cmd' }));
    registry.dispose();

    const handle = registry.registerCommand('ext1', 'ext1.cmd', vi.fn());
    expect(() => handle.dispose()).not.toThrow();
  });

  it('dispose is idempotent', () => {
    const registry = createFreshRegistry();
    registry.dispose();
    expect(() => registry.dispose()).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// getCommand / getKeybinding lookups
// ---------------------------------------------------------------------------

describe('CommandRegistry — lookup behavior', () => {
  it('getCommand returns undefined for unknown commands', () => {
    const registry = createFreshRegistry();
    expect(registry.getCommand('nonexistent')).toBeUndefined();
  });

  it('getKeybinding returns undefined for unknown keys', () => {
    const registry = createFreshRegistry();
    expect(registry.getKeybinding('ctrl+nonexistent')).toBeUndefined();
  });

  it('getCommand returns frozen entries', () => {
    const registry = createFreshRegistry();
    registerTestCommand(registry, 'ext1', 'ext1.cmd', vi.fn());

    const cmd = registry.getCommand('ext1.cmd')!;
    expect(() => {
      (cmd as any).label = 'hacked';
    }).toThrow();
  });

  it('getKeybinding returns frozen entries', () => {
    const registry = createFreshRegistry();
    registry.ingestKeybindingContribution('ext1', makeKeybindingContribution({ key: 'Ctrl+K', command: 'ext1.cmd' }));

    const kb = registry.getKeybinding('ctrl+k')!;
    expect(() => {
      (kb as any).key = 'hacked';
    }).toThrow();
  });
});

// ---------------------------------------------------------------------------
// Sync handler (non-async) support
// ---------------------------------------------------------------------------

describe('CommandRegistry — sync handler support', () => {
  it('supports synchronous handlers that return void', async () => {
    const registry = createFreshRegistry();
    const handler = vi.fn();
    registerTestCommand(registry, 'ext1', 'ext1.cmd', handler);

    const ok = await registry.executeCommand('ext1.cmd');
    expect(ok).toBe(true);
    expect(handler).toHaveBeenCalled();
  });

  it('sync handler that throws is caught', async () => {
    const registry = createFreshRegistry();
    const handler = vi.fn(() => {
      throw new Error('Sync error');
    });
    registerTestCommand(registry, 'ext1', 'ext1.cmd', handler);

    const ok = await registry.executeCommand('ext1.cmd');
    expect(ok).toBe(false);
    expect(registry.diagnostics.some((d) => d.code === 'command-registry/invoke-error')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Multiple extensions coexistence
// ---------------------------------------------------------------------------

describe('CommandRegistry — multiple extensions coexistence', () => {
  it('handles many commands across many extensions correctly', () => {
    const registry = createFreshRegistry();
    const extensions = ['ext.alpha', 'ext.beta', 'ext.gamma'];

    for (const extId of extensions) {
      for (let i = 0; i < 5; i++) {
        registerTestCommand(registry, extId, `${extId}.cmd${i}`, vi.fn());
      }
    }

    const snap = registry.getSnapshot();
    expect(snap.commands).toHaveLength(15);

    for (const extId of extensions) {
      const extCommands = snap.commands.filter((c) => c.extensionId === extId);
      expect(extCommands).toHaveLength(5);
    }
  });
});

// ---------------------------------------------------------------------------
// T19: Run-status preservation across unregisterAll
// ---------------------------------------------------------------------------

describe('CommandRegistry — run-status preservation across unregisterAll (T19)', () => {
  it('preserves run statuses for unrelated extensions after unregisterAll', async () => {
    const registry = createFreshRegistry();
    const handler1 = vi.fn();
    const handler2 = vi.fn();

    registerTestCommand(registry, 'ext1', 'ext1.cmd', handler1);
    registerTestCommand(registry, 'ext2', 'ext2.cmd', handler2);

    // Execute ext1's command twice to build up invocation history
    await registry.executeCommand('ext1.cmd');
    await registry.executeCommand('ext1.cmd');

    // Execute ext2's command once
    await registry.executeCommand('ext2.cmd');

    // Verify run statuses before unregister
    const ext1StatusBefore = registry.getStatus('ext1.cmd');
    expect(ext1StatusBefore.invocationCount).toBe(2);
    expect(ext1StatusBefore.lastRunOk).toBe(true);

    const ext2StatusBefore = registry.getStatus('ext2.cmd');
    expect(ext2StatusBefore.invocationCount).toBe(1);
    expect(ext2StatusBefore.lastRunOk).toBe(true);

    // Unregister ext2 — ext1's run status should survive
    registry.unregisterAll('ext2');

    // ext2's command should be gone
    expect(registry.getCommand('ext2.cmd')).toBeUndefined();
    // ext1's command should survive
    expect(registry.getCommand('ext1.cmd')).toBeDefined();

    // ext1's run status should be preserved
    const ext1StatusAfter = registry.getStatus('ext1.cmd');
    expect(ext1StatusAfter.invocationCount).toBe(2);
    expect(ext1StatusAfter.lastRunOk).toBe(true);
    expect(ext1StatusAfter.lastRunAt).toBeGreaterThan(0);
  });

  it('clears run statuses for the unregistered extension only', async () => {
    const registry = createFreshRegistry();
    registerTestCommand(registry, 'ext1', 'ext1.cmdA', vi.fn());
    registerTestCommand(registry, 'ext1', 'ext1.cmdB', vi.fn());
    registerTestCommand(registry, 'ext2', 'ext2.cmd', vi.fn());

    // Execute all commands once
    await registry.executeCommand('ext1.cmdA');
    await registry.executeCommand('ext1.cmdB');
    await registry.executeCommand('ext2.cmd');

    // Verify all have run statuses
    expect(registry.getStatus('ext1.cmdA').invocationCount).toBe(1);
    expect(registry.getStatus('ext1.cmdB').invocationCount).toBe(1);
    expect(registry.getStatus('ext2.cmd').invocationCount).toBe(1);

    // Unregister ext1
    registry.unregisterAll('ext1');

    // ext1 run statuses should be cleared (back to default zero-state)
    expect(registry.getStatus('ext1.cmdA').invocationCount).toBe(0);
    expect(registry.getStatus('ext1.cmdA').lastRunAt).toBe(0);
    expect(registry.getStatus('ext1.cmdB').invocationCount).toBe(0);

    // ext2's run status should be preserved
    expect(registry.getStatus('ext2.cmd').invocationCount).toBe(1);
    expect(registry.getStatus('ext2.cmd').lastRunOk).toBe(true);
  });

  it('re-enabling an extension does not create duplicate command entries', () => {
    const registry = createFreshRegistry();

    // First enable: register commands for ext1
    registerTestCommand(registry, 'ext1', 'ext1.cmd', vi.fn());
    registry.ingestKeybindingContribution('ext1', makeKeybindingContribution({
      key: 'Ctrl+K',
      command: 'ext1.cmd',
    }));
    registry.ingestContextMenuItemContribution('ext1', makeContextMenuContribution({
      target: 'clip',
      command: 'ext1.cmd',
    }));

    const snap1 = registry.getSnapshot();
    expect(snap1.commands.filter((c) => c.extensionId === 'ext1')).toHaveLength(1);
    expect(snap1.keybindings.filter((k) => k.extensionId === 'ext1')).toHaveLength(1);
    expect(snap1.contextMenuItems.filter((m) => m.extensionId === 'ext1')).toHaveLength(1);

    // Disable: unregister ext1
    registry.unregisterAll('ext1');

    const snap2 = registry.getSnapshot();
    expect(snap2.commands.filter((c) => c.extensionId === 'ext1')).toHaveLength(0);
    expect(snap2.keybindings.filter((k) => k.extensionId === 'ext1')).toHaveLength(0);
    expect(snap2.contextMenuItems.filter((m) => m.extensionId === 'ext1')).toHaveLength(0);

    // Re-enable: re-register the same commands
    registerTestCommand(registry, 'ext1', 'ext1.cmd', vi.fn());
    registry.ingestKeybindingContribution('ext1', makeKeybindingContribution({
      key: 'Ctrl+K',
      command: 'ext1.cmd',
    }));
    registry.ingestContextMenuItemContribution('ext1', makeContextMenuContribution({
      target: 'clip',
      command: 'ext1.cmd',
    }));

    const snap3 = registry.getSnapshot();
    expect(snap3.commands.filter((c) => c.extensionId === 'ext1')).toHaveLength(1);
    expect(snap3.keybindings.filter((k) => k.extensionId === 'ext1')).toHaveLength(1);
    expect(snap3.contextMenuItems.filter((m) => m.extensionId === 'ext1')).toHaveLength(1);
  });

  it('re-enabling an extension preserves unrelated extension commands', () => {
    const registry = createFreshRegistry();

    // Register ext1 and ext2
    registerTestCommand(registry, 'ext1', 'ext1.cmd', vi.fn());
    registerTestCommand(registry, 'ext2', 'ext2.cmd', vi.fn());
    registry.ingestKeybindingContribution('ext1', makeKeybindingContribution({ key: 'Ctrl+K', command: 'ext1.cmd' }));
    registry.ingestKeybindingContribution('ext2', makeKeybindingContribution({ key: 'Ctrl+J', command: 'ext2.cmd' }));

    // Disable ext1
    registry.unregisterAll('ext1');
    expect(registry.getCommand('ext1.cmd')).toBeUndefined();
    expect(registry.getCommand('ext2.cmd')).toBeDefined();
    expect(registry.getKeybinding('ctrl+j')).toBeDefined();

    // Re-enable ext1
    registerTestCommand(registry, 'ext1', 'ext1.cmd', vi.fn());
    registry.ingestKeybindingContribution('ext1', makeKeybindingContribution({ key: 'Ctrl+K', command: 'ext1.cmd' }));

    // Both should be present, no duplicates
    expect(registry.getCommand('ext1.cmd')).toBeDefined();
    expect(registry.getCommand('ext2.cmd')).toBeDefined();
    expect(registry.getKeybinding('ctrl+k')).toBeDefined();
    expect(registry.getKeybinding('ctrl+j')).toBeDefined();

    const snap = registry.getSnapshot();
    expect(snap.commands).toHaveLength(2);
    expect(snap.keybindings).toHaveLength(2);
  });
});
