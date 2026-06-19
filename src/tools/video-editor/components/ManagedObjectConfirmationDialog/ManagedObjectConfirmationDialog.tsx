/**
 * ManagedObjectConfirmationDialog — host-owned confirmation dialog shown when
 * a user attempts to manually edit a clip or track that is managed by an
 * extension.
 *
 * Provides three actions:
 * - Cancel: dismiss the dialog, no mutation occurs.
 * - Edit Anyway (Detach): clear the managed-object metadata and allow the edit.
 * - Open Source: navigate to the source that generated this object (if available).
 *
 * Uses the existing AlertDialog pattern from TimelineEditorShellCore.
 */

import React from 'react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import type { ManagedObjectInfo } from '@/tools/video-editor/lib/managed-object-guard';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface ManagedObjectConfirmationDialogProps {
  /** Whether the dialog is open. */
  open: boolean;
  /** Called when the dialog's open state should change. */
  onOpenChange: (open: boolean) => void;
  /** Metadata about the managed object being edited. Null when nothing to confirm. */
  managedInfo: ManagedObjectInfo | null;
  /** Called when the user chooses "Edit Anyway / Detach". */
  onEditAnyway: (info: ManagedObjectInfo) => void;
  /** Called when the user chooses "Open Source" to navigate to the source. */
  onOpenSource: (info: ManagedObjectInfo) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ManagedObjectConfirmationDialog({
  open,
  onOpenChange,
  managedInfo,
  onEditAnyway,
  onOpenSource,
}: ManagedObjectConfirmationDialogProps) {
  if (!managedInfo) return null;

  const kindLabel = managedInfo.kind === 'clip' ? 'Clip' : 'Track';
  const hasSourceMap = !!managedInfo.sourceMapEntryId;

  const handleEditAnyway = () => {
    onEditAnyway(managedInfo);
    onOpenChange(false);
  };

  const handleOpenSource = () => {
    onOpenSource(managedInfo);
    onOpenChange(false);
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Managed {kindLabel}</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3 text-sm">
            <p>
              This {kindLabel.toLowerCase()} is managed by{' '}
              <span className="font-semibold text-foreground">
                {managedInfo.managedBy}
              </span>
              {managedInfo.contributionId && (
                <>
                  {' '}(contribution:{' '}
                  <code className="text-xs">{managedInfo.contributionId}</code>)
                </>
              )}
              .
            </p>
            <p>
              Manual edits may be overwritten the next time the extension
              regenerates this object. You can detach it from management to
              take full control, or open the source to edit it there.
            </p>
            {managedInfo.provenance && (
              <div className="rounded-md bg-muted/50 p-2 text-xs">
                <span className="font-medium">Provenance:</span>{' '}
                <code>{JSON.stringify(managedInfo.provenance)}</code>
              </div>
            )}
          </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={() => onOpenChange(false)}>
            Cancel
          </AlertDialogCancel>
          {hasSourceMap && (
            <AlertDialogAction
              onClick={handleOpenSource}
              className="bg-secondary text-secondary-foreground hover:bg-secondary/80"
              data-testid="managed-object-dialog-open-source"
            >
              Open Source
            </AlertDialogAction>
          )}
          <AlertDialogAction
            onClick={handleEditAnyway}
            data-testid="managed-object-dialog-edit-anyway"
          >
            Edit Anyway (Detach)
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export default ManagedObjectConfirmationDialog;
