/**
 * ShotsContext Tests
 *
 * Tests for shots data context.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

// Use vi.hoisted for variables referenced in vi.mock factories
const { mockRefetch } = vi.hoisted(() => ({
  mockRefetch: vi.fn(),
}));

vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProjectSelectionContext: vi.fn().mockReturnValue({
    selectedProjectId: 'proj-1',
  }),
}));

vi.mock('@/shared/hooks/shots', () => ({
  useListShots: vi.fn().mockReturnValue({
    data: [
      { id: 'shot-1', name: 'Shot 1' },
      { id: 'shot-2', name: 'Shot 2' },
    ],
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: mockRefetch,
  }),
  useProjectImageStats: vi.fn().mockReturnValue({
    data: { allCount: 10, noShotCount: 3 },
    isLoading: false,
  }),
}));

import { ShotsProvider, useShots } from '../ShotsContext';

// Test consumer component
function ShotsConsumer() {
  const ctx = useShots();
  return (
    <div>
      <span data-testid="shotCount">{ctx.shots?.length ?? 'undefined'}</span>
      <span data-testid="isLoading">{String(ctx.isLoading)}</span>
      <span data-testid="allImagesCount">{ctx.allImagesCount ?? 'undefined'}</span>
      <span data-testid="noShotImagesCount">{ctx.noShotImagesCount ?? 'undefined'}</span>
    </div>
  );
}

describe('ShotsContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useShots hook', () => {
    it('throws when used outside ShotsProvider', () => {
      function BadConsumer() {
        useShots();
        return null;
      }

      expect(() => {
        render(<BadConsumer />);
      }).toThrow('useShots must be used within a ShotsProvider');
    });
  });

  describe('ShotsProvider', () => {
    it('renders children', () => {
      render(
        <ShotsProvider>
          <div data-testid="child">Hello</div>
        </ShotsProvider>
      );

      expect(screen.getByTestId('child')).toHaveTextContent('Hello');
    });

    it('provides shots data from hooks', () => {
      render(
        <ShotsProvider>
          <ShotsConsumer />
        </ShotsProvider>
      );

      expect(screen.getByTestId('shotCount')).toHaveTextContent('2');
      expect(screen.getByTestId('isLoading')).toHaveTextContent('false');
      expect(screen.getByTestId('allImagesCount')).toHaveTextContent('10');
      expect(screen.getByTestId('noShotImagesCount')).toHaveTextContent('3');
    });

    it('exposes refetchShots function', () => {
      function RefetchConsumer() {
        const { refetchShots } = useShots();
        return (
          <button data-testid="refetch" onClick={() => refetchShots()}>
            Refetch
          </button>
        );
      }

      render(
        <ShotsProvider>
          <RefetchConsumer />
        </ShotsProvider>
      );

      screen.getByTestId('refetch').click();
      expect(mockRefetch).toHaveBeenCalled();
    });
  });
});
