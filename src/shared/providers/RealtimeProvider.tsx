/**
 * RealtimeProvider - Manages realtime connection and provides status to the app
 *
 * This provider:
 * 1. Connects to the realtime service when a project is selected
 * 2. Wires raw events from connection → processor → invalidation
 * 3. Exposes connection status to the component tree
 *
 */

import React, { createContext, useContext, useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { isTaskDbRow, mapTaskDbRowToTask } from '@/shared/lib/taskRowMapper';
import { getRealtimeConnection } from '@/shared/realtime/RealtimeConnection';
import { realtimeEventProcessor } from '@/shared/realtime/RealtimeEventProcessor';
import { dataFreshnessManager } from '@/shared/realtime/DataFreshnessManager';
import { useRealtimeInvalidation } from '@/shared/hooks/useRealtimeInvalidation';
import { fetchAndSeedTaskQuery, getCachedTaskSnapshot } from '@/shared/hooks/tasks/useTasks';
import {
  resetRealtimeTaskScope,
  upsertRealtimeTaskSnapshot,
} from '@/shared/state/realtimeStore';
import type { ConnectionState, ConnectionStatus, RawDatabaseEvent } from '@/shared/realtime/types';

// =============================================================================
// Context
// =============================================================================

interface RealtimeContextValue {
  /** Current connection status */
  status: ConnectionStatus;
  /** Whether currently connected */
  isConnected: boolean;
  /** Whether connection is in progress */
  isConnecting: boolean;
  /** Whether in a failed state (exhausted retries) */
  isFailed: boolean;
  /** Error message if any */
  error: string | null;
  /** Current reconnect attempt (0 if not reconnecting) */
  reconnectAttempt: number;
  /** Manually trigger reconnection */
  reconnect: () => void;
}

const RealtimeContext = createContext<RealtimeContextValue>({
  status: 'disconnected',
  isConnected: false,
  isConnecting: false,
  isFailed: false,
  error: null,
  reconnectAttempt: 0,
  reconnect: () => {},
});

export const useRealtime = () => useContext(RealtimeContext);

// =============================================================================
// Provider
// =============================================================================

interface RealtimeProviderProps {
  children: React.ReactNode;
}

function getTaskRowStringField(value: unknown, field: 'id' | 'project_id'): string | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }

  const fieldValue = (value as Record<string, unknown>)[field];
  return typeof fieldValue === 'string' && fieldValue.trim().length > 0 ? fieldValue : null;
}

export function RealtimeProvider({ children }: RealtimeProviderProps) {
  const { selectedProjectId } = useProjectSelectionContext();
  const queryClient = useQueryClient();
  const realtimeConnection = useMemo(() => getRealtimeConnection(), []);
  const [connectionState, setConnectionState] = useState<ConnectionState>(() =>
    realtimeConnection.getState()
  );
  const activeProjectIdRef = useRef<string | null>(null);

  // Set up the invalidation hook (subscribes to processed events)
  useRealtimeInvalidation();

  const hydrateTaskSnapshot = useCallback(async (event: RawDatabaseEvent) => {
    if (event.table !== 'tasks' || (event.eventType !== 'INSERT' && event.eventType !== 'UPDATE')) {
      return;
    }

    const fallbackProjectId = getTaskRowStringField(event.new, 'project_id')
      ?? getTaskRowStringField(event.old, 'project_id')
      ?? activeProjectIdRef.current;

    if (isTaskDbRow(event.new)) {
      upsertRealtimeTaskSnapshot(mapTaskDbRowToTask(event.new), fallbackProjectId);
      return;
    }

    const taskId = getTaskRowStringField(event.new, 'id') ?? getTaskRowStringField(event.old, 'id');
    if (!taskId || !fallbackProjectId) {
      return;
    }

    try {
      const cachedTask = getCachedTaskSnapshot(queryClient, taskId, fallbackProjectId);

      if (cachedTask !== undefined) {
        if (cachedTask && activeProjectIdRef.current === fallbackProjectId) {
          upsertRealtimeTaskSnapshot(cachedTask, fallbackProjectId);
        }
        return;
      }

      const fetchedTask = await fetchAndSeedTaskQuery(queryClient, taskId, fallbackProjectId);

      if (fetchedTask && activeProjectIdRef.current === fallbackProjectId) {
        upsertRealtimeTaskSnapshot(fetchedTask, fallbackProjectId);
      }
    } catch (error) {
      normalizeAndPresentError(error, {
        context: 'RealtimeProvider.hydrateTaskSnapshot',
        showToast: false,
        logData: {
          taskId,
          projectId: fallbackProjectId,
          eventType: event.eventType,
        },
      });
    }
  }, [queryClient]);

  // Wire connection events → processor
  useEffect(() => {
    const unsubscribe = realtimeConnection.onEvent((event) => {
      void hydrateTaskSnapshot(event);
      realtimeEventProcessor.process(event);
    });
    return unsubscribe;
  }, [hydrateTaskSnapshot, realtimeConnection]);

  // Subscribe to connection status changes
  useEffect(() => {
    const unsubscribe = realtimeConnection.onStatusChange((state) => {
      setConnectionState(state);
    });
    return unsubscribe;
  }, [realtimeConnection]);

  // Connect/disconnect when project changes
  useEffect(() => {
    const previousProjectId = activeProjectIdRef.current;

    if (previousProjectId && previousProjectId !== selectedProjectId) {
      resetRealtimeTaskScope(previousProjectId);
    }

    if (!selectedProjectId) {
      activeProjectIdRef.current = null;
      realtimeConnection.disconnect();
      dataFreshnessManager.reset();
      return;
    }

    if (previousProjectId !== selectedProjectId) {
      resetRealtimeTaskScope(selectedProjectId);
    }

    activeProjectIdRef.current = selectedProjectId;
    realtimeConnection.connect(selectedProjectId);

    return () => {
      // Don't disconnect on cleanup - let the next effect handle it
      // This prevents disconnect/reconnect when the component re-renders
    };
  }, [selectedProjectId, realtimeConnection]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (activeProjectIdRef.current) {
        resetRealtimeTaskScope(activeProjectIdRef.current);
      }
      realtimeEventProcessor.clear();
    };
  }, []);

  // Manual reconnect function
  const reconnect = useCallback(() => {
    if (selectedProjectId) {
      realtimeConnection.reset();
      realtimeConnection.connect(selectedProjectId);
    }
  }, [selectedProjectId, realtimeConnection]);

  // Derive context value from connection state
  const contextValue: RealtimeContextValue = {
    status: connectionState.status,
    isConnected: connectionState.status === 'connected',
    isConnecting: connectionState.status === 'connecting',
    isFailed: connectionState.status === 'failed',
    error: connectionState.error,
    reconnectAttempt: connectionState.reconnectAttempt,
    reconnect,
  };

  return (
    <RealtimeContext.Provider value={contextValue}>
      {children}
    </RealtimeContext.Provider>
  );
}
