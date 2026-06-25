/**
 * Negative fixture: an alias-resolved relative import that lands inside
 * src/tools/video-editor. The SDK import guard must resolve this and reject it.
 */
import type { ExtensionStateRepository } from '../../../../src/tools/video-editor/runtime/extensionStateRepository';
export type _AliasImportCheck = ExtensionStateRepository;
