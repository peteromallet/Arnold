/**
 * LightboxShell - Dialog/Overlay container for MediaLightbox
 *
 * Encapsulates all the complex event handling for the lightbox modal:
 * - Dialog root/portal/overlay
 * - Pointer/touch/click event handling with z-index awareness
 * - Body scroll locking
 * - Accessibility elements
 *
 * Note: Tasks pane controls are handled by the existing PaneControlTab from TasksPane,
 * while pane content uses UI_Z_LAYERS.TASKS_PANE_CONTENT (100016) above the lightbox.
 * The overlay adjusts its size to account for the pane when it's open or locked.
 *
 * This allows the main MediaLightbox to focus on content orchestration.
 */

import React, { useEffect } from 'react';
import { cn } from '@/shared/components/ui/contracts/cn';
import {
  LightboxDialog,
  LightboxDialogBackdrop,
  LightboxDialogDescription,
  LightboxDialogPopup,
  LightboxDialogPortal,
  LightboxDialogTitle,
} from '@/shared/components/ui/overlay';
import { useLightboxShellInteractionHandlers } from '@/domains/media-lightbox/hooks/useLightboxShellInteractionHandlers';
import { useLightboxViewportLock } from '@/domains/media-lightbox/hooks/useLightboxViewportLock';
import { useLightboxPaneLayout } from '@/domains/media-lightbox/hooks/useLightboxPaneLayout';
import type { OverlayViewportConstraints } from '@/shared/lib/layout/overlayViewportConstraints';
import { useRenderBudget } from '@/shared/dev/useRenderBudget';

interface LightboxShellProps {
  children: React.ReactNode;
  onClose: () => void;

  // Edit mode
  /** Canvas/brush edit overlay is active (inpaint, annotate, reposition, text).
   *  Used to allow canvas touch events to pass through. */
  hasCanvasOverlay: boolean;
  /** Reposition (move) mode — the only edit mode that blocks background click-to-close
   *  (because dragging could cause accidental closes). */
  isRepositionMode: boolean;

  // Responsive
  isMobile: boolean;
  isTabletOrLarger: boolean;

  // Layout constraints from the layout subsystem.
  overlayViewport: OverlayViewportConstraints;

  // Ref for content
  contentRef: React.RefObject<HTMLDivElement>;

  // Accessibility
  accessibilityTitle: string;
  accessibilityDescription: string;
}

export const LightboxShell: React.FC<LightboxShellProps> = ({
  children,
  onClose,
  hasCanvasOverlay,
  isRepositionMode,
  isMobile,
  isTabletOrLarger,
  overlayViewport,
  contentRef,
  accessibilityTitle,
  accessibilityDescription,
}) => {
  useRenderBudget('LightboxShell', 5);
  const isActuallyModal = isMobile && !isTabletOrLarger;
  useLightboxViewportLock({ isActuallyModal });

  const {
    handleOverlayPointerDown,
    handleOverlayPointerUp,
    handleBgPointerDownCapture,
    handleBgClickCapture,
    handleContentPointerDown,
    handleContentClick,
    handleTouchEvent,
    handleTouchCancel,
  } = useLightboxShellInteractionHandlers({
    hasCanvasOverlay,
    isRepositionMode,
    isMobile,
    onClose,
    popupRef: contentRef,
  });

  // Focus the content element on mount
  useEffect(() => {
    contentRef.current?.focus();
  }, [contentRef]);

  const { overlayStyle, contentStyle } = useLightboxPaneLayout({
    overlayViewport,
  });

  return (
    <LightboxDialog
      open={true}
      modal={isActuallyModal}
      disablePointerDismissal
      onOpenChange={(_open, eventDetails) => {
        // Prevent Base UI from updating internal state (which corrupts controlled open={true})
        // and from calling stopPropagation on the native event (which blocks our custom handlers).
        // Our own handlers in useLightboxNavigation (Escape) and our overlay dismissal handlers
        // manage all closing logic.
        eventDetails.cancel();
        eventDetails.allowPropagation();
      }}
    >
      <LightboxDialogPortal>
        <LightboxDialogBackdrop
          data-dialog-backdrop
          className={cn(
            "fixed bg-black/80 p-0 border-none shadow-none",
            "data-[open]:animate-in data-[ending-style]:animate-out data-[ending-style]:fade-out-0 data-[open]:fade-in-0",
            !isMobile && "duration-200"
          )}
          onPointerDown={handleOverlayPointerDown}
          onPointerUp={handleOverlayPointerUp}
          onTouchStart={handleTouchEvent}
          onTouchMove={handleTouchEvent}
          onTouchEnd={handleTouchEvent}
          onTouchCancel={handleTouchCancel}
          style={{
            ...overlayStyle,
          }}
        />

        {/* Task pane handle removed - the existing PaneControlTab from TasksPane
            is now visible above the lightbox and handles all pane controls.
            The overlay correctly accounts for the pane via shouldAccountForTasksPane. */}

        <LightboxDialogPopup
          ref={contentRef}
          data-lightbox-popup
          tabIndex={-1}
          onPointerDownCapture={handleBgPointerDownCapture}
          onClickCapture={handleBgClickCapture}
          onPointerDown={handleContentPointerDown}
          onClick={handleContentClick}
          onTouchStart={handleTouchEvent}
          onTouchMove={handleTouchEvent}
          onTouchEnd={handleTouchEvent}
          onTouchCancel={handleTouchCancel}
          className={cn(
            "fixed",
            isMobile
              ? ""
              : "duration-200 data-[open]:animate-in data-[ending-style]:animate-out data-[ending-style]:fade-out-0 data-[open]:fade-in-0 data-[ending-style]:zoom-out-95 data-[open]:zoom-in-95",
            "p-0 border-none bg-transparent shadow-none",
            overlayViewport.needsFullscreenLayout
              ? "inset-0 w-full h-full"
              : "left-[50%] top-[50%] translate-x-[-50%] translate-y-[-50%] w-auto h-auto data-[ending-style]:slide-out-to-left-1/2 data-[ending-style]:slide-out-to-top-[48%] data-[open]:slide-in-from-left-1/2 data-[open]:slide-in-from-top-[48%]"
          )}
          style={{
            ...contentStyle,
          }}
        >
          {/* Accessibility: Hidden dialog title for screen readers */}
          <LightboxDialogTitle className="sr-only">
            {accessibilityTitle}
          </LightboxDialogTitle>
          <LightboxDialogDescription className="sr-only">
            {accessibilityDescription}
          </LightboxDialogDescription>

          {children}
        </LightboxDialogPopup>
      </LightboxDialogPortal>
    </LightboxDialog>
  );
};
