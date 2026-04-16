import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockRender = vi.fn();
const mockCreateRoot = vi.fn(() => ({ render: mockRender }));

vi.mock('react-dom/client', () => ({
  createRoot: mockCreateRoot,
}));

vi.mock('@/shared/lib/logger', () => ({
  initializeLoggerRuntime: vi.fn(),
  reactProfilerOnRender: vi.fn(),
}));

const initializeProjectSelectionStoreMock = vi.fn();
const initializePreloadingServiceMock = vi.fn();
const initializeToolSettingsWriteRuntimeMock = vi.fn();
const initializeNetworkStatusManagerMock = vi.fn();

vi.mock('@/shared/contexts/projectSelectionStore', () => ({
  initializeProjectSelectionStore: initializeProjectSelectionStoreMock,
}));

vi.mock('@/shared/lib/preloading', () => ({
  initializePreloadingService: initializePreloadingServiceMock,
}));

vi.mock('@/shared/settings', () => ({
  initializeToolSettingsWriteRuntime: initializeToolSettingsWriteRuntimeMock,
}));

vi.mock('@/shared/services/network/networkStatusManager', () => ({
  initializeNetworkStatusManager: initializeNetworkStatusManagerMock,
}));

vi.mock('@/app/App', () => ({
  App: () => null,
}));

vi.mock('@/app/components/error/AppErrorBoundary', () => ({
  AppErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

describe('bootstrap.renderApp', () => {
  beforeEach(() => {
    vi.resetModules();
    mockCreateRoot.mockClear();
    mockRender.mockClear();
    initializeProjectSelectionStoreMock.mockClear();
    initializePreloadingServiceMock.mockClear();
    initializeToolSettingsWriteRuntimeMock.mockClear();
    initializeNetworkStatusManagerMock.mockClear();
    localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  it('renders the app into the provided root element', async () => {
    const { renderApp } = await import('@/app/bootstrap');
    const root = document.createElement('div');

    renderApp(root);

    expect(mockCreateRoot).toHaveBeenCalledWith(root);
    expect(mockRender).toHaveBeenCalledTimes(1);
  }, 15_000);

  it('initializes dark mode when no preference exists', async () => {
    const { initializeAppEnvironment } = await import('@/app/bootstrap');

    initializeAppEnvironment();

    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(initializeProjectSelectionStoreMock.mock.calls.length).toBeGreaterThanOrEqual(1);
    expect(initializePreloadingServiceMock.mock.calls.length).toBeGreaterThanOrEqual(1);
    expect(initializeToolSettingsWriteRuntimeMock.mock.calls.length).toBeGreaterThanOrEqual(1);
    expect(initializeNetworkStatusManagerMock.mock.calls.length).toBeGreaterThanOrEqual(1);
  }, 15_000);
});

describe('bootstrap runtime gates', () => {
  it('loads debug tools only in non-test dev runtime', async () => {
    const { shouldLoadDevDebugTools } = await import('@/app/bootstrap');

    expect(shouldLoadDevDebugTools({ MODE: 'development', DEV: true, VITEST: false })).toBe(true);
    expect(shouldLoadDevDebugTools({ MODE: 'test', DEV: true, VITEST: false })).toBe(false);
    expect(shouldLoadDevDebugTools({ MODE: 'development', DEV: false, VITEST: false })).toBe(false);
    expect(shouldLoadDevDebugTools({ MODE: 'development', DEV: true, VITEST: true })).toBe(false);
  });

  it('loads autoplay monitor only in non-test dev runtime', async () => {
    const { shouldLoadAutoplayMonitor } = await import('@/app/bootstrap');

    expect(shouldLoadAutoplayMonitor({ MODE: 'development', DEV: true, VITEST: false })).toBe(true);
    expect(shouldLoadAutoplayMonitor({ MODE: 'production', DEV: false, VITEST: false })).toBe(false);
    expect(shouldLoadAutoplayMonitor({ MODE: 'test', DEV: true, VITEST: false })).toBe(false);
    expect(shouldLoadAutoplayMonitor({ MODE: 'development', DEV: true, VITEST: true })).toBe(false);
  });
});
