/**
 * Negative fixture: an export-from re-export of a video-editor internal module.
 * The SDK import guard must reject this.
 */
export type { ExtensionStateRepository } from '@/tools/video-editor/runtime/extensionStateRepository';
