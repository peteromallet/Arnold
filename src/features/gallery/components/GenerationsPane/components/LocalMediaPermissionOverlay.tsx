import React, { useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { AlertCircle, FolderOpen, KeyRound } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { unifiedGenerationQueryKeys } from '@/shared/lib/queryKeys/unified';
import { loadHandle, saveHandle, type PersistedLocalMediaHandle } from '@/shared/lib/media/localHandleStore';
import { materializeLocalGeneration } from '@/shared/lib/media/materializeLocalGeneration';

type LocalMediaOverlayState = 'needs-permission' | 'missing';

interface LocalMediaOverlayGeneration {
  id: string;
  local_handle_id?: string | null;
  local_file_name?: string | null;
  local_file_mime?: string | null;
}

interface LocalMediaPermissionOverlayProps {
  generation: LocalMediaOverlayGeneration;
  state: LocalMediaOverlayState;
  onPermissionGranted: () => void;
  onMaterialized: (location: string) => void;
}

type WindowWithPicker = Window & {
  showOpenFilePicker?: (options?: {
    multiple?: boolean;
    excludeAcceptAllOption?: boolean;
    types?: Array<{
      description?: string;
      accept: Record<string, string[]>;
    }>;
  }) => Promise<FileSystemFileHandle[]>;
};

function buildPickerTypes(mime: string | null | undefined): Array<{ description?: string; accept: Record<string, string[]> }> | undefined {
  if (!mime) {
    return undefined;
  }

  const [category, subtype] = mime.split('/');
  if (!category || !subtype) {
    return undefined;
  }

  return [{
    description: category === 'video' ? 'Videos' : 'Images',
    accept: {
      [mime]: [`.${subtype}`],
    },
  }];
}

export function LocalMediaPermissionOverlay({
  generation,
  state,
  onPermissionGranted,
  onMaterialized,
}: LocalMediaPermissionOverlayProps): React.ReactElement {
  const queryClient = useQueryClient();
  const { selectedProjectId } = useProjectSelectionContext();
  const [isWorking, setIsWorking] = useState(false);

  const invalidateProjectGenerations = useCallback(async () => {
    if (!selectedProjectId) {
      return;
    }

    await queryClient.invalidateQueries({
      queryKey: unifiedGenerationQueryKeys.projectPrefix(selectedProjectId),
    });
  }, [queryClient, selectedProjectId]);

  const handleGrantPermission = useCallback(async () => {
    if (!generation.local_handle_id || isWorking) {
      return;
    }

    setIsWorking(true);
    try {
      const handle = await loadHandle(generation.local_handle_id);
      if (!handle) {
        toast.error('The local file handle is missing. Drop the file again or upload it instead.');
        return;
      }

      const permission = await handle.requestPermission({ mode: 'read' });
      if (permission !== 'granted') {
        toast.error('Permission was not granted for this local file.');
        return;
      }

      onPermissionGranted();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to request file access.');
    } finally {
      setIsWorking(false);
    }
  }, [generation.local_handle_id, isWorking, onPermissionGranted]);

  const handleUploadAnyway = useCallback(async () => {
    if (!generation.local_handle_id || isWorking) {
      return;
    }

    const pickerWindow = window as WindowWithPicker;
    if (typeof pickerWindow.showOpenFilePicker !== 'function') {
      toast.error('This browser cannot reopen the source file here. Drop the file again to restore it.');
      return;
    }

    setIsWorking(true);
    try {
      const handles = await pickerWindow.showOpenFilePicker({
        multiple: false,
        excludeAcceptAllOption: false,
        types: buildPickerTypes(generation.local_file_mime),
      });
      const handle = handles[0];
      if (!handle) {
        return;
      }

      await saveHandle(generation.local_handle_id, handle as unknown as PersistedLocalMediaHandle);
      const { location } = await materializeLocalGeneration(generation.id, {
        handleOverride: handle as unknown as PersistedLocalMediaHandle,
      });
      await invalidateProjectGenerations();
      onMaterialized(location);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to upload the replacement file.');
    } finally {
      setIsWorking(false);
    }
  }, [
    generation.id,
    generation.local_file_mime,
    generation.local_handle_id,
    invalidateProjectGenerations,
    isWorking,
    onMaterialized,
  ]);

  const isPermissionState = state === 'needs-permission';

  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/65 p-4 text-white">
      <div className="max-w-xs rounded-xl border border-white/10 bg-zinc-950/95 p-4 text-center shadow-2xl backdrop-blur">
        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-white/10">
          {isPermissionState ? <KeyRound className="h-5 w-5" /> : <AlertCircle className="h-5 w-5" />}
        </div>
        <p className="text-sm font-medium">
          {isPermissionState
            ? 'This generation lives on your device. Grant file access to open it.'
            : 'File moved or browser data cleared — drop again to restore or upload the original now.'}
        </p>
        <p className="mt-2 text-xs text-zinc-300">
          {generation.local_file_name ?? 'Local file'}
        </p>
        <div className="mt-4 flex flex-col gap-2">
          {isPermissionState ? (
            <Button
              type="button"
              size="sm"
              className="w-full"
              onClick={() => void handleGrantPermission()}
              disabled={isWorking}
            >
              <KeyRound className="mr-2 h-4 w-4" />
              Grant access
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              className="w-full"
              onClick={() => void handleUploadAnyway()}
              disabled={isWorking}
            >
              <FolderOpen className="mr-2 h-4 w-4" />
              Upload anyway
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
