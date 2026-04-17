import React, { useEffect, useRef } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '@/shared/contexts/AuthContext';
import { AuthGate } from '@/shared/auth/components/AuthGate';
import { UserSettingsProvider } from '@/shared/contexts/UserSettingsContext';
import { ProjectProvider, useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { RealtimeProvider } from '@/shared/providers/RealtimeProvider';
import { ShotsProvider } from '@/shared/contexts/ShotsContext';
import { GenerationTaskProvider } from '@/shared/contexts/GenerationTaskContext';
import { IncomingTasksProvider } from '@/shared/contexts/IncomingTasksContext';
import { AgentChatProvider } from '@/shared/contexts/AgentChatContext';
import { ToolPageHeaderProvider } from '@/shared/contexts/ToolPageHeaderContext';
import { TaskTypeConfigInitializer } from '@/shared/components/TaskTypeConfigInitializer';
import { TooltipProvider } from '@/shared/components/ui/tooltip';
import { useToolSettings } from '@/shared/hooks/settings/useToolSettings';
import { SETTINGS_IDS } from '@/shared/lib/settingsIds';
import { PanesStoreBootstrapBoundary } from '@/shared/state/panesStore';
import { useLastAffectedShot, useSelectionStoreApi } from '@/shared/state/selectionStore';
import { queryClient } from '@/app/providers/queryClient';

interface AppProvidersProps {
  children: React.ReactNode;
}

type TreeProvider = React.ComponentType<{ children: React.ReactNode }>;

function composeProviders(providers: TreeProvider[]): TreeProvider {
  return function ProviderTree({ children }: { children: React.ReactNode }) {
    return providers.reduceRight(
      (acc, Provider) => <Provider>{acc}</Provider>,
      children
    );
  };
}

interface LastAffectedShotSettings {
  lastAffectedShotId?: string | null;
}

function SelectionStoreBoundary({ children }: { children: React.ReactNode }) {
  const { selectedProjectId } = useProjectSelectionContext();
  const selectionStore = useSelectionStoreApi();
  const { lastAffectedShotId } = useLastAffectedShot();
  const previousProjectIdRef = useRef<string | null>(null);
  const hydratedProjectIdRef = useRef<string | null>(null);
  const lastPersistedShotIdRef = useRef<string | null>(null);
  const {
    settings,
    update,
    isLoading,
  } = useToolSettings<LastAffectedShotSettings>(SETTINGS_IDS.LAST_AFFECTED_SHOT, {
    projectId: selectedProjectId ?? undefined,
    enabled: !!selectedProjectId,
  });

  useEffect(() => {
    if (previousProjectIdRef.current === selectedProjectId) {
      return;
    }

    previousProjectIdRef.current = selectedProjectId;
    hydratedProjectIdRef.current = null;
    lastPersistedShotIdRef.current = null;
    selectionStore.getState().resetForProjectChange();
  }, [selectedProjectId, selectionStore]);

  useEffect(() => {
    if (!selectedProjectId || isLoading) {
      return;
    }

    if (hydratedProjectIdRef.current === selectedProjectId) {
      return;
    }

    const storedShotId = settings?.lastAffectedShotId ?? null;
    hydratedProjectIdRef.current = selectedProjectId;
    lastPersistedShotIdRef.current = storedShotId;
    selectionStore.getState().hydrateLastAffectedShotId(storedShotId);
  }, [isLoading, selectedProjectId, selectionStore, settings?.lastAffectedShotId]);

  useEffect(() => {
    if (!selectedProjectId) {
      return;
    }

    if (hydratedProjectIdRef.current !== selectedProjectId) {
      return;
    }

    if (lastPersistedShotIdRef.current === lastAffectedShotId) {
      return;
    }

    lastPersistedShotIdRef.current = lastAffectedShotId;
    void update('project', { lastAffectedShotId });
  }, [lastAffectedShotId, selectedProjectId, update]);

  return <>{children}</>;
}

const AppProviderTree = composeProviders([
  AuthProvider,
  AuthGate,
  TaskTypeConfigInitializer,
  UserSettingsProvider,
  ProjectProvider,
  RealtimeProvider,
  ShotsProvider,
  GenerationTaskProvider,
  IncomingTasksProvider,
  PanesStoreBootstrapBoundary,
  AgentChatProvider,
  SelectionStoreBoundary,
  ToolPageHeaderProvider,
]);

export function AppProviders({ children }: AppProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={300}>
        <AppProviderTree>{children}</AppProviderTree>
      </TooltipProvider>
    </QueryClientProvider>
  );
}
