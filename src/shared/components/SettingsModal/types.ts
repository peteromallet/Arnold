import type { AIInputMode } from "@/shared/contexts/AIInputModeContext"
import type { ExtensionReferenceReport, ReferenceKind, ExtensionReference } from "@/tools/video-editor/runtime/extensionReferenceReport"
import type { WorkerLaunchConfigValues, WorkerLaunchConfigSetters } from "./hooks/useWorkerLaunchConfig"

// Types for SettingsModal components

export interface SettingsModalProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  initialTab?: string;
  creditsTab?: 'purchase' | 'history' | 'task-log';
  /** Optional extension display data for the Extensions tab. */
  extensions?: readonly ExtensionDisplayInfo[];
  /** Whether extension data is still being resolved. */
  extensionsLoading?: boolean;
  /** Callback when user requests to enable an extension. */
  onEnableExtension?: (extensionId: string) => void | Promise<void>;
  /** Callback when user requests to disable an extension. */
  onDisableExtension?: (extensionId: string) => void | Promise<void>;
  /** Callback when user requests to install a trusted local/test-provided pack. */
  onInstallExtension?: () => void | Promise<void>;
  /** Callback when user requests to use local source for a conflicting extension. */
  onUseLocalSource?: (extensionId: string) => void | Promise<void>;
  /** Callback when user requests to revert to installed for a conflicting extension. */
  onRevertToInstalled?: (extensionId: string) => void | Promise<void>;
  /** Lifecycle events for all extensions (for the aggregate log panel). */
  allLifecycleEvents?: readonly (LifecycleEventDisplayInfo & { extensionId: string; extensionName: string })[];
  /** Callback when user updates settings for an extension. */
  onUpdateSettings?: (extensionId: string, key: string, value: unknown) => void | Promise<void>;
  /** Callback when user requests to uninstall an extension. */
  onUninstallExtension?: (extensionId: string) => void | Promise<void>;
  /** Reference report for an extension pending uninstall (null when no uninstall in progress). */
  pendingUninstallReport?: ExtensionReferenceReport | null;
  /** Whether an uninstall operation is in progress. */
  isUninstalling?: boolean;
}

export interface CommandConfig {
  computerType: string;
  gpuType: string;
  memoryProfile: string;
  windowsShell: string;
  showDebugLogs: boolean;
  idleReleaseMinutes: string;
  token: string;
}

export interface GenerationSectionProps {
  isMobile: boolean;
  // Generation method state
  onComputerChecked: boolean;
  inCloudChecked: boolean;
  updateGenerationMethodsWithNotification: (patch: { onComputer?: boolean; inCloud?: boolean }) => void;
  isLoadingGenerationMethods: boolean;
  // Token state
  hasValidToken: boolean;
  generatedToken: string | null;
  handleGenerateToken: () => void;
  isGenerating: boolean;
  getActiveToken: () => { token: string; created_at: string } | undefined;
  // Worker launch config (bundled)
  launchConfig: WorkerLaunchConfigValues;
  launchSetters: WorkerLaunchConfigSetters;
  // Tab state
  activeInstallTab: string;
  setActiveInstallTab: (value: string) => void;
  // Props
  creditsTab?: 'purchase' | 'history' | 'task-log';
}

export interface PreferencesSectionProps {
  isMobile: boolean;
  darkMode: boolean;
  setDarkMode: (value: boolean) => void;
  preserveUserText: boolean;
  setPreserveUserText: (value: boolean) => void;
  privacyDefaults: { resourcesPublic: boolean; generationsPublic: boolean };
  updatePrivacyDefaults: (patch: { resourcesPublic?: boolean; generationsPublic?: boolean }) => void;
  isLoadingPrivacyDefaults: boolean;
  aiInputMode: AIInputMode;
  setAIInputMode: (mode: AIInputMode) => void;
}

// ---------------------------------------------------------------------------
// Extensions tab types (T18)
// ---------------------------------------------------------------------------

/** Status classification for an extension displayed in the manager. */
export type ExtensionStatus = 'active' | 'blocked' | 'degraded' | 'disabled' | 'error';

// ---------------------------------------------------------------------------
// T21: Dependency badges, degraded contributions, lifecycle events
// ---------------------------------------------------------------------------


// ---------------------------------------------------------------------------
// T22: Settings schema-driven controls and migration summary
// ---------------------------------------------------------------------------

/** Supported primitive types for settings fields. */
export type SettingsFieldType = 'string' | 'number' | 'boolean' | 'json';

/** A single settings field derived from the typed settings schema. */
export interface SettingsFieldInfo {
  /** The settings key. */
  key: string;
  /** Human-readable label (derived from key or schema title). */
  label: string;
  /** The JSON type of the field. */
  type: SettingsFieldType;
  /** The current value (from persisted settings or manifest defaults). */
  currentValue: unknown;
  /** The default value from the manifest. */
  defaultValue?: unknown;
  /** Optional description from the schema. */
  description?: string;
}

/** Migration summary display info for the settings editor. */
export interface MigrationSummaryDisplayInfo {
  /** The schema version in the persisted snapshot (before migration). */
  oldSchemaVersion: number;
  /** The schema version declared by the manifest (target). */
  newSchemaVersion: number;
  /** ISO 8601 timestamp of the migration attempt. */
  migrationTimestamp?: string;
  /** Human-readable migration status. */
  status: 'no-migration' | 'up-to-date' | 'migrated' | 'migration-failed' | 'migration-reset';
  /** Diagnostic message from the migration. */
  message?: string;
  /** Whether the migration resulted in a reset to defaults. */
  resetToDefaults?: boolean;
}

/** Summary of an extension's dependency resolution state. */
export interface DependencySummary {
  /** Total number of dependencies declared by this extension. */
  totalCount: number;
  /** Number that are fully satisfied. */
  satisfiedCount: number;
  /** Missing required dependencies. */
  missingRequiredCount: number;
  /** Missing optional dependencies. */
  missingOptionalCount: number;
  /** Version mismatches (required + optional). */
  versionMismatchCount: number;
  /** Whether the extension is running in degraded mode due to optional deps. */
  degraded: boolean;
  /** Whether the extension is blocked by a dependency cycle. */
  inCycle: boolean;
}

/** Information about a contribution degraded by a dependency issue. */
export interface DegradedContributionInfo {
  /** The contribution ID that is degraded/unavailable. */
  contributionId: string;
  /** The dependency extension ID that caused the degradation. */
  dependencyId: string;
  /** Human-readable reason for the degradation. */
  reason: string;
}

/** Compact display info for a single lifecycle event. */
export interface LifecycleEventDisplayInfo {
  /** Event kind (e.g. 'install', 'activation_failure', 'integrity_fail'). */
  kind: string;
  /** ISO 8601 timestamp. */
  timestamp: string;
  /** Human-readable message. */
  message: string;
  /** Whether this is a failure/error event. */
  isFailure: boolean;
}

/** Display-ready information for a single extension in the manager listing. */
export interface ExtensionDisplayInfo {
  /** Unique extension identifier (the manifest id). */
  extensionId: string;
  /** Human-readable name (manifest label). */
  name: string;
  /** Semver version string. */
  version: string;
  /** Whether the extension is workspace-source or installed-bundle. */
  source: 'local' | 'installed';
  /** Whether the extension is currently enabled. */
  enabled: boolean;
  /** High-level activation status. */
  status: ExtensionStatus;
  /** True when publisher or license info is missing/untrusted. */
  trustWarning: boolean;
  /** Human-readable reason for the trust warning. */
  trustWarningReason?: string;
  /** Number of diagnostics emitted by or about this extension. */
  diagnosticsCount: number;
  /** Whether a conflict exists between local and installed forms. */
  hasConflict: boolean;
  /** Description of the conflict resolution strategy, if any. */
  conflictStrategy?: string;
  /** Which form is currently winning the conflict ('local', 'installed', or null if no conflict). */
  conflictWinner?: 'local' | 'installed' | null;
  /** Publisher identity (if known). */
  publisher?: string;
  /** SPDX license identifier (if known). */
  license?: string;
  /** Short description from the manifest. */
  description?: string;
  /** Icon URL or data URI from the manifest. */
  icon?: string;
  /** When true, this installed pack is trusted local code (not externally sourced). */
  trustedLocalCode?: boolean;
  /** Dependency resolution summary for this extension. */
  dependencies?: DependencySummary;
  /** Degraded contributions caused by dependency issues. */
  degradedContributions?: readonly DegradedContributionInfo[];
  /** Recent lifecycle events for this extension (newest first, max ~10). */
  lifecycleEvents?: readonly LifecycleEventDisplayInfo[];
  /** Settings fields derived from the typed settings schema (null if no schema). */
  settingsFields?: readonly SettingsFieldInfo[] | null;
  /** Migration summary (null if no settings schema is declared). */
  migrationSummary?: MigrationSummaryDisplayInfo | null;
}

export interface ExtensionsSectionProps {
  isMobile: boolean;
  /** Extensions to display. Empty/undefined shows an empty state. */
  extensions?: readonly ExtensionDisplayInfo[];
  /** Whether extension data is still loading. */
  isLoading?: boolean;
  /** Callback when user requests to enable an extension. */
  onEnableExtension?: (extensionId: string) => void | Promise<void>;
  /** Callback when user requests to disable an extension. */
  onDisableExtension?: (extensionId: string) => void | Promise<void>;
  /** Callback when user requests to install a trusted local/test-provided pack. */
  onInstallExtension?: () => void | Promise<void>;
  /** Whether an action (enable/disable/install) is in progress. */
  isPerformingAction?: boolean;
  /** Callback when user requests to use local source for a conflicting extension. */
  onUseLocalSource?: (extensionId: string) => void | Promise<void>;
  /** Callback when user requests to revert to installed for a conflicting extension. */
  onRevertToInstalled?: (extensionId: string) => void | Promise<void>;
  /** Lifecycle events for all extensions (for the aggregate log panel). */
  allLifecycleEvents?: readonly (LifecycleEventDisplayInfo & { extensionId: string; extensionName: string })[];
  /** Callback when user updates a settings value. */
  onUpdateSettings?: (extensionId: string, key: string, value: unknown) => void | Promise<void>;
  /** Callback when user requests to uninstall an extension. */
  onUninstallExtension?: (extensionId: string) => void | Promise<void>;
  /** Reference report for an extension pending uninstall. */
  pendingUninstallReport?: ExtensionReferenceReport | null;
  /** Whether an uninstall operation is in progress. */
  isUninstalling?: boolean;
}
