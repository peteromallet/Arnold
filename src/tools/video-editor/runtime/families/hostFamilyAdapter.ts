/**
 * Host family adapter contract — runtime re-export of the SDK adapter types.
 *
 * This module exists so host runtime consumers can import the adapter
 * contract from a host-owned path while the canonical types remain in the
 * public SDK.
 *
 * @module families/hostFamilyAdapter
 */

export type {
  HostFamilyAdapter,
  HostAdapterManifest,
  HostAdapterRegistrationDescriptor,
  FamilyAdapterRegistry,
  FamilyContributionRef,
  NormalizeFamilyInput,
  FamilyNormalizeResult,
  FamilyCapabilityInput,
} from '@reigh/editor-sdk';

export { FamilyAdapterRegistryImpl } from '@reigh/editor-sdk';
