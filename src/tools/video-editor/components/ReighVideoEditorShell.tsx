import { memo, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useHomeNavigation } from '@/shared/hooks/useHomeNavigation';
import { usePanesStore } from '@/shared/state/panesStore';
import { CompactPreview } from '@/tools/video-editor/components/CompactPreview';
import { TimelineEditorShellCore } from '@/tools/video-editor/components/TimelineEditorShellCore';

interface ReighVideoEditorShellProps {
  mode: 'full' | 'compact';
  timelineId?: string | null;
  onCreateTimeline?: () => void;
}

function ReighVideoEditorShellComponent({ mode, timelineId, onCreateTimeline }: ReighVideoEditorShellProps) {
  const { navigateHome } = useHomeNavigation();
  const isEditorPaneLocked = usePanesStore((state) => state.isEditorPaneLocked);
  const isGenerationsPaneLocked = usePanesStore((state) => state.isGenerationsPaneLocked);
  const setIsGenerationsPaneLocked = usePanesStore((state) => state.setIsGenerationsPaneLocked);
  const location = useLocation();
  const navigate = useNavigate();
  const isOnEditorPage = location.pathname.startsWith('/tools/video-editor');
  const openEditorRoute = useCallback((nextTimelineId: string) => {
    navigate(`/tools/video-editor?timeline=${nextTimelineId}`);
  }, [navigate]);

  if (!timelineId) {
    if (mode === 'compact') {
      return <CompactPreview timelineId={timelineId} onCreateTimeline={onCreateTimeline} />;
    }
    return null;
  }

  return (
    <TimelineEditorShellCore
      timelineId={timelineId}
      forceCondensed={mode === 'compact'}
      isOnEditorPage={isOnEditorPage}
      isEditorPaneLocked={isEditorPaneLocked}
      isGenerationsPaneLocked={isGenerationsPaneLocked}
      onSetGenerationsPaneLocked={setIsGenerationsPaneLocked}
      onNavigateHome={navigateHome}
      onOpenEditorRoute={openEditorRoute}
    />
  );
}

export const ReighVideoEditorShell = memo(ReighVideoEditorShellComponent);
