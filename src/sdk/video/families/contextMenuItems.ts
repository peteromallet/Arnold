/**
 * Context menu item family contracts — manifest contribution declarations.
 *
 * Context menu item contributions add items to clip, track, and timeline-area
 * context menus. Fully bridged at M4 through the command dispatch system.
 *
 * @module video/families/contextMenuItems
 * @publicContract
 */

import type { ContributionId } from '../../ids';
import type { TargetContext } from '../../commands';

/** A context-menu item contribution for clip/track/timeline-area surfaces. */
export interface ContextMenuItemContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'contextMenuItem';
  /** The command identifier this menu item invokes. */
  command: string;
  /** Override label for the menu item (falls back to command contribution label). */
  label?: string;
  /** The target context(s) where this item appears. */
  target: TargetContext;
  /** Optional visibility predicate (evaluated by host). */
  when?: string;
  /** Lower values sort first. Default 0. */
  order?: number;
  /** Optional icon name for the menu item. */
  icon?: string;
}
