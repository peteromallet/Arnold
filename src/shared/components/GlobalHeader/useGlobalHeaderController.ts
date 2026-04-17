import { useCallback, useEffect, useRef, useState } from 'react';
import { useIsTablet } from '@/shared/hooks/mobile';
import { useTextCase } from '@/shared/hooks/useTextCase';
import { useProjectContextDebug } from '@/shared/hooks/projects/useProjectContextDebug';
import { useProjectCrudContext, useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { usePanesStore } from '@/shared/state/panesStore';
import { useGlobalHeaderAuth } from './useGlobalHeaderAuth';

export function useGlobalHeaderController() {
  const { selectedProjectId } = useProjectSelectionContext();
  const { projects } = useProjectCrudContext();
  const isTablet = useIsTablet();
  useTextCase();
  const isGenerationsPaneLocked = usePanesStore((state) => state.isGenerationsPaneLocked);
  useProjectContextDebug(import.meta.env.DEV);

  const { session, referralStats } = useGlobalHeaderAuth();

  const [isBrandFlash, setIsBrandFlash] = useState(false);
  const brandFlashTimeoutRef = useRef<number | null>(null);

  const triggerBrandFlash = useCallback(() => {
    setIsBrandFlash(true);
    if (brandFlashTimeoutRef.current != null) {
      window.clearTimeout(brandFlashTimeoutRef.current);
    }
    brandFlashTimeoutRef.current = window.setTimeout(() => setIsBrandFlash(false), 220);
  }, []);

  useEffect(() => {
    return () => {
      if (brandFlashTimeoutRef.current != null) {
        window.clearTimeout(brandFlashTimeoutRef.current);
      }
    };
  }, []);

  const [isWideViewport, setIsWideViewport] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth >= 768 : true
  );

  useEffect(() => {
    const handleResize = () => setIsWideViewport(window.innerWidth >= 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const shouldHaveStickyHeader = (isWideViewport || isTablet) && !isGenerationsPaneLocked;

  const [isCreateProjectModalOpen, setIsCreateProjectModalOpen] = useState(false);
  const [isProjectSettingsModalOpen, setIsProjectSettingsModalOpen] = useState(false);
  const [isReferralModalOpen, setIsReferralModalOpen] = useState(false);
  const [createProjectInitialName, setCreateProjectInitialName] = useState<string | undefined>(undefined);

  const handleOpenCreateProject = useCallback((initialName?: string) => {
    setCreateProjectInitialName(initialName);
    setIsCreateProjectModalOpen(true);
  }, []);

  const handleOpenProjectSettings = useCallback(() => {
    setIsProjectSettingsModalOpen(true);
  }, []);

  const handleOpenReferralModal = useCallback(() => {
    setIsReferralModalOpen(true);
  }, []);

  const handleCreateProjectModalOpenChange = useCallback((open: boolean) => {
    setIsCreateProjectModalOpen(open);
    if (!open) {
      setCreateProjectInitialName(undefined);
    }
  }, []);

  const selectedProject = projects.find(project => project.id === selectedProjectId);

  return {
    session,
    referralStats,
    isBrandFlash,
    triggerBrandFlash,
    shouldHaveStickyHeader,
    selectedProject,
    isCreateProjectModalOpen,
    handleCreateProjectModalOpenChange,
    createProjectInitialName,
    isProjectSettingsModalOpen,
    setIsProjectSettingsModalOpen,
    isReferralModalOpen,
    setIsReferralModalOpen,
    handleOpenCreateProject,
    handleOpenProjectSettings,
    handleOpenReferralModal,
  };
}
