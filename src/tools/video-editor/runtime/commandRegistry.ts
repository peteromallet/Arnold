/**
 * Pure command registry foundation — provider-scoped, in-memory, unit-testable.
 *
 * Responsibilities:
 * - Imperative command handler registration during activate()
 * - Declarative command/keybinding/context-menu contribution ingestion
 * - Reserved `reigh.*` command rejection
 * - First-registered-wins command & keybinding conflicts (among extensions)
 * - Platform-aware keybinding normalization
 * - Built-in reserved shortcut enforcement
 * - Command invocation with run context, last-run status, diagnostics, and
 *   failure toast hooks (pure host callbacks).
 *
 * One registry per editor provider mount.  Wired into the lifecycle so that
 * `unregisterAll(extensionId)` tears down every contribution for a disposed
 * extension.
 */

import type {
  DisposeHandle,
  ExtensionDiagnostic,
  DiagnosticSeverity,
  CommandContribution,
  KeybindingContribution,
  ContextMenuItemContribution,
  CommandHandler,
  CommandRunContext,
  CommandRegistrationOptions,
  TargetContext,
  TargetContextPayload,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Public registry shapes
// ---------------------------------------------------------------------------

/** A single resolved command entry (frozen for snapshot consumers). */
export interface CommandEntry {
  /** Fully-qualified command ID, e.g. "myExtension.doSomething". */
  readonly commandId: string;
  /** The extension that registered the handler. */
  readonly extensionId: string;
  /** Human-readable label (from contribution or registration options). */
  readonly label: string;
  /** Category for palette grouping. */
  readonly category?: string;
  /** Optional visibility predicate. */
  readonly when?: string;
  /** Palette sort order. */
  readonly order: number;
}

/** A single resolved keybinding entry. */
export interface KeybindingEntry {
  /** The command this keybinding triggers. */
  readonly commandId: string;
  /** The extension that owns this keybinding. */
  readonly extensionId: string;
  /** Normalized key notation. */
  readonly key: string;
  /** Optional visibility predicate. */
  readonly when?: string;
  /** Sort order. */
  readonly order: number;
}

/** A single resolved context menu item. */
export interface ContextMenuItemEntry {
  /** The command this menu item invokes. */
  readonly commandId: string;
  /** The extension that owns this item. */
  readonly extensionId: string;
  /** Override label (falls back to command label). */
  readonly label?: string;
  /** The target context where this item appears. */
  readonly target: TargetContext;
  /** Optional visibility predicate. */
  readonly when?: string;
  /** Sort order. */
  readonly order: number;
  /** Optional icon name. */
  readonly icon?: string;
}

/** Execution status for the most recent invocation of a command. */
export interface CommandRunStatus {
  /** The total number of invocations (successful + failed). */
  readonly invocationCount: number;
  /** Timestamp of the most recent invocation (epoch ms), or 0 if never invoked. */
  readonly lastRunAt: number;
  /** Whether the most recent invocation completed without errors. */
  readonly lastRunOk: boolean;
  /** Error message from the most recent failed invocation, or null. */
  readonly lastError: string | null;
}

/** Frozen snapshot of the entire command registry for external consumers. */
export interface CommandRegistrySnapshot {
  /** All registered commands, ordered by extensionId → commandId. */
  readonly commands: readonly CommandEntry[];
  /** All registered keybindings, ordered by normalized key → extensionId. */
  readonly keybindings: readonly KeybindingEntry[];
  /** All registered context menu items, ordered by target → extensionId → commandId. */
  readonly contextMenuItems: readonly ContextMenuItemEntry[];
  /** Diagnostics emitted by the registry. */
  readonly diagnostics: readonly ExtensionDiagnostic[];
  /** Lookup a command entry by fully-qualified command ID. */
  readonly getCommand: (commandId: string) => CommandEntry | undefined;
  /** Lookup keybinding by normalized key string. */
  readonly getKeybinding: (normalizedKey: string) => KeybindingEntry | undefined;
  /** Lookup execution status for a command. */
  readonly getStatus: (commandId: string) => CommandRunStatus;
}

// ---------------------------------------------------------------------------
// Built-in reserved keybindings
//
// Derived from useKeyboardShortcuts.ts and useGlobalPaneShortcuts.ts.
// Extensions must not register these shortcuts. Registered attempts produce
// a diagnostic.
// ---------------------------------------------------------------------------

/** Canonical set of reserved built-in keybindings (normalized form). */
export const BUILT_IN_RESERVED_KEYBINDINGS: ReadonlySet<string> = new Set([
  // Editor commands (useKeyboardShortcuts.ts)
  'ctrl+shift+z',       // Redo (cross-platform: CtrlOrCmd+Shift+Z)
  'ctrl+z',             // Undo (cross-platform: CtrlOrCmd+Z)
  'ctrl+y',             // Redo (Windows style)
  'arrowleft',          // Seek back 1s
  'arrowright',         // Seek forward 1s
  'arrowup',            // Move clip up
  'arrowdown',          // Move clip down
  'ctrl+a',             // Select all clips
  ' ',                  // Play/pause (Space)
  'm',                  // Mute toggle
  's',                  // Split clip
  'backspace',          // Delete clip
  'delete',             // Delete clip
  'escape',             // Clear selection

  // Pane shortcuts (useGlobalPaneShortcuts.ts)
  'alt+w',              // Toggle editor pane
  'alt+s',              // Toggle generations pane
  'alt+a',              // Toggle shots pane
  'alt+d',              // Toggle tasks pane
  'alt+shift+w',        // Navigate to video editor
  'alt+shift+s',        // Navigate to image generation

  // Command palette trigger (locked)
  'ctrl+shift+p',       // Command palette (CtrlOrCmd+Shift+P)
]);

// ---------------------------------------------------------------------------
// Reserved command ID prefix
// ---------------------------------------------------------------------------

const RESERVED_COMMAND_PREFIX = 'reigh.';

/** True when commandId starts with "reigh." */
export function isReservedCommandId(commandId: string): boolean {
  return commandId.startsWith(RESERVED_COMMAND_PREFIX);
}

// ---------------------------------------------------------------------------
// Keybinding normalization
// ---------------------------------------------------------------------------

/**
 * Supported modifier keys in platform-aware key notation.
 * "CtrlOrCmd" is a special cross-platform modifier resolved by the host at
 * runtime (maps to Cmd on macOS, Ctrl otherwise).
 */
type KnownModifier = 'alt' | 'ctrl' | 'ctrlOrCmd' | 'shift';

const MODIFIER_ORDER: Record<KnownModifier, number> = {
  alt: 0,
  ctrl: 1,
  ctrlOrCmd: 2,
  shift: 3,
};

/** Look up a known modifier by its lowercase form. */
function resolveModifier(lowerPart: string): KnownModifier | undefined {
  if (lowerPart === 'alt') return 'alt';
  if (lowerPart === 'ctrl') return 'ctrl';
  if (lowerPart === 'ctrlOrCmd' || lowerPart === 'ctrlorcmd') return 'ctrlOrCmd';
  if (lowerPart === 'shift') return 'shift';
  return undefined;
}

/** Regular expression matching a valid keybinding notation string. */
const KEYBINDING_RE = /^[a-zA-Z][a-zA-Z0-9]*(?:\+[a-zA-Z][a-zA-Z0-9]*)*$/;

/**
 * Normalize a keybinding notation string.
 *
 * Rules:
 * - Lowercase everything
 * - Split on "+"
 * - Sort modifiers alphabetically (Alt, Ctrl, CtrlOrCmd, Shift)
 * - Preserve non-modifier key parts in original order
 * - Trim whitespace
 * - CtrlOrCmd is the canonical form for the cross-platform modifier
 *   (resolves Cmd on macOS, Ctrl otherwise at runtime).
 *
 * Returns the normalized key string, or null if the notation is invalid.
 */
export function normalizeKeybinding(notation: string): string | null {
  if (typeof notation !== 'string') return null;

  const trimmed = notation.trim();
  if (!trimmed) return null;

  // Quick check: basic grammar (case-sensitive for alphanumeric parts)
  if (!KEYBINDING_RE.test(trimmed)) {
    return null;
  }

  const parts = trimmed.split('+').map((p) => p.trim().toLowerCase());

  // Collect modifiers and key parts separately
  const modifiers: KnownModifier[] = [];
  const keyParts: string[] = [];

  for (const part of parts) {
    if (!part) return null; // empty segment from malformed input
    const mod = resolveModifier(part);
    if (mod) {
      modifiers.push(mod);
    } else {
      keyParts.push(part);
    }
  }

  // Sort modifiers by canonical order
  modifiers.sort((a, b) => MODIFIER_ORDER[a] - MODIFIER_ORDER[b]);

  // Reassemble: sorted modifiers + key parts in original order
  const result = [...modifiers, ...keyParts].join('+');

  return result;
}

/**
 * Normalize a key, apply CtrlOrCmd→ctrl canonicalization for reserved-list
 * comparisons (since CtrlOrCmd means Ctrl/Cmd, but reserved shortcuts use
 * the lower-level ctrl notation).
 */
function normalizeForReservedCheck(normalized: string): string {
  return normalized.replace(/ctrlOrCmd\+/g, 'ctrl+');
}

/**
 * Check if a normalized keybinding is reserved (built-in or host-owned).
 * Handles CtrlOrCmd→Ctrl canonicalization for comparison against the
 * built-in reserved set (which uses the concrete `ctrl` notation).
 */
export function isReservedKeybinding(normalizedKey: string): boolean {
  const canonical = normalizeForReservedCheck(normalizedKey);
  return BUILT_IN_RESERVED_KEYBINDINGS.has(canonical);
}

// ---------------------------------------------------------------------------
// Internal state
// ---------------------------------------------------------------------------

interface InternalCommand {
  commandId: string;
  extensionId: string;
  label: string;
  category?: string;
  when?: string;
  order: number;
  handler: CommandHandler | null; // null until registerCommand() is called
}

interface InternalKeybinding {
  key: string; // normalized
  commandId: string;
  extensionId: string;
  when?: string;
  order: number;
}

interface InternalContextMenuItem {
  commandId: string;
  extensionId: string;
  label?: string;
  target: TargetContext;
  when?: string;
  order: number;
  icon?: string;
}

interface InternalCommandRunStatus {
  invocationCount: number;
  lastRunAt: number;
  lastRunOk: boolean;
  lastError: string | null;
}

const VALID_CONTEXT_MENU_TARGETS = new Set<TargetContext>([
  'clip',
  'clip-selection',
  'track',
  'timeline-area',
]);

// ---------------------------------------------------------------------------
// Emit helper
// ---------------------------------------------------------------------------

function emitDiagnostic(
  diagnostics: ExtensionDiagnostic[],
  severity: DiagnosticSeverity,
  code: string,
  message: string,
  extensionId?: string,
  contributionId?: string,
  detail?: Record<string, unknown>,
): void {
  diagnostics.push(Object.freeze({
    severity,
    code,
    message,
    ...(extensionId ? { extensionId } : {}),
    ...(contributionId ? { contributionId } : {}),
    ...(detail ? { detail } : {}),
  }));
}

// ---------------------------------------------------------------------------
// Public interface
// ---------------------------------------------------------------------------

/**
 * Callbacks for toast and progress reporting from the command runtime.
 * The host wires these at provider mount time so the pure registry can
 * signal failures to the UI without importing React or host components.
 */
export interface CommandRegistryCallbacks {
  /** Called when a command handler throws or rejects. */
  onCommandFailure?: (commandId: string, error: Error, extensionId: string) => void;
  /** Called when a reserved command ID is rejected. */
  onReservedCommand?: (commandId: string, extensionId: string) => void;
  /** Called when a reserved keybinding is rejected. */
  onReservedKeybinding?: (key: string, extensionId: string, commandId: string) => void;
  /** Called when a duplicate command registration is diagnosed. */
  onDuplicateCommand?: (commandId: string, originalExtension: string, conflictingExtension: string) => void;
  /** Called when a keybinding conflict is diagnosed. */
  onKeybindingConflict?: (key: string, originalExtension: string, conflictingExtension: string) => void;
  /** Called when a context-menu command is rejected because its snapshotted target is stale. */
  onContextMenuStaleTarget?: (commandId: string, extensionId: string, reason: string) => void;
}

export interface CommandRegistry {
  // ---- Imperative handler registration -----------------------------------

  /**
   * Register a command handler imperatively during activate().
   *
   * The command must have been declared via a CommandContribution in the
   * extension manifest. Returns a DisposeHandle that unregisters the handler
   * (but not the command declaration itself).
   */
  registerCommand(
    extensionId: string,
    commandId: string,
    handler: CommandHandler,
    options?: CommandRegistrationOptions,
  ): DisposeHandle;

  // ---- Declarative contribution ingestion --------------------------------

  /**
   * Ingest a CommandContribution from an extension manifest.
   * Called during synchronization when contributions are discovered.
   *
   * - Reserved `reigh.*` command IDs are rejected with diagnostics.
   * - Duplicate command IDs (already registered by a different extension)
   *   are rejected (first-registered-wins).
   * - Duplicate contributions from the same extension are treated as
   *   overwrites (last wins within the same extension).
   */
  ingestCommandContribution(extensionId: string, contribution: CommandContribution): void;

  /** Ingest a KeybindingContribution. */
  ingestKeybindingContribution(extensionId: string, contribution: KeybindingContribution): void;

  /** Ingest a ContextMenuItemContribution. */
  ingestContextMenuItemContribution(extensionId: string, contribution: ContextMenuItemContribution): void;

  // ---- Command lookup & invocation ---------------------------------------

  /** Look up a command entry by fully-qualified ID. */
  getCommand(commandId: string): CommandEntry | undefined;

  /** Look up a keybinding by normalized key string. */
  getKeybinding(normalizedKey: string): KeybindingEntry | undefined;

  /** Get execution status for a command (never returns null — defaults to zero state). */
  getStatus(commandId: string): CommandRunStatus;

  /**
   * Execute a command by fully-qualified ID.
   *
   * Handles missing commands, commands without handlers (disabled),
   * and handler errors gracefully — all are captured as diagnostics
   * and surfaced through failure callbacks.
   *
   * @param commandId  The fully-qualified command ID to invoke.
   * @param target     Optional target context payload for context-menu invocations.
   * @returns true if the handler was invoked without throwing, false otherwise.
   */
  executeCommand(commandId: string, target?: TargetContextPayload): Promise<boolean>;

  /** Emit a diagnostic for a context-menu item whose snapshotted target is no longer current. */
  diagnoseContextMenuStaleTarget(
    commandId: string,
    extensionId: string,
    target: TargetContextPayload,
    reason: string,
  ): void;

  // ---- Diagnostics -------------------------------------------------------

  /** All diagnostics emitted by the registry. */
  readonly diagnostics: readonly ExtensionDiagnostic[];

  /** Subscribe to registry diagnostic changes. */
  subscribe(listener: () => void): DisposeHandle;

  // ---- Snapshot ----------------------------------------------------------

  /** Return a frozen snapshot suitable for external consumers. */
  getSnapshot(): CommandRegistrySnapshot;

  // ---- Lifecycle ---------------------------------------------------------

  /**
   * Remove every command, keybinding, context menu item, and handler
   * for a given extension. Called during extension disposal.
   */
  unregisterAll(extensionId: string): void;

  /** Set callbacks for toast/diagnostic integration with the host UI. */
  setCallbacks(callbacks: CommandRegistryCallbacks): void;

  /** Dispose the entire registry. Terminal. */
  dispose(): void;
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

export function createCommandRegistry(): CommandRegistry {
  // commandId → InternalCommand
  const commands = new Map<string, InternalCommand>();

  // normalizedKey → InternalKeybinding (only one winner per key)
  const keybindings = new Map<string, InternalKeybinding>();

  // target → context menu items array
  const contextMenuItems = new Map<TargetContext, InternalContextMenuItem[]>();

  // commandId → InternalCommandRunStatus
  const runStatuses = new Map<string, InternalCommandRunStatus>();

  const diagnostics: ExtensionDiagnostic[] = [];
  const listeners = new Set<() => void>();
  let callbacks: CommandRegistryCallbacks = {};
  let disposed = false;
  let frozenSnapshot: CommandRegistrySnapshot | null = null;

  // ---- helpers -----------------------------------------------------------

  function guardDisposed(operation: string): boolean {
    if (disposed) {
      // Silently no-op; emit a diagnostic so operators can see post-dispose misuse.
      addDiagnostic('warning',
        'command-registry/disposed',
        `CommandRegistry operation "${operation}" called after dispose.`,
      );
      return true;
    }
    return false;
  }

  function invalidateSnapshot(): void {
    frozenSnapshot = null;
  }

  function notifyListeners(): void {
    for (const listener of listeners) {
      listener();
    }
  }

  function addDiagnostic(
    severity: DiagnosticSeverity,
    code: string,
    message: string,
    extensionId?: string,
    contributionId?: string,
    detail?: Record<string, unknown>,
  ): void {
    emitDiagnostic(diagnostics, severity, code, message, extensionId, contributionId, detail);
    invalidateSnapshot();
    notifyListeners();
  }

  function getOrCreateStatus(commandId: string): InternalCommandRunStatus {
    let s = runStatuses.get(commandId);
    if (!s) {
      s = { invocationCount: 0, lastRunAt: 0, lastRunOk: true, lastError: null };
      runStatuses.set(commandId, s);
    }
    return s;
  }

  function ensureContextMenuTarget(target: TargetContext): InternalContextMenuItem[] {
    let items = contextMenuItems.get(target);
    if (!items) {
      items = [];
      contextMenuItems.set(target, items);
    }
    return items;
  }

  // ---- ingestCommandContribution -----------------------------------------

  function ingestCommandContribution(
    extensionId: string,
    contribution: CommandContribution,
  ): void {
    if (guardDisposed('ingestCommandContribution')) return;

    const commandId = contribution.command;

    // Reserved check
    if (isReservedCommandId(commandId)) {
      addDiagnostic('error',
        'command-registry/reserved-command',
        `Command "${commandId}" (extension "${extensionId}") uses reserved "reigh." prefix.`,
        extensionId,
        contribution.id,
      );
      callbacks.onReservedCommand?.(commandId, extensionId);
      return;
    }

    // Conflict check: first-registered-wins (across extensions)
    const existing = commands.get(commandId);
    if (existing && existing.extensionId !== extensionId) {
      addDiagnostic('warning',
        'command-registry/duplicate-command',
        `Command "${commandId}" already registered by extension "${existing.extensionId}". Extension "${extensionId}" cannot override it.`,
        extensionId,
        contribution.id,
        { originalExtension: existing.extensionId },
      );
      callbacks.onDuplicateCommand?.(commandId, existing.extensionId, extensionId);
      return;
    }

    // Same-extension re-registration: overwrite metadata (handler preserved if already set)
    const existingSameExt = commands.get(commandId);
    const existingHandler = existingSameExt?.handler ?? null;

    commands.set(commandId, {
      commandId,
      extensionId,
      label: contribution.label,
      category: contribution.category,
      when: contribution.when,
      order: contribution.order ?? 0,
      handler: existingHandler,
    });

    invalidateSnapshot();
  }

  // ---- ingestKeybindingContribution --------------------------------------

  function ingestKeybindingContribution(
    extensionId: string,
    contribution: KeybindingContribution,
  ): void {
    if (guardDisposed('ingestKeybindingContribution')) return;

    const normalized = normalizeKeybinding(contribution.key);
    if (!normalized) {
      addDiagnostic('error',
        'command-registry/invalid-keybinding',
        `Invalid keybinding notation "${contribution.key}" from extension "${extensionId}".`,
        extensionId,
        contribution.id,
      );
      return;
    }

    // Check reserved built-in shortcuts
    if (isReservedKeybinding(normalized)) {
      addDiagnostic('error',
        'command-registry/reserved-keybinding',
        `Keybinding "${contribution.key}" (normalized: "${normalized}") is reserved. Extension "${extensionId}" cannot use it.`,
        extensionId,
        contribution.id,
      );
      callbacks.onReservedKeybinding?.(normalized, extensionId, contribution.command);
      return;
    }

    const existing = keybindings.get(normalized);
    if (existing && existing.extensionId !== extensionId) {
      addDiagnostic('warning',
        'command-registry/keybinding-conflict',
        `Keybinding "${normalized}" already bound to command "${existing.commandId}" by extension "${existing.extensionId}". Extension "${extensionId}" cannot override it.`,
        extensionId,
        contribution.id,
        { originalExtension: existing.extensionId, existingCommand: existing.commandId },
      );
      callbacks.onKeybindingConflict?.(normalized, existing.extensionId, extensionId);
      return;
    }

    keybindings.set(normalized, {
      key: normalized,
      commandId: contribution.command,
      extensionId,
      when: contribution.when,
      order: contribution.order ?? 0,
    });

    invalidateSnapshot();
  }

  // ---- ingestContextMenuItemContribution ---------------------------------

  function ingestContextMenuItemContribution(
    extensionId: string,
    contribution: ContextMenuItemContribution,
  ): void {
    if (guardDisposed('ingestContextMenuItemContribution')) return;

    if (!VALID_CONTEXT_MENU_TARGETS.has(contribution.target)) {
      addDiagnostic('error',
        'command-registry/reserved-context-menu-target',
        `Context menu target "${contribution.target}" from extension "${extensionId}" is reserved or unsupported.`,
        extensionId,
        contribution.id,
        { target: contribution.target },
      );
      return;
    }

    const items = ensureContextMenuTarget(contribution.target);

    // Remove any existing item for the same extension + command + target
    // (same-extension overwrite semantics)
    const existingIdx = items.findIndex(
      (i) => i.extensionId === extensionId && i.commandId === contribution.command,
    );
    if (existingIdx !== -1) {
      items.splice(existingIdx, 1);
    }

    items.push({
      commandId: contribution.command,
      extensionId,
      label: contribution.label,
      target: contribution.target,
      when: contribution.when,
      order: contribution.order ?? 0,
      icon: contribution.icon,
    });

    invalidateSnapshot();
  }

  // ---- registerCommand ---------------------------------------------------

  function registerCommand(
    extensionId: string,
    commandId: string,
    handler: CommandHandler,
    options?: CommandRegistrationOptions,
  ): DisposeHandle {
    if (guardDisposed('registerCommand')) {
      return { dispose() {} };
    }

    // Must have a command contribution already ingested
    const cmd = commands.get(commandId);
    if (!cmd) {
      addDiagnostic('warning',
        'command-registry/handler-no-command',
        `Cannot register handler for command "${commandId}" — no matching CommandContribution found for extension "${extensionId}".`,
        extensionId,
      );
      return { dispose() {} };
    }

    if (cmd.extensionId !== extensionId) {
      addDiagnostic('error',
        'command-registry/handler-wrong-extension',
        `Cannot register handler for command "${commandId}" — it is owned by extension "${cmd.extensionId}", not "${extensionId}".`,
        extensionId,
      );
      return { dispose() {} };
    }

    // Update command metadata from options
    if (options?.label !== undefined) {
      cmd.label = options.label;
    }
    if (options?.category !== undefined) {
      cmd.category = options.category;
    }

    // Set the handler
    cmd.handler = handler;
    invalidateSnapshot();

    let handlerDisposed = false;
    return {
      dispose(): void {
        if (handlerDisposed) return;
        handlerDisposed = true;

        const current = commands.get(commandId);
        if (current && current.extensionId === extensionId) {
          current.handler = null;
          invalidateSnapshot();
        }
      },
    };
  }

  // ---- lookup ------------------------------------------------------------

  function getCommand(commandId: string): CommandEntry | undefined {
    const cmd = commands.get(commandId);
    if (!cmd) return undefined;

    return Object.freeze({
      commandId: cmd.commandId,
      extensionId: cmd.extensionId,
      label: cmd.label,
      category: cmd.category,
      when: cmd.when,
      order: cmd.order,
    });
  }

  function getKeybinding(normalizedKey: string): KeybindingEntry | undefined {
    const kb = keybindings.get(normalizedKey);
    if (!kb) return undefined;

    return Object.freeze({
      commandId: kb.commandId,
      extensionId: kb.extensionId,
      key: kb.key,
      when: kb.when,
      order: kb.order,
    });
  }

  function getStatus(commandId: string): CommandRunStatus {
    const s = getOrCreateStatus(commandId);
    return Object.freeze({ ...s });
  }

  // ---- invocation --------------------------------------------------------

  async function executeCommand(
    commandId: string,
    target?: TargetContextPayload,
  ): Promise<boolean> {
    if (guardDisposed('executeCommand')) return false;

    const cmd = commands.get(commandId);
    if (!cmd) {
      addDiagnostic('warning',
        'command-registry/invoke-unknown-command',
        `Cannot execute unknown command "${commandId}".`,
      );
      return false;
    }

    if (!cmd.handler) {
      addDiagnostic('info',
        'command-registry/invoke-no-handler',
        `Command "${commandId}" has no registered handler and cannot be executed.`,
        cmd.extensionId,
      );
      return false;
    }

    const status = getOrCreateStatus(commandId);
    const ctx: CommandRunContext = Object.freeze({
      commandId,
      extensionId: cmd.extensionId,
      ...(target ? { target } : {}),
    });

    try {
      await cmd.handler(ctx);
      status.invocationCount++;
      status.lastRunAt = Date.now();
      status.lastRunOk = true;
      status.lastError = null;
      return true;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      status.invocationCount++;
      status.lastRunAt = Date.now();
      status.lastRunOk = false;
      status.lastError = error.message;

      addDiagnostic('error',
        'command-registry/invoke-error',
        `Command "${commandId}" handler threw: ${error.message}`,
        cmd.extensionId,
        undefined,
        { stack: error.stack },
      );

      callbacks.onCommandFailure?.(commandId, error, cmd.extensionId);
      return false;
    }
  }

  function diagnoseContextMenuStaleTarget(
    commandId: string,
    extensionId: string,
    target: TargetContextPayload,
    reason: string,
  ): void {
    if (guardDisposed('diagnoseContextMenuStaleTarget')) return;

    addDiagnostic('warning',
      'command-registry/context-menu-stale-target',
      `Context menu command "${commandId}" was not invoked because its target is stale: ${reason}`,
      extensionId,
      undefined,
      { commandId, target, reason },
    );
    callbacks.onContextMenuStaleTarget?.(commandId, extensionId, reason);
  }

  // ---- snapshot ----------------------------------------------------------

  function buildCommandsSnapshot(): CommandEntry[] {
    const result: CommandEntry[] = [];
    commands.forEach((cmd) => {
      result.push({
        commandId: cmd.commandId,
        extensionId: cmd.extensionId,
        label: cmd.label,
        category: cmd.category,
        when: cmd.when,
        order: cmd.order,
      });
    });
    result.sort((a, b) => {
      const extCmp = a.extensionId.localeCompare(b.extensionId);
      if (extCmp !== 0) return extCmp;
      return a.commandId.localeCompare(b.commandId);
    });
    return result;
  }

  function buildKeybindingsSnapshot(): KeybindingEntry[] {
    const result: KeybindingEntry[] = [];
    keybindings.forEach((kb) => {
      result.push({
        commandId: kb.commandId,
        extensionId: kb.extensionId,
        key: kb.key,
        when: kb.when,
        order: kb.order,
      });
    });
    result.sort((a, b) => {
      const keyCmp = a.key.localeCompare(b.key);
      if (keyCmp !== 0) return keyCmp;
      return a.extensionId.localeCompare(b.extensionId);
    });
    return result;
  }

  function buildContextMenuItemsSnapshot(): ContextMenuItemEntry[] {
    const result: ContextMenuItemEntry[] = [];
    contextMenuItems.forEach((items) => {
      for (const item of items) {
        result.push({
          commandId: item.commandId,
          extensionId: item.extensionId,
          label: item.label,
          target: item.target,
          when: item.when,
          order: item.order,
          icon: item.icon,
        });
      }
    });
    result.sort((a, b) => {
      const tgtCmp = a.target.localeCompare(b.target);
      if (tgtCmp !== 0) return tgtCmp;
      const extCmp = a.extensionId.localeCompare(b.extensionId);
      if (extCmp !== 0) return extCmp;
      return a.commandId.localeCompare(b.commandId);
    });
    return result;
  }

  function getSnapshot(): CommandRegistrySnapshot {
    if (frozenSnapshot) return frozenSnapshot;

    const commandsSnap: readonly CommandEntry[] = Object.freeze(
      buildCommandsSnapshot().map((c) => Object.freeze(c) as CommandEntry),
    );
    const keybindingsSnap: readonly KeybindingEntry[] = Object.freeze(
      buildKeybindingsSnapshot().map((k) => Object.freeze(k) as KeybindingEntry),
    );
    const contextMenuItemsSnap: readonly ContextMenuItemEntry[] = Object.freeze(
      buildContextMenuItemsSnapshot().map((m) => Object.freeze(m) as ContextMenuItemEntry),
    );

    const snap: CommandRegistrySnapshot = {
      commands: commandsSnap,
      keybindings: keybindingsSnap,
      contextMenuItems: contextMenuItemsSnap,
      diagnostics: Object.freeze([...diagnostics]),
      getCommand: (commandId: string) => getCommand(commandId),
      getKeybinding: (normalizedKey: string) => getKeybinding(normalizedKey),
      getStatus: (commandId: string) => getStatus(commandId),
    };

    frozenSnapshot = Object.freeze(snap) as CommandRegistrySnapshot;

    return frozenSnapshot;
  }

  // ---- lifecycle ---------------------------------------------------------

  function unregisterAll(extensionId: string): void {
    if (guardDisposed('unregisterAll')) return;

    // Collect command IDs for this extension before removal so we can
    // scope run-status cleanup to only the disposed extension's commands.
    const removedCommandIds: string[] = [];
    commands.forEach((cmd, id) => {
      if (cmd.extensionId === extensionId) {
        removedCommandIds.push(id);
      }
    });

    // Remove all commands for this extension
    let cmdCount = 0;
    for (const id of removedCommandIds) {
      commands.delete(id);
      cmdCount++;
    }

    // Remove all keybindings for this extension
    let kbCount = 0;
    keybindings.forEach((kb, key) => {
      if (kb.extensionId === extensionId) {
        keybindings.delete(key);
        kbCount++;
      }
    });

    // Remove all context menu items for this extension
    let cmCount = 0;
    contextMenuItems.forEach((items, target) => {
      const before = items.length;
      const filtered = items.filter((i) => i.extensionId !== extensionId);
      cmCount += before - filtered.length;
      if (filtered.length === 0) {
        contextMenuItems.delete(target);
      } else {
        contextMenuItems.set(target, filtered);
      }
    });

    // Clean up run statuses only for the removed commands, preserving
    // invocation history for unrelated extensions.
    for (const id of removedCommandIds) {
      runStatuses.delete(id);
    }

    if (cmdCount > 0 || kbCount > 0 || cmCount > 0) {
      invalidateSnapshot();
    }
  }

  function setCallbacks(cbs: CommandRegistryCallbacks): void {
    callbacks = { ...cbs };
  }

  function dispose(): void {
    if (disposed) return;
    disposed = true;

    commands.clear();
    keybindings.clear();
    contextMenuItems.clear();
    runStatuses.clear();
    callbacks = {};
    invalidateSnapshot();

    addDiagnostic('info',
      'command-registry/disposed',
      'CommandRegistry disposed.',
    );
  }

  function subscribe(listener: () => void): DisposeHandle {
    listeners.add(listener);
    return {
      dispose(): void {
        listeners.delete(listener);
      },
    };
  }

  // ---- assemble ----------------------------------------------------------

  const registry: CommandRegistry = {
    registerCommand,
    ingestCommandContribution,
    ingestKeybindingContribution,
    ingestContextMenuItemContribution,
    getCommand,
    getKeybinding,
    getStatus,
    executeCommand,
    diagnoseContextMenuStaleTarget,
    get diagnostics() {
      return diagnostics;
    },
    subscribe,
    getSnapshot,
    unregisterAll,
    setCallbacks,
    dispose,
  };

  return registry;
}
