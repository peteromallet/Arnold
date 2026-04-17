// @vitest-environment jsdom

import * as React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import { HoverCard, HoverCardContent, HoverCardTrigger } from './hover-card';
import { __resetOverlayStackForTests, useOverlayStackApi } from '@/shared/state/overlayStack';

describe('overlay hover-card wrapper', () => {
  it('registers preview-card overlays without taking modal pointer-events ownership', async () => {
    __resetOverlayStackForTests();

    render(
      <HoverCard open onOpenChange={() => {}}>
        <HoverCardTrigger asChild>
          <button type="button">Preview</button>
        </HoverCardTrigger>
        <HoverCardContent data-testid="hover-card-content">Preview body</HoverCardContent>
      </HoverCard>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('hover-card-content')).toBeInTheDocument();
    });

    const topOverlay = useOverlayStackApi().getState().getTopOverlay();
    expect(topOverlay?.type).toBe('preview-card');
    expect(topOverlay?.modal).toBe(false);
    expect(topOverlay?.elements).toContain(screen.getByTestId('hover-card-content'));
    expect(document.body.style.pointerEvents).toBe('');
  });

  it('does not restore focus when a preview-card closes because it is non-modal ordering only', async () => {
    const opener = document.createElement('button');
    document.body.appendChild(opener);
    const focusSpy = vi.spyOn(opener, 'focus');

    function Harness() {
      const [open, setOpen] = React.useState(true);

      React.useEffect(() => {
        opener.focus();
      }, []);

      return (
        <HoverCard open={open} onOpenChange={setOpen}>
          <HoverCardTrigger asChild>
            <button type="button">Preview</button>
          </HoverCardTrigger>
          <HoverCardContent data-testid="hover-card-content">Preview body</HoverCardContent>
          <button type="button" onClick={() => setOpen(false)}>
            Close preview
          </button>
        </HoverCard>
      );
    }

    render(<Harness />);

    await waitFor(() => {
      expect(screen.getByTestId('hover-card-content')).toBeInTheDocument();
    });

    act(() => {
      screen.getByRole('button', { name: 'Close preview' }).click();
    });

    await waitFor(() => {
      expect(screen.queryByTestId('hover-card-content')).toBeNull();
    });

    expect(focusSpy).toHaveBeenCalledTimes(1);
    expect(document.body.style.pointerEvents).toBe('');
  });
});
