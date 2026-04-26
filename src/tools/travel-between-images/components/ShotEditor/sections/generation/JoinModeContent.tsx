import React from 'react';
import { ArrowLeftRight } from 'lucide-react';
import {
  JoinClipsSettingsForm,
} from '@/shared/components/JoinClipsSettingsForm/JoinClipsSettingsForm';
import { useShotSettingsGeneration, useShotSettingsIdentity } from '../../ShotSettingsContext';
import { buildJoinClipsFormProps } from './joinClipsFormProps';
import { useBoundarySummary } from '../../hooks/actions/useBoundarySummary';

interface JoinModeContentProps {
  joinSegmentsSectionRef: React.RefObject<HTMLDivElement>;
  swapButtonRef: React.RefObject<HTMLButtonElement>;
}

export const JoinModeContent: React.FC<JoinModeContentProps> = ({
  joinSegmentsSectionRef,
  swapButtonRef,
}) => {
  const { projectId } = useShotSettingsIdentity();
  const { availableLoras, generationMode, joinState } = useShotSettingsGeneration();

  console.log('[JoinModeContent] joinState.joinSegmentSlots:', joinState.joinSegmentSlots?.length, joinState.joinSegmentSlots);
  const boundarySummary = useBoundarySummary((joinState.joinSegmentSlots ?? []) as import('@/shared/hooks/segments/useSegmentOutputsForShot').SegmentSlot[]);

  const joinFormProps = buildJoinClipsFormProps({
    joinState,
    availableLoras,
    projectId,
    loraPersistenceKey: 'join-clips-shot-editor',
  });

  return (
    <div ref={joinSegmentsSectionRef}>
      <JoinClipsSettingsForm
        clipSettings={joinFormProps.clipSettings}
        motionConfig={joinFormProps.motionConfig}
        uiState={{
          onGenerate: joinState.handleJoinSegments,
          isGenerating: joinState.isJoiningClips,
          generateSuccess: joinState.joinClipsSuccess,
          generateButtonText: boundarySummary?.every(b => b.canCrossfade)
            ? 'Stitch Segments'
            : 'Join Segments',
          isGenerateDisabled: joinState.joinValidationData.videoCount < 2,
          onRestoreDefaults: joinState.handleRestoreJoinDefaults,
          boundarySummary,
        }}
      />

      <button
        ref={swapButtonRef}
        onClick={() => generationMode.toggleGenerateModePreserveScroll('batch')}
        className="mt-4 w-full flex items-center justify-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors py-2"
      >
        <ArrowLeftRight className="w-4 h-4" />
        <span>Swap to Batch Generate</span>
      </button>
    </div>
  );
};
