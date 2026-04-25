import type { ReactNode } from 'react';
import type { AdjacentSegmentsData, SegmentSlotModeData } from '../../types';
import type { LightboxButtonGroupProps } from '../../hooks/useSharedLightboxState';
import type { WorkflowControlsBarProps } from '../WorkflowControlsBar';

type LayoutButtonGroupProps = LightboxButtonGroupProps;

interface LayoutPanelProps {
  effectiveTasksPaneOpen: boolean;
  effectiveTasksPaneWidth: number;
}

export interface LightboxLayoutProps extends LayoutPanelProps {
  showPanel: boolean;
  shouldShowSidePanel: boolean;
  workflowBar: WorkflowControlsBarProps;
  buttonGroups: LayoutButtonGroupProps;
  controlsPanelContent?: ReactNode;
  customOverlay?: ReactNode;
  adjacentSegments?: AdjacentSegmentsData;
  segmentSlotMode?: SegmentSlotModeData;
}
