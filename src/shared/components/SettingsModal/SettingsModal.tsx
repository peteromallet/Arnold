import React, { useState, useEffect } from "react";
import { LogOut } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/shared/components/ui/dialog";
import { Button } from "@/shared/components/ui/button";
import { useApiTokens } from "@/shared/hooks/account/useApiTokens";
import { usePersistentState } from "@/shared/hooks/usePersistentState";
import { getSupabaseClient as supabase } from '@/integrations/supabase/client';
import { useIsMobile } from "@/shared/hooks/mobile";
import { useLargeModal } from '@/shared/hooks/useModal';
import { useScrollFade } from "@/shared/hooks/useScrollFade";
import { useUserUIState } from "@/shared/hooks/useUserUIState";
import { useDarkMode } from "@/shared/hooks/core/useDarkMode";
import { useTextCase } from "@/shared/hooks/useTextCase";
import { useAIInputMode } from "@/shared/contexts/AIInputModeContext";
import { dispatchAppEvent } from '@/shared/lib/typedEvents';
import { GenerationSection } from "./sections/GenerationSection";
import { useWorkerLaunchConfig } from "./hooks/useWorkerLaunchConfig";
import { PreferencesSection } from "./sections/PreferencesSection";
import { TransactionsSection } from "./sections/TransactionsSection";
import { ExtensionsSection } from "./sections/ExtensionsSection";
import type { SettingsModalProps } from "./types";

const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onOpenChange,
  creditsTab = "purchase",
  extensions,
  extensionsLoading = false,
  onEnableExtension,
  onDisableExtension,
  onInstallExtension,
  onUseLocalSource,
  onRevertToInstalled,
  allLifecycleEvents,
  onUpdateSettings,
  onUninstallExtension,
  pendingUninstallReport,
  isUninstalling,
}) => {
  const isMobile = useIsMobile();

  // Modal styling and scroll fade
  const modal = useLargeModal();
  const { showFade, scrollRef } = useScrollFade({
    isOpen: isOpen,
    debug: false,
    preloadFade: modal.isMobile
  });

  const {
    tokens,
    generateToken,
    isGenerating,
    generatedToken,
  } = useApiTokens();

  // Installation tab preference (persistent)
  const [activeInstallTab, setActiveInstallTab] = usePersistentState<string>("settings-install-tab", "need-install");

  // Local-worker launch settings (6 persistent values bundled into one hook)
  const { config: launchConfig, setters: launchSetters } = useWorkerLaunchConfig();

  // Settings section toggle (Generation vs Transactions vs Preferences)
  const [settingsSection, setSettingsSection] = useState<'app' | 'transactions' | 'preferences' | 'extensions'>('app');

  // Lock modal height based on first section content
  const [lockedHeight, setLockedHeight] = useState<number | null>(null);

  // Lock height immediately on open (avoid "skeleton -> real data" resize)
  const setDialogContentNode = React.useCallback((node: HTMLDivElement | null) => {
    if (!node) return;
    if (!isOpen) return;
    if (lockedHeight !== null) return;
    if (settingsSection !== 'app') return;
    setLockedHeight(node.offsetHeight);
  }, [isOpen, lockedHeight, settingsSection]);

  // Reset locked height when modal closes
  useEffect(() => {
    if (!isOpen) {
      setLockedHeight(null);
    }
  }, [isOpen]);

  // Dark mode
  const { darkMode, setDarkMode } = useDarkMode();

  // Text case mode (whether to preserve user-inputted text casing)
  const { preserveUserText, setPreserveUserText } = useTextCase();

  // AI input mode (voice vs text)
  const { mode: aiInputMode, setMode: setAIInputMode } = useAIInputMode();

  // Generation method preferences (database-backed)
  const {
    value: generationMethods,
    update: updateGenerationMethods,
    isLoading: isLoadingGenerationMethods
  } = useUserUIState('generationMethods', { onComputer: true, inCloud: true });

  // Privacy defaults preferences (database-backed)
  const {
    value: privacyDefaults,
    update: updatePrivacyDefaults,
    isLoading: isLoadingPrivacyDefaults
  } = useUserUIState('privacyDefaults', { resourcesPublic: true, generationsPublic: false });

  // Enhanced update function that notifies other components
  const updateGenerationMethodsWithNotification = (patch: Partial<typeof generationMethods>) => {
    updateGenerationMethods(patch);

    // Notify other components immediately
    dispatchAppEvent('generation-settings-changed');

    // For cross-tab communication
    localStorage.setItem('generation-settings-updated', Date.now().toString());
    localStorage.removeItem('generation-settings-updated');
  };

  const onComputerChecked = generationMethods.onComputer;
  const inCloudChecked = generationMethods.inCloud;

  const hasValidToken = tokens.length > 0;

  const getActiveToken = () => {
    return tokens[0]; // Just return the first token since we no longer have expiry
  };

  const handleGenerateToken = () => {
    // Default label
    const defaultLabel = "Local Generator";
    generateToken(defaultLabel);
  };

  const handleSignOut = async () => {
    await supabase().auth.signOut();
    onOpenChange(false); // Close the modal after signing out
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent
        ref={setDialogContentNode}
        className={modal.className}
        style={(() => {
          const desktopMaxHeight = 'calc(100vh - 24px)';
          const maxHeight = modal.isMobile
            ? (modal.style.maxHeight as string | undefined) ?? '90vh'
            : desktopMaxHeight;
          return {
            ...modal.style,
            ...(lockedHeight !== null
              ? { height: lockedHeight, maxHeight, overflow: 'hidden' }
              : { maxHeight }),
          };
        })()}
      >

        <div className={modal.headerClass}>
          <DialogHeader className={`${modal.isMobile ? 'px-2 pt-1 pb-1' : 'px-2 pt-1 pb-1'} flex-shrink-0 relative`}>
            <div className={`flex ${isMobile ? 'flex-col items-center gap-3' : 'items-center gap-4'}`}>
              <DialogTitle className={`text-2xl ${isMobile ? 'mb-1' : 'md:mt-[11px]'}`}>
                App Settings
              </DialogTitle>
              <div className="relative inline-flex items-center bg-muted rounded-full p-0.5 shadow-inner md:mt-[11px] w-fit">
                <button
                  onClick={() => setSettingsSection('app')}
                  className={`${isMobile ? 'px-2 py-0.5 text-[11px]' : 'px-3 py-1 text-xs'} font-medium rounded-full transition-all duration-200 focus:outline-none ${
                    settingsSection === 'app'
                      ? 'bg-background text-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  Generation
                </button>
                <button
                  onClick={() => setSettingsSection('transactions')}
                  className={`${isMobile ? 'px-2 py-0.5 text-[11px]' : 'px-3 py-1 text-xs'} font-medium rounded-full transition-all duration-200 focus:outline-none ${
                    settingsSection === 'transactions'
                      ? 'bg-background text-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  Transactions
                </button>
                <button
                  onClick={() => setSettingsSection('preferences')}
                  className={`${isMobile ? 'px-2 py-0.5 text-[11px]' : 'px-3 py-1 text-xs'} font-medium rounded-full transition-all duration-200 focus:outline-none ${
                    settingsSection === 'preferences'
                      ? 'bg-background text-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  Preferences
                </button>
                <button
                  onClick={() => setSettingsSection('extensions')}
                  className={`${isMobile ? 'px-2 py-0.5 text-[11px]' : 'px-3 py-1 text-xs'} font-medium rounded-full transition-all duration-200 focus:outline-none ${
                    settingsSection === 'extensions'
                      ? 'bg-background text-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  Extensions
                </button>
              </div>
            </div>
          </DialogHeader>
        </div>

        {/* Scrollable content container */}
        <div
          ref={scrollRef}
          className={`${modal.scrollClass} ${modal.isMobile ? 'px-2' : 'px-2'} overflow-x-hidden [scrollbar-gutter:stable_both-edges] [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none] sm:[&::-webkit-scrollbar]:block sm:[-ms-overflow-style:auto] sm:[scrollbar-width:auto] sm:pr-4`}
        >
          {/* Extensions Section */}
          {settingsSection === 'extensions' && (
            <ExtensionsSection
              isMobile={isMobile}
              extensions={extensions}
              isLoading={extensionsLoading}
              onEnableExtension={onEnableExtension}
              onDisableExtension={onDisableExtension}
              onInstallExtension={onInstallExtension}
              onUseLocalSource={onUseLocalSource}
              onRevertToInstalled={onRevertToInstalled}
              allLifecycleEvents={allLifecycleEvents}
              onUpdateSettings={onUpdateSettings}
              onUninstallExtension={onUninstallExtension}
              pendingUninstallReport={pendingUninstallReport}
              isUninstalling={isUninstalling}
            />
          )}

          {/* Transactions Section */}
          {settingsSection === 'transactions' && <TransactionsSection />}

          {/* Preferences Section */}
          {settingsSection === 'preferences' && (
            <PreferencesSection
              isMobile={isMobile}
              darkMode={darkMode}
              setDarkMode={setDarkMode}
              preserveUserText={preserveUserText}
              setPreserveUserText={setPreserveUserText}
              privacyDefaults={privacyDefaults}
              updatePrivacyDefaults={updatePrivacyDefaults}
              isLoadingPrivacyDefaults={isLoadingPrivacyDefaults}
              aiInputMode={aiInputMode}
              setAIInputMode={setAIInputMode}
            />
          )}

          {/* App Settings Section */}
          {settingsSection === 'app' && (
            <GenerationSection
              isMobile={isMobile}
              onComputerChecked={onComputerChecked}
              inCloudChecked={inCloudChecked}
              updateGenerationMethodsWithNotification={updateGenerationMethodsWithNotification}
              isLoadingGenerationMethods={isLoadingGenerationMethods}
              hasValidToken={hasValidToken}
              generatedToken={generatedToken}
              handleGenerateToken={handleGenerateToken}
              isGenerating={isGenerating}
              getActiveToken={getActiveToken}
              launchConfig={launchConfig}
              launchSetters={launchSetters}
              activeInstallTab={activeInstallTab}
              setActiveInstallTab={setActiveInstallTab}
              creditsTab={creditsTab}
            />
          )}
        </div>

        {/* Footer */}
        <div className={`${modal.footerClass} relative`}>
          {/* Fade overlay */}
          {showFade && (
            <div
              className="absolute top-0 left-0 right-0 h-16 pointer-events-none z-10"
              style={{ transform: 'translateY(-64px)' }}
            >
              <div className="h-full bg-gradient-to-t from-background via-background/95 to-transparent" />
            </div>
          )}

          <DialogFooter className={`${modal.isMobile ? 'px-2 pt-6 pb-3 flex-row justify-between' : 'px-2 pt-7 pb-3'} border-t relative z-20`}>
            <div className="flex gap-2 mr-auto">
              <Button variant="retro-secondary" size="retro-sm" onClick={handleSignOut}>
                <LogOut className="h-4 w-4 mr-2" />
                Sign out
              </Button>
            </div>
            <Button variant="retro" size="retro-sm" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export { SettingsModal };
