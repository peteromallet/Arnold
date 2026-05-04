import {
  createContext,
  useContext,
  useEffect,
  useId,
  useMemo,
  useState,
  type PropsWithChildren,
} from 'react';
import type { VideoEditorDialogDescriptor } from '@/tools/video-editor/runtime/extensionSurface';
import {
  useVideoEditorDialogDescriptors,
  useVideoEditorRenderContext,
} from '@/tools/video-editor/runtime/useVideoEditorRenderContext';

interface VideoEditorDialogHostRegistryValue {
  upsert: (ownerId: string, dialogs: readonly VideoEditorDialogDescriptor[]) => void;
  remove: (ownerId: string) => void;
}

const VideoEditorDialogHostRegistryContext = createContext<VideoEditorDialogHostRegistryValue | null>(null);

function sortDialogs(dialogs: readonly VideoEditorDialogDescriptor[]) {
  return [...dialogs].sort((left, right) => {
    const leftOrder = left.order ?? 0;
    const rightOrder = right.order ?? 0;
    if (leftOrder !== rightOrder) {
      return leftOrder - rightOrder;
    }

    return left.id.localeCompare(right.id);
  });
}

export function VideoEditorDialogHost({
  dialogs = [],
  children,
}: PropsWithChildren<{
  dialogs?: readonly VideoEditorDialogDescriptor[];
}>) {
  const renderContext = useVideoEditorRenderContext();
  const extensionDialogs = useVideoEditorDialogDescriptors();
  const [registeredDialogs, setRegisteredDialogs] = useState<Record<string, readonly VideoEditorDialogDescriptor[]>>({});

  const registryValue = useMemo<VideoEditorDialogHostRegistryValue>(() => ({
    upsert: (ownerId, nextDialogs) => {
      setRegisteredDialogs((current) => {
        if (current[ownerId] === nextDialogs) {
          return current;
        }

        return {
          ...current,
          [ownerId]: nextDialogs,
        };
      });
    },
    remove: (ownerId) => {
      setRegisteredDialogs((current) => {
        if (!Object.prototype.hasOwnProperty.call(current, ownerId)) {
          return current;
        }

        const { [ownerId]: _removed, ...rest } = current;
        return rest;
      });
    },
  }), []);

  const resolvedDialogs = useMemo(() => {
    const localDialogs = Object.values(registeredDialogs).flat();
    return sortDialogs([
      ...extensionDialogs,
      ...dialogs,
      ...localDialogs,
    ]);
  }, [dialogs, extensionDialogs, registeredDialogs]);

  return (
    <VideoEditorDialogHostRegistryContext.Provider value={registryValue}>
      {children}
      {resolvedDialogs.map((dialog) => {
        if (dialog.when && !dialog.when(renderContext)) {
          return null;
        }

        return (
          <div
            key={dialog.id}
            data-video-editor-dialog-id={dialog.id}
            data-video-editor-dialog-layer={dialog.layer ?? 'modal'}
          >
            {dialog.render(renderContext)}
          </div>
        );
      })}
    </VideoEditorDialogHostRegistryContext.Provider>
  );
}

export function useVideoEditorDialogRegistration(dialogs: readonly VideoEditorDialogDescriptor[]) {
  const registry = useContext(VideoEditorDialogHostRegistryContext);
  const ownerId = useId();

  useEffect(() => {
    if (!registry) {
      return;
    }

    registry.upsert(ownerId, dialogs);
    return () => {
      registry.remove(ownerId);
    };
  }, [dialogs, ownerId, registry]);
}
