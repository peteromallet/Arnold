/**
 * Process placeholder adapter.
 *
 * Wraps {@link buildProcessDescriptors} as a delegated HostFamilyAdapter.
 *
 * @module families/processAdapter
 */

import { createPlaceholderAdapter } from './placeholderAdapterFactory';
import { buildProcessDescriptors } from './projectors/processProjector';

export const processAdapter = createPlaceholderAdapter(
  'process',
  ({ contributions, extensionOrder }) => ({
    descriptors: buildProcessDescriptors(contributions, extensionOrder),
  }),
  {
    description: 'Delegated placeholder for process declaration projection.',
    owner: 'video-editor-runtime',
    reason: 'Process execution is reserved for M12; only declarations are surfaced for planning.',
    expiration: 'M12',
  },
);
