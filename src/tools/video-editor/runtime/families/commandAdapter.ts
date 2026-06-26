/**
 * Command real compatibility adapter.
 *
 * Command runtime wiring lives in the command registry and palette dispatch.
 * This adapter satisfies the host adapter contract without duplicating that
 * wiring inside the extension surface.
 *
 * @module families/commandAdapter
 */

import { createCompatibilityAdapter } from './compatibilityAdapterFactory';

export const commandAdapter = createCompatibilityAdapter({
  adapterId: 'command-default',
  kind: 'command',
  maturity: 'host-integrated',
  description: 'Compatibility adapter for M4 command contributions.',
});
