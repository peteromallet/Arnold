/**
 * Negative fixture: a direct static import from a video-editor internal module.
 * The SDK import guard must reject this.
 */
import type { ExtensionStateRepository } from '@/tools/video-editor/runtime/extensionStateRepository';
export type _DirectImportCheck = ExtensionStateRepository;
