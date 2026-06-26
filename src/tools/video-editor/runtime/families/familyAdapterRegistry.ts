/**
 * Host family adapter registry — canonical runtime registration for every
 * video-editor family that has a host adapter or placeholder.
 *
 * This registry is the single source of truth for adapter dispatch in
 * {@link assembleExtensionRuntime}.  It is passive: no audit logic, no
 * host runtime imports beyond the adapter modules themselves.
 *
 * @module families/familyAdapterRegistry
 */

import { FamilyAdapterRegistryImpl } from '@reigh/editor-sdk';
import type { FamilyAdapterRegistry } from '@reigh/editor-sdk';

import { metadataFacetAdapter } from './metadataFacetAdapter';
import { slotAdapter } from './slotAdapter';
import { dialogAdapter } from './dialogAdapter';
import { panelAdapter } from './panelAdapter';
import { inspectorSectionAdapter } from './inspectorSectionAdapter';
import { timelineOverlayAdapter } from './timelineOverlayAdapter';

import { outputFormatAdapter } from './outputFormatAdapter';
import { processAdapter } from './processAdapter';
import { searchProviderAdapter } from './searchProviderAdapter';
import { assetDetailSectionAdapter } from './assetDetailSectionAdapter';
import { parserAdapter } from './parserAdapter';
import { effectAdapter } from './effectAdapter';
import { transitionAdapter } from './transitionAdapter';
import { shaderAdapter } from './shaderAdapter';
import { agentToolAdapter } from './agentToolAdapter';

import { commandAdapter } from './commandAdapter';
import { contextMenuItemAdapter } from './contextMenuItemAdapter';
import { keybindingAdapter } from './keybindingAdapter';
import { automationAdapter } from './automationAdapter';
import { clipTypeAdapter } from './clipTypeAdapter';

const registry = new FamilyAdapterRegistryImpl();

// Real adapters
registry.register({ adapter: metadataFacetAdapter });
registry.register({ adapter: slotAdapter });
registry.register({ adapter: dialogAdapter });
registry.register({ adapter: panelAdapter });
registry.register({ adapter: inspectorSectionAdapter });
registry.register({ adapter: timelineOverlayAdapter });

// Delegated placeholder adapters
registry.register({ adapter: outputFormatAdapter });
registry.register({ adapter: processAdapter });
registry.register({ adapter: searchProviderAdapter });
registry.register({ adapter: assetDetailSectionAdapter });
registry.register({ adapter: parserAdapter });
registry.register({ adapter: effectAdapter });
registry.register({ adapter: transitionAdapter });
registry.register({ adapter: shaderAdapter });
registry.register({ adapter: agentToolAdapter });

// Compatibility adapters for families whose host wiring lives elsewhere
registry.register({ adapter: commandAdapter });
registry.register({ adapter: contextMenuItemAdapter });
registry.register({ adapter: keybindingAdapter });
registry.register({ adapter: automationAdapter });
registry.register({ adapter: clipTypeAdapter });

// Agent is delegated with no host adapter yet — register as known-unavailable
registry.register({ adapter: null, metadata: { kind: 'agent' } });

/**
 * Frozen snapshot of the canonical video-editor family adapter registry.
 */
export const VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY: FamilyAdapterRegistry =
  Object.freeze(registry.snapshot());

/**
 * All kinds registered in the canonical adapter registry, sorted.
 */
export const VIDEO_EDITOR_FAMILY_ADAPTER_KINDS: readonly string[] =
  Object.freeze(registry.kinds());
