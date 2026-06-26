/**
 * Context menu item real compatibility adapter.
 *
 * @module families/contextMenuItemAdapter
 */

import { createCompatibilityAdapter } from './compatibilityAdapterFactory';

export const contextMenuItemAdapter = createCompatibilityAdapter({
  adapterId: 'contextMenuItem-default',
  kind: 'contextMenuItem',
  maturity: 'host-integrated',
  description: 'Compatibility adapter for M4 context menu item contributions.',
});
