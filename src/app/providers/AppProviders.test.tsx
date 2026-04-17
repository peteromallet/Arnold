// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useAgentChatBridge } from '@/shared/contexts/AgentChatContext';
import { useGallerySelectionOptional } from '@/shared/state/selectionStore';
import { AppProviders } from './AppProviders';

function passthroughProvider(testId: string) {
  return function Provider({ children }: { children: ReactNode }) {
    return <div data-testid={testId}>{children}</div>;
  };
}

vi.mock('@/shared/contexts/AuthContext', () => ({
  AuthProvider: passthroughProvider('AuthProvider'),
}));

vi.mock('@/shared/auth/components/AuthGate', () => ({
  AuthGate: passthroughProvider('AuthGate'),
}));

vi.mock('@/shared/contexts/UserSettingsContext', () => ({
  UserSettingsProvider: passthroughProvider('UserSettingsProvider'),
  useUserSettings: () => ({
    userSettings: { lastTimelineId: 'timeline-from-settings' },
    isLoadingSettings: false,
    fetchUserSettings: vi.fn(),
    updateUserSettings: vi.fn(),
  }),
}));

vi.mock('@/shared/hooks/settings/useToolSettings', () => ({
  useToolSettings: () => ({
    settings: { lastAffectedShotId: 'shot-from-settings', lastTimelineId: 'timeline-from-settings' },
    update: vi.fn(),
    isLoading: false,
  }),
}));

vi.mock('@/shared/contexts/ProjectContext', () => ({
  ProjectProvider: passthroughProvider('ProjectProvider'),
  useProject: () => ({ selectedProjectId: 'project-1' }),
  useProjectSelectionContext: () => ({ selectedProjectId: 'project-1' }),
}));

vi.mock('@/shared/providers/RealtimeProvider', () => ({
  RealtimeProvider: passthroughProvider('RealtimeProvider'),
}));

vi.mock('@/shared/contexts/ShotsContext', () => ({
  ShotsProvider: passthroughProvider('ShotsProvider'),
}));

vi.mock('@/shared/contexts/GenerationTaskContext', () => ({
  GenerationTaskProvider: passthroughProvider('GenerationTaskProvider'),
}));

vi.mock('@/shared/contexts/IncomingTasksContext', () => ({
  IncomingTasksProvider: passthroughProvider('IncomingTasksProvider'),
}));

vi.mock('@/shared/state/panesStore', () => ({
  PanesStoreBootstrapBoundary: passthroughProvider('PanesStoreBootstrapBoundary'),
}));

vi.mock('@/shared/contexts/ToolPageHeaderContext', () => ({
  ToolPageHeaderProvider: passthroughProvider('ToolPageHeaderProvider'),
}));

vi.mock('@/shared/components/TaskTypeConfigInitializer', () => ({
  TaskTypeConfigInitializer: passthroughProvider('TaskTypeConfigInitializer'),
}));

vi.mock('@/shared/state/selectionStore', async () => {
  const actual = await vi.importActual<typeof import('@/shared/state/selectionStore')>('@/shared/state/selectionStore');
  return {
    ...actual,
    useLastAffectedShot: () => ({
      lastAffectedShotId: 'shot-from-settings',
      setLastAffectedShotId: vi.fn(),
    }),
  };
});

function GallerySelectionConsumer() {
  const context = useGallerySelectionOptional();
  return <span data-testid="gallery-selection-context">{context ? 'available' : 'missing'}</span>;
}

function AgentChatBridgeConsumer() {
  const bridge = useAgentChatBridge();
  return (
    <>
      <span data-testid="agent-chat-timeline-id">{bridge.timelineId ?? 'none'}</span>
      <span data-testid="agent-chat-timeline-clips">{String(bridge.timelineClips.length)}</span>
    </>
  );
}

describe('AppProviders', () => {
  it('mounts the selection-store boundary and the default AgentChat bridge inside the provider tree', () => {
    render(
      <AppProviders>
        <GallerySelectionConsumer />
        <AgentChatBridgeConsumer />
      </AppProviders>,
    );

    expect(screen.getByTestId('gallery-selection-context')).toHaveTextContent('available');
    expect(screen.getByTestId('agent-chat-timeline-id')).toHaveTextContent('timeline-from-settings');
    expect(screen.getByTestId('agent-chat-timeline-clips')).toHaveTextContent('0');
    expect(screen.getByTestId('PanesStoreBootstrapBoundary')).toBeInTheDocument();
  });
});
