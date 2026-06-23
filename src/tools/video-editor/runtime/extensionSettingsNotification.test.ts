/**
 * Tests for the host-visible settings notification registry (T9).
 *
 * Validates:
 *  - Registry creation and disposal
 *  - Service registration and notification forwarding
 *  - Global and per-extension subscriptions
 *  - Idempotent disposal and error isolation
 *  - Integration with SDK settings service subscribe()
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { createExtensionSettingsNotificationRegistry } from './extensionSettingsNotification';
import type { ExtensionSettingsNotificationRegistry } from './extensionSettingsNotification';
import {
  createExtensionSettingsService,
  getSettingsPrefix,
} from '@/sdk/extensionSettingsService';
import type { ExtensionManifest } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeManifest(extensionId: string): ExtensionManifest {
  return {
    id: extensionId as any,
    version: '1.0.0',
    label: 'Test Extension',
    contributions: [],
  } as ExtensionManifest;
}

function cleanupLocalStorage(extensionId: string): void {
  const prefix = getSettingsPrefix(extensionId);
  const keysToRemove: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key && key.startsWith(prefix)) {
      keysToRemove.push(key);
    }
  }
  keysToRemove.forEach((k) => localStorage.removeItem(k));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ExtensionSettingsNotificationRegistry', () => {
  let registry: ExtensionSettingsNotificationRegistry;

  beforeEach(() => {
    registry = createExtensionSettingsNotificationRegistry();
  });

  describe('creation and disposal', () => {
    it('creates a registry that is not disposed', () => {
      expect(registry.isDisposed).toBe(false);
    });

    it('disposes cleanly', () => {
      registry.dispose();
      expect(registry.isDisposed).toBe(true);
    });

    it('disposal is idempotent', () => {
      registry.dispose();
      registry.dispose();
      expect(registry.isDisposed).toBe(true);
    });

    it('getRegisteredExtensionIds returns empty when no services registered', () => {
      expect(registry.getRegisteredExtensionIds()).toEqual([]);
    });
  });

  describe('service registration', () => {
    it('registers a service and returns a dispose handle', () => {
      const manifest = makeManifest('test.register');
      const { service } = createExtensionSettingsService('test.register', manifest);
      const handle = registry.registerService('test.register', service);
      expect(registry.getRegisteredExtensionIds()).toEqual(['test.register']);
      expect(typeof handle.dispose).toBe('function');
      cleanupLocalStorage('test.register');
    });

    it('unregisters a service via the dispose handle', () => {
      const manifest = makeManifest('test.unregister');
      const { service } = createExtensionSettingsService('test.unregister', manifest);
      const handle = registry.registerService('test.unregister', service);
      handle.dispose();
      expect(registry.getRegisteredExtensionIds()).toEqual([]);
      cleanupLocalStorage('test.unregister');
    });

    it('unregister is idempotent', () => {
      const manifest = makeManifest('test.idempotent');
      const { service } = createExtensionSettingsService('test.idempotent', manifest);
      const handle = registry.registerService('test.idempotent', service);
      handle.dispose();
      handle.dispose();
      expect(registry.getRegisteredExtensionIds()).toEqual([]);
      cleanupLocalStorage('test.idempotent');
    });

    it('replaces existing service for same extension', () => {
      const manifest = makeManifest('test.replace');
      const { service: svc1 } = createExtensionSettingsService('test.replace', manifest);
      const { service: svc2 } = createExtensionSettingsService('test.replace', manifest);
      registry.registerService('test.replace', svc1);
      registry.registerService('test.replace', svc2);
      expect(registry.getRegisteredExtensionIds()).toEqual(['test.replace']);
      cleanupLocalStorage('test.replace');
    });

    it('returns no-op dispose handle when registry is disposed', () => {
      registry.dispose();
      const manifest = makeManifest('test.disposed');
      const { service } = createExtensionSettingsService('test.disposed', manifest);
      const handle = registry.registerService('test.disposed', service);
      expect(registry.getRegisteredExtensionIds()).toEqual([]);
      handle.dispose(); // Should not throw
      cleanupLocalStorage('test.disposed');
    });
  });

  describe('global subscriptions', () => {
    it('notifies global listener when a registered service fires', () => {
      const manifest = makeManifest('test.global');
      const { service } = createExtensionSettingsService('test.global', manifest);
      registry.registerService('test.global', service);

      const calls: string[] = [];
      const unsub = registry.subscribe((extId) => {
        calls.push(extId);
      });

      service.set('myKey', 'myValue');

      expect(calls).toEqual(['test.global']);
      unsub.dispose();
      cleanupLocalStorage('test.global');
    });

    it('does not notify after global unsubscribe', () => {
      const manifest = makeManifest('test.unsub');
      const { service } = createExtensionSettingsService('test.unsub', manifest);
      registry.registerService('test.unsub', service);

      const calls: string[] = [];
      const unsub = registry.subscribe((extId) => {
        calls.push(extId);
      });

      unsub.dispose();
      service.set('key', 'value');

      expect(calls).toEqual([]);
      cleanupLocalStorage('test.unsub');
    });

    it('notifies multiple global listeners', () => {
      const manifest = makeManifest('test.multi');
      const { service } = createExtensionSettingsService('test.multi', manifest);
      registry.registerService('test.multi', service);

      const calls1: string[] = [];
      const calls2: string[] = [];
      registry.subscribe((extId) => calls1.push(extId));
      registry.subscribe((extId) => calls2.push(extId));

      service.set('a', 1);

      expect(calls1).toEqual(['test.multi']);
      expect(calls2).toEqual(['test.multi']);
      cleanupLocalStorage('test.multi');
    });

    it('survives listener errors without breaking other listeners', () => {
      const manifest = makeManifest('test.error');
      const { service } = createExtensionSettingsService('test.error', manifest);
      registry.registerService('test.error', service);

      const calls: string[] = [];
      registry.subscribe(() => {
        throw new Error('Boom!');
      });
      registry.subscribe((extId) => calls.push(extId));

      // Should not throw
      service.set('x', 1);

      expect(calls).toEqual(['test.error']);
      cleanupLocalStorage('test.error');
    });
  });

  describe('per-extension subscriptions', () => {
    it('notifies per-extension listener for the correct extension', () => {
      const manifestA = makeManifest('test.per-ext-a');
      const manifestB = makeManifest('test.per-ext-b');
      const { service: svcA } = createExtensionSettingsService('test.per-ext-a', manifestA);
      const { service: svcB } = createExtensionSettingsService('test.per-ext-b', manifestB);
      registry.registerService('test.per-ext-a', svcA);
      registry.registerService('test.per-ext-b', svcB);

      const callsA: number = 0;
      let callCountA = 0;
      const callCountB = 0;
      let actualCallCountB = 0;

      registry.subscribeToExtension('test.per-ext-a', () => {
        callCountA++;
      });
      registry.subscribeToExtension('test.per-ext-b', () => {
        actualCallCountB++;
      });

      svcA.set('key', 'val');

      expect(callCountA).toBe(1);
      expect(actualCallCountB).toBe(0);

      cleanupLocalStorage('test.per-ext-a');
      cleanupLocalStorage('test.per-ext-b');
    });

    it('unsubscribes per-extension listener', () => {
      const manifest = makeManifest('test.ext-unsub');
      const { service } = createExtensionSettingsService('test.ext-unsub', manifest);
      registry.registerService('test.ext-unsub', service);

      let calls = 0;
      const unsub = registry.subscribeToExtension('test.ext-unsub', () => {
        calls++;
      });

      unsub.dispose();
      service.set('a', 1);

      expect(calls).toBe(0);
      cleanupLocalStorage('test.ext-unsub');
    });

    it('listener never fires for unregistered extension', () => {
      let calls = 0;
      registry.subscribeToExtension('test.never', () => {
        calls++;
      });

      const manifest = makeManifest('test.other');
      const { service } = createExtensionSettingsService('test.other', manifest);
      registry.registerService('test.other', service);

      service.set('x', 1);

      expect(calls).toBe(0);
      cleanupLocalStorage('test.other');
    });
  });

  describe('disposal behavior', () => {
    it('stops all notifications after disposal', () => {
      const manifest = makeManifest('test.disp');
      const { service } = createExtensionSettingsService('test.disp', manifest);
      registry.registerService('test.disp', service);

      let globalCalls = 0;
      let extCalls = 0;
      registry.subscribe(() => globalCalls++);
      registry.subscribeToExtension('test.disp', () => extCalls++);

      registry.dispose();

      // Should not notify after disposal
      service.set('key', 'value');

      expect(globalCalls).toBe(0);
      expect(extCalls).toBe(0);

      cleanupLocalStorage('test.disp');
    });

    it('disposal cleans up service subscriptions', () => {
      const manifest = makeManifest('test.cleanup');
      const { service } = createExtensionSettingsService('test.cleanup', manifest);
      registry.registerService('test.cleanup', service);

      registry.dispose();

      // The service itself still works, but registry should not forward
      let notified = false;
      const sub = registry.subscribe(() => notified = true);
      service.set('k', 'v');
      expect(notified).toBe(false);
      sub.dispose();

      cleanupLocalStorage('test.cleanup');
    });
  });

  describe('notifySettingsChanged (T10)', () => {
    it('notifies per-extension listeners when called directly', () => {
      let calls = 0;
      registry.subscribeToExtension('test.notify', () => {
        calls++;
      });

      registry.notifySettingsChanged('test.notify');
      expect(calls).toBe(1);
    });

    it('notifies global listeners when called directly', () => {
      const calls: string[] = [];
      registry.subscribe((extId) => {
        calls.push(extId);
      });

      registry.notifySettingsChanged('test.notify-global');
      expect(calls).toEqual(['test.notify-global']);
    });

    it('is a no-op when registry is disposed', () => {
      let calls = 0;
      registry.subscribeToExtension('test.notify-disp', () => {
        calls++;
      });

      registry.dispose();
      registry.notifySettingsChanged('test.notify-disp');
      expect(calls).toBe(0);
    });

    it('notifies both global and per-extension listeners', () => {
      const globalCalls: string[] = [];
      let extCalls = 0;

      registry.subscribe((extId) => globalCalls.push(extId));
      registry.subscribeToExtension('test.notify-both', () => extCalls++);

      registry.notifySettingsChanged('test.notify-both');
      expect(globalCalls).toEqual(['test.notify-both']);
      expect(extCalls).toBe(1);
    });

    it('survives listener errors', () => {
      const calls: string[] = [];
      registry.subscribeToExtension('test.notify-err', () => {
        throw new Error('Boom!');
      });
      registry.subscribe((extId) => calls.push(extId));

      // Should not throw
      registry.notifySettingsChanged('test.notify-err');
      expect(calls).toEqual(['test.notify-err']);
    });

    it('works even when no service is registered for the extension', () => {
      let calls = 0;
      registry.subscribeToExtension('test.notify-noreg', () => {
        calls++;
      });

      registry.notifySettingsChanged('test.notify-noreg');
      expect(calls).toBe(1);
    });
  });

  describe('integration: global + per-extension coexistence', () => {
    it('both global and per-extension listeners receive notifications', () => {
      const manifest = makeManifest('test.both');
      const { service } = createExtensionSettingsService('test.both', manifest);
      registry.registerService('test.both', service);

      const globalCalls: string[] = [];
      let extCalls = 0;

      registry.subscribe((extId) => globalCalls.push(extId));
      registry.subscribeToExtension('test.both', () => extCalls++);

      service.set('hello', 'world');

      expect(globalCalls).toEqual(['test.both']);
      expect(extCalls).toBe(1);

      cleanupLocalStorage('test.both');
    });
  });
});
