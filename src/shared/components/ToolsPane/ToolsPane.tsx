import React, { useState, useEffect, memo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useSlidingPane } from '@/shared/hooks/useSlidingPane';
import { cn } from '@/shared/components/ui/contracts/cn';
import { PaneControlTab } from '../PaneControlTab';
import { useBottomOffset } from '@/shared/hooks/layout/useBottomOffset';
import { useUserUIState } from '@/shared/hooks/useUserUIState';
import { useDarkMode } from '@/shared/hooks/core/useDarkMode';
import { useClickRipple } from '@/shared/hooks/interaction/useClickRipple';
import { PaneBackdrop } from '@/shared/components/panes/PaneBackdrop';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { useToolSettings } from '@/shared/hooks/settings/useToolSettings';
import { VIDEO_EDITOR_PATH, videoEditorPathWithTimeline } from '@/tools/video-editor/lib/video-editor-path';
import { videoEditorSettings } from '@/tools/video-editor/settings/videoEditorDefaults';
import {
  Home,
  LayoutGrid,
} from 'lucide-react';
import { AppEnv, type AppEnvValue } from '@/types/env';
import { isToolEligible } from '@/shared/lib/tooling/toolEligibility';
import { toolsUIManifest, type ToolUIDefinition } from '@/shared/lib/tooling/toolManifest';
import { usePanesStore } from '@/shared/state/panesStore';

const processTools = toolsUIManifest.filter((tool) => tool.paneSection === 'main');
const assistantTools = toolsUIManifest.filter((tool) => tool.paneSection === 'assistant');

type ToolItem = ToolUIDefinition;

interface ToolCardProps {
  item: ToolItem;
  isCurrentTool: boolean;
  isDefault: boolean;
  isVisible: boolean;
  onNavigate: (path: string) => void;
  onSetDefault: () => void;
}

const ToolCard = memo(({ item, isCurrentTool, isDefault, isVisible, onNavigate, onSetDefault }: ToolCardProps) => {
  const { triggerRipple, rippleStyles, isRippleActive } = useClickRipple();
  const { darkMode } = useDarkMode();
  const [isWiggling, setIsWiggling] = useState(false);
  const wiggleTimeoutRef = React.useRef<NodeJS.Timeout | null>(null);

  // Cleanup timeout on unmount
  React.useEffect(() => {
    return () => {
      if (wiggleTimeoutRef.current) {
        clearTimeout(wiggleTimeoutRef.current);
      }
    };
  }, []);

  const isDisabled = !item.path;
  const defaultButtonLabel = isDefault ? 'Default landing tool' : 'Set as default landing tool';
  const stopDefaultToolEvent = (
    event: React.PointerEvent<HTMLButtonElement> | React.MouseEvent<HTMLButtonElement>,
  ) => {
    event.stopPropagation();
  };

  const handleClick = (e: React.PointerEvent) => {
    if (isDisabled) {
      e.preventDefault();
      setIsWiggling(true);
      wiggleTimeoutRef.current = setTimeout(() => setIsWiggling(false), 600);
      return;
    }
    
    if (item.path) {
      triggerRipple(e);
      onNavigate(item.path);
    }
  };

  if (!isVisible && !isDisabled) return null;

  return (
    <div
      className={cn(
        "relative group cursor-pointer rounded-lg transition-all duration-200",
        "hover:shadow-md",
        isCurrentTool && "ring-2 ring-blue-500 ring-offset-2 ring-offset-zinc-900",
        isDisabled && "opacity-40 cursor-not-allowed",
        isWiggling && "animate-subtle-wiggle"
      )}
      onPointerUp={handleClick}
    >
      <div 
        className={cn(
          "p-3 rounded-lg bg-zinc-800/80 border border-zinc-700 click-ripple",
          isRippleActive && "ripple-active",
          !isDisabled && "hover:bg-zinc-700/80 hover:border-zinc-600"
        )}
        style={rippleStyles}
      >
        <div className="flex items-center gap-3">
          {/* Icon */}
          <div 
            className={cn(
              "w-10 h-10 rounded-md flex items-center justify-center bg-gradient-to-br shadow-sm",
              item.gradient,
              "dark:bg-none dark:border"
            )}
            style={darkMode ? { borderColor: item.darkIconColor, backgroundColor: `${item.darkIconColor}0d` } : undefined}
          >
            <item.icon 
              className="w-5 h-5 drop-shadow-lg dark:drop-shadow-none transition-colors duration-300" 
              style={{ color: darkMode ? item.darkIconColor : 'white' }} 
            />
          </div>
          
          {/* Text */}
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-medium text-zinc-100 truncate">
              {item.name}
            </h3>
            <p className="text-xs text-zinc-400 line-clamp-2">
              {item.description}
            </p>
          </div>
          
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              type="button"
              className={cn(
                'rounded-md p-1 transition-colors',
                isDefault ? 'text-blue-400 hover:text-blue-300' : 'text-zinc-500 hover:text-zinc-300',
              )}
              aria-label={defaultButtonLabel}
              title={defaultButtonLabel}
              onPointerDown={stopDefaultToolEvent}
              onPointerUp={(event) => {
                event.stopPropagation();
                onSetDefault();
              }}
              onClick={stopDefaultToolEvent}
            >
              {isDefault ? (
                <Home className="w-4 h-4 fill-current" />
              ) : (
                <Home className="w-4 h-4 text-zinc-500" />
              )}
            </button>

            {/* Current indicator */}
            {isCurrentTool && (
              <div className="w-2 h-2 rounded-full bg-blue-500 flex-shrink-0" />
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

ToolCard.displayName = 'ToolCard';

interface ToolsPaneDrawerProps {
  paneProps: Record<string, unknown>;
  transformClass: string;
  shotsPaneWidth: number;
  isPointerEventsEnabled: boolean;
  currentToolId: string | null;
  defaultToolId: string;
  isToolVisible: (tool: Pick<ToolUIDefinition, 'id' | 'environments'> | null | undefined) => boolean;
  handleNavigate: (path: string) => void;
  onSetDefaultTool: (toolId: string) => void;
}

const ToolsPaneDrawer = ({
  paneProps,
  transformClass,
  shotsPaneWidth,
  isPointerEventsEnabled,
  currentToolId,
  defaultToolId,
  isToolVisible,
  handleNavigate,
  onSetDefaultTool,
}: ToolsPaneDrawerProps) => {
  return (
    <div
      className="pointer-events-none"
      style={{
        position: 'fixed',
        left: 0,
        top: 0,
        bottom: 0,
        width: `${shotsPaneWidth}px`,
        zIndex: 60,
      }}
    >
      <div
        {...paneProps}
        className={cn(
          'pointer-events-auto absolute top-0 left-0 h-full w-full border-2 border-r shadow-xl transform transition-transform duration-300 ease-smooth flex flex-col bg-zinc-900/95 border-zinc-700',
          transformClass
        )}
      >
        <div
          className={cn(
            'flex flex-col h-full',
            isPointerEventsEnabled ? 'pointer-events-auto' : 'pointer-events-none'
          )}
        >
          <div className="p-2 border-b border-zinc-800 flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-2">
              <LayoutGrid className="h-5 w-5 text-zinc-400 ml-2" />
              <h2 className="text-xl font-light text-zinc-200">Tools</h2>
            </div>
          </div>

          <div className="flex flex-col gap-2 p-3 flex-grow overflow-y-auto scrollbar-hide">
            <div className="mb-2">
              <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2 px-1">
                Main Tools
              </h3>
              <div className="flex flex-col gap-2">
                {processTools.map((tool) => (
                  <ToolCard
                    key={tool.id}
                    item={tool}
                    isCurrentTool={currentToolId === tool.id}
                    isDefault={defaultToolId === tool.id}
                    isVisible={isToolVisible(tool)}
                    onNavigate={handleNavigate}
                    onSetDefault={() => onSetDefaultTool(tool.id)}
                  />
                ))}
              </div>
            </div>

            <div>
              <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2 px-1">
                Assistant Tools
              </h3>
              <div className="flex flex-col gap-2">
                {assistantTools.filter((tool) => isToolVisible(tool)).map((tool) => (
                  <ToolCard
                    key={tool.id}
                    item={tool}
                    isCurrentTool={currentToolId === tool.id}
                    isDefault={defaultToolId === tool.id}
                    isVisible={isToolVisible(tool)}
                    onNavigate={handleNavigate}
                    onSetDefault={() => onSetDefaultTool(tool.id)}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const ToolsPaneComponent: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { selectedProjectId } = useProjectSelectionContext();
  const isShotsPaneLocked = usePanesStore((state) => state.isShotsPaneLocked);
  const setIsShotsPaneLocked = usePanesStore((state) => state.setIsShotsPaneLocked);
  const shotsPaneWidth = usePanesStore((state) => state.shotsPaneWidth);

  // Get current environment
  let env = import.meta.env.VITE_APP_ENV?.toLowerCase() || AppEnv.WEB;
  if (env === 'production' || env === 'prod') env = AppEnv.WEB;
  const currentEnv = env as AppEnvValue;

  // Get generation method preferences for character-animate visibility
  const { value: generationMethods, isLoading: isLoadingGenerationMethods } = useUserUIState('generationMethods', { onComputer: true, inCloud: true });
  const { value: defaultTool, update: updateDefaultTool } = useUserUIState('defaultTool', { toolId: 'travel-between-images' });
  const isCloudGenerationEnabled = generationMethods.inCloud;
  const { settings } = useToolSettings(videoEditorSettings.id, {
    projectId: selectedProjectId ?? undefined,
    enabled: Boolean(selectedProjectId),
  });

  const { isLocked, isOpen, toggleLock, openPane, paneProps, transformClass, handlePaneEnter, handlePaneLeave, showBackdrop, closePane } = useSlidingPane({
    side: 'left',
    isLocked: isShotsPaneLocked,
    onToggleLock: () => setIsShotsPaneLocked(!isShotsPaneLocked),
  });

  // Delay pointer events until animation completes
  const [isPointerEventsEnabled, setIsPointerEventsEnabled] = useState(false);
  
  useEffect(() => {
    if (isOpen) {
      const timeoutId = setTimeout(() => {
        setIsPointerEventsEnabled(true);
      }, 300);
      return () => clearTimeout(timeoutId);
    } else {
      setIsPointerEventsEnabled(false);
    }
  }, [isOpen]);

  // Determine current tool from path
  const getCurrentTool = () => {
    const path = location.pathname;
    for (const tool of [...processTools, ...assistantTools]) {
      if (tool.path && path.startsWith(tool.path)) {
        return tool;
      }
    }
    return null;
  };
  const currentTool = getCurrentTool();
  const currentToolId = currentTool?.id || null;

  // Tool visibility check
  const isToolVisible = (tool: Pick<ToolUIDefinition, 'id' | 'environments'> | null | undefined) =>
    isToolEligible(tool, {
      currentEnv,
      isCloudGenerationEnabled,
      isLoadingGenerationMethods,
    });

  const handleNavigate = (path: string) => {
    setIsShotsPaneLocked(false); // Close the pane when navigating

    if (path === VIDEO_EDITOR_PATH) {
      navigate(videoEditorPathWithTimeline(settings?.lastTimelineId));
      return;
    }

    navigate(path);
  };

  return (
    <>
      {/* Backdrop overlay to capture taps outside the pane on mobile */}
      <PaneBackdrop show={showBackdrop} zIndex={59} onClose={closePane} />
      <PaneControlTab
        position={{ side: "left", paneDimension: shotsPaneWidth, bottomOffset: useBottomOffset() }}
        state={{ isLocked, isOpen: !!isOpen }}
        handlers={{ toggleLock, openPane, handlePaneEnter, handlePaneLeave }}
        display={{ paneIcon: "tools", paneTooltip: "See all tools", shortcutHint: '⌥A' }}
        actions={{
          thirdButton: currentTool ? {
            onClick: openPane,
            ariaLabel: `Current tool: ${currentTool.name}`,
            content: <currentTool.icon className="h-4 w-4" />,
            tooltip: `Current tool: ${currentTool.name}`,
          } : undefined,
        }}
        dataTour="tools-pane-tab"
      />
      <ToolsPaneDrawer
        paneProps={paneProps as Record<string, unknown>}
        transformClass={transformClass}
        shotsPaneWidth={shotsPaneWidth}
        isPointerEventsEnabled={isPointerEventsEnabled}
        currentToolId={currentToolId}
        defaultToolId={defaultTool.toolId}
        isToolVisible={isToolVisible}
        handleNavigate={handleNavigate}
        onSetDefaultTool={(toolId) => updateDefaultTool({ toolId })}
      />
    </>
  );
};

export const ToolsPane = React.memo(ToolsPaneComponent);
