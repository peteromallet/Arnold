// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { BlockerActionCard } from '@/tools/video-editor/components/BlockerActionCard';
import type {
  BlockerActionCardNextAction,
  BlockerActionCardProps,
} from '@/tools/video-editor/components/BlockerActionCard';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function defaultProps(
  overrides: Partial<BlockerActionCardProps> = {},
): BlockerActionCardProps {
  return {
    severity: 'error',
    code: 'composition/effect-missing-ref',
    message: 'Effect "custom:glow" could not be resolved.',
    ...overrides,
  };
}

function sampleAction(
  overrides: Partial<BlockerActionCardNextAction> = {},
): BlockerActionCardNextAction {
  return {
    kind: 'install-extension',
    label: 'Install Extension',
    message: 'Install the missing extension to resolve this blocker.',
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('BlockerActionCard', () => {
  // -----------------------------------------------------------------------
  // Rendering basics
  // -----------------------------------------------------------------------

  it('renders severity badge with correct data attribute', () => {
    const props = defaultProps({ severity: 'warning' });
    render(<BlockerActionCard {...props} />);

    const badge = screen.getByText('WARNING');
    expect(badge).toBeDefined();
    expect(badge.getAttribute('data-video-editor-blocker-severity-badge')).toBe(
      'warning',
    );
  });

  it('renders the diagnostic code inside a <code> element', () => {
    render(<BlockerActionCard {...defaultProps()} />);

    const codeEl = screen.getByText('composition/effect-missing-ref');
    expect(codeEl.tagName).toBe('CODE');
  });

  it('renders the diagnostic message', () => {
    render(
      <BlockerActionCard
        {...defaultProps({
          message: 'Transition "dissolve" is from a disabled package.',
        })}
      />,
    );

    expect(
      screen.getByText('Transition "dissolve" is from a disabled package.'),
    ).toBeDefined();
  });

  it('sets role="alert" on the container', () => {
    render(<BlockerActionCard {...defaultProps()} />);

    const card = screen.getByRole('alert');
    expect(card).toBeDefined();
  });

  it('exposes severity and code as data attributes on the card', () => {
    render(
      <BlockerActionCard
        {...defaultProps({
          severity: 'info',
          code: 'composition/material-stale',
        })}
      />,
    );

    const card = screen.getByRole('alert');
    expect(card.getAttribute('data-video-editor-blocker-severity')).toBe(
      'info',
    );
    expect(card.getAttribute('data-video-editor-blocker-code')).toBe(
      'composition/material-stale',
    );
  });

  // -----------------------------------------------------------------------
  // Action button visibility
  // -----------------------------------------------------------------------

  it('renders the action button when both nextAction and onAction are provided', () => {
    const onAction = vi.fn();
    render(
      <BlockerActionCard
        {...defaultProps()}
        nextAction={sampleAction({ label: 'Fix Now' })}
        onAction={onAction}
      />,
    );

    const btn = screen.getByRole('button', { name: 'Fix Now' });
    expect(btn).toBeDefined();
    expect(btn.getAttribute('data-video-editor-blocker-action-kind')).toBe(
      'install-extension',
    );
  });

  it('does NOT render the action button when onAction is missing', () => {
    render(
      <BlockerActionCard
        {...defaultProps()}
        nextAction={sampleAction()}
        // onAction intentionally omitted
      />,
    );

    expect(screen.queryByRole('button')).toBeNull();
  });

  it('does NOT render the action button when nextAction is missing', () => {
    const onAction = vi.fn();
    render(
      <BlockerActionCard
        {...defaultProps()}
        // nextAction intentionally omitted
        onAction={onAction}
      />,
    );

    expect(screen.queryByRole('button')).toBeNull();
  });

  it('does NOT render the action button when nextAction is null', () => {
    const onAction = vi.fn();
    render(
      <BlockerActionCard
        {...defaultProps()}
        nextAction={null as unknown as BlockerActionCardNextAction}
        onAction={onAction}
      />,
    );

    expect(screen.queryByRole('button')).toBeNull();
  });

  it('does NOT render the action button when nextAction is undefined', () => {
    const onAction = vi.fn();
    render(
      <BlockerActionCard
        {...defaultProps()}
        nextAction={undefined}
        onAction={onAction}
      />,
    );

    expect(screen.queryByRole('button')).toBeNull();
  });

  // -----------------------------------------------------------------------
  // Action button callback
  // -----------------------------------------------------------------------

  it('invokes onAction exactly once when the action button is clicked', () => {
    const onAction = vi.fn();
    render(
      <BlockerActionCard
        {...defaultProps()}
        nextAction={sampleAction({ label: 'Repair' })}
        onAction={onAction}
      />,
    );

    const btn = screen.getByRole('button', { name: 'Repair' });
    fireEvent.click(btn);

    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it('sets the button title from nextAction.message', () => {
    const onAction = vi.fn();
    render(
      <BlockerActionCard
        {...defaultProps()}
        nextAction={sampleAction({
          label: 'Enable Extension',
          message: 'Enable the extension to unblock export.',
        })}
        onAction={onAction}
      />,
    );

    const btn = screen.getByRole('button', { name: 'Enable Extension' });
    expect(btn.getAttribute('title')).toBe(
      'Enable the extension to unblock export.',
    );
  });

  it('renders only one action button even with both props present', () => {
    const onAction = vi.fn();
    render(
      <BlockerActionCard
        {...defaultProps()}
        nextAction={sampleAction({ label: 'Bake' })}
        onAction={onAction}
      />,
    );

    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBe(1);
  });

  // -----------------------------------------------------------------------
  // start-process label and resolve-blocker compatibility
  // -----------------------------------------------------------------------

  it('renders "Start Process" label for start-process action kind', () => {
    const onAction = vi.fn();
    render(
      <BlockerActionCard
        {...defaultProps()}
        nextAction={sampleAction({
          kind: 'start-process',
          label: 'Start Process',
          message: 'Start the process to unblock.',
        })}
        onAction={onAction}
      />,
    );

    const btn = screen.getByRole('button', { name: 'Start Process' });
    expect(btn).toBeDefined();
    expect(btn.getAttribute('data-video-editor-blocker-action-kind')).toBe(
      'start-process',
    );
    expect(btn.getAttribute('title')).toBe('Start the process to unblock.');
  });

  it('preserves resolve-blocker label compatibility unchanged', () => {
    const onAction = vi.fn();
    render(
      <BlockerActionCard
        {...defaultProps()}
        nextAction={sampleAction({
          kind: 'resolve-blockers',
          label: 'Resolve Blockers',
          message: 'Resolve blocker issues.',
        })}
        onAction={onAction}
      />,
    );

    const btn = screen.getByRole('button', { name: 'Resolve Blockers' });
    expect(btn).toBeDefined();
    expect(btn.getAttribute('data-video-editor-blocker-action-kind')).toBe(
      'resolve-blockers',
    );
  });

  // -----------------------------------------------------------------------
  // Severity variants
  // -----------------------------------------------------------------------

  it.each([
    ['error', 'ERROR'],
    ['warning', 'WARNING'],
    ['info', 'INFO'],
  ] as const)('renders "%s" severity badge as "%s"', (severity, label) => {
    render(
      <BlockerActionCard
        {...defaultProps({ severity })}
        nextAction={sampleAction({ label: 'Go' })}
        onAction={vi.fn()}
      />,
    );

    expect(screen.getByText(label)).toBeDefined();
    const badge = screen.getByText(label);
    expect(
      badge.getAttribute('data-video-editor-blocker-severity-badge'),
    ).toBe(severity);
  });
});
