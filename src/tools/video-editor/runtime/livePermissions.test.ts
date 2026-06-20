/**
 * M11 T3: Unit tests for livePermissions.
 *
 * Covers:
 *  - API availability checks for all LiveSourceKind values
 *  - Probe results for available, unavailable, and no-API-required kinds
 *  - Request flows with mocked browser APIs (getUserMedia, requestMIDIAccess,
 *    serial, bluetooth)
 *  - Denied permission handling
 *  - Error handling for API failures
 *  - Media track cleanup on release
 *  - Dispose behavior and idempotent release
 *  - No mutation of persisted live binding metadata (verified via
 *    non-interaction with registry bindings)
 *
 * @module livePermissions.test
 * @milestone M11
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import {
  createLivePermissionService,
  getPermissionApiKind,
  type LivePermissionService,
  type PermissionProbeResult,
} from '@/tools/video-editor/runtime/livePermissions';
import type {
  LiveSourceKind,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Source kinds that require no browser API. */
const NO_API_KINDS: LiveSourceKind[] = ['generated', 'osc', 'custom'];

/** All LiveSourceKind values. */
const ALL_KINDS: LiveSourceKind[] = [
  'webcam',
  'microphone',
  'midi',
  'serial',
  'bluetooth',
  'generated',
  'screen-capture',
  'audio-device',
  'osc',
  'custom',
];

// Create a mock MediaStreamTrack for cleanup verification
function createMockTrack(kind: string, label = `${kind}-device`): MediaStreamTrack {
  const stopFn = vi.fn();
  return {
    kind,
    id: `${kind}-${Math.random()}`,
    label,
    enabled: true,
    muted: false,
    readyState: 'live',
    stop: stopFn,
    getConstraints: () => ({} as MediaTrackConstraints),
    getSettings: () => ({} as MediaTrackSettings),
    getCapabilities: () => ({} as MediaTrackCapabilities),
    applyConstraints: () => Promise.resolve(),
    clone: () => createMockTrack(kind, label),
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => true,
    contentHint: '',
    onended: null,
    onmute: null,
    onunmute: null,
  } as unknown as MediaStreamTrack;
}

// Create a mock MediaStream with tracks
function createMockStream(tracks: MediaStreamTrack[]): MediaStream {
  return {
    id: `stream-${Math.random()}`,
    active: true,
    getTracks: () => tracks,
    getAudioTracks: () => tracks.filter((t) => t.kind === 'audio'),
    getVideoTracks: () => tracks.filter((t) => t.kind === 'video'),
    addTrack: () => {},
    removeTrack: () => {},
    clone: () => createMockStream([...tracks]),
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => true,
    onaddtrack: null,
    onremovetrack: null,
    onactive: null,
    oninactive: null,
  } as unknown as MediaStream;
}

/** Create a DOMException-like error for permission denial mocking. */
function createPermissionDeniedError(message = 'Permission denied'): Error {
  // DOMException.name is read-only after construction in jsdom.
  // We create a proper DOMException with the right name.
  return new DOMException(message, 'NotAllowedError');
}

/** Create an AbortError DOMException. */
function createAbortError(message = 'The request was aborted'): Error {
  return new DOMException(message, 'AbortError');
}

/** Create a generic Error (not a DOMException). */
function createGenericError(message = 'No devices found'): Error {
  return new Error(message);
}

// ---------------------------------------------------------------------------
// Navigator setup helpers
// ---------------------------------------------------------------------------

/** Ensure mediaDevices.getUserMedia is available on navigator. */
function ensureMediaDevices(): () => void {
  const nav = navigator as Record<string, unknown>;
  if (!nav.mediaDevices) {
    nav.mediaDevices = {};
  }
  const md = nav.mediaDevices as Record<string, unknown>;
  const hadGetUserMedia = 'getUserMedia' in md;
  const original = md.getUserMedia;
  if (!hadGetUserMedia) {
    md.getUserMedia = vi.fn().mockRejectedValue(new Error('mock not configured'));
  }
  return () => {
    if (!hadGetUserMedia) {
      delete md.getUserMedia;
    } else {
      md.getUserMedia = original;
    }
  };
}

/** Ensure requestMIDIAccess is available on navigator. */
function ensureMIDI(): () => void {
  const nav = navigator as Record<string, unknown>;
  const hadRequestMIDI = 'requestMIDIAccess' in nav;
  const original = nav.requestMIDIAccess;
  if (!hadRequestMIDI) {
    nav.requestMIDIAccess = vi.fn().mockRejectedValue(new Error('mock not configured'));
  }
  return () => {
    if (!hadRequestMIDI) {
      delete nav.requestMIDIAccess;
    } else {
      nav.requestMIDIAccess = original;
    }
  };
}

/** Ensure navigator.serial is available. */
function ensureSerial(): () => void {
  const nav = navigator as Record<string, unknown>;
  const hadSerial = 'serial' in nav;
  const original = nav.serial;
  if (!hadSerial) {
    nav.serial = {};
  }
  return () => {
    if (!hadSerial) {
      delete nav.serial;
    } else {
      nav.serial = original;
    }
  };
}

/** Ensure navigator.bluetooth is available. */
function ensureBluetooth(): () => void {
  const nav = navigator as Record<string, unknown>;
  const hadBluetooth = 'bluetooth' in nav;
  const original = nav.bluetooth;
  if (!hadBluetooth) {
    nav.bluetooth = {};
  }
  return () => {
    if (!hadBluetooth) {
      delete nav.bluetooth;
    } else {
      nav.bluetooth = original;
    }
  };
}

/** Fully remove an API from navigator (for unavailable tests). */
function removeApi(apiKind: string): () => void {
  const nav = navigator as Record<string, unknown>;
  switch (apiKind) {
    case 'mediaDevices': {
      const original = nav.mediaDevices;
      nav.mediaDevices = undefined;
      return () => { nav.mediaDevices = original; };
    }
    case 'requestMIDIAccess': {
      const original = nav.requestMIDIAccess;
      delete nav.requestMIDIAccess;
      return () => { if (original !== undefined) nav.requestMIDIAccess = original; };
    }
    case 'serial': {
      const original = nav.serial;
      delete nav.serial;
      return () => { if (original !== undefined) nav.serial = original; };
    }
    case 'bluetooth': {
      const original = nav.bluetooth;
      delete nav.bluetooth;
      return () => { if (original !== undefined) nav.bluetooth = original; };
    }
    default:
      return () => {};
  }
}

// ---------------------------------------------------------------------------
// getPermissionApiKind
// ---------------------------------------------------------------------------

describe('getPermissionApiKind', () => {
  it('maps media-device source kinds to media-devices', () => {
    expect(getPermissionApiKind('webcam')).toBe('media-devices');
    expect(getPermissionApiKind('microphone')).toBe('media-devices');
    expect(getPermissionApiKind('screen-capture')).toBe('media-devices');
    expect(getPermissionApiKind('audio-device')).toBe('media-devices');
  });

  it('maps midi to midi', () => {
    expect(getPermissionApiKind('midi')).toBe('midi');
  });

  it('maps serial to serial', () => {
    expect(getPermissionApiKind('serial')).toBe('serial');
  });

  it('maps bluetooth to bluetooth', () => {
    expect(getPermissionApiKind('bluetooth')).toBe('bluetooth');
  });

  it('maps generated/osc/custom to none', () => {
    expect(getPermissionApiKind('generated')).toBe('none');
    expect(getPermissionApiKind('osc')).toBe('none');
    expect(getPermissionApiKind('custom')).toBe('none');
  });
});

// ---------------------------------------------------------------------------
// Probe tests
// ---------------------------------------------------------------------------

describe('LivePermissionService: probe', () => {
  let service: LivePermissionService;
  let restoreApis: (() => void)[] = [];

  beforeEach(() => {
    // Set up all browser APIs so probes can find them
    restoreApis = [
      ensureMediaDevices(),
      ensureMIDI(),
      ensureSerial(),
      ensureBluetooth(),
    ];
    service = createLivePermissionService({ defaultReason: 'Testing' });
  });

  afterEach(() => {
    restoreApis.forEach((r) => r());
  });

  it('returns prompt state for available webcam API', () => {
    const result = service.probe('webcam');
    expect(result.sourceKind).toBe('webcam');
    expect(result.apiKind).toBe('media-devices');
    expect(result.apiAvailable).toBe(true);
    expect(result.permission.state).toBe('prompt');
    expect(result.diagnostic).toBeUndefined();
    expect(result.permission.reason).toBe('Testing');
  });

  it('returns prompt state for available microphone API', () => {
    const result = service.probe('microphone');
    expect(result.apiAvailable).toBe(true);
    expect(result.permission.state).toBe('prompt');
  });

  it('returns prompt state for available MIDI API', () => {
    const result = service.probe('midi');
    expect(result.apiKind).toBe('midi');
    expect(result.permission.state).toBe('prompt');
  });

  it('returns prompt state for available serial API', () => {
    const result = service.probe('serial');
    expect(result.apiKind).toBe('serial');
    expect(result.permission.state).toBe('prompt');
  });

  it('returns prompt state for available bluetooth API', () => {
    const result = service.probe('bluetooth');
    expect(result.apiKind).toBe('bluetooth');
    expect(result.permission.state).toBe('prompt');
  });

  it('returns granted for no-API-required kinds', () => {
    for (const kind of NO_API_KINDS) {
      const result = service.probe(kind);
      expect(result.apiKind).toBe('none');
      expect(result.apiAvailable).toBe(true);
      expect(result.permission.state).toBe('granted');
      expect(result.diagnostic).toBeUndefined();
      expect(result.permission.reason).toContain('No browser permission required');
    }
  });

  it('returns unavailable when mediaDevices API is missing', () => {
    // Remove APIs first, then create a fresh service
    restoreApis.forEach((r) => r());
    const restore = removeApi('mediaDevices');
    const svc = createLivePermissionService();

    const result = svc.probe('webcam');
    expect(result.apiAvailable).toBe(false);
    expect(result.permission.state).toBe('unavailable');
    expect(result.diagnostic).toBeDefined();
    expect(result.diagnostic!.code).toBe('live/permission-unavailable');
    expect(result.diagnostic!.severity).toBe('warning');

    restore();
  });

  it('returns unavailable when MIDI API is missing', () => {
    restoreApis.forEach((r) => r());
    const restore = removeApi('requestMIDIAccess');
    const svc = createLivePermissionService();

    const result = svc.probe('midi');
    expect(result.apiAvailable).toBe(false);
    expect(result.permission.state).toBe('unavailable');
    expect(result.diagnostic!.code).toBe('live/permission-unavailable');

    restore();
  });

  it('returns unavailable when serial API is missing', () => {
    restoreApis.forEach((r) => r());
    const restore = removeApi('serial');
    const svc = createLivePermissionService();

    const result = svc.probe('serial');
    expect(result.apiAvailable).toBe(false);
    expect(result.permission.state).toBe('unavailable');

    restore();
  });

  it('returns unavailable when bluetooth API is missing', () => {
    restoreApis.forEach((r) => r());
    const restore = removeApi('bluetooth');
    const svc = createLivePermissionService();

    const result = svc.probe('bluetooth');
    expect(result.apiAvailable).toBe(false);
    expect(result.permission.state).toBe('unavailable');

    restore();
  });

  it('covers all LiveSourceKind values in probe', () => {
    for (const kind of ALL_KINDS) {
      const result = service.probe(kind);
      expect(result.sourceKind).toBe(kind);
      expect(result.permission).toBeDefined();
      expect(result.permission.state).toBeDefined();
    }
  });
});

// ---------------------------------------------------------------------------
// Request tests — granted
// ---------------------------------------------------------------------------

describe('LivePermissionService: request — granted', () => {
  let service: LivePermissionService;
  let restoreApis: (() => void)[] = [];

  beforeEach(() => {
    restoreApis = [
      ensureMediaDevices(),
      ensureMIDI(),
      ensureSerial(),
      ensureBluetooth(),
    ];
    service = createLivePermissionService({ defaultReason: 'Testing request' });
  });

  afterEach(() => {
    service.releaseAll();
    restoreApis.forEach((r) => r());
  });

  it('grants permission via getUserMedia for webcam', async () => {
    const mockTrack = createMockTrack('video', 'Test Camera');
    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockResolvedValue(
      createMockStream([mockTrack]),
    );

    const result = await service.request('webcam');
    expect(result.userGranted).toBe(true);
    expect(result.permission.state).toBe('granted');
    expect(result.permission.deviceLabel).toBe('Test Camera');
    expect(result.error).toBeUndefined();
  });

  it('grants permission via getUserMedia for microphone', async () => {
    const mockTrack = createMockTrack('audio', 'Test Mic');
    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockResolvedValue(
      createMockStream([mockTrack]),
    );

    const result = await service.request('microphone');
    expect(result.userGranted).toBe(true);
    expect(result.permission.state).toBe('granted');
    expect(result.permission.deviceLabel).toBe('Test Mic');
  });

  it('grants permission for generated sources without API call', async () => {
    const result = await service.request('generated');
    expect(result.userGranted).toBe(true);
    expect(result.permission.state).toBe('granted');
    expect(result.apiKind).toBe('none');
  });

  it('grants permission for osc sources without API call', async () => {
    const result = await service.request('osc');
    expect(result.userGranted).toBe(true);
  });

  it('grants permission for custom sources without API call', async () => {
    const result = await service.request('custom');
    expect(result.userGranted).toBe(true);
  });

  it('grants MIDI permission via requestMIDIAccess', async () => {
    const mockMidiAccess = { inputs: new Map(), outputs: new Map(), sysexEnabled: false };
    (navigator as Record<string, unknown>).requestMIDIAccess = vi.fn().mockResolvedValue(mockMidiAccess);

    const result = await service.request('midi');
    expect(result.userGranted).toBe(true);
    expect(result.permission.state).toBe('granted');
  });

  it('grants serial permission via navigator.serial.requestPort', async () => {
    const mockPort = { readable: null, writable: null };
    ((navigator as Record<string, unknown>).serial as Record<string, unknown>).requestPort = vi.fn().mockResolvedValue(mockPort);

    const result = await service.request('serial');
    expect(result.userGranted).toBe(true);
    expect(result.permission.state).toBe('granted');
  });

  it('grants bluetooth permission via navigator.bluetooth.requestDevice', async () => {
    const mockDevice = { id: 'bt-1', name: 'Test BT' };
    ((navigator as Record<string, unknown>).bluetooth as Record<string, unknown>).requestDevice = vi.fn().mockResolvedValue(mockDevice);

    const result = await service.request('bluetooth');
    expect(result.userGranted).toBe(true);
    expect(result.permission.state).toBe('granted');
  });

  it('stores media tracks for later cleanup', async () => {
    const mockTrack = createMockTrack('video', 'Cleanup Camera');
    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockResolvedValue(
      createMockStream([mockTrack]),
    );

    await service.request('webcam');

    // Release should call stop() on the track
    service.release('webcam');
    expect(mockTrack.stop).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Request tests — denied
// ---------------------------------------------------------------------------

describe('LivePermissionService: request — denied', () => {
  let service: LivePermissionService;
  let restoreApis: (() => void)[] = [];

  beforeEach(() => {
    restoreApis = [
      ensureMediaDevices(),
      ensureMIDI(),
      ensureSerial(),
      ensureBluetooth(),
    ];
    service = createLivePermissionService({ defaultReason: 'Testing denied' });
  });

  afterEach(() => {
    service.releaseAll();
    restoreApis.forEach((r) => r());
  });

  it('handles NotAllowedError as permission denied', async () => {
    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockRejectedValue(
      createPermissionDeniedError(),
    );

    const result = await service.request('webcam');
    expect(result.userGranted).toBe(false);
    expect(result.permission.state).toBe('denied');
    expect(result.diagnostic).toBeDefined();
    expect(result.diagnostic!.code).toBe('live/permission-denied');
    expect(result.diagnostic!.severity).toBe('warning');
    expect(result.error).toContain('Permission denied');
  });

  it('handles AbortError as permission denied', async () => {
    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockRejectedValue(
      createAbortError(),
    );

    const result = await service.request('webcam');
    expect(result.userGranted).toBe(false);
    expect(result.permission.state).toBe('denied');
    expect(result.diagnostic!.code).toBe('live/permission-denied');
  });

  it('handles MIDI denial', async () => {
    (navigator as Record<string, unknown>).requestMIDIAccess = vi.fn().mockRejectedValue(
      createPermissionDeniedError(),
    );

    const result = await service.request('midi');
    expect(result.userGranted).toBe(false);
    expect(result.permission.state).toBe('denied');
  });

  it('handles serial denial', async () => {
    ((navigator as Record<string, unknown>).serial as Record<string, unknown>).requestPort = vi.fn().mockRejectedValue(
      createPermissionDeniedError(),
    );

    const result = await service.request('serial');
    expect(result.userGranted).toBe(false);
    expect(result.permission.state).toBe('denied');
  });

  it('handles bluetooth denial', async () => {
    ((navigator as Record<string, unknown>).bluetooth as Record<string, unknown>).requestDevice = vi.fn().mockRejectedValue(
      createPermissionDeniedError(),
    );

    const result = await service.request('bluetooth');
    expect(result.userGranted).toBe(false);
    expect(result.permission.state).toBe('denied');
  });

  it('handles non-permission errors (generic error)', async () => {
    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockRejectedValue(
      createGenericError(),
    );

    const result = await service.request('webcam');
    expect(result.userGranted).toBe(false);
    expect(result.permission.state).toBe('denied');
    expect(result.diagnostic!.code).toBe('live/permission-error');
    expect(result.diagnostic!.severity).toBe('error');
  });
});

// ---------------------------------------------------------------------------
// Unsupported API tests
// ---------------------------------------------------------------------------

describe('LivePermissionService: request — unsupported API', () => {
  it('returns unavailable for webcam when mediaDevices is missing', async () => {
    const restore = removeApi('mediaDevices');
    const service = createLivePermissionService();

    const result = await service.request('webcam');
    expect(result.apiAvailable).toBe(false);
    expect(result.permission.state).toBe('unavailable');
    expect(result.userGranted).toBe(false);
    expect(result.error).toBe('API not available');

    restore();
  });

  it('returns unavailable for midi when requestMIDIAccess is missing', async () => {
    const restore = removeApi('requestMIDIAccess');
    const service = createLivePermissionService();

    const result = await service.request('midi');
    expect(result.apiAvailable).toBe(false);
    expect(result.permission.state).toBe('unavailable');

    restore();
  });

  it('returns unavailable for serial when navigator.serial is missing', async () => {
    const restore = removeApi('serial');
    const service = createLivePermissionService();

    const result = await service.request('serial');
    expect(result.apiAvailable).toBe(false);
    expect(result.permission.state).toBe('unavailable');

    restore();
  });

  it('returns unavailable for bluetooth when navigator.bluetooth is missing', async () => {
    const restore = removeApi('bluetooth');
    const service = createLivePermissionService();

    const result = await service.request('bluetooth');
    expect(result.apiAvailable).toBe(false);
    expect(result.permission.state).toBe('unavailable');

    restore();
  });
});

// ---------------------------------------------------------------------------
// Cleanup and release
// ---------------------------------------------------------------------------

describe('LivePermissionService: cleanup', () => {
  let service: LivePermissionService;
  let restoreApis: (() => void)[] = [];

  beforeEach(() => {
    restoreApis = [
      ensureMediaDevices(),
    ];
    service = createLivePermissionService();
  });

  afterEach(() => {
    service.releaseAll();
    restoreApis.forEach((r) => r());
  });

  it('release stops acquired media tracks', async () => {
    const videoTrack = createMockTrack('video', 'Vid');
    const audioTrack = createMockTrack('audio', 'Aud');
    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockResolvedValue(
      createMockStream([videoTrack, audioTrack]),
    );

    await service.request('webcam');
    service.release('webcam');

    expect(videoTrack.stop).toHaveBeenCalled();
    expect(audioTrack.stop).toHaveBeenCalled();
  });

  it('release is idempotent', async () => {
    const track = createMockTrack('video', 'V');
    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockResolvedValue(
      createMockStream([track]),
    );

    await service.request('webcam');
    service.release('webcam');
    service.release('webcam');
    // stop should only be called once per track
    expect(track.stop).toHaveBeenCalledTimes(1);
  });

  it('releaseAll stops all acquired tracks', async () => {
    const videoTrack = createMockTrack('video', 'Vid');
    const audioTrack = createMockTrack('audio', 'Aud');
    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn()
      .mockResolvedValueOnce(createMockStream([videoTrack]))
      .mockResolvedValueOnce(createMockStream([audioTrack]));

    await service.request('webcam');
    await service.request('microphone');

    service.releaseAll();
    expect(videoTrack.stop).toHaveBeenCalled();
    expect(audioTrack.stop).toHaveBeenCalled();
  });

  it('releaseAll clears tracked tracks', async () => {
    const track = createMockTrack('video', 'V');
    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockResolvedValue(
      createMockStream([track]),
    );

    await service.request('webcam');
    service.releaseAll();
    // Second releaseAll should not fail
    service.releaseAll();
    expect(track.stop).toHaveBeenCalledTimes(1);
  });

  it('dispose handle cleans up and marks service as disposed', async () => {
    const track = createMockTrack('video', 'V');
    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockResolvedValue(
      createMockStream([track]),
    );

    await service.request('webcam');
    const handle = service.getDisposeHandle();
    expect(service.isDisposed).toBe(false);

    handle.dispose();
    expect(service.isDisposed).toBe(true);
    expect(track.stop).toHaveBeenCalled();

    // Subsequent probe after dispose should still work but request should reflect disposed state
    const result = await service.request('webcam');
    expect(result.userGranted).toBe(false);
    expect(result.error).toBe('Service disposed');
  });

  it('dispose handle is idempotent', () => {
    const handle = service.getDisposeHandle();
    handle.dispose();
    handle.dispose();
    expect(service.isDisposed).toBe(true);
  });

  it('release on unacquired sourceKind is safe (no-op)', () => {
    expect(() => service.release('webcam')).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

describe('LivePermissionService: edge cases', () => {
  let service: LivePermissionService;
  let restoreApis: (() => void)[] = [];

  beforeEach(() => {
    restoreApis = [
      ensureMediaDevices(),
    ];
    service = createLivePermissionService({ defaultReason: 'Edge' });
  });

  afterEach(() => {
    service.releaseAll();
    restoreApis.forEach((r) => r());
  });

  it('request for unsupported source kind that has no API gives available + granted', async () => {
    const result = await service.request('generated');
    expect(result.apiAvailable).toBe(true);
    expect(result.userGranted).toBe(true);
    expect(result.permission.state).toBe('granted');
  });

  it('probe after dispose still works (stateless)', () => {
    const handle = service.getDisposeHandle();
    handle.dispose();

    // probe is stateless and should still work
    const result = service.probe('webcam');
    expect(result.permission.state).toBe('prompt');
  });

  it('multiple requests accumulate tracks for cleanup', async () => {
    const track1 = createMockTrack('video', 'Cam1');
    const track2 = createMockTrack('video', 'Cam2');
    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn()
      .mockResolvedValueOnce(createMockStream([track1]))
      .mockResolvedValueOnce(createMockStream([track2]));

    await service.request('webcam');
    await service.request('webcam');
    service.releaseAll();

    expect(track1.stop).toHaveBeenCalled();
    expect(track2.stop).toHaveBeenCalled();
  });

  it('permission results include requestedAt timestamp when granted', async () => {
    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockResolvedValue(
      createMockStream([createMockTrack('video', 'Cam')]),
    );

    const result = await service.request('webcam');
    expect(result.permission.state).toBe('granted');
    expect(result.permission.requestedAt).toBeDefined();
    expect(new Date(result.permission.requestedAt!).getTime()).toBeGreaterThan(0);
  });

  it('permission denied result includes requestedAt timestamp', async () => {
    (navigator.mediaDevices as Record<string, unknown>).getUserMedia = vi.fn().mockRejectedValue(
      createPermissionDeniedError(),
    );

    const result = await service.request('webcam');
    expect(result.permission.state).toBe('denied');
    expect(result.permission.requestedAt).toBeDefined();
  });

  it('does not interact with or remove persisted live binding metadata', () => {
    // The service is pure - it has no binding or registry hooks.
    // This test verifies that createLivePermissionService does not require
    // or accept a registry reference.
    const svc = createLivePermissionService();
    expect(svc).toBeDefined();
    // No binding metadata API is exposed — the service is purely about
    // browser permission probing and has zero coupling to live bindings.
    expect('resolveBinding' in svc).toBe(false);
    expect('getBindingMetadata' in svc).toBe(false);
    expect('removeLiveBindings' in svc).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Full LiveSourceKind coverage
// ---------------------------------------------------------------------------

describe('LivePermissionService: full source kind coverage', () => {
  let service: LivePermissionService;
  let restoreApis: (() => void)[] = [];

  beforeEach(() => {
    restoreApis = [
      ensureMediaDevices(),
      ensureMIDI(),
      ensureSerial(),
      ensureBluetooth(),
    ];
    service = createLivePermissionService();
  });

  afterEach(() => {
    restoreApis.forEach((r) => r());
  });

  it('probe covers all 10 LiveSourceKind values', () => {
    const results: Record<string, PermissionProbeResult> = {};

    for (const kind of ALL_KINDS) {
      const result = service.probe(kind);
      results[kind] = result;

      // All probes should produce well-formed results
      expect(result.sourceKind).toBe(kind);
      expect(result.permission).toBeDefined();
      expect(['prompt', 'granted', 'denied', 'unavailable']).toContain(result.permission.state);
    }

    expect(Object.keys(results)).toHaveLength(10);
  });

  it('media-devices kinds all probe to prompt state when available', () => {
    const mediaKinds: LiveSourceKind[] = ['webcam', 'microphone', 'screen-capture', 'audio-device'];
    for (const kind of mediaKinds) {
      const result = service.probe(kind);
      expect(result.apiKind).toBe('media-devices');
      expect(result.permission.state).toBe('prompt');
    }
  });

  it('non-browser-api kinds all probe to granted state', () => {
    for (const kind of NO_API_KINDS) {
      const result = service.probe(kind);
      expect(result.permission.state).toBe('granted');
    }
  });
});
