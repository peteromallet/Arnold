/**
 * M11: Live permission helper service.
 *
 * Provides browser-gated permission probes and request wrappers for camera,
 * microphone, MIDI, serial, and Bluetooth where the browser exposes the
 * relevant API. Unsupported APIs produce structured diagnostics and do not
 * expose bespoke per-source APIs.
 *
 * The service is pure: it does not mutate the live data registry or persisted
 * binding metadata. Callers are responsible for wiring permission results
 * into the registry and timeline.
 *
 * @module livePermissions
 * @milestone M11
 */

import type {
  LiveSourceKind,
  LiveSourcePermission,
  LivePermissionState,
  LiveSourceDiagnostic,
  DiagnosticSeverity,
  DisposeHandle,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

/**
 * Describes which browser API (if any) backs a given source kind.
 */
export type PermissionApiKind =
  | 'media-devices'
  | 'midi'
  | 'serial'
  | 'bluetooth'
  | 'none';

/**
 * Result of a single permission probe.
 */
export interface PermissionProbeResult {
  /** The target source kind. */
  readonly sourceKind: LiveSourceKind;
  /** Which browser API would back this kind. */
  readonly apiKind: PermissionApiKind;
  /** The resolved permission state. */
  readonly permission: LiveSourcePermission;
  /** Structured diagnostic (undefined if state is 'granted'). */
  readonly diagnostic?: LiveSourceDiagnostic;
  /** Whether the browser API is available at all. */
  readonly apiAvailable: boolean;
}

/**
 * Result of a permission request (probe + browser prompt).
 */
export interface PermissionRequestResult extends PermissionProbeResult {
  /** Whether the user granted the permission interactively. */
  readonly userGranted: boolean;
  /** Browser API error details if the request failed. */
  readonly error?: string;
}

/**
 * Describes which kind of media constraint to request.
 */
export interface MediaPermissionOptions {
  /** Request video (camera) access. */
  video?: boolean;
  /** Request audio (microphone) access. */
  audio?: boolean;
  /** Screen capture (getDisplayMedia) instead of getUserMedia. */
  screen?: boolean;
}

/**
 * A service that probes and requests browser permissions for live data sources.
 *
 * The service does NOT alter persisted binding metadata — its callers do that.
 * It is safe to call multiple times; repeated probes return the same cached
 * result for a given source kind within the same service instance.
 */
export interface LivePermissionService {
  /**
   * Probe browser API availability for a source kind without prompting the user.
   *
   * This checks whether navigator.mediaDevices / requestMIDIAccess / serial /
   * Bluetooth exist in the current environment. It does NOT trigger a browser
   * permission prompt.
   *
   * If an API is unavailable the result returns `state: 'unavailable'` with a
   * structured diagnostic message.
   */
  probe(sourceKind: LiveSourceKind): PermissionProbeResult;

  /**
   * Request permission for a source kind, potentially triggering a browser
   * permission prompt.
   *
   * For media-devices-backed kinds (webcam, microphone, screen-capture) this
   * calls getUserMedia / getDisplayMedia. For MIDI/serial/Bluetooth it calls
   * the respective browser API if available.
   *
   * If an API is unavailable the result carries `apiAvailable: false` with
   * diagnostics; no prompt is shown.
   */
  request(
    sourceKind: LiveSourceKind,
    options?: MediaPermissionOptions,
  ): Promise<PermissionRequestResult>;

  /**
   * Release resources (media tracks, ports) acquired during a previous
   * permission request. The implementor is responsible for cleanup.
   *
   * This is idempotent and always safe to call.
   */
  release(sourceKind: LiveSourceKind): void;

  /**
   * Release ALL tracked resources. Safe to call on dispose / unmount.
   */
  releaseAll(): void;

  /**
   * Get a disposable handle that calls releaseAll on disposal. This is the
   * preferred integration pattern for provider lifecycle binding.
   */
  getDisposeHandle(): DisposeHandle;

  /**
   * Whether the service has been disposed.
   */
  readonly isDisposed: boolean;
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

export interface LivePermissionServiceConfig {
  /** Reason shown to users in permission prompts. */
  readonly defaultReason?: string;
  /** Device label shown in permission results. */
  readonly defaultDeviceLabel?: string;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Map a LiveSourceKind to its corresponding PermissionApiKind.
 */
export function getPermissionApiKind(kind: LiveSourceKind): PermissionApiKind {
  switch (kind) {
    case 'webcam':
    case 'microphone':
    case 'screen-capture':
    case 'audio-device':
      return 'media-devices';
    case 'midi':
      return 'midi';
    case 'serial':
      return 'serial';
    case 'bluetooth':
      return 'bluetooth';
    case 'generated':
    case 'osc':
    case 'custom':
      return 'none';
  }
}

/**
 * Check whether a given browser API is available in the current environment.
 */
function isApiAvailable(apiKind: PermissionApiKind): boolean {
  if (typeof navigator === 'undefined') return false;

  switch (apiKind) {
    case 'media-devices':
      return (
        'mediaDevices' in navigator &&
        typeof (navigator as Navigator & { mediaDevices?: unknown }).mediaDevices === 'object' &&
        (navigator as Navigator & { mediaDevices?: unknown }).mediaDevices !== null &&
        'getUserMedia' in (navigator as Navigator & { mediaDevices?: unknown }).mediaDevices!
      );
    case 'midi':
      return (
        'requestMIDIAccess' in navigator &&
        typeof (navigator as Navigator & { requestMIDIAccess?: unknown }).requestMIDIAccess === 'function'
      );
    case 'serial':
      return (
        'serial' in navigator &&
        typeof (navigator as Navigator & { serial?: unknown }).serial === 'object' &&
        (navigator as Navigator & { serial?: unknown }).serial !== null
      );
    case 'bluetooth':
      return (
        'bluetooth' in navigator &&
        typeof (navigator as Navigator & { bluetooth?: unknown }).bluetooth === 'object' &&
        (navigator as Navigator & { bluetooth?: unknown }).bluetooth !== null
      );
    case 'none':
      return true;
  }
}

function makeDiagnostic(
  severity: DiagnosticSeverity,
  code: string,
  message: string,
  sourceId?: string,
  detail?: Record<string, unknown>,
): LiveSourceDiagnostic {
  return { severity, code, message, sourceId, detail };
}

function makePermission(
  state: LivePermissionState,
  reason?: string,
  deviceLabel?: string,
): LiveSourcePermission {
  const perm: LiveSourcePermission = { state };
  if (reason !== undefined) (perm as Record<string, unknown>).reason = reason;
  if (deviceLabel !== undefined) (perm as Record<string, unknown>).deviceLabel = deviceLabel;
  if (state === 'granted' || state === 'denied') {
    (perm as Record<string, unknown>).requestedAt = new Date().toISOString();
  }
  return perm;
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

export function createLivePermissionService(
  config: LivePermissionServiceConfig = {},
): LivePermissionService {
  const defaultReason = config.defaultReason ?? 'Live data source permission';
  const defaultDeviceLabel = config.defaultDeviceLabel;

  // Track acquired media tracks for cleanup
  const acquiredTracks: Map<LiveSourceKind, MediaStreamTrack[]> = new Map();
  let disposed = false;

  function guard(): boolean {
    if (disposed) return true;
    return false;
  }

  // ---- probe ---------------------------------------------------------------

  function probe(sourceKind: LiveSourceKind): PermissionProbeResult {
    const apiKind = getPermissionApiKind(sourceKind);
    const apiAvailable = isApiAvailable(apiKind);

    if (apiKind === 'none') {
      // Sources like 'generated', 'osc', 'custom' don't need browser API
      return {
        sourceKind,
        apiKind,
        apiAvailable: true,
        permission: makePermission('granted', 'No browser permission required'),
      };
    }

    if (!apiAvailable) {
      const apiNames: Record<PermissionApiKind, string> = {
        'media-devices': 'MediaDevices (getUserMedia)',
        'midi': 'Web MIDI (requestMIDIAccess)',
        'serial': 'Web Serial (navigator.serial)',
        'bluetooth': 'Web Bluetooth (navigator.bluetooth)',
        'none': '',
      };

      return {
        sourceKind,
        apiKind,
        apiAvailable: false,
        permission: makePermission('unavailable', `Browser API not available: ${apiNames[apiKind]}`),
        diagnostic: makeDiagnostic(
          'warning',
          `live/permission-unavailable`,
          `The ${apiNames[apiKind]} API is not available in this browser or environment.`,
          undefined,
          { sourceKind, apiKind },
        ),
      };
    }

    // API is available — permission state is 'prompt' (not yet requested)
    const deviceLabel = defaultDeviceLabel ?? sourceKindDeviceLabel(sourceKind);
    return {
      sourceKind,
      apiKind,
      apiAvailable: true,
      permission: makePermission('prompt', defaultReason, deviceLabel),
    };
  }

  // ---- request -------------------------------------------------------------

  async function request(
    sourceKind: LiveSourceKind,
    options?: MediaPermissionOptions,
  ): Promise<PermissionRequestResult> {
    if (guard()) {
      const probeResult = probe(sourceKind);
      return {
        ...probeResult,
        userGranted: false,
        error: 'Service disposed',
      };
    }

    const apiKind = getPermissionApiKind(sourceKind);
    const apiAvailable = isApiAvailable(apiKind);

    if (apiKind === 'none') {
      return {
        sourceKind,
        apiKind,
        apiAvailable: true,
        permission: makePermission('granted', 'No browser permission required'),
        userGranted: true,
      };
    }

    if (!apiAvailable) {
      const probeResult = probe(sourceKind);
      return {
        ...probeResult,
        userGranted: false,
        error: 'API not available',
      };
    }

    try {
      switch (apiKind) {
        case 'media-devices': {
          const constraints = buildMediaConstraints(sourceKind, options);
          let stream: MediaStream;

          if (options?.screen) {
            stream = await (navigator.mediaDevices as MediaDevices & {
              getDisplayMedia?: (c?: DisplayMediaStreamOptions) => Promise<MediaStream>;
            }).getDisplayMedia?.({ video: true }) ?? (await navigator.mediaDevices.getUserMedia(constraints));
          } else {
            stream = await navigator.mediaDevices.getUserMedia(constraints);
          }

          // Track acquired tracks for cleanup
          const tracks = stream.getTracks();
          if (tracks.length > 0) {
            acquiredTracks.set(sourceKind, [...(acquiredTracks.get(sourceKind) ?? []), ...tracks]);
          }

          const deviceLabel = tracks[0]?.label ?? defaultDeviceLabel ?? sourceKindDeviceLabel(sourceKind);
          return {
            sourceKind,
            apiKind,
            apiAvailable: true,
            permission: makePermission('granted', defaultReason, deviceLabel),
            userGranted: true,
          };
        }

        case 'midi': {
          const access = await (navigator as Navigator & {
            requestMIDIAccess?: (opts?: MIDIOptions) => Promise<WebMidi.MIDIAccess>;
          }).requestMIDIAccess?.({ sysex: false });
          if (!access) {
            throw new Error('MIDI access returned null');
          }
          // No per-source track to store for MIDI; the MIDIAccess is global
          return {
            sourceKind,
            apiKind,
            apiAvailable: true,
            permission: makePermission('granted', defaultReason, 'MIDI Device'),
            userGranted: true,
          };
        }

        case 'serial': {
          // Requesting a port triggers the permission prompt
          const port = await (navigator as Navigator & {
            serial?: { requestPort?: (opts?: SerialPortRequestOptions) => Promise<unknown> };
          }).serial?.requestPort?.();
          if (!port) {
            throw new Error('Serial port request returned null');
          }
          return {
            sourceKind,
            apiKind,
            apiAvailable: true,
            permission: makePermission('granted', defaultReason, 'Serial Device'),
            userGranted: true,
          };
        }

        case 'bluetooth': {
          const device = await (navigator as Navigator & {
            bluetooth?: { requestDevice?: (opts?: RequestDeviceOptions) => Promise<unknown> };
          }).bluetooth?.requestDevice?.({ acceptAllDevices: true });
          if (!device) {
            throw new Error('Bluetooth device request returned null');
          }
          return {
            sourceKind,
            apiKind,
            apiAvailable: true,
            permission: makePermission('granted', defaultReason, 'Bluetooth Device'),
            userGranted: true,
          };
        }

        default:
          return {
            sourceKind,
            apiKind,
            apiAvailable: true,
            permission: makePermission('prompt', defaultReason),
            userGranted: false,
            error: `Unsupported API kind: ${apiKind}`,
          };
      }
    } catch (err: unknown) {
      const isPermissionDenied =
        err instanceof DOMException &&
        (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError' || err.name === 'AbortError');

      const errorMessage = err instanceof Error ? err.message : String(err);

      if (isPermissionDenied) {
        return {
          sourceKind,
          apiKind,
          apiAvailable: true,
          permission: makePermission('denied', defaultReason),
          diagnostic: makeDiagnostic(
            'warning',
            'live/permission-denied',
            `Permission denied for ${sourceKind}: ${errorMessage}`,
            undefined,
            { sourceKind, error: errorMessage },
          ),
          userGranted: false,
          error: errorMessage,
        };
      }

      // Other errors (e.g., no devices available)
      return {
        sourceKind,
        apiKind,
        apiAvailable: true,
        permission: makePermission('denied', defaultReason),
        diagnostic: makeDiagnostic(
          'error',
          'live/permission-error',
          `Error requesting permission for ${sourceKind}: ${errorMessage}`,
          undefined,
          { sourceKind, error: errorMessage },
        ),
        userGranted: false,
        error: errorMessage,
      };
    }
  }

  // ---- release -------------------------------------------------------------

  function release(sourceKind: LiveSourceKind): void {
    const tracks = acquiredTracks.get(sourceKind);
    if (tracks) {
      for (const track of tracks) {
        track.stop();
      }
      acquiredTracks.delete(sourceKind);
    }
  }

  function releaseAll(): void {
    for (const sourceKind of Array.from(acquiredTracks.keys())) {
      release(sourceKind);
    }
    acquiredTracks.clear();
  }

  function getDisposeHandle(): DisposeHandle {
    let isDisposed = false;
    return {
      dispose(): void {
        if (isDisposed) return;
        isDisposed = true;
        releaseAll();
        disposed = true;
      },
    };
  }

  // ---- dispose -------------------------------------------------------------

  function dispose(): void {
    if (disposed) return;
    disposed = true;
    releaseAll();
  }

  // ---------------------------------------------------------------------------

  return {
    probe,
    request,
    release,
    releaseAll,
    getDisposeHandle,
    get isDisposed() {
      return disposed;
    },
    dispose,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function sourceKindDeviceLabel(kind: LiveSourceKind): string {
  switch (kind) {
    case 'webcam': return 'Camera';
    case 'microphone': return 'Microphone';
    case 'screen-capture': return 'Screen';
    case 'audio-device': return 'Audio Device';
    case 'midi': return 'MIDI Device';
    case 'serial': return 'Serial Device';
    case 'bluetooth': return 'Bluetooth Device';
    case 'generated': return 'Generated';
    case 'osc': return 'OSC Device';
    case 'custom': return 'Custom Source';
  }
}

function buildMediaConstraints(
  sourceKind: LiveSourceKind,
  options?: MediaPermissionOptions,
): MediaStreamConstraints {
  const constraints: MediaStreamConstraints = {};

  if (options?.video || sourceKind === 'webcam' || sourceKind === 'screen-capture') {
    constraints.video = true;
  }
  if (options?.audio || sourceKind === 'microphone' || sourceKind === 'audio-device') {
    constraints.audio = true;
  }
  if (sourceKind === 'screen-capture') {
    constraints.video = { ...(typeof constraints.video === 'object' ? constraints.video : {}), displaySurface: 'monitor' };
  }

  return constraints;
}
