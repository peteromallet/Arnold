import React from 'react';
import { LayoutGrid } from 'lucide-react';
import { cn } from '@/shared/components/ui/contracts/cn';
import { PaneControlTab } from '@/shared/components/PaneControlTab';
import { useSlidingPane } from '@/shared/hooks/useSlidingPane';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { usePanesStore } from '@/shared/state/panesStore';
import { ShotsPanelContent } from '@/features/editor/components/ShotsPanelContent';

function useEditorPane() {
  const isEditorPaneLocked = usePanesStore((state) => state.isEditorPaneLocked);
  const setIsEditorPaneLocked = usePanesStore((state) => state.setIsEditorPaneLocked);
  const setIsEditorPaneOpen = usePanesStore((state) => state.setIsEditorPaneOpen);
  const effectiveEditorPaneHeight = usePanesStore((state) => state.effectiveEditorPaneHeight);
  const isShotsPaneLocked = usePanesStore((state) => state.isShotsPaneLocked);
  const shotsPaneWidth = usePanesStore((state) => state.shotsPaneWidth);
  const isTasksPaneLocked = usePanesStore((state) => state.isTasksPaneLocked);
  const tasksPaneWidth = usePanesStore((state) => state.tasksPaneWidth);

  const pane = useSlidingPane({
    side: 'top',
    isLocked: isEditorPaneLocked,
    onToggleLock: () => setIsEditorPaneLocked(!isEditorPaneLocked),
    onOpenChange: setIsEditorPaneOpen,
  });

  const adjustedEditorPaneHeight = effectiveEditorPaneHeight;

  return {
    pane,
    effectiveEditorPaneHeight: adjustedEditorPaneHeight,
    isEditorPaneLocked,
    setIsEditorPaneLocked,
    isShotsPaneLocked,
    shotsPaneWidth,
    isTasksPaneLocked,
    tasksPaneWidth,
  };
}

const EditorPaneComponent: React.FC = () => {
  const { selectedProjectId } = useProjectSelectionContext();
  const {
    pane,
    effectiveEditorPaneHeight,
    isShotsPaneLocked,
    shotsPaneWidth,
    isTasksPaneLocked,
    tasksPaneWidth,
  } = useEditorPane();

  const horizontalOffset =
    (isShotsPaneLocked ? shotsPaneWidth : 0) -
    (isTasksPaneLocked ? tasksPaneWidth : 0);

  return (
    <>
      {/* Control tab */}
      <PaneControlTab
        position={{
          side: 'top',
          paneDimension: effectiveEditorPaneHeight,
          horizontalOffset,
        }}
        state={{ isLocked: pane.isLocked, isOpen: pane.isOpen }}
        handlers={{
          toggleLock: pane.toggleLock,
          openPane: pane.openPane,
          handlePaneEnter: pane.handlePaneEnter,
          handlePaneLeave: pane.handlePaneLeave,
        }}
        display={{
          paneTooltip: 'Shots',
          shortcutHint: '⌥W',
        }}
      />

      {/* Pane surface */}
      <div
        {...pane.paneProps}
        data-testid="editor-pane"
        style={{
          height: `${effectiveEditorPaneHeight}px`,
          marginLeft: isShotsPaneLocked ? `${shotsPaneWidth}px` : '0px',
          marginRight: isTasksPaneLocked ? `${tasksPaneWidth}px` : '0px',
          zIndex: 59,
        }}
        className={cn(
          'fixed top-0 left-0 right-0 flex flex-col border-b border-border bg-background/95 shadow-xl backdrop-blur-sm transform transition-[transform,margin,padding] duration-300 ease-smooth pointer-events-auto',
          pane.transformClass,
        )}
      >
        {selectedProjectId ? (
          <ShotsPanelContent projectId={selectedProjectId} />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
            Select a project to browse shots
          </div>
        )}
      </div>
    </>
  );
};

export const EditorPane = React.memo(EditorPaneComponent);
