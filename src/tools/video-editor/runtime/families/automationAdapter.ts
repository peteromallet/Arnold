/**
 * Automation real compatibility adapter.
 *
 * @module families/automationAdapter
 */

import { createCompatibilityAdapter } from './compatibilityAdapterFactory';

export const automationAdapter = createCompatibilityAdapter({
  adapterId: 'automation-default',
  kind: 'automation',
  maturity: 'runtime-bridged',
  description: 'Compatibility adapter for M9 automation clip contributions.',
});
