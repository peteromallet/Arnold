/**
 * Keybinding real compatibility adapter.
 *
 * @module families/keybindingAdapter
 */

import { createCompatibilityAdapter } from './compatibilityAdapterFactory';

export const keybindingAdapter = createCompatibilityAdapter({
  adapterId: 'keybinding-default',
  kind: 'keybinding',
  maturity: 'host-integrated',
  description: 'Compatibility adapter for M4 keybinding contributions.',
});
