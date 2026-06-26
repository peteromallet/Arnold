/**
 * Clip type real compatibility adapter.
 *
 * @module families/clipTypeAdapter
 */

import { createCompatibilityAdapter } from './compatibilityAdapterFactory';

export const clipTypeAdapter = createCompatibilityAdapter({
  adapterId: 'clipType-default',
  kind: 'clipType',
  maturity: 'runtime-bridged',
  description: 'Compatibility adapter for M9 clip type contributions.',
});
