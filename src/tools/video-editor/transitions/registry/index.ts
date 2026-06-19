export { createTransitionRegistry } from '@/tools/video-editor/transitions/registry/TransitionRegistry.ts';
export {
  TransitionRegistryProvider,
  useTransitionRegistryContext,
  useTransitionRegistrySnapshot,
  useOptionalTransitionRegistryContext,
  type TransitionRegistryContextValue,
  type TransitionRegistryProviderProps,
} from '@/tools/video-editor/transitions/registry/TransitionRegistryContext.tsx';
export type {
  TransitionRegistry,
  TransitionRegistryProvenance,
  TransitionRegistryRecord,
  TransitionRegistryRecordStatus,
  TransitionRegistrySnapshot,
  TransitionRegistrySubscriber,
} from '@/tools/video-editor/transitions/registry/types.ts';
