/**
 * Command family contracts — manifest contribution declarations.
 *
 * Command contributions declare palette-invocable actions with optional
 * target context dispatch (clip, clip-selection, track, timeline-area).
 * Fully bridged at M4 with host adapter, keybinding, and context-menu wiring.
 *
 * @module video/families/commands
 * @publicContract
 */

import type { ContributionId } from '../../ids';

/** A command contribution in an extension manifest. */
export interface CommandContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'command';
  /** The command identifier (e.g. 'myExtension.doSomething'). */
  command: string;
  /** Human-readable label for the command palette. */
  label: string;
  /** Category for palette grouping. */
  category?: string;
  /** Optional visibility predicate (evaluated by host). */
  when?: string;
  /** Lower values sort first. Default 0. */
  order?: number;
}
