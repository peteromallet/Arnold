import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { __resetOverlayStackForTests, useOverlayStackApi } from '@/shared/state/overlayStack';
import { useCurrentOverlayHandle, useCurrentOverlayTopmost } from './overlayBridge';
import {
  LightboxDialog,
  LightboxDialogBackdrop,
  LightboxDialogDescription,
  LightboxDialogPopup,
  LightboxDialogPortal,
  LightboxDialogTitle,
} from './lightbox';

function OverlayProbe() {
  const handle = useCurrentOverlayHandle();
  const isTopmost = useCurrentOverlayTopmost();

  return (
    <div
      data-testid="overlay-probe"
      data-overlay-id={handle.id}
      data-topmost={String(isTopmost)}
    />
  );
}

describe('Lightbox overlay wrapper', () => {
  afterEach(() => {
    cleanup();
    __resetOverlayStackForTests();
    document.body.innerHTML = '';
  });

  it('registers lightbox popup and backdrop with the overlay stack and exposes bridge hooks', () => {
    render(
      <LightboxDialog open modal onOpenChange={() => {}}>
        <LightboxDialogPortal>
          <LightboxDialogBackdrop data-testid="lightbox-backdrop" />
          <LightboxDialogPopup data-testid="lightbox-popup">
            <LightboxDialogTitle>Lightbox title</LightboxDialogTitle>
            <LightboxDialogDescription>Lightbox description</LightboxDialogDescription>
            <OverlayProbe />
          </LightboxDialogPopup>
        </LightboxDialogPortal>
      </LightboxDialog>,
    );

    const popup = screen.getByTestId('lightbox-popup');
    const backdrop = screen.getByTestId('lightbox-backdrop');
    const probe = screen.getByTestId('overlay-probe');
    const overlay = useOverlayStackApi().getState().getTopOverlay();

    expect(overlay?.type).toBe('lightbox');
    expect(overlay?.elements).toContain(popup);
    expect(overlay?.elements).toContain(backdrop);
    expect(probe).toHaveAttribute('data-overlay-id', overlay?.id);
    expect(probe).toHaveAttribute('data-topmost', 'true');
    expect(backdrop.style.zIndex).toBe('1010');
    expect(popup.style.zIndex).toBe('1012');
  });
});
