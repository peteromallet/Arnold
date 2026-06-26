/**
 * Agent tool placeholder adapter.
 *
 * Wraps {@link buildAgentToolDescriptors} as a delegated HostFamilyAdapter.
 *
 * @module families/agentToolAdapter
 */

import { createPlaceholderAdapter } from './placeholderAdapterFactory';
import { buildAgentToolDescriptors } from './projectors/agentToolProjector';

export const agentToolAdapter = createPlaceholderAdapter(
  'agentTool',
  ({ contributions, extensionOrder }) => ({
    descriptors: buildAgentToolDescriptors(contributions, extensionOrder),
  }),
  {
    description: 'Delegated placeholder for agent tool descriptor projection.',
    owner: 'video-editor-runtime',
    reason: 'Agent tool descriptor projection is delegated pending a dedicated real adapter.',
    expiration: 'M10',
  },
);
