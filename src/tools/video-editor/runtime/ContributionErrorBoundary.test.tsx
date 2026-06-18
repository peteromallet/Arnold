// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
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
});
