import React, { useEffect } from 'react';
import { useLocation, Navigate } from 'react-router-dom';
import { TasksPane } from '@/features/tasks/components/TasksPane/TasksPane';
import { GenerationsPane } from '@/features/gallery/components/GenerationsPane/GenerationsPane';
import { EditorPane } from '@/features/editor/components/EditorPaneTab';
import { ToolsPane } from '@/shared/components/ToolsPane/ToolsPane';
import { ReighLoading } from '@/shared/components/ReighLoading';
import { SettingsModal } from '@/shared/components/SettingsModal/SettingsModal';
import { OnboardingModal } from '@/shared/components/modals/OnboardingModal';
import { ChunkLoadErrorBoundary } from '@/shared/runtime/ChunkLoadErrorBoundary';
import { dispatchAppEvent } from '@/shared/lib/typedEvents';

// Lazy load ProductTour since it only shows during onboarding
const LazyProductTour = React.lazy(() =>
  import('@/shared/components/ProductTour').then(module => ({
    default: module.ProductTour
  }))
);
import { AIInputModeProvider } from '@/shared/contexts/AIInputModeContext';
import { useIsMobile, useIsTablet } from '@/shared/hooks/mobile';
import { cn } from '@/shared/components/ui/contracts/cn';
import { useVideoEditorRouteState } from '@/app/hooks/useVideoEditorRouteState';
import { SocialIcons } from './components/SocialIcons';

import { useAuth } from '@/shared/contexts/AuthContext';
import { useSplitViewScroll } from './hooks/useSplitViewScroll';
import { useGlobalPaneShortcuts } from './hooks/useGlobalPaneShortcuts';
import { useSettingsModal } from './hooks/useSettingsModal';
import { useOnboardingFlow } from './hooks/useOnboardingFlow';
import { useResetCurrentShotOnRouteChange } from './hooks/useResetCurrentShotOnRouteChange';
import { LayoutMainContent } from './components/LayoutMainContent';
import { usePanesStore } from '@/shared/state/panesStore';

// Scroll to top component
function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo(0, 0);
    // Also dispatch event for custom scroll containers
    dispatchAppEvent('app:scrollToTop', { behavior: 'auto' });
  }, [pathname]);

  return null;
}

export const Layout: React.FC = () => {
  const { isVideoEditorShellActive } = useVideoEditorRouteState();
  const isTasksPaneLocked = usePanesStore((state) => state.isTasksPaneLocked);
  const tasksPaneWidth = usePanesStore((state) => state.tasksPaneWidth);
  const isShotsPaneLocked = usePanesStore((state) => state.isShotsPaneLocked);
  const shotsPaneWidth = usePanesStore((state) => state.shotsPaneWidth);
  const isGenerationsPaneLocked = usePanesStore((state) => state.isGenerationsPaneLocked);
  const generationsPaneHeight = usePanesStore((state) => state.generationsPaneHeight);

  // Mobile detection for split-view scroll handling
  const isMobile = useIsMobile();
  const isTablet = useIsTablet();
  const isSmallMobile = isMobile && !isTablet;

  // On small mobile with locked generations pane, create split-view scroll behavior
  const isMobileSplitView = isSmallMobile && isGenerationsPaneLocked && !isVideoEditorShellActive;

  // Extracted hooks
  const { splitViewWrapperRef } = useSplitViewScroll(isMobileSplitView);
  const { isAuthenticated, isLoading } = useAuth();
  const { isSettingsModalOpen, setIsSettingsModalOpen, settingsInitialTab, settingsCreditsTab, handleOpenSettings } = useSettingsModal();
  const { showOnboardingModal, handleOnboardingClose } = useOnboardingFlow();
  useResetCurrentShotOnRouteChange();
  useGlobalPaneShortcuts();

  // Show loading spinner while determining auth state
  // (isLoading is always false here because AuthGate gates on it, but kept for safety)
  if (isLoading) {
    return (
      <ReighLoading />
    );
  }

  // Redirect unauthenticated users to home page
  // Use /home instead of / to avoid redirect loops in non-WEB environments
  // where / is inside Layout
  if (!isAuthenticated) {
    return <Navigate to="/home" replace state={{ fromProtected: true }} />;
  }

  // Footer style matches main content margins for side panes
  const footerStyle = {
    marginRight: isTasksPaneLocked ? `${tasksPaneWidth}px` : '0px',
    marginLeft: isShotsPaneLocked ? `${shotsPaneWidth}px` : '0px',
    willChange: 'margin',
  } as React.CSSProperties;

  // Style for the scroll wrapper when in mobile split view
  // This wraps both header and content so they scroll together
  const splitViewWrapperStyle: React.CSSProperties = isMobileSplitView ? {
    height: `calc(100dvh - ${generationsPaneHeight}px)`,
    overflowY: 'auto',
    overscrollBehavior: 'contain',
    WebkitOverflowScrolling: 'touch',
  } : {};

  const mainContent = (
    <LayoutMainContent
      isMobileSplitView={isMobileSplitView}
      onOpenSettings={handleOpenSettings}
    />
  );

  return (
    <AIInputModeProvider>
      <div className={cn('flex flex-col', isVideoEditorShellActive && 'h-screen overflow-hidden')}>
        <ScrollToTop />
        {/* Theme-adaptive background gradient - subtle in dark mode */}
        <div className="fixed inset-0 bg-gradient-to-br from-background via-secondary/10 to-accent/5 opacity-40 dark:opacity-0 pointer-events-none"></div>

        {/* When in mobile split view, wrap header + content in a scroll container */}
        {isMobileSplitView ? (
          <div ref={splitViewWrapperRef} style={splitViewWrapperStyle}>
            {mainContent}
          </div>
        ) : (
          mainContent
        )}

        <EditorPane />
        <TasksPane onOpenSettings={handleOpenSettings} />
        <ToolsPane />
        <GenerationsPane />

        {/* Social Icons Footer */}
        {!isVideoEditorShellActive && (
          <div
            className="relative transition-[margin] duration-300 ease-smooth"
            style={footerStyle}
          >
            <SocialIcons />
          </div>
        )}

        <SettingsModal
          isOpen={isSettingsModalOpen}
          onOpenChange={setIsSettingsModalOpen}
          initialTab={settingsInitialTab}
          creditsTab={settingsCreditsTab}
        />

        {/* Onboarding Modal */}
        <OnboardingModal
          isOpen={showOnboardingModal}
          onClose={handleOnboardingClose}
        />

        {/* Product Tour - lazy loaded since only needed during onboarding */}
        <ChunkLoadErrorBoundary>
          <React.Suspense fallback={null}>
            <LazyProductTour />
          </React.Suspense>
        </ChunkLoadErrorBoundary>
      </div>
    </AIInputModeProvider>
  );
};
