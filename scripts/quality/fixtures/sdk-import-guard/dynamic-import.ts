/**
 * Negative fixture: a literal dynamic import of a video-editor internal module.
 * The SDK import guard must reject this.
 */
export async function loadHostRuntime() {
  const mod = await import('@/tools/video-editor/runtime/extensionStateRepository');
  return mod;
}
