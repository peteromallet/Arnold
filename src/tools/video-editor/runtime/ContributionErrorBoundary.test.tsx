// @vitest-environment jsdom
import { act, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useState, type ReactNode } from 'react';
import {
  ContributionErrorBoundary,
  type ContributionErrorInfo,
} from '@/tools/video-editor/runtime/ContributionErrorBoundary';

// Component that throws during render
function ThrowingSlot({ message = 'Boom!' }: { message?: string }) {
  throw new Error(message);
}

// Normal rendering component
function NormalSlot({ label = 'OK' }: { label?: string }) {
  return <div data-testid="normal-slot">{label}</div>;
}

// Wrapper that can toggle between crashing and normal children for recovery tests.
function RecoverableBoundaryWrapper({
  initialRecoveryKey = '0',
  initialCrash = false,
  children,
}: {
  initialRecoveryKey?: string;
  initialCrash?: boolean;
  children?: ReactNode;
}) {
  const [recoveryKey, setRecoveryKey] = useState(initialRecoveryKey);
  const [shouldCrash, setShouldCrash] = useState(initialCrash);

  return (
    <div>
      <button
        data-testid="recover-btn"
        onClick={() => {
          setRecoveryKey(String(Number(recoveryKey) + 1));
          setShouldCrash(false);
        }}
      >
        Recover
      </button>
      <button
        data-testid="crash-btn"
        onClick={() => setShouldCrash(true)}
      >
        Crash
      </button>
      <ContributionErrorBoundary
        contributionId="test.recoverable"
        kind="slot"
        label="Recoverable slot"
        recoveryKey={recoveryKey}
      >
        {shouldCrash ? (
          <ThrowingSlot message="Deliberate crash" />
        ) : (
          children ?? <NormalSlot label="All good" />
        )}
      </ContributionErrorBoundary>
    </div>
  );
}

describe('ContributionErrorBoundary', () => {
  describe('error containment', () => {
    it('renders children normally when no error', () => {
      render(
        <ContributionErrorBoundary contributionId="test.slot" kind="slot">
          <NormalSlot label="Hello" />
        </ContributionErrorBoundary>,
      );

      expect(screen.getByTestId('normal-slot')).toBeDefined();
      expect(screen.getByText('Hello')).toBeDefined();
    });

    it('renders fallback UI when child throws', () => {
      render(
        <ContributionErrorBoundary
          contributionId="test.broken"
          kind="slot"
          label="Broken header"
        >
          <ThrowingSlot />
        </ContributionErrorBoundary>,
      );

      // Fallback UI should be visible
      expect(screen.getByRole('alert')).toBeDefined();
      expect(screen.getByText(/Slot error/)).toBeDefined();
      expect(screen.getByText(/Broken header/)).toBeDefined();
      // Error message should be in the fallback
      expect(screen.getByText('Boom!')).toBeDefined();
    });

    it('emits onError callback with structured error info', () => {
      const onError = vi.fn();

      render(
        <ContributionErrorBoundary
          contributionId="test.err"
          extensionId="com.example.err"
          kind="panel"
          label="Test panel"
          onError={onError}
        >
          <ThrowingSlot message="Panel crash" />
        </ContributionErrorBoundary>,
      );

      expect(onError).toHaveBeenCalledTimes(1);
      const info: ContributionErrorInfo = onError.mock.calls[0][0];
      expect(info.contributionId).toBe('test.err');
      expect(info.extensionId).toBe('com.example.err');
      expect(info.kind).toBe('panel');
      expect(info.error.message).toBe('Panel crash');
      expect(info.componentStack).toBeTruthy();
    });

    it('falls back to contributionId as label when none provided', () => {
      render(
        <ContributionErrorBoundary contributionId="test.nolabel" kind="inspectorSection">
          <ThrowingSlot />
        </ContributionErrorBoundary>,
      );

      expect(screen.getByText(/test\.nolabel/)).toBeDefined();
    });
  });

  describe('contribution kind labels', () => {
    it('renders "Slot error" for kind=slot', () => {
      render(
        <ContributionErrorBoundary contributionId="s1" kind="slot" label="My slot">
          <ThrowingSlot />
        </ContributionErrorBoundary>,
      );
      expect(screen.getByText(/Slot error/)).toBeDefined();
    });

    it('renders "Dialog error" for kind=dialog', () => {
      render(
        <ContributionErrorBoundary contributionId="d1" kind="dialog" label="My dialog">
          <ThrowingSlot />
        </ContributionErrorBoundary>,
      );
      expect(screen.getByText(/Dialog error/)).toBeDefined();
    });

    it('renders "Panel error" for kind=panel', () => {
      render(
        <ContributionErrorBoundary contributionId="p1" kind="panel" label="My panel">
          <ThrowingSlot />
        </ContributionErrorBoundary>,
      );
      expect(screen.getByText(/Panel error/)).toBeDefined();
    });

    it('renders "Inspector section error" for kind=inspectorSection', () => {
      render(
        <ContributionErrorBoundary
          contributionId="i1"
          kind="inspectorSection"
          label="My section"
        >
          <ThrowingSlot />
        </ContributionErrorBoundary>,
      );
      expect(screen.getByText(/Inspector section error/)).toBeDefined();
    });
  });

  describe('isolation', () => {
    it('does not catch errors from sibling boundaries', () => {
      const onErrorA = vi.fn();
      const onErrorB = vi.fn();

      render(
        <div>
          <ContributionErrorBoundary
            contributionId="slot.a"
            kind="slot"
            label="Slot A"
            onError={onErrorA}
          >
            <ThrowingSlot message="Error in A" />
          </ContributionErrorBoundary>
          <ContributionErrorBoundary
            contributionId="slot.b"
            kind="slot"
            label="Slot B"
            onError={onErrorB}
          >
            <NormalSlot label="Should render" />
          </ContributionErrorBoundary>
        </div>,
      );

      // Only slot A should have errored
      expect(onErrorA).toHaveBeenCalledTimes(1);
      expect(onErrorB).not.toHaveBeenCalled();

      // Slot B should still render normally
      expect(screen.getByTestId('normal-slot')).toBeDefined();
      expect(screen.getByText('Should render')).toBeDefined();

      // Slot A fallback should be present
      expect(screen.getByText(/Slot A/)).toBeDefined();
      expect(screen.getByText(/Error in A/)).toBeDefined();
    });
  });

  describe('data attributes', () => {
    it('sets data-video-editor-contribution-error and kind on fallback', () => {
      const { container } = render(
        <ContributionErrorBoundary contributionId="test.data" kind="dialog">
          <ThrowingSlot />
        </ContributionErrorBoundary>,
      );

      const fallback = container.querySelector('[data-video-editor-contribution-error="true"]');
      expect(fallback).toBeTruthy();
      expect(fallback!.getAttribute('data-video-editor-contribution-kind')).toBe('dialog');
    });
  });

  describe('onError not called when no error', () => {
    it('does not call onError for normal renders', () => {
      const onError = vi.fn();

      render(
        <ContributionErrorBoundary
          contributionId="test.ok"
          kind="slot"
          onError={onError}
        >
          <NormalSlot />
        </ContributionErrorBoundary>,
      );

      expect(onError).not.toHaveBeenCalled();
    });
  });

  describe('crash recovery', () => {
    describe('with recoveryKey', () => {
      it('resets error and renders children when recoveryKey changes', async () => {
        render(
          <RecoverableBoundaryWrapper initialRecoveryKey="0" initialCrash={true} />,
        );

        // Should show fallback after crash
        expect(screen.getByRole('alert')).toBeDefined();
        expect(screen.getByText(/Slot error/)).toBeDefined();
        expect(screen.getByText('Deliberate crash')).toBeDefined();

        // Trigger recovery by changing recoveryKey + setting shouldCrash=false
        await act(async () => {
          screen.getByTestId('recover-btn').click();
        });

        // Should now render normal content
        await waitFor(() => {
          expect(screen.getByTestId('normal-slot')).toBeDefined();
        });
        expect(screen.getByText('All good')).toBeDefined();
        // Fallback should be gone
        expect(screen.queryByRole('alert')).toBeNull();
      });

      it('does NOT auto-reset on children change when recoveryKey is unchanged', () => {
        // This test verifies the infinite-loop prevention:
        // even if the parent re-renders and passes new children,
        // as long as recoveryKey stays the same, the error persists.
        const onError = vi.fn();

        // Use a stable wrapper that toggles children reference without
        // changing recoveryKey.  We render a throwing child first, then
        // re-render with different (still-throwing) children.
        const { rerender } = render(
          <ContributionErrorBoundary
            contributionId="test.norecovery"
            kind="slot"
            label="No recovery yet"
            recoveryKey="fixed-key"
            onError={onError}
          >
            <ThrowingSlot message="First crash" />
          </ContributionErrorBoundary>,
        );

        expect(screen.getByText('First crash')).toBeDefined();
        const firstCallCount = onError.mock.calls.length;

        // Re-render with new children (different message), same recoveryKey
        rerender(
          <ContributionErrorBoundary
            contributionId="test.norecovery"
            kind="slot"
            label="No recovery yet"
            recoveryKey="fixed-key"
            onError={onError}
          >
            <ThrowingSlot message="Second crash" />
          </ContributionErrorBoundary>,
        );

        // The boundary should NOT have reset — error from first crash persists.
        // The fallback should still show the FIRST error message, not the second.
        expect(screen.getByText('First crash')).toBeDefined();
        expect(screen.queryByText('Second crash')).toBeNull();

        // onError should only have been called once (for the first crash),
        // not again for the re-render with new children.
        expect(onError.mock.calls.length).toBe(firstCallCount);
      });

      it('allows recovery through recoveryKey after crash prevents auto-recovery', () => {
        // Step 1: crash
        const { rerender } = render(
          <ContributionErrorBoundary
            contributionId="test.manual"
            kind="slot"
            label="Manual recovery"
            recoveryKey="v1"
          >
            <ThrowingSlot message="Crash v1" />
          </ContributionErrorBoundary>,
        );

        expect(screen.getByRole('alert')).toBeDefined();
        expect(screen.getByText('Crash v1')).toBeDefined();

        // Step 2: re-render with new children but same recoveryKey — no reset
        rerender(
          <ContributionErrorBoundary
            contributionId="test.manual"
            kind="slot"
            label="Manual recovery"
            recoveryKey="v1"
          >
            <ThrowingSlot message="Crash v1 again" />
          </ContributionErrorBoundary>,
        );

        // Still showing old error
        expect(screen.getByText('Crash v1')).toBeDefined();

        // Step 3: change recoveryKey AND provide non-crashing children
        rerender(
          <ContributionErrorBoundary
            contributionId="test.manual"
            kind="slot"
            label="Manual recovery"
            recoveryKey="v2"
          >
            <NormalSlot label="Recovered!" />
          </ContributionErrorBoundary>,
        );

        // Should now render normal content
        expect(screen.getByTestId('normal-slot')).toBeDefined();
        expect(screen.getByText('Recovered!')).toBeDefined();
        expect(screen.queryByRole('alert')).toBeNull();
      });

      it('does not reset when recoveryKey is the same string value', () => {
        const onError = vi.fn();

        render(
          <ContributionErrorBoundary
            contributionId="test.samekey"
            kind="slot"
            label="Same key"
            recoveryKey="unchanged"
            onError={onError}
          >
            <ThrowingSlot message="Original crash" />
          </ContributionErrorBoundary>,
        );

        expect(onError).toHaveBeenCalledTimes(1);
        expect(screen.getByText('Original crash')).toBeDefined();
        // No recovery — error state should persist
      });
    });

    describe('without recoveryKey (legacy behavior)', () => {
      it('resets error when children reference changes', () => {
        const { rerender } = render(
          <ContributionErrorBoundary
            contributionId="test.legacy"
            kind="slot"
            label="Legacy"
          >
            <ThrowingSlot message="Legacy crash" />
          </ContributionErrorBoundary>,
        );

        expect(screen.getByRole('alert')).toBeDefined();
        expect(screen.getByText('Legacy crash')).toBeDefined();

        // Re-render with new children (different reference)
        rerender(
          <ContributionErrorBoundary
            contributionId="test.legacy"
            kind="slot"
            label="Legacy"
          >
            <NormalSlot label="Legacy recovered" />
          </ContributionErrorBoundary>,
        );

        // Without recoveryKey, children-change resets the error
        expect(screen.getByTestId('normal-slot')).toBeDefined();
        expect(screen.getByText('Legacy recovered')).toBeDefined();
        expect(screen.queryByRole('alert')).toBeNull();
      });
    });

    describe('recovery key integration via RecoverableBoundaryWrapper', () => {
      it('shows fallback after crash and recovers after recovery button click', async () => {
        render(
          <RecoverableBoundaryWrapper
            initialRecoveryKey="0"
            initialCrash={false}
          />,
        );

        // Start normal
        expect(screen.getByTestId('normal-slot')).toBeDefined();
        expect(screen.getByText('All good')).toBeDefined();

        // Trigger crash
        await act(async () => {
          screen.getByTestId('crash-btn').click();
        });

        // Fallback shown
        expect(screen.getByRole('alert')).toBeDefined();
        expect(screen.getByText('Deliberate crash')).toBeDefined();

        // Recover
        await act(async () => {
          screen.getByTestId('recover-btn').click();
        });

        // Normal again
        await waitFor(() => {
          expect(screen.getByTestId('normal-slot')).toBeDefined();
        });
        expect(screen.getByText('All good')).toBeDefined();
        expect(screen.queryByRole('alert')).toBeNull();
      });
    });
  });
});
