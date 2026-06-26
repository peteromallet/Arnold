/**
 * Keybinding family contracts — manifest contribution declarations.
 *
 * Keybinding contributions bind keyboard shortcuts to commands with
 * platform-aware key notation. Fully bridged at M4 through the command
 * dispatch system.
 *
 * @module video/families/keybindings
 * @publicContract
 */

import type { ContributionId } from '../../ids';

/** A keybinding contribution that binds a keyboard shortcut to a command. */
export interface KeybindingContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'keybinding';
  /** The command identifier this keybinding triggers. */
  command: string;
  /**
   * Platform-aware key notation (e.g. 'CtrlOrCmd+K', 'Alt+Shift+R').
   * Modifier keys: CtrlOrCmd, Ctrl, Cmd, Alt, Shift.
   * Key names are case-insensitive and normalized at registration time.
   */
  key: string;
  /** Optional visibility predicate (evaluated by host). */
  when?: string;
  /** Lower values sort first. Default 0. */
  order?: number;
}
