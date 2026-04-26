import React from 'react';
import { ArrowLeftRight } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/shared/components/ui/card';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';

import { BatchModeContent } from './generation/BatchModeContent';
import { JoinModeContent } from './generation/JoinModeContent';
import { useShotSettingsGeneration, useShotSettingsMedia } from '../ShotSettingsContext';

export interface GenerationSectionProps {
  refs: {
    generateVideosCardRef: React.RefObject<HTMLDivElement>;
    ctaContainerRef?: (node: HTMLDivElement | null) => void;
    swapButtonRef: React.RefObject<HTMLButtonElement>;
    joinSegmentsSectionRef: React.RefObject<HTMLDivElement>;
  };
  cta: {
    parentVariantName?: string;
    parentOnVariantNameChange?: (name: string) => void;
    parentIsGeneratingVideo?: boolean;
    parentVideoJustQueued?: boolean;
  };
}

export const GenerationSection: React.FC<GenerationSectionProps> = ({
  refs,
  cta,
}) => {
  const { simpleFilteredImages } = useShotSettingsMedia();
  const { generationMode, joinState } = useShotSettingsGeneration();
  const showSimpleHeader = simpleFilteredImages.length <= 2;
  const canSwitchToJoin = joinState.joinValidationData.videoCount >= 2;

  return (
    <div className="w-full" ref={refs.generateVideosCardRef} style={{ overflowAnchor: 'none' }}>
      <Card>
        <CardHeader className="pb-2">
          {showSimpleHeader ? (
            <div className="flex items-center justify-between w-full">
              <span className="text-base sm:text-lg font-light text-foreground">
                {simpleFilteredImages.length <= 1 ? 'Generate' : 'Batch Generate'}
              </span>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="text-xs bg-primary/15 text-primary px-2.5 py-1 rounded-full font-medium cursor-help">
                    Shot Defaults
                  </span>
                </TooltipTrigger>
                <TooltipContent>
                  <p>These settings are used as defaults for individual<br />segment generation and batch generation.</p>
                </TooltipContent>
              </Tooltip>
            </div>
          ) : (
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center gap-2">
                <span className="text-base sm:text-lg font-light text-foreground">
                  {generationMode.generateMode === 'batch' ? 'Batch Generate' : 'Join Segments'}
                </span>
                <button
                  onClick={() => {
                    generationMode.setGenerateMode(generationMode.generateMode === 'batch' ? 'join' : 'batch');
                  }}
                  className={`p-1 rounded-full transition-colors ${
                    (generationMode.generateMode === 'batch' && !canSwitchToJoin)
                      ? 'text-muted-foreground/30 cursor-not-allowed'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted cursor-pointer'
                  }`}
                  title={generationMode.generateMode === 'batch' ? 'Switch to Join Segments' : 'Switch to Batch Generate'}
                >
                  <ArrowLeftRight className="w-4 h-4" />
                </button>
                <button
                  onClick={() => {
                    generationMode.setGenerateMode(generationMode.generateMode === 'batch' ? 'join' : 'batch');
                  }}
                  className={`text-sm transition-colors ${
                    (generationMode.generateMode === 'batch' && !canSwitchToJoin)
                      ? 'text-muted-foreground/30 cursor-not-allowed'
                      : 'text-muted-foreground hover:text-foreground cursor-pointer'
                  }`}
                >
                  {generationMode.generateMode === 'batch' ? 'Join Segments' : 'Batch Generate'}
                </button>
              </div>
              {generationMode.generateMode === 'batch' && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="text-xs bg-primary/15 text-primary px-2.5 py-1 rounded-full font-medium cursor-help">
                      Shot Defaults
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>These settings are used as defaults for individual<br />segment generation and batch generation.</p>
                  </TooltipContent>
                </Tooltip>
              )}
            </div>
          )}
        </CardHeader>
        <CardContent>
          {generationMode.generateMode === 'batch' ? (
            <BatchModeContent
              ctaContainerRef={refs.ctaContainerRef}
              swapButtonRef={refs.swapButtonRef}
              parentVariantName={cta.parentVariantName}
              parentOnVariantNameChange={cta.parentOnVariantNameChange}
              parentIsGeneratingVideo={cta.parentIsGeneratingVideo}
              parentVideoJustQueued={cta.parentVideoJustQueued}
            />
          ) : (
            <JoinModeContent
              joinSegmentsSectionRef={refs.joinSegmentsSectionRef}
              swapButtonRef={refs.swapButtonRef}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
};
