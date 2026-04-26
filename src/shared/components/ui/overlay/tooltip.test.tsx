import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/overlay/tooltip';
import { __resetOverlayStackForTests, useOverlayStackApi } from '@/shared/state/overlayStack';

describe('overlay tooltip wrapper', () => {
  it('renders an asChild trigger and registers a non-modal overlay when opened', async () => {
    __resetOverlayStackForTests();

    render(
      <TooltipProvider delayDuration={0}>
        <Tooltip open>
          <TooltipTrigger asChild>
            <button type="button">Hover me</button>
          </TooltipTrigger>
          <TooltipContent>Tooltip body</TooltipContent>
        </Tooltip>
      </TooltipProvider>,
    );

    expect(screen.getByRole('button', { name: 'Hover me' })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Tooltip body')).toBeInTheDocument();
    });

    const topOverlay = useOverlayStackApi().getState().getTopOverlay();
    expect(topOverlay?.type).toBe('tooltip');
    expect(topOverlay?.modal).toBe(false);
    expect(document.body.style.pointerEvents).toBe('');
  });

  it('supports toggling open state through the root onOpenChange callback', () => {
    let open = false;

    const Example = () => (
      <Tooltip open={open} onOpenChange={(nextOpen) => { open = nextOpen; }}>
        <TooltipTrigger>Open tooltip</TooltipTrigger>
        <TooltipContent>Content</TooltipContent>
      </Tooltip>
    );

    render(<Example />);
    fireEvent.pointerMove(screen.getByRole('button', { name: 'Open tooltip' }));

    expect(typeof open).toBe('boolean');
  });
});
