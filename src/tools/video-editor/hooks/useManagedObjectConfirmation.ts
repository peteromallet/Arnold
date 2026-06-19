/**
 * useManagedObjectConfirmation — hook that manages the lifecycle of the
 * managed-object confirmation dialog shown when a user attempts to edit a
 * clip that is managed by an extension.
 *
 * Usage in a host shell component:
 *
 * ```tsx
 * const confirmation = useManagedObjectConfirmation({
 *   commands: useTimelineCommands(),
 *   onNavigateToSource: (extensionId, clipId) => { ... },
 * });
 * // Then:
 * const result = commands.updateClip({ clipId, patch });
 * if (!result.ok && result.error.code === 'managed_object_blocked') {
 *   confirmation.requestConfirmation(result.error.managedInfo!);
 *   return;
 * }
 * // ...
 * <ManagedObjectConfirmationDialog
 *   open={confirmation.isOpen}
 *   onOpenChange={confirmation.close}
 *   managedInfo={confirmation.pendingInfo}
 *   onEditAnyway={confirmation.confirmEditAnyway}
 *   onOpenSource={confirmation.confirmOpenSource}
 * />
 * ```
 *
 * @publicContract — implements M3 managed-object confirmation flow.
 */

import { useState, useCallback } from 'react';
import type { ManagedObjectInfo } from '@/tools/video-editor/lib/managed-object-guard';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UseManagedObjectConfirmationOptions {
  /** Callback invoked when the user chooses "Open Source". */
  onNavigateToSource?: (info: ManagedObjectInfo) => void;
}

export interface UseManagedObjectConfirmation {
  /** Whether the confirmation dialog should be shown. */
  isOpen: boolean;
  /** The managed-object info for the pending confirmation, or null. */
  pendingInfo: ManagedObjectInfo | null;
  /** Request confirmation for a managed object. Call this when a command returns managed_object_blocked. */
  requestConfirmation: (info: ManagedObjectInfo) => void;
  /** The user chose "Edit Anyway / Detach". The caller should detach and re-issue the edit. */
  confirmEditAnyway: (info: ManagedObjectInfo) => void;
  /** The user chose "Open Source". */
  confirmOpenSource: (info: ManagedObjectInfo) => void;
  /** Close the dialog without action. */
  close: () => void;
  /** Callback setter for handling detach. The host sets this once. */
  onConfirmEditAnyway: ((info: ManagedObjectInfo) => void) | null;
  /** Set the handler for "Edit Anyway". */
  setOnConfirmEditAnyway: (handler: ((info: ManagedObjectInfo) => void) | null) => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useManagedObjectConfirmation(
  options?: UseManagedObjectConfirmationOptions,
): UseManagedObjectConfirmation {
  const [isOpen, setIsOpen] = useState(false);
  const [pendingInfo, setPendingInfo] = useState<ManagedObjectInfo | null>(null);
  const [onConfirmEditAnyway, setOnConfirmEditAnyway] = useState<
    ((info: ManagedObjectInfo) => void) | null
  >(null);

  const requestConfirmation = useCallback((info: ManagedObjectInfo) => {
    setPendingInfo(info);
    setIsOpen(true);
  }, []);

  const confirmEditAnyway = useCallback(
    (info: ManagedObjectInfo) => {
      setIsOpen(false);
      setPendingInfo(null);
      if (onConfirmEditAnyway) {
        onConfirmEditAnyway(info);
      }
    },
    [onConfirmEditAnyway],
  );

  const confirmOpenSource = useCallback(
    (info: ManagedObjectInfo) => {
      setIsOpen(false);
      setPendingInfo(null);
      options?.onNavigateToSource?.(info);
    },
    [options],
  );

  const close = useCallback(() => {
    setIsOpen(false);
    setPendingInfo(null);
  }, []);

  return {
    isOpen,
    pendingInfo,
    requestConfirmation,
    confirmEditAnyway,
    confirmOpenSource,
    close,
    onConfirmEditAnyway,
    setOnConfirmEditAnyway,
  };
}
