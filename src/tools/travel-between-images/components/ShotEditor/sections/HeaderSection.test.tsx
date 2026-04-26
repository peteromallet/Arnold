// @vitest-environment jsdom

import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { HeaderSection } from './HeaderSection';

const {
  updateShotAspectRatioMock,
  useShotSettingsIdentityMock,
  useShotSettingsUiMock,
} = vi.hoisted(() => ({
  updateShotAspectRatioMock: vi.fn(),
  useShotSettingsIdentityMock: vi.fn(),
  useShotSettingsUiMock: vi.fn(),
}));

vi.mock('../ui/Header', () => ({
  Header: ({
    autoAdjustedInfo,
    onRevertAspectRatio,
  }: {
    autoAdjustedInfo?: { adjustedTo: string } | null;
    onRevertAspectRatio?: () => void | Promise<void>;
  }) => (
    <div>
      <div data-testid="header-auto-adjusted">
        {autoAdjustedInfo ? autoAdjustedInfo.adjustedTo : 'none'}
      </div>
      <button type="button" data-testid="header-revert" onClick={onRevertAspectRatio}>
        Revert
      </button>
    </div>
  ),
}));

vi.mock('../ShotSettingsContext', () => ({
  useShotSettingsIdentity: useShotSettingsIdentityMock,
  useShotSettingsUi: useShotSettingsUiMock,
}));

vi.mock('@/shared/hooks/shots', () => ({
  useUpdateShotAspectRatio: () => ({
    updateShotAspectRatio: updateShotAspectRatioMock,
  }),
}));

function createContextValue(overrides: Record<string, unknown> = {}) {
  return {
    selectedShot: {
      id: 'shot-1',
      name: 'Shot 1',
      aspect_ratio: '16:9',
    },
    selectedShotId: 'shot-1',
    projectId: 'project-1',
    projects: [
      {
        id: 'project-1',
        aspectRatio: '1:1',
      },
    ],
    state: {
      isEditingName: false,
      editingName: 'Shot 1',
      isTransitioningFromNameEdit: false,
      autoAdjustedAspectRatio: {
        previousAspectRatio: '1:1',
        adjustedTo: '16:9',
      },
    },
    actions: {
      setEditingNameValue: vi.fn(),
      setAutoAdjustedAspectRatio: vi.fn(),
    },
    effectiveAspectRatio: '16:9',
    ...overrides,
  };
}

function createCallbacks() {
  return {
    onBack: vi.fn(),
    onUpdateShotName: vi.fn(),
    onPreviousShot: vi.fn(),
    onNextShot: vi.fn(),
    hasPrevious: true,
    hasNext: true,
    onNameClick: vi.fn(),
    onNameSave: vi.fn(),
    onNameCancel: vi.fn(),
    onNameKeyDown: vi.fn(),
  };
}

function createLayout() {
  return {
    headerContainerRef: { current: null },
    centerSectionRef: { current: null },
    isSticky: false,
  };
}

describe('HeaderSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    updateShotAspectRatioMock.mockResolvedValue(true);
  });

  it('reverts to the project default aspect ratio instead of the current shot ratio', async () => {
    const contextValue = createContextValue();
    useShotSettingsIdentityMock.mockReturnValue({
      selectedShot: contextValue.selectedShot,
      selectedShotId: contextValue.selectedShotId,
      projectId: contextValue.projectId,
      projects: contextValue.projects,
      effectiveAspectRatio: contextValue.effectiveAspectRatio,
    });
    useShotSettingsUiMock.mockReturnValue({
      state: contextValue.state,
      actions: contextValue.actions,
    });

    render(
      <HeaderSection
        callbacks={createCallbacks()}
        layout={createLayout()}
      />
    );

    await waitFor(() => {
      expect(contextValue.actions.setAutoAdjustedAspectRatio).toHaveBeenCalledWith(null);
    });
    contextValue.actions.setAutoAdjustedAspectRatio.mockClear();

    fireEvent.click(screen.getByTestId('header-revert'));

    await waitFor(() => {
      expect(updateShotAspectRatioMock).toHaveBeenCalledWith('shot-1', 'project-1', '1:1', { immediate: true });
    });
    expect(contextValue.actions.setAutoAdjustedAspectRatio).toHaveBeenCalledWith(null);
    expect(screen.getByTestId('header-auto-adjusted')).toHaveTextContent('16:9');
  });

  it('clears autoAdjustedAspectRatio when selectedShotId changes', async () => {
    const contextValue = createContextValue();
    useShotSettingsIdentityMock.mockReturnValue({
      selectedShot: contextValue.selectedShot,
      selectedShotId: contextValue.selectedShotId,
      projectId: contextValue.projectId,
      projects: contextValue.projects,
      effectiveAspectRatio: contextValue.effectiveAspectRatio,
    });
    useShotSettingsUiMock.mockReturnValue({
      state: contextValue.state,
      actions: contextValue.actions,
    });

    const { rerender } = render(
      <HeaderSection
        callbacks={createCallbacks()}
        layout={createLayout()}
      />
    );

    await waitFor(() => {
      expect(contextValue.actions.setAutoAdjustedAspectRatio).toHaveBeenCalledWith(null);
    });
    contextValue.actions.setAutoAdjustedAspectRatio.mockClear();

    const nextContextValue = createContextValue({
      selectedShot: {
        id: 'shot-2',
        name: 'Shot 2',
        aspect_ratio: '16:9',
      },
      selectedShotId: 'shot-2',
    });
    useShotSettingsIdentityMock.mockReturnValue({
      selectedShot: nextContextValue.selectedShot,
      selectedShotId: nextContextValue.selectedShotId,
      projectId: nextContextValue.projectId,
      projects: nextContextValue.projects,
      effectiveAspectRatio: nextContextValue.effectiveAspectRatio,
    });
    useShotSettingsUiMock.mockReturnValue({
      state: nextContextValue.state,
      actions: nextContextValue.actions,
    });

    rerender(
      <HeaderSection
        callbacks={createCallbacks()}
        layout={createLayout()}
      />
    );

    await waitFor(() => {
      expect(nextContextValue.actions.setAutoAdjustedAspectRatio).toHaveBeenCalledWith(null);
    });
  });
});
