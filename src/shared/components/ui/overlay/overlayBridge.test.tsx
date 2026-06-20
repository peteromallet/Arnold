// @vitest-environment jsdom

import * as React from 'react';
import { act, cleanup, render, renderHook, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  __resetOverlayStackForTests,
  useOverlayStackApi,
} from '@/shared/state/overlayStack';
import {
  OverlayInstanceProvider,
  getClosestOverlayContainer,
  getTopmostKnownOverlaySurface,
  isElementWithinKnownOverlay,
  isElementWithinTopmostOverlay,
  useCurrentOverlayHandle,
  useCurrentOverlayTopmost,
  useCurrentOverlayTopmostForElement,
  useOverlayBridge,
  useOverlayElementRegistration,
} from './index';

function OverlayPopup({
  testId,
  children,
}: React.PropsWithChildren<{ testId: string }>) {
  const registerPopup = useOverlayElementRegistration('popup');
  return (
    <div ref={registerPopup} data-testid={testId}>
      {children}
    </div>
  );
}

function OverlayBackdrop({ testId }: { testId: string }) {
  const registerBackdrop = useOverlayElementRegistration('backdrop');
  return <div ref={registerBackdrop} data-testid={testId} />;
}

function OverlayStateProbe({
  testId,
}: {
  testId: string;
}) {
  const handle = useCurrentOverlayHandle();
  const [element, setElement] = React.useState<HTMLElement | null>(null);
  const isTopmost = useCurrentOverlayTopmost();
  const isElementTopmost = useCurrentOverlayTopmostForElement(element);

  return (
    <div
      ref={setElement}
      data-testid={testId}
      data-overlay-id={handle.id}
      data-topmost={String(isTopmost)}
      data-element-topmost={String(isElementTopmost)}
    />
  );
}

function TestOverlay({
  id,
  type,
  modal = false,
  withPopup = true,
  withBackdrop = false,
  children,
}: React.PropsWithChildren<{
  id?: string;
  type: string;
  modal?: boolean;
  withPopup?: boolean;
  withBackdrop?: boolean;
}>) {
  const bridge = useOverlayBridge({ id, type, modal });

  return (
    <OverlayInstanceProvider value={bridge}>
      {withBackdrop ? <OverlayBackdrop testId={`${type}-backdrop`} /> : null}
      {withPopup ? <OverlayPopup testId={`${type}-popup`}>{children}</OverlayPopup> : null}
    </OverlayInstanceProvider>
  );
}

describe('overlayBridge', () => {
  beforeEach(() => {
    __resetOverlayStackForTests();
  });

  afterEach(() => {
    cleanup();
    document.body.innerHTML = '';
    vi.restoreAllMocks();
    __resetOverlayStackForTests();
  });

  it('registers overlays only while popup or backdrop DOM exists and updates tracked elements as refs change', () => {
    const { rerender, unmount } = render(
      <TestOverlay id="dialog-a" type="dialog" modal withPopup={false} withBackdrop={false} />,
    );
    const store = useOverlayStackApi();

    expect(store.getState().overlays).toHaveLength(0);

    rerender(<TestOverlay id="dialog-a" type="dialog" modal withPopup />);
    expect(store.getState().overlays).toHaveLength(1);
    expect(store.getState().overlays[0].elements).toHaveLength(1);
    expect(screen.getByTestId('dialog-popup')).toHaveAttribute('data-overlay-stack-id', 'dialog-a');

    rerender(<TestOverlay id="dialog-a" type="dialog" modal withPopup withBackdrop />);
    expect(store.getState().overlays[0].elements).toHaveLength(2);
    expect(screen.getByTestId('dialog-backdrop')).toHaveAttribute('data-overlay-stack-kind', 'backdrop');

    rerender(<TestOverlay id="dialog-a" type="dialog" modal withPopup={false} withBackdrop />);
    expect(store.getState().overlays).toHaveLength(1);
    expect(store.getState().overlays[0].elements).toHaveLength(1);
    expect(screen.queryByTestId('dialog-popup')).toBeNull();

    rerender(<TestOverlay id="dialog-a" type="dialog" modal withPopup={false} withBackdrop={false} />);
    expect(store.getState().overlays).toHaveLength(0);

    unmount();
    expect(store.getState().overlays).toHaveLength(0);
  });

  it('exposes current overlay handle and topmost hooks for nested overlays', () => {
    render(
      <>
        <TestOverlay id="dialog-a" type="dialog" modal>
          <OverlayStateProbe testId="dialog-probe" />
        </TestOverlay>
        <TestOverlay id="popover-b" type="popover">
          <OverlayStateProbe testId="popover-probe" />
        </TestOverlay>
      </>,
    );

    expect(screen.getByTestId('dialog-probe')).toHaveAttribute('data-overlay-id', 'dialog-a');
    expect(screen.getByTestId('dialog-probe')).toHaveAttribute('data-topmost', 'false');
    expect(screen.getByTestId('dialog-probe')).toHaveAttribute('data-element-topmost', 'true');
    expect(screen.getByTestId('popover-probe')).toHaveAttribute('data-overlay-id', 'popover-b');
    expect(screen.getByTestId('popover-probe')).toHaveAttribute('data-topmost', 'true');
    expect(screen.getByTestId('popover-probe')).toHaveAttribute('data-element-topmost', 'true');
  });

  it('provides marker-compatible DOM helpers for container resolution and topmost checks', () => {
    render(
      <>
        <TestOverlay id="dialog-a" type="dialog" modal>
          <div data-testid="dialog-child" />
        </TestOverlay>
        <TestOverlay id="popover-b" type="popover">
          <div data-testid="popover-child" />
        </TestOverlay>
      </>,
    );

    const dialogPopup = screen.getByTestId('dialog-popup');
    const popoverPopup = screen.getByTestId('popover-popup');
    const dialogChild = screen.getByTestId('dialog-child');
    const popoverChild = screen.getByTestId('popover-child');

    expect(getClosestOverlayContainer(dialogChild)).toBe(dialogPopup);
    expect(getClosestOverlayContainer(popoverChild)).toBe(popoverPopup);
    expect(isElementWithinKnownOverlay(dialogChild)).toBe(true);
    expect(isElementWithinKnownOverlay(popoverChild)).toBe(true);
    expect(isElementWithinTopmostOverlay(dialogChild)).toBe(false);
    expect(isElementWithinTopmostOverlay(popoverChild)).toBe(true);
    expect(getTopmostKnownOverlaySurface()).toBe(popoverPopup);
  });

  it('falls back to legacy markers for callers that have not migrated yet', () => {
    const legacyDialog = document.createElement('div');
    legacyDialog.setAttribute('data-dialog-content', '');
    const legacyMenu = document.createElement('div');
    legacyMenu.setAttribute('role', 'menu');
    const legacyChild = document.createElement('button');
    legacyMenu.appendChild(legacyChild);
    document.body.append(legacyDialog, legacyMenu);

    vi.spyOn(window, 'getComputedStyle').mockImplementation((element: Element) => {
      const zIndex = element === legacyMenu ? '20' : '10';
      return {
        zIndex,
        display: 'block',
        visibility: 'visible',
      } as CSSStyleDeclaration;
    });

    expect(getClosestOverlayContainer(legacyChild)).toBe(legacyMenu);
    expect(isElementWithinKnownOverlay(legacyChild)).toBe(true);
    expect(isElementWithinTopmostOverlay(legacyChild)).toBe(true);
    expect(getTopmostKnownOverlaySurface()).toBe(legacyMenu);
  });

  it('stays usable from hooks-only consumers that only need the current overlay handle', () => {
    const Wrapper = ({ children }: React.PropsWithChildren) => {
      const bridge = useOverlayBridge({ id: 'menu-a', type: 'menu' });
      return (
        <OverlayInstanceProvider value={bridge}>
          <OverlayPopup testId="menu-popup">{children}</OverlayPopup>
        </OverlayInstanceProvider>
      );
    };

    const { result } = renderHook(() => useCurrentOverlayHandle(), { wrapper: Wrapper });

    expect(result.current.id).toBe('menu-a');
    act(() => {
      expect(result.current.isRegistered()).toBe(true);
    });
  });
});
