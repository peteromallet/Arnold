// @vitest-environment jsdom
import { act, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useState, type ReactNode } from 'react';
import {
  ContributionErrorBoundary,
  HostContributionErrorBoundary,
  type ContributionErrorInfo,
} from '@/tools/video-editor/runtime/ContributionErrorBoundary';
import { DataProviderWrapper } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import type { VideoEditorRuntimeContextValue } from '@/tools/video-editor/contexts/DataProviderContext.tsx';

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

    it('does not show retry button when onRetry is not provided', () => {
      render(
        <ContributionErrorBoundary
          contributionId="test.broken"
          kind="slot"
          label="Broken header"
        >
          <ThrowingSlot />
        </ContributionErrorBoundary>,
      );

      // No retry button when onRetry is absent
      expect(screen.queryByTestId
        ? screen.queryByTestId?.('retry-btn')
        : screen.queryByText('Retry')
      ).toBeFalsy();
    });

    it('shows retry button when onRetry is provided', () => {
      const onRetry = vi.fn();
      render(
        <ContributionErrorBoundary
          contributionId="test.broken"
          kind="slot"
          label="Broken header"
          onRetry={onRetry}
        >
          <ThrowingSlot />
        </ContributionErrorBoundary>,
      );

      // Retry button visible
      const retryBtn = screen.getByText('Retry');
      expect(retryBtn).toBeDefined();
    });

    it('calls onRetry when retry button is clicked', async () => {
      const onRetry = vi.fn();
      render(
        <ContributionErrorBoundary
          contributionId="test.broken"
          kind="slot"
          label="Broken header"
          onRetry={onRetry}
        >
          <ThrowingSlot />
        </ContributionErrorBoundary>,
      );

      const retryBtn = screen.getByText('Retry');
      await act(async () => {
        retryBtn.click();
      });

      expect(onRetry).toHaveBeenCalledTimes(1);
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

// ─── HostContributionErrorBoundary integration tests ────────────────────

// Component that throws during render
function HostThrowingSlot({ message = 'Boom!' }: { message?: string }) {
  throw new Error(message);
}

// Normal rendering component
function HostNormalSlot({ label = 'OK' }: { label?: string }) {
  return <div data-testid="host-normal-slot">{label}</div>;
}

describe('HostContributionErrorBoundary', () => {
  describe('with real DataProviderWrapper context', () => {
    it('renders children normally when no error', () => {
      const runtime: VideoEditorRuntimeContextValue = {
        provider: null as unknown as VideoEditorRuntimeContextValue['provider'],
        assetResolver: null as unknown as VideoEditorRuntimeContextValue['assetResolver'],
        auth: null as unknown as VideoEditorRuntimeContextValue['auth'],
        project: null as unknown as VideoEditorRuntimeContextValue['project'],
        shots: null as unknown as VideoEditorRuntimeContextValue['shots'],
        mediaLightbox: null as unknown as VideoEditorRuntimeContextValue['mediaLightbox'],
        agentChat: null as unknown as VideoEditorRuntimeContextValue['agentChat'],
        toast: null as unknown as VideoEditorRuntimeContextValue['toast'],
        telemetry: null as unknown as VideoEditorRuntimeContextValue['telemetry'],
        timelineId: 'test-timeline',
        userId: 'test-user',
        extensions: null as unknown as VideoEditorRuntimeContextValue['extensions'],
      };

      render(
        <DataProviderWrapper value={runtime}>
          <HostContributionErrorBoundary
            contributionId="test.host.normal"
            kind="slot"
          >
            <HostNormalSlot label="Host normal" />
          </HostContributionErrorBoundary>
        </DataProviderWrapper>,
      );

      expect(screen.getByTestId('host-normal-slot')).toBeDefined();
      expect(screen.getByText('Host normal')).toBeDefined();
    });

    it('renders fallback UI with retry button when extensionId is known, and retry triggers lifecycle-host recovery', async () => {
      const getRecoveryKey = vi.fn(() => '1');
      const incrementRecoveryKey = vi.fn(() => '2');

      const runtime: VideoEditorRuntimeContextValue = {
        provider: null as unknown as VideoEditorRuntimeContextValue['provider'],
        assetResolver: null as unknown as VideoEditorRuntimeContextValue['assetResolver'],
        auth: null as unknown as VideoEditorRuntimeContextValue['auth'],
        project: null as unknown as VideoEditorRuntimeContextValue['project'],
        shots: null as unknown as VideoEditorRuntimeContextValue['shots'],
        mediaLightbox: null as unknown as VideoEditorRuntimeContextValue['mediaLightbox'],
        agentChat: null as unknown as VideoEditorRuntimeContextValue['agentChat'],
        toast: null as unknown as VideoEditorRuntimeContextValue['toast'],
        telemetry: null as unknown as VideoEditorRuntimeContextValue['telemetry'],
        timelineId: 'test-timeline',
        userId: 'test-user',
        extensions: null as unknown as VideoEditorRuntimeContextValue['extensions'],
        getRecoveryKey,
        incrementRecoveryKey,
      };

      render(
        <DataProviderWrapper value={runtime}>
          <HostContributionErrorBoundary
            contributionId="test.host.broken"
            extensionId="com.example.broken"
            kind="slot"
            label="Broken host slot"
            maxRetries={3}
            retryDebounceMs={0}
          >
            <HostThrowingSlot message="Host crash" />
          </HostContributionErrorBoundary>
        </DataProviderWrapper>,
      );

      // Fallback UI shown
      expect(screen.getByRole('alert')).toBeDefined();
      expect(screen.getByText(/Slot error/)).toBeDefined();

      // getRecoveryKey should have been called
      expect(getRecoveryKey).toHaveBeenCalledWith('com.example.broken');

      // Retry button should be visible (since extensionId is known)
      const retryBtn = screen.getByText(/Retry/);
      expect(retryBtn).toBeDefined();

      // incrementRecoveryKey should NOT have been called automatically (no auto-retry)
      expect(incrementRecoveryKey).not.toHaveBeenCalled();

      // Click the retry button
      await act(async () => {
        retryBtn.click();
      });

      // Now incrementRecoveryKey should have been called (user-initiated retry)
      expect(incrementRecoveryKey).toHaveBeenCalledWith('com.example.broken');
    });

    it('falls back to legacy boundary behavior when no extensionId is provided (no retry button)', () => {
      const runtime: VideoEditorRuntimeContextValue = {
        provider: null as unknown as VideoEditorRuntimeContextValue['provider'],
        assetResolver: null as unknown as VideoEditorRuntimeContextValue['assetResolver'],
        auth: null as unknown as VideoEditorRuntimeContextValue['auth'],
        project: null as unknown as VideoEditorRuntimeContextValue['project'],
        shots: null as unknown as VideoEditorRuntimeContextValue['shots'],
        mediaLightbox: null as unknown as VideoEditorRuntimeContextValue['mediaLightbox'],
        agentChat: null as unknown as VideoEditorRuntimeContextValue['agentChat'],
        toast: null as unknown as VideoEditorRuntimeContextValue['toast'],
        telemetry: null as unknown as VideoEditorRuntimeContextValue['telemetry'],
        timelineId: 'test-timeline',
        userId: 'test-user',
        extensions: null as unknown as VideoEditorRuntimeContextValue['extensions'],
      };

      const { rerender } = render(
        <DataProviderWrapper value={runtime}>
          <HostContributionErrorBoundary
            contributionId="test.host.noid"
            kind="slot"
          >
            <HostThrowingSlot message="No ID crash" />
          </HostContributionErrorBoundary>
        </DataProviderWrapper>,
      );

      // Fallback shown
      expect(screen.getByRole('alert')).toBeDefined();
      expect(screen.getByText('No ID crash')).toBeDefined();

      // No retry button since no extensionId
      expect(screen.queryByText(/Retry/)).toBeNull();

      // Re-render with new children — should auto-reset (legacy behavior)
      rerender(
        <DataProviderWrapper value={runtime}>
          <HostContributionErrorBoundary
            contributionId="test.host.noid"
            kind="slot"
          >
            <HostNormalSlot label="Recovered without ID" />
          </HostContributionErrorBoundary>
        </DataProviderWrapper>,
      );

      // Should recover (legacy children-change reset)
      expect(screen.getByTestId('host-normal-slot')).toBeDefined();
      expect(screen.getByText('Recovered without ID')).toBeDefined();
      expect(screen.queryByRole('alert')).toBeNull();
    });

    it('resets error when recovery key changes (disable/re-enable render fresh children exactly once)', async () => {
      // Start with recovery key "1"
      let currentKey = '1';
      const getRecoveryKey = vi.fn(() => currentKey);
      const incrementRecoveryKey = vi.fn(() => {
        currentKey = String(Number(currentKey) + 1);
        return currentKey;
      });

      function createRuntime(): VideoEditorRuntimeContextValue {
        return {
          provider: null as unknown as VideoEditorRuntimeContextValue['provider'],
          assetResolver: null as unknown as VideoEditorRuntimeContextValue['assetResolver'],
          auth: null as unknown as VideoEditorRuntimeContextValue['auth'],
          project: null as unknown as VideoEditorRuntimeContextValue['project'],
          shots: null as unknown as VideoEditorRuntimeContextValue['shots'],
          mediaLightbox: null as unknown as VideoEditorRuntimeContextValue['mediaLightbox'],
          agentChat: null as unknown as VideoEditorRuntimeContextValue['agentChat'],
          toast: null as unknown as VideoEditorRuntimeContextValue['toast'],
          telemetry: null as unknown as VideoEditorRuntimeContextValue['telemetry'],
          timelineId: 'test-timeline',
          userId: 'test-user',
          extensions: null as unknown as VideoEditorRuntimeContextValue['extensions'],
          getRecoveryKey,
          incrementRecoveryKey,
        };
      }

      const { rerender } = render(
        <DataProviderWrapper value={createRuntime()}>
          <HostContributionErrorBoundary
            contributionId="test.host.recover"
            extensionId="com.example.recover"
            kind="slot"
            maxRetries={0}
          >
            <HostThrowingSlot message="Will recover" />
          </HostContributionErrorBoundary>
        </DataProviderWrapper>,
      );

      // Fallback shown
      expect(screen.getByRole('alert')).toBeDefined();
      expect(screen.getByText('Will recover')).toBeDefined();

      // Simulate external recovery: increment key and re-render
      currentKey = '2';
      rerender(
        <DataProviderWrapper value={createRuntime()}>
          <HostContributionErrorBoundary
            contributionId="test.host.recover"
            extensionId="com.example.recover"
            kind="slot"
            maxRetries={0}
          >
            <HostNormalSlot label="Fresh after recovery" />
          </HostContributionErrorBoundary>
        </DataProviderWrapper>,
      );

      // Should render fresh children after recovery key change
      expect(screen.getByTestId('host-normal-slot')).toBeDefined();
      expect(screen.getByText('Fresh after recovery')).toBeDefined();
      expect(screen.queryByRole('alert')).toBeNull();
    });

    it('does NOT reset on children change when recovery key is unchanged', () => {
      const getRecoveryKey = vi.fn(() => 'fixed');
      const incrementRecoveryKey = vi.fn(() => 'fixed');

      function createRuntime(): VideoEditorRuntimeContextValue {
        return {
          provider: null as unknown as VideoEditorRuntimeContextValue['provider'],
          assetResolver: null as unknown as VideoEditorRuntimeContextValue['assetResolver'],
          auth: null as unknown as VideoEditorRuntimeContextValue['auth'],
          project: null as unknown as VideoEditorRuntimeContextValue['project'],
          shots: null as unknown as VideoEditorRuntimeContextValue['shots'],
          mediaLightbox: null as unknown as VideoEditorRuntimeContextValue['mediaLightbox'],
          agentChat: null as unknown as VideoEditorRuntimeContextValue['agentChat'],
          toast: null as unknown as VideoEditorRuntimeContextValue['toast'],
          telemetry: null as unknown as VideoEditorRuntimeContextValue['telemetry'],
          timelineId: 'test-timeline',
          userId: 'test-user',
          extensions: null as unknown as VideoEditorRuntimeContextValue['extensions'],
          getRecoveryKey,
          incrementRecoveryKey,
        };
      }

      const { rerender } = render(
        <DataProviderWrapper value={createRuntime()}>
          <HostContributionErrorBoundary
            contributionId="test.host.stuck"
            extensionId="com.example.stuck"
            kind="slot"
            maxRetries={0}
          >
            <HostThrowingSlot message="First crash" />
          </HostContributionErrorBoundary>
        </DataProviderWrapper>,
      );

      expect(screen.getByRole('alert')).toBeDefined();
      expect(screen.getByText('First crash')).toBeDefined();

      // Re-render with new children but same recovery key
      rerender(
        <DataProviderWrapper value={createRuntime()}>
          <HostContributionErrorBoundary
            contributionId="test.host.stuck"
            extensionId="com.example.stuck"
            kind="slot"
            maxRetries={0}
          >
            <HostThrowingSlot message="Second crash" />
          </HostContributionErrorBoundary>
        </DataProviderWrapper>,
      );

      // Error should persist — recovery key hasn't changed
      // Still shows FIRST error, not second (boundary did NOT reset)
      expect(screen.getByRole('alert')).toBeDefined();
      expect(screen.getByText('First crash')).toBeDefined();
      expect(screen.queryByText('Second crash')).toBeNull();
    });

    it('disables retry button after maxRetries exhausted', async () => {
      const getRecoveryKey = vi.fn(() => '1');
      const incrementRecoveryKey = vi.fn(() => '2');

      const runtime: VideoEditorRuntimeContextValue = {
        provider: null as unknown as VideoEditorRuntimeContextValue['provider'],
        assetResolver: null as unknown as VideoEditorRuntimeContextValue['assetResolver'],
        auth: null as unknown as VideoEditorRuntimeContextValue['auth'],
        project: null as unknown as VideoEditorRuntimeContextValue['project'],
        shots: null as unknown as VideoEditorRuntimeContextValue['shots'],
        mediaLightbox: null as unknown as VideoEditorRuntimeContextValue['mediaLightbox'],
        agentChat: null as unknown as VideoEditorRuntimeContextValue['agentChat'],
        toast: null as unknown as VideoEditorRuntimeContextValue['toast'],
        telemetry: null as unknown as VideoEditorRuntimeContextValue['telemetry'],
        timelineId: 'test-timeline',
        userId: 'test-user',
        extensions: null as unknown as VideoEditorRuntimeContextValue['extensions'],
        getRecoveryKey,
        incrementRecoveryKey,
      };

      render(
        <DataProviderWrapper value={runtime}>
          <HostContributionErrorBoundary
            contributionId="test.host.exhausted"
            extensionId="com.example.exhausted"
            kind="panel"
            maxRetries={1}
            retryDebounceMs={0}
          >
            <HostThrowingSlot message="Always crashes" />
          </HostContributionErrorBoundary>
        </DataProviderWrapper>,
      );

      // Fallback shown
      expect(screen.getByRole('alert')).toBeDefined();

      // Retry button should be visible with "Retry (1)" text
      const retryBtn = screen.getByText(/Retry/);
      expect(retryBtn).toBeDefined();

      // No auto-retry — incrementRecoveryKey not called
      expect(incrementRecoveryKey).not.toHaveBeenCalled();

      // Click retry once (exhausts the only retry)
      await act(async () => {
        retryBtn.click();
      });

      expect(incrementRecoveryKey).toHaveBeenCalledTimes(1);

      // After exhaustion, button should show "Exhausted" and be disabled
      // (Note: since the throwing component still throws, the boundary
      //  re-catches the error, and retryCountRef shows 1 >= maxRetries=1)
      // The button text becomes "Exhausted" when retryDisabled is true.
      const exhaustedBtn = screen.getByText('Exhausted');
      expect(exhaustedBtn).toBeDefined();
      expect((exhaustedBtn as HTMLButtonElement).disabled).toBe(true);

      // Error persists
      expect(screen.getByText('Always crashes')).toBeDefined();
    });

    it('does NOT auto-retry on error (retry is user-initiated only)', () => {
      const getRecoveryKey = vi.fn(() => '1');
      const incrementRecoveryKey = vi.fn(() => '2');

      const runtime: VideoEditorRuntimeContextValue = {
        provider: null as unknown as VideoEditorRuntimeContextValue['provider'],
        assetResolver: null as unknown as VideoEditorRuntimeContextValue['assetResolver'],
        auth: null as unknown as VideoEditorRuntimeContextValue['auth'],
        project: null as unknown as VideoEditorRuntimeContextValue['project'],
        shots: null as unknown as VideoEditorRuntimeContextValue['shots'],
        mediaLightbox: null as unknown as VideoEditorRuntimeContextValue['mediaLightbox'],
        agentChat: null as unknown as VideoEditorRuntimeContextValue['agentChat'],
        toast: null as unknown as VideoEditorRuntimeContextValue['toast'],
        telemetry: null as unknown as VideoEditorRuntimeContextValue['telemetry'],
        timelineId: 'test-timeline',
        userId: 'test-user',
        extensions: null as unknown as VideoEditorRuntimeContextValue['extensions'],
        getRecoveryKey,
        incrementRecoveryKey,
      };

      render(
        <DataProviderWrapper value={runtime}>
          <HostContributionErrorBoundary
            contributionId="test.host.noauto"
            extensionId="com.example.noauto"
            kind="slot"
            maxRetries={3}
            retryDebounceMs={0}
          >
            <HostThrowingSlot message="No auto retry" />
          </HostContributionErrorBoundary>
        </DataProviderWrapper>,
      );

      // Fallback shown
      expect(screen.getByRole('alert')).toBeDefined();

      // incrementRecoveryKey must NOT have been called (no auto-retry)
      expect(incrementRecoveryKey).not.toHaveBeenCalled();

      // Retry button is visible — retry is user-initiated only
      const retryBtn = screen.getByText(/Retry/);
      expect(retryBtn).toBeDefined();
    });
  });
});

});
