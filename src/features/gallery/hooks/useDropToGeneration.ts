import { useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import {
  createGenerationForLocalFile,
  createGenerationForUploadedImage,
  createGenerationForUploadedVideo,
} from '@/shared/lib/media/createGenerationFromFile';
import {
  IMAGE_INLINE_UPLOAD_LIMIT_BYTES,
  VIDEO_INLINE_UPLOAD_LIMIT_BYTES,
} from '@/shared/lib/media/dropToGenerationConfig';
import { unifiedGenerationQueryKeys } from '@/shared/lib/queryKeys/unified';

function isImageFile(file: File): boolean {
  return file.type.startsWith('image/');
}

function isVideoFile(file: File): boolean {
  return file.type.startsWith('video/');
}

function formatLimitMb(bytes: number): number {
  return Math.round(bytes / (1024 * 1024));
}

type FileDropHandleItem = DataTransferItem & {
  getAsFileSystemHandle?: () => Promise<FileSystemHandle | null>;
};

type FileSystemHandleLike = FileSystemHandle & {
  getFile?: () => Promise<File>;
};

interface DropToGenerationOptions {
  items?: Iterable<DataTransferItem>;
}

function supportsLocalFileHandles(): boolean {
  return typeof DataTransferItem !== 'undefined'
    && typeof (DataTransferItem.prototype as FileDropHandleItem).getAsFileSystemHandle === 'function';
}

function isReadableFileHandle(handle: FileSystemHandleLike | null): handle is FileSystemFileHandle {
  return !!handle && handle.kind === 'file' && typeof handle.getFile === 'function';
}

export function useDropToGeneration(): (files: File[], options?: DropToGenerationOptions) => Promise<void> {
  const queryClient = useQueryClient();
  const { selectedProjectId } = useProjectSelectionContext();

  return useCallback(async (files: File[], options?: DropToGenerationOptions) => {
    if (!selectedProjectId) {
      toast.error('Please select a project first');
      return;
    }

    const dropItems = Array.from(options?.items ?? []).filter((item): item is FileDropHandleItem => item.kind === 'file');
    const canUseLocalHandles = supportsLocalFileHandles();
    let insertedCount = 0;

    for (const [index, file] of files.entries()) {
      try {
        if (isImageFile(file)) {
          if (file.size >= IMAGE_INLINE_UPLOAD_LIMIT_BYTES) {
            const item = dropItems[index];
            if (!canUseLocalHandles || !item?.getAsFileSystemHandle) {
              toast.info(
                `${file.name} is ${formatLimitMb(IMAGE_INLINE_UPLOAD_LIMIT_BYTES)}MB+ and will use the browser fallback flow in a later batch.`,
              );
              continue;
            }

            const handle = await item.getAsFileSystemHandle();
            if (!isReadableFileHandle(handle)) {
              toast.info(
                `${file.name} could not keep a local file handle. The browser fallback flow will arrive in a later batch.`,
              );
              continue;
            }

            await createGenerationForLocalFile({
              file,
              projectId: selectedProjectId,
              handle,
              mediaType: 'image',
            });
            insertedCount += 1;
            continue;
          }

          await createGenerationForUploadedImage({
            imageFile: file,
            projectId: selectedProjectId,
          });
          insertedCount += 1;
          continue;
        }

        if (isVideoFile(file)) {
          if (file.size >= VIDEO_INLINE_UPLOAD_LIMIT_BYTES) {
            const item = dropItems[index];
            if (!canUseLocalHandles || !item?.getAsFileSystemHandle) {
              toast.info(
                `${file.name} is ${formatLimitMb(VIDEO_INLINE_UPLOAD_LIMIT_BYTES)}MB+ and will use the browser fallback flow in a later batch.`,
              );
              continue;
            }

            const handle = await item.getAsFileSystemHandle();
            if (!isReadableFileHandle(handle)) {
              toast.info(
                `${file.name} could not keep a local file handle. The browser fallback flow will arrive in a later batch.`,
              );
              continue;
            }

            await createGenerationForLocalFile({
              file,
              projectId: selectedProjectId,
              handle,
              mediaType: 'video',
            });
            insertedCount += 1;
            continue;
          }

          await createGenerationForUploadedVideo({
            videoFile: file,
            projectId: selectedProjectId,
          });
          insertedCount += 1;
          continue;
        }

        toast.error(`Unsupported file type: ${file.name}`);
      } catch (error) {
        normalizeAndPresentError(error, {
          context: 'useDropToGeneration',
          toastTitle: `Failed to add ${file.name}`,
        });
      }
    }

    if (insertedCount > 0) {
      await queryClient.invalidateQueries({
        queryKey: unifiedGenerationQueryKeys.projectPrefix(selectedProjectId),
      });
    }
  }, [queryClient, selectedProjectId]);
}
