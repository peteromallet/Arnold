/**
 * Asset detail section placeholder adapter.
 *
 * Distinct from metadataFacet. Wraps
 * {@link buildAssetDetailSectionDescriptors} as a delegated HostFamilyAdapter.
 *
 * @module families/assetDetailSectionAdapter
 */

import { createPlaceholderAdapter } from './placeholderAdapterFactory';
import { buildAssetDetailSectionDescriptors } from './projectors/assetDetailSectionProjector';

export const assetDetailSectionAdapter = createPlaceholderAdapter(
  'assetDetailSection',
  ({ contributions, extensionOrder }) => ({
    descriptors: buildAssetDetailSectionDescriptors(contributions, extensionOrder),
  }),
  {
    description: 'Delegated placeholder for asset detail section projection.',
    owner: 'video-editor-runtime',
    reason: 'Asset detail section descriptor projection is delegated pending a dedicated real adapter.',
    expiration: 'M6',
  },
);
