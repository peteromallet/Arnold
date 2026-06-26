/**
 * Effect placeholder adapter.
 *
 * Wraps {@link buildEffectDescriptors} as a delegated HostFamilyAdapter.
 *
 * @module families/effectAdapter
 */

import { createPlaceholderAdapter } from './placeholderAdapterFactory';
import { buildEffectDescriptors } from './projectors/effectProjector';

export const effectAdapter = createPlaceholderAdapter(
  'effect',
  ({ contributions, extensionOrder }) => ({
    descriptors: buildEffectDescriptors(contributions, extensionOrder),
  }),
  {
    description: 'Delegated placeholder for effect descriptor projection.',
    owner: 'video-editor-runtime',
    reason: 'Effect descriptor projection is delegated pending a dedicated real adapter.',
    expiration: 'M7',
  },
);
