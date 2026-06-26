/**
 * Transition placeholder adapter.
 *
 * Wraps {@link buildTransitionDescriptors} as a delegated HostFamilyAdapter.
 *
 * @module families/transitionAdapter
 */

import { createPlaceholderAdapter } from './placeholderAdapterFactory';
import { buildTransitionDescriptors } from './projectors/transitionProjector';

export const transitionAdapter = createPlaceholderAdapter(
  'transition',
  ({ contributions, extensionOrder }) => ({
    descriptors: buildTransitionDescriptors(contributions, extensionOrder),
  }),
  {
    description: 'Delegated placeholder for transition descriptor projection.',
    owner: 'video-editor-runtime',
    reason: 'Transition descriptor projection is delegated pending a dedicated real adapter.',
    expiration: 'M8',
  },
);
