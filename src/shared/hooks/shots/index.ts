// Mappers
export { mapShotGenerationToRow } from './mappers';

// Shot CRUD operations
export {
  useCreateShot,
  useDeleteShot,
  useDuplicateShot,
  useReorderShots,
} from './useShotsCrud';
export { useDuplicateShotWithVideos } from './useDuplicateShotWithVideos';

// Shot queries
export { useListShots, useProjectImageStats } from './useShotsQueries';

// Shot field updates
export { useUpdateShotName } from './useShotUpdates';
export { useUpdateShotAspectRatio } from './useUpdateShotAspectRatio';

// Shot-generation mutations (add, remove, reorder images in shots)
export {
  useAddImageToShot,
  useRemoveImageFromShot,
  useUpdateShotImageOrder,
  usePositionExistingGenerationInShot,
  useDuplicateAsNewGeneration,
} from './useShotGenerationMutations';

// Composite creation operations
export {
  useCreateShotWithGenerations,
  useHandleExternalImageDrop,
} from './useShotCreation';
