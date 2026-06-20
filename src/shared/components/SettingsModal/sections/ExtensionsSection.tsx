import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Puzzle,
  AlertTriangle,
  CheckCircle,
  XCircle,
  AlertCircle,
  Package,
  Code2,
  Shield,
  BadgeCheck,
  Download,
  Loader2,
  ArrowUpRight,
  RotateCcw,
  ChevronDown,
  ChevronRight,
  Link2,
  Unlink2,
  History,
  Clock,
  AlertOctagon,
  Settings2,
  Undo2,
  Save,
  ArrowRightLeft,
  Trash2,
  FileWarning,
} from "lucide-react";
import type { ExtensionsSectionProps, ExtensionDisplayInfo, DependencySummary, DegradedContributionInfo, LifecycleEventDisplayInfo, SettingsFieldInfo, MigrationSummaryDisplayInfo } from "../types";
import type { ExtensionReferenceReport, ExtensionReference, ReferenceKind } from "@/tools/video-editor/runtime/extensionReferenceReport";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map status to an icon + colour class. */
function statusBadge(
  status: ExtensionDisplayInfo["status"],
): { icon: React.ReactNode; label: string; className: string } {
  switch (status) {
    case "active":
      return {
        icon: <CheckCircle className="h-3.5 w-3.5" />,
        label: "Active",
        className: "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300",
      };
    case "blocked":
      return {
        icon: <XCircle className="h-3.5 w-3.5" />,
        label: "Blocked",
        className: "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300",
      };
    case "degraded":
      return {
        icon: <AlertCircle className="h-3.5 w-3.5" />,
        label: "Degraded",
        className: "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300",
      };
    case "disabled":
      return {
        icon: <AlertCircle className="h-3.5 w-3.5" />,
        label: "Disabled",
        className: "bg-gray-100 dark:bg-gray-700/50 text-gray-500 dark:text-gray-400",
      };
    case "error":
      return {
        icon: <XCircle className="h-3.5 w-3.5" />,
        label: "Error",
        className: "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300",
      };
  }
}

function sourceBadge(
  source: ExtensionDisplayInfo["source"],
): { icon: React.ReactNode; label: string } {
  switch (source) {
    case "local":
      return { icon: <Code2 className="h-3 w-3" />, label: "Workspace" };
    case "installed":
      return { icon: <Package className="h-3 w-3" />, label: "Installed" };
  }
}

/** Format an ISO timestamp to a short local string. */
function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** Map lifecycle event kind to a compact label. */
function lifecycleEventLabel(kind: string): string {
  const labels: Record<string, string> = {
    install: "Installed",
    uninstall: "Uninstalled",
    enable: "Enabled",
    disable: "Disabled",
    load: "Loaded",
    unload: "Unloaded",
    activation_success: "Activated",
    activation_failure: "Activation failed",
    migration_start: "Migration started",
    migration_success: "Migration OK",
    migration_failure: "Migration failed",
    migration_reset: "Settings reset",
    integrity_pass: "Integrity OK",
    integrity_fail: "Integrity failed",
    dependency_blocked: "Dependency blocked",
    dependency_degraded: "Degraded",
    conflict_override_set: "Override set",
    conflict_override_cleared: "Override cleared",
  };
  return labels[kind] ?? kind;
}

/** Return a colour class for a lifecycle event kind. */
function lifecycleEventColor(kind: string, isFailure: boolean): string {
  if (isFailure) return "text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800/50";
  const successKinds = new Set([
    "install", "enable", "load", "activation_success", "migration_success",
    "integrity_pass", "conflict_override_set",
  ]);
  const warnKinds = new Set([
    "disable", "uninstall", "unload", "migration_start", "migration_reset",
    "dependency_degraded", "conflict_override_cleared",
  ]);
  if (successKinds.has(kind)) return "text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800/50";
  if (warnKinds.has(kind)) return "text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800/50";
  return "text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700/50";
}


// ---------------------------------------------------------------------------
// T22: Settings field editor (inline per-field)
// ---------------------------------------------------------------------------

interface SettingsFieldEditorProps {
  field: SettingsFieldInfo;
  extensionId: string;
  isSaving: boolean;
  onUpdateSettings?: (extensionId: string, key: string, value: unknown) => void | Promise<void>;
}

const SettingsFieldEditor: React.FC<SettingsFieldEditorProps> = ({
  field,
  extensionId,
  isSaving,
  onUpdateSettings,
}) => {
  const [editValue, setEditValue] = useState<string>(() => {
    if (field.type === 'json') {
      return JSON.stringify(field.currentValue, null, 2);
    }
    return String(field.currentValue ?? '');
  });
  const [isDirty, setIsDirty] = useState(false);
  const [hasSaved, setHasSaved] = useState(false);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);

  // Update edit value if currentValue changes externally
  useEffect(() => {
    if (!isDirty) {
      if (field.type === 'json') {
        setEditValue(JSON.stringify(field.currentValue, null, 2));
      } else {
        setEditValue(String(field.currentValue ?? ''));
      }
    }
  }, [field.currentValue, field.type, isDirty]);

  const isResetToDefault = useCallback(() => {
    if (field.defaultValue === undefined) return false;
    return JSON.stringify(field.currentValue) !== JSON.stringify(field.defaultValue);
  }, [field.currentValue, field.defaultValue]);

  const parseValue = (raw: string): unknown => {
    switch (field.type) {
      case 'number': {
        const n = Number(raw);
        return Number.isNaN(n) ? field.currentValue : n;
      }
      case 'boolean':
        return raw === 'true';
      case 'json':
        try {
          return JSON.parse(raw);
        } catch {
          return field.currentValue;
        }
      default:
        return raw;
    }
  };

  const handleSave = async () => {
    if (!onUpdateSettings) return;
    const value = parseValue(editValue);
    setIsDirty(false);
    setHasSaved(true);
    await onUpdateSettings(extensionId, field.key, value);
    setTimeout(() => setHasSaved(false), 1500);
  };

  const handleReset = async () => {
    if (!onUpdateSettings || field.defaultValue === undefined) return;
    setIsDirty(false);
    setEditValue(field.type === 'json'
      ? JSON.stringify(field.defaultValue, null, 2)
      : String(field.defaultValue ?? ''));
    await onUpdateSettings(extensionId, field.key, field.defaultValue);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && field.type !== 'json') {
      e.preventDefault();
      handleSave();
    }
  };

  const handleChange = (val: string) => {
    setEditValue(val);
    setIsDirty(true);
    setHasSaved(false);
  };

  const defaultVal = field.defaultValue;
  const showReset = isResetToDefault() && onUpdateSettings;

  return (
    <div className="flex items-start gap-2 py-1 group">
      {/* Label */}
      <label
        className="text-[10px] font-medium text-muted-foreground w-28 flex-shrink-0 pt-1.5 truncate"
        title={field.description ?? field.key}
      >
        {field.label}
      </label>

      {/* Input */}
      <div className="flex-1 min-w-0">
        {field.type === 'boolean' ? (
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                const newVal = !field.currentValue;
                setEditValue(String(newVal));
                onUpdateSettings?.(extensionId, field.key, newVal);
              }}
              disabled={isSaving}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-primary ${
                field.currentValue
                  ? 'bg-green-500 dark:bg-green-600'
                  : 'bg-gray-300 dark:bg-gray-600'
              } ${isSaving ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <span
                className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                  field.currentValue ? 'translate-x-[18px]' : 'translate-x-[3px]'
                }`}
              />
            </button>
            <span className="text-[10px] text-muted-foreground">
              {field.currentValue ? 'Enabled' : 'Disabled'}
            </span>
          </div>
        ) : field.type === 'json' ? (
          <div className="relative">
            <textarea
              ref={inputRef as React.Ref<HTMLTextAreaElement>}
              value={editValue}
              onChange={(e) => handleChange(e.target.value)}
              disabled={isSaving}
              rows={3}
              className="w-full text-[11px] font-mono bg-background border border-border rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary disabled:opacity-50 resize-y"
              spellCheck={false}
            />
            {isDirty && (
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="absolute top-1 right-1 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium bg-primary/10 text-primary hover:bg-primary/20 transition-colors disabled:opacity-50"
              >
                {isSaving ? (
                  <Loader2 className="h-2.5 w-2.5 animate-spin" />
                ) : (
                  <Save className="h-2.5 w-2.5" />
                )}
                Save
              </button>
            )}
            {hasSaved && (
              <span className="absolute top-1 right-1 text-[9px] text-green-600 dark:text-green-400 font-medium">
                <CheckCircle className="h-2.5 w-2.5 inline mr-0.5" />
                Saved
              </span>
            )}
          </div>
        ) : (
          <div className="relative">
            <input
              ref={inputRef as React.Ref<HTMLInputElement>}
              type={field.type === 'number' ? 'number' : 'text'}
              value={editValue}
              onChange={(e) => handleChange(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isSaving}
              className="w-full text-[11px] font-mono bg-background border border-border rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary disabled:opacity-50"
              spellCheck={false}
            />
            {isDirty && (
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="absolute right-1 top-1/2 -translate-y-1/2 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium bg-primary/10 text-primary hover:bg-primary/20 transition-colors disabled:opacity-50"
              >
                {isSaving ? (
                  <Loader2 className="h-2.5 w-2.5 animate-spin" />
                ) : (
                  <Save className="h-2.5 w-2.5" />
                )}
                Save
              </button>
            )}
            {hasSaved && !isDirty && (
              <span className="absolute right-1 top-1/2 -translate-y-1/2 text-[9px] text-green-600 dark:text-green-400 font-medium">
                <CheckCircle className="h-2.5 w-2.5 inline mr-0.5" />
                Saved
              </span>
            )}
          </div>
        )}
      </div>

      {/* Default value indicator + reset */}
      {defaultVal !== undefined && (
        <div className="flex items-center gap-1 flex-shrink-0 pt-1.5">
          {showReset && (
            <button
              onClick={handleReset}
              disabled={isSaving}
              className="text-[9px] text-muted-foreground hover:text-amber-600 dark:hover:text-amber-400 transition-colors disabled:opacity-50"
              title={`Reset to default: ${JSON.stringify(defaultVal)}`}
            >
              <Undo2 className="h-3 w-3" />
            </button>
          )}
          <span
            className="text-[9px] text-muted-foreground/50 cursor-help"
            title={`Default: ${JSON.stringify(defaultVal)}`}
          >
            default
          </span>
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// T22: Migration summary panel (collapsible)
// ---------------------------------------------------------------------------

interface MigrationSummaryPanelProps {
  migration: MigrationSummaryDisplayInfo;
  extensionName: string;
}

const MigrationSummaryPanel: React.FC<MigrationSummaryPanelProps> = ({ migration }) => {
  const [expanded, setExpanded] = useState(false);

  const statusConfig = (status: MigrationSummaryDisplayInfo['status']) => {
    switch (status) {
      case 'up-to-date':
        return {
          icon: <CheckCircle className="h-3 w-3" />,
          label: 'Schema up-to-date',
          className: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 border-green-200 dark:border-green-800/50',
        };
      case 'migrated':
        return {
          icon: <CheckCircle className="h-3 w-3" />,
          label: 'Migrated',
          className: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 border-green-200 dark:border-green-800/50',
        };
      case 'no-migration':
        return {
          icon: <AlertCircle className="h-3 w-3" />,
          label: 'No migration needed',
          className: 'bg-gray-100 dark:bg-gray-700/50 text-gray-500 dark:text-gray-400 border-gray-200 dark:border-gray-700/50',
        };
      case 'migration-failed':
        return {
          icon: <XCircle className="h-3 w-3" />,
          label: 'Migration failed',
          className: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800/50',
        };
      case 'migration-reset':
        return {
          icon: <AlertTriangle className="h-3 w-3" />,
          label: 'Settings reset to defaults',
          className: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800/50',
        };
    }
  };

  const status = statusConfig(migration.status);

  return (
    <div className="mt-2 pt-2 border-t border-border/30">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-[10px] font-medium text-muted-foreground hover:text-foreground transition-colors w-full text-left"
      >
        <ArrowRightLeft className="h-3 w-3 flex-shrink-0" />
        <span>Settings Migration</span>
        <span
          className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[9px] font-medium ml-auto border ${status.className}`}
        >
          {status.icon}
          {status.label}
        </span>
        {expanded ? (
          <ChevronDown className="h-3 w-3 flex-shrink-0" />
        ) : (
          <ChevronRight className="h-3 w-3 flex-shrink-0" />
        )}
      </button>

      {expanded && (
        <div className="mt-1.5 space-y-1.5 bg-muted/20 rounded p-2">
          {/* Version transition */}
          <div className="flex items-center gap-2 text-[10px]">
            <span className="px-1.5 py-0.5 rounded bg-muted font-mono text-[10px]">
              v{migration.oldSchemaVersion}
            </span>
            <ArrowRightLeft className="h-3 w-3 text-muted-foreground/50" />
            <span className="px-1.5 py-0.5 rounded bg-muted font-mono text-[10px]">
              v{migration.newSchemaVersion}
            </span>
            <span className="text-muted-foreground ml-auto">
              {migration.migrationTimestamp
                ? formatTimestamp(migration.migrationTimestamp)
                : '—'}
            </span>
          </div>

          {/* Message */}
          {migration.message && (
            <p className="text-[10px] text-muted-foreground">{migration.message}</p>
          )}

          {/* Reset indicator */}
          {migration.resetToDefaults && (
            <div className="flex items-center gap-1 text-[10px] text-amber-600 dark:text-amber-400">
              <AlertTriangle className="h-3 w-3" />
              Settings were reset to manifest defaults because no migration path was available.
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Settings editor panel (collapsible, per-extension)
// ---------------------------------------------------------------------------

interface SettingsEditorPanelProps {
  fields: readonly SettingsFieldInfo[];
  extensionId: string;
  extensionName: string;
  isSaving?: boolean;
  onUpdateSettings?: (extensionId: string, key: string, value: unknown) => void | Promise<void>;
}

const SettingsEditorPanel: React.FC<SettingsEditorPanelProps> = ({
  fields,
  extensionId,
  extensionName,
  isSaving = false,
  onUpdateSettings,
}) => {
  const [expanded, setExpanded] = useState(false);

  if (!fields || fields.length === 0) return null;

  return (
    <div className="mt-2 pt-2 border-t border-border/30">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-[10px] font-medium text-muted-foreground hover:text-foreground transition-colors w-full text-left"
      >
        <Settings2 className="h-3 w-3 flex-shrink-0" />
        <span>{`Settings (${fields.length} field${fields.length > 1 ? 's' : ''})`}</span>
        {expanded ? (
          <ChevronDown className="h-3 w-3 ml-auto" />
        ) : (
          <ChevronRight className="h-3 w-3 ml-auto" />
        )}
      </button>

      {expanded && (
        <div className="mt-1.5 space-y-0.5 bg-muted/20 rounded p-2 max-h-64 overflow-y-auto">
          {fields.map((field) => (
            <SettingsFieldEditor
              key={field.key}
              field={field}
              extensionId={extensionId}
              isSaving={isSaving}
              onUpdateSettings={onUpdateSettings}
            />
          ))}
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Dependency badge (compact pill)
// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// Dependency badge (compact pill)
// ---------------------------------------------------------------------------

const DependencyBadge: React.FC<{ deps: DependencySummary }> = ({ deps }) => {
  const hasIssues = deps.missingRequiredCount > 0 || deps.versionMismatchCount > 0 || deps.inCycle;
  const isDegraded = deps.degraded && !hasIssues;

  let colorClass = "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 border-green-200 dark:border-green-800/50";
  let icon = <Link2 className="h-3 w-3" />;

  if (hasIssues || deps.inCycle) {
    colorClass = "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800/50";
    icon = <Unlink2 className="h-3 w-3" />;
  } else if (isDegraded) {
    colorClass = "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800/50";
    icon = <AlertCircle className="h-3 w-3" />;
  }

  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium border ${colorClass}`}
      title={`${deps.totalCount} deps: ${deps.satisfiedCount} satisfied, ${deps.missingRequiredCount} missing required, ${deps.missingOptionalCount} missing optional, ${deps.versionMismatchCount} version mismatch${deps.degraded ? ', degraded' : ''}${deps.inCycle ? ', cycle' : ''}`}
    >
      {icon}
      {`${deps.totalCount}d`}
      {hasIssues && ` ✗${deps.missingRequiredCount + deps.versionMismatchCount + (deps.inCycle ? 1 : 0)}`}
      {isDegraded && !hasIssues && ` ⚠`}
    </span>
  );
};

// ---------------------------------------------------------------------------
// Compact lifecycle event log (collapsible)
// ---------------------------------------------------------------------------

interface LifecycleLogProps {
  events: readonly LifecycleEventDisplayInfo[];
  extensionName: string;
}

const LifecycleLog: React.FC<LifecycleLogProps> = ({ events, extensionName }) => {
  const [expanded, setExpanded] = useState(false);

  if (!events || events.length === 0) return null;

  const displayEvents = expanded ? events : events.slice(0, 3);
  const hiddenCount = events.length - displayEvents.length;

  return (
    <div className="mt-2 pt-2 border-t border-border/30">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-[10px] font-medium text-muted-foreground hover:text-foreground transition-colors w-full text-left"
      >
        <History className="h-3 w-3 flex-shrink-0" />
        <span>{`Lifecycle Events (${events.length})`}</span>
        {expanded ? (
          <ChevronDown className="h-3 w-3 ml-auto" />
        ) : (
          <ChevronRight className="h-3 w-3 ml-auto" />
        )}
      </button>

      {expanded && (
        <div className="mt-1.5 space-y-1 max-h-48 overflow-y-auto">
          {displayEvents.map((event, idx) => (
            <div
              key={`${event.kind}-${event.timestamp}-${idx}`}
              className={`flex items-start gap-1.5 text-[10px] rounded px-1.5 py-0.5 border ${lifecycleEventColor(event.kind, event.isFailure)}`}
            >
              <Clock className="h-2.5 w-2.5 mt-0.5 flex-shrink-0" />
              <div className="min-w-0 flex-1">
                <span className="font-medium">{lifecycleEventLabel(event.kind)}</span>
                <span className="text-muted-foreground ml-1">
                  {formatTimestamp(event.timestamp)}
                </span>
                {event.message && (
                  <span className="block text-[9px] opacity-70 truncate" title={event.message}>
                    {event.message}
                  </span>
                )}
              </div>
            </div>
          ))}
          {hiddenCount > 0 && !expanded && (
            <div className="text-[10px] text-muted-foreground text-center">
              +{hiddenCount} more
            </div>
          )}
        </div>
      )}

      {!expanded && (
        <div className="mt-1 space-y-0.5">
          {displayEvents.map((event, idx) => (
            <div
              key={`collapsed-${event.kind}-${event.timestamp}-${idx}`}
              className="flex items-center gap-1 text-[9px] text-muted-foreground truncate"
            >
              <span className={`inline-block w-1 h-1 rounded-full flex-shrink-0 ${
                event.isFailure ? "bg-red-500" :
                event.kind.includes("fail") || event.kind.includes("blocked") ? "bg-red-400" :
                event.kind.includes("success") || event.kind === "install" || event.kind === "enable" || event.kind === "activation_success" ? "bg-green-500" :
                "bg-amber-400"
              }`} />
              <span className="font-medium">{lifecycleEventLabel(event.kind)}</span>
              <span className="opacity-50">{formatTimestamp(event.timestamp)}</span>
            </div>
          ))}
          {hiddenCount > 0 && (
            <div className="text-[9px] text-muted-foreground pl-3">
              +{hiddenCount} more events
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Degraded contribution inventory (collapsible)
// ---------------------------------------------------------------------------

interface DegradedInventoryProps {
  contributions: readonly DegradedContributionInfo[];
  extensionName: string;
}

const DegradedInventory: React.FC<DegradedInventoryProps> = ({ contributions }) => {
  const [expanded, setExpanded] = useState(false);

  if (!contributions || contributions.length === 0) return null;

  return (
    <div className="mt-1.5 pt-1.5 border-t border-border/20">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-[10px] font-medium text-amber-600 dark:text-amber-400 hover:text-amber-700 dark:hover:text-amber-300 transition-colors w-full text-left"
      >
        <AlertOctagon className="h-3 w-3 flex-shrink-0" />
        <span>{`${contributions.length} degraded contribution${contributions.length > 1 ? "s" : ""}`}</span>
        {expanded ? (
          <ChevronDown className="h-3 w-3 ml-auto" />
        ) : (
          <ChevronRight className="h-3 w-3 ml-auto" />
        )}
      </button>

      {expanded && (
        <div className="mt-1 space-y-0.5">
          {contributions.map((c, idx) => (
            <div
              key={`${c.contributionId}-${idx}`}
              className="flex items-start gap-1.5 text-[10px] rounded px-1.5 py-0.5 bg-amber-50 dark:bg-amber-900/10 border border-amber-200/50 dark:border-amber-800/30 text-amber-700 dark:text-amber-300"
            >
              <AlertCircle className="h-2.5 w-2.5 mt-0.5 flex-shrink-0" />
              <div className="min-w-0 flex-1">
                <span className="font-mono font-medium">{c.contributionId}</span>
                <span className="text-amber-600/70 dark:text-amber-400/70 ml-1">
                  via {c.dependencyId}
                </span>
                <span className="block text-[9px] opacity-70">{c.reason}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Aggregate lifecycle event log (section-level, collapsible)
// ---------------------------------------------------------------------------

interface AggregateLifecycleLogProps {
  events: readonly (LifecycleEventDisplayInfo & { extensionId: string; extensionName: string })[];
}

const AggregateLifecycleLog: React.FC<AggregateLifecycleLogProps> = ({ events }) => {
  const [expanded, setExpanded] = useState(false);

  if (!events || events.length === 0) return null;

  const displayEvents = expanded ? events : events.slice(0, 5);
  const hiddenCount = events.length - displayEvents.length;
  const failureCount = events.filter((e) => e.isFailure).length;

  return (
    <div className="border border-border/40 rounded-lg p-3 space-y-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors w-full text-left"
      >
        <History className="h-3.5 w-3.5 flex-shrink-0" />
        <span>{`Event Log (${events.length} events${failureCount > 0 ? `, ${failureCount} failure${failureCount > 1 ? 's' : ''}` : ''})`}</span>
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 ml-auto" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 ml-auto" />
        )}
      </button>

      {expanded && (
        <div className="space-y-1 max-h-64 overflow-y-auto">
          {displayEvents.map((event, idx) => (
            <div
              key={`agg-${event.extensionId}-${event.kind}-${event.timestamp}-${idx}`}
              className={`flex items-start gap-1.5 text-[10px] rounded px-1.5 py-0.5 border ${lifecycleEventColor(event.kind, event.isFailure)}`}
            >
              <Clock className="h-2.5 w-2.5 mt-0.5 flex-shrink-0" />
              <div className="min-w-0 flex-1">
                <span className="font-medium">{event.extensionName}</span>
                <span className="ml-1">{lifecycleEventLabel(event.kind)}</span>
                <span className="text-muted-foreground ml-1">
                  {formatTimestamp(event.timestamp)}
                </span>
                {event.message && (
                  <span className="block text-[9px] opacity-70 truncate" title={event.message}>
                    {event.message}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {!expanded && (
        <div className="space-y-0.5">
          {displayEvents.map((event, idx) => (
            <div
              key={`agg-collapsed-${event.extensionId}-${event.kind}-${event.timestamp}-${idx}`}
              className="flex items-center gap-1 text-[9px] text-muted-foreground truncate"
            >
              <span className={`inline-block w-1 h-1 rounded-full flex-shrink-0 ${
                event.isFailure ? "bg-red-500" :
                event.kind.includes("fail") || event.kind.includes("blocked") ? "bg-red-400" :
                event.kind.includes("success") || event.kind === "install" || event.kind === "enable" || event.kind === "activation_success" ? "bg-green-500" :
                "bg-amber-400"
              }`} />
              <span className="font-medium">{event.extensionName}</span>
              <span>{lifecycleEventLabel(event.kind)}</span>
              <span className="opacity-50">{formatTimestamp(event.timestamp)}</span>
            </div>
          ))}
          {hiddenCount > 0 && (
            <div className="text-[9px] text-muted-foreground pl-3">
              +{hiddenCount} more events
            </div>
          )}
        </div>
      )}
    </div>
  );
};


// ---------------------------------------------------------------------------
// T23: Reference kind label helper
// ---------------------------------------------------------------------------

/** Map reference kind to a human-readable label. */
function referenceKindLabel(kind: ReferenceKind): string {
  const labels: Record<ReferenceKind, string> = {
    'contribution': 'Contribution',
    'effect': 'Effect',
    'transition': 'Transition',
    'shader': 'Shader',
    'clip-type': 'Clip Type',
    'agent-tool': 'Agent Tool',
    'live-data-source': 'Live Data Source',
    'settings': 'Settings',
    'lock-entry': 'Lock Entry',
    'other': 'Other',
  };
  return labels[kind] ?? kind;
}

// ---------------------------------------------------------------------------
// T23: Uninstall reference report panel (collapsible, per-extension)
// ---------------------------------------------------------------------------

interface UninstallReferenceReportPanelProps {
  report: ExtensionReferenceReport;
  extensionName: string;
  isUninstalling?: boolean;
  onConfirmUninstall?: (extensionId: string) => void | Promise<void>;
  onCancel?: () => void;
}

const UninstallReferenceReportPanel: React.FC<UninstallReferenceReportPanelProps> = ({
  report,
  extensionName,
  isUninstalling = false,
  onConfirmUninstall,
  onCancel,
}) => {
  const [expandedRefs, setExpandedRefs] = useState<Set<string>>(new Set());
  const [showConfirm, setShowConfirm] = useState(false);

  const toggleKind = (kind: string) => {
    setExpandedRefs((prev) => {
      const next = new Set(prev);
      if (next.has(kind)) next.delete(kind);
      else next.add(kind);
      return next;
    });
  };

  const kindEntries = Object.entries(report.referencesByKind).filter(
    ([, refs]) => refs.length > 0,
  ) as [ReferenceKind, readonly ExtensionReference[]][];

  if (!report.hasReferences) {
    return (
      <div className="mt-3 p-3 border border-border/40 rounded-lg bg-muted/10 space-y-2">
        <div className="flex items-center gap-2">
          <CheckCircle className="h-4 w-4 text-green-500" />
          <span className="text-sm font-medium text-green-700 dark:text-green-300">
            No project references found
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          Extension "{extensionName}" can be safely uninstalled. No project references
          will be orphaned.
        </p>
        <div className="flex items-center gap-2 pt-1">
          {!showConfirm ? (
            <button
              onClick={() => setShowConfirm(true)}
              disabled={isUninstalling}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-red-600 hover:bg-red-700 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isUninstalling ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Trash2 className="h-3.5 w-3.5" />
              )}
              Uninstall Extension
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={() => onConfirmUninstall?.(report.extensionId)}
                disabled={isUninstalling}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-red-600 hover:bg-red-700 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isUninstalling ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Trash2 className="h-3.5 w-3.5" />
                )}
                Confirm Uninstall
              </button>
              <button
                onClick={() => {
                  setShowConfirm(false);
                  onCancel?.();
                }}
                disabled={isUninstalling}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium border border-border bg-background hover:bg-muted text-foreground transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="mt-3 p-3 border border-red-200 dark:border-red-800/50 rounded-lg bg-red-50/30 dark:bg-red-900/10 space-y-2">
      {/* Warning header */}
      <div className="flex items-start gap-2">
        <FileWarning className="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
        <div>
          <span className="text-sm font-medium text-red-700 dark:text-red-300">
            {report.totalReferenceCount} project reference{report.totalReferenceCount > 1 ? 's' : ''} found
          </span>
          <p className="text-xs text-red-600/80 dark:text-red-400/80 mt-0.5">
            Uninstalling "{extensionName}" will orphan these references.
            Timeline data will be preserved — orphaned references become diagnostics
            until manually resolved.
          </p>
        </div>
      </div>

      {/* Reference breakdown by kind */}
      <div className="space-y-1">
        {kindEntries.map(([kind, refs]) => (
          <div key={kind}>
            <button
              onClick={() => toggleKind(kind)}
              className="flex items-center gap-1.5 text-[10px] font-medium text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 transition-colors w-full text-left"
            >
              {expandedRefs.has(kind) ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
              <span>{referenceKindLabel(kind)}</span>
              <span className="text-red-400/80 dark:text-red-500/80">
                ({refs.length})
              </span>
            </button>
            {expandedRefs.has(kind) && (
              <div className="mt-0.5 ml-4 space-y-0.5">
                {refs.slice(0, 20).map((ref, idx) => (
                  <div
                    key={`${ref.referenceId}-${idx}`}
                    className="text-[9px] text-muted-foreground truncate pl-2 border-l-2 border-red-200 dark:border-red-800/30"
                    title={ref.label}
                  >
                    <span className="font-mono">{ref.referenceId}</span>
                    <span className="opacity-50 ml-1">in {ref.location}</span>
                  </div>
                ))}
                {refs.length > 20 && (
                  <div className="text-[9px] text-muted-foreground pl-2">
                    +{refs.length - 20} more
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {!report.scanIsComplete && (
        <div className="flex items-center gap-1 text-[10px] text-amber-600 dark:text-amber-400">
          <AlertCircle className="h-3 w-3" />
          Reference scan is incomplete — additional references may exist.
        </div>
      )}

      <div className="flex items-center gap-2 pt-1">
        {!showConfirm ? (
          <button
            onClick={() => setShowConfirm(true)}
            disabled={isUninstalling}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-red-600 hover:bg-red-700 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isUninstalling ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Trash2 className="h-3.5 w-3.5" />
            )}
            Uninstall Anyway
          </button>
        ) : (
          <div className="flex items-center gap-2">
            <button
              onClick={() => onConfirmUninstall?.(report.extensionId)}
              disabled={isUninstalling}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-red-600 hover:bg-red-700 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isUninstalling ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Trash2 className="h-3.5 w-3.5" />
              )}
              Confirm — Orphan References
            </button>
            <button
              onClick={() => {
                setShowConfirm(false);
                onCancel?.();
              }}
              disabled={isUninstalling}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium border border-border bg-background hover:bg-muted text-foreground transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Extension row
// ---------------------------------------------------------------------------

interface ExtensionRowProps {
  ext: ExtensionDisplayInfo;
  isMobile: boolean;
  onToggleEnable?: (extensionId: string, enabled: boolean) => void | Promise<void>;
  isPerformingAction?: boolean;
  onUseLocalSource?: (extensionId: string) => void | Promise<void>;
  onRevertToInstalled?: (extensionId: string) => void | Promise<void>;
  onUpdateSettings?: (extensionId: string, key: string, value: unknown) => void | Promise<void>;
  isSavingSettings?: boolean;
  onUninstallExtension?: (extensionId: string) => void | Promise<void>;
  pendingUninstallReport?: ExtensionReferenceReport | null;
  isUninstalling?: boolean;
}

const ExtensionRow: React.FC<ExtensionRowProps> = ({ ext, isMobile, onToggleEnable, isPerformingAction, onUseLocalSource, onRevertToInstalled, onUpdateSettings, isSavingSettings, onUninstallExtension, pendingUninstallReport, isUninstalling }) => {
  const status = statusBadge(ext.status);
  const source = sourceBadge(ext.source);

  return (
    <div
      className={`${
        isMobile ? "p-3 space-y-2" : "p-4"
      } bg-muted/30 rounded-lg space-y-2 border border-transparent hover:border-border/40 transition-colors`}
    >
      {/* Header: name, version, status */}
      <div
        className={`flex ${
          isMobile ? "flex-col gap-2" : "items-center justify-between gap-4"
        }`}
      >
        {/* Left side: icon + name + version */}
        <div className="flex items-center gap-2 min-w-0">
          <Puzzle className="h-4 w-4 text-muted-foreground flex-shrink-0" />
          <span className="font-medium truncate">{ext.name}</span>
          <span className="text-xs text-muted-foreground flex-shrink-0">
            v{ext.version}
          </span>
          {/* Dependency badge (T21) */}
          {ext.dependencies && ext.dependencies.totalCount > 0 && (
            <DependencyBadge deps={ext.dependencies} />
          )}
          {ext.trustWarning && (
            <Shield
              className="h-3.5 w-3.5 text-amber-500 flex-shrink-0"
              title={
                ext.trustWarningReason ?? "Publisher or license information is missing"
              }
            />
          )}
        </div>

        {/* Right side: source + status badges */}
        <div
          className={`flex items-center gap-2 ${
            isMobile ? "flex-wrap" : "flex-shrink-0"
          }`}
        >
          {/* Source badge */}
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
            {source.icon}
            {source.label}
          </span>

          {/* Trusted Local Code badge */}
          {ext.trustedLocalCode && ext.source === 'installed' && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300">
              <BadgeCheck className="h-3 w-3" />
              Trusted Local Code
            </span>
          )}

          {/* Status badge */}
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${status.className}`}
          >
            {status.icon}
            {status.label}
          </span>
        </div>
      </div>

      {/* Details row */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {/* Extension ID */}
        <span className="font-mono text-[10px] opacity-60">{ext.extensionId}</span>

        {/* Publisher */}
        {ext.publisher && <span>Publisher: {ext.publisher}</span>}
        {!ext.publisher && ext.source === "installed" && (
          <span className="text-amber-600 dark:text-amber-400 flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" />
            Unverified publisher
          </span>
        )}

        {/* License */}
        {ext.license && <span>License: {ext.license}</span>}
        {!ext.license && ext.source === "installed" && (
          <span className="text-amber-600 dark:text-amber-400 flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" />
            No license
          </span>
        )}

        {/* Diagnostics count */}
        {ext.diagnosticsCount > 0 && (
          <span className="text-amber-600 dark:text-amber-400 flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" />
            {ext.diagnosticsCount} diagnostic{ext.diagnosticsCount > 1 ? "s" : ""}
          </span>
        )}

        {/* Conflict state */}
        {ext.hasConflict && (
          <span className="text-purple-600 dark:text-purple-400 flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            Conflict: {ext.conflictStrategy ?? "unknown"}
          </span>
        )}
      </div>

      {/* Enabled state toggle (read-only) */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>Enabled:</span>
        <span
          className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium ${
            ext.enabled
              ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300"
              : "bg-gray-100 dark:bg-gray-700/50 text-gray-500 dark:text-gray-400"
          }`}
        >
          {ext.enabled ? (
            <CheckCircle className="h-3 w-3" />
          ) : (
            <XCircle className="h-3 w-3" />
          )}
          {ext.enabled ? "Yes" : "No"}
        </span>
      </div>

      {/* Degraded contribution inventory (T21) */}
      <DegradedInventory
        contributions={ext.degradedContributions ?? []}
        extensionName={ext.name}
      />

      {/* Lifecycle event log (T21) */}
      <LifecycleLog
        events={ext.lifecycleEvents ?? []}
        extensionName={ext.name}
      />

      {/* Settings editor panel (T22) */}
      {ext.settingsFields && ext.settingsFields.length > 0 && (
        <SettingsEditorPanel
          fields={ext.settingsFields}
          extensionId={ext.extensionId}
          extensionName={ext.name}
          isSaving={isSavingSettings}
          onUpdateSettings={onUpdateSettings}
        />
      )}

      {/* Migration summary panel (T22) */}
      {ext.migrationSummary && (
        <MigrationSummaryPanel
          migration={ext.migrationSummary}
          extensionName={ext.name}
        />
      )}

      {/* Action buttons */}
      {onToggleEnable && (
        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleEnable(ext.extensionId, !ext.enabled);
            }}
            disabled={isPerformingAction}
            className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors border ${
              ext.enabled
                ? "border-red-200 dark:border-red-800/50 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/40"
                : "border-green-200 dark:border-green-800/50 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 hover:bg-green-100 dark:hover:bg-green-900/40"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {isPerformingAction ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : ext.enabled ? (
              <XCircle className="h-3 w-3" />
            ) : (
              <CheckCircle className="h-3 w-3" />
            )}
            {ext.enabled ? "Disable" : "Enable"}
          </button>
        </div>
      )}
      {/* Conflict override actions */}
      {ext.hasConflict && (
        <div className="flex items-center gap-2 pt-1">
          {ext.conflictWinner !== "local" && onUseLocalSource && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onUseLocalSource(ext.extensionId);
              }}
              disabled={isPerformingAction}
              className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors border border-purple-200 dark:border-purple-800/50 bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-300 hover:bg-purple-100 dark:hover:bg-purple-900/40 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isPerformingAction ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <ArrowUpRight className="h-3 w-3" />
              )}
              Use Local Source
            </button>
          )}
          {ext.conflictWinner === "local" && onRevertToInstalled && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onRevertToInstalled(ext.extensionId);
              }}
              disabled={isPerformingAction}
              className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors border border-blue-200 dark:border-blue-800/50 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/40 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isPerformingAction ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <RotateCcw className="h-3 w-3" />
              )}
              Revert to Installed
            </button>
          )}
        </div>
      )}

      {/* Uninstall button (only for installed extensions) */}
      {ext.source === 'installed' && onUninstallExtension && (
        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onUninstallExtension(ext.extensionId);
            }}
            disabled={isPerformingAction || isUninstalling}
            className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors border border-red-200 dark:border-red-800/50 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/40 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isUninstalling ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Trash2 className="h-3 w-3" />
            )}
            Uninstall
          </button>
        </div>
      )}

      {/* Pending uninstall reference report */}
      {pendingUninstallReport && pendingUninstallReport.extensionId === ext.extensionId && (
        <UninstallReferenceReportPanel
          report={pendingUninstallReport}
          extensionName={ext.name}
          isUninstalling={isUninstalling}
          onConfirmUninstall={onUninstallExtension}
          onCancel={() => {
            // Cancel uninstall - call with empty to indicate cancel
            onUninstallExtension?.('');
          }}
        />
      )}

      {/* Description */}
      {ext.description && (
        <p className="text-xs text-muted-foreground line-clamp-2">
          {ext.description}
        </p>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Section
// ---------------------------------------------------------------------------

const ExtensionsSection: React.FC<ExtensionsSectionProps> = ({
  isMobile,
  extensions,
  isLoading = false,
  onEnableExtension,
  onDisableExtension,
  onInstallExtension,
  isPerformingAction = false,
  onUseLocalSource,
  onRevertToInstalled,
  allLifecycleEvents,
  onUpdateSettings,
  isSavingSettings = false,
  onUninstallExtension,
  pendingUninstallReport,
  isUninstalling = false,
}) => {
  const list = extensions ?? [];

  // Build a combined toggle handler from enable/disable callbacks
  const onToggleEnableForSection =
    onEnableExtension || onDisableExtension
      ? async (extensionId: string, enabled: boolean) => {
          if (enabled && onEnableExtension) {
            await onEnableExtension(extensionId);
          } else if (!enabled && onDisableExtension) {
            await onDisableExtension(extensionId);
          }
        }
      : undefined;

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-medium text-muted-foreground mb-3">
          Extensions
        </h3>

        {isLoading ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div
                key={i}
                className={`${
                  isMobile ? "p-3" : "p-4"
                } bg-muted/30 rounded-lg space-y-2 animate-pulse`}
              >
                <div className="flex items-center gap-2">
                  <div className="h-4 w-4 bg-muted rounded" />
                  <div className="h-4 w-32 bg-muted rounded" />
                  <div className="h-3 w-16 bg-muted rounded" />
                </div>
                <div className="h-3 w-48 bg-muted rounded" />
              </div>
            ))}
          </div>
        ) : list.length === 0 ? (
          <div
            className={`${
              isMobile ? "p-6" : "p-8"
            } bg-muted/20 rounded-lg text-center space-y-2`}
          >
            <Puzzle className="h-8 w-8 text-muted-foreground/40 mx-auto" />
            <p className="text-sm text-muted-foreground">
              No extensions configured
            </p>
            <p className="text-xs text-muted-foreground/60 max-w-xs mx-auto">
              Extensions from the video editor workspace and installed packs will
              appear here. Enable the video editor with extensions to see their
              status and diagnostics.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {/* Summary bar */}
            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground px-1">
              <span>
                {list.length} extension{list.length > 1 ? "s" : ""}
              </span>
              {list.some((e) => e.source === "local") && (
                <span className="flex items-center gap-1">
                  <Code2 className="h-3 w-3" />
                  {list.filter((e) => e.source === "local").length} workspace
                </span>
              )}
              {list.some((e) => e.source === "installed") && (
                <span className="flex items-center gap-1">
                  <Package className="h-3 w-3" />
                  {list.filter((e) => e.source === "installed").length} installed
                </span>
              )}
              {list.some((e) => !e.enabled) && (
                <span className="flex items-center gap-1 text-gray-500">
                  <XCircle className="h-3 w-3" />
                  {list.filter((e) => !e.enabled).length} disabled
                </span>
              )}
              {list.some((e) => e.trustWarning) && (
                <span className="flex items-center gap-1 text-amber-500">
                  <Shield className="h-3 w-3" />
                  {list.filter((e) => e.trustWarning).length} untrusted
                </span>
              )}
              {list.some((e) => e.dependencies?.degraded) && (
                <span className="flex items-center gap-1 text-amber-500">
                  <AlertCircle className="h-3 w-3" />
                  {list.filter((e) => e.dependencies?.degraded).length} degraded
                </span>
              )}
              {list.some((e) => e.dependencies?.inCycle || (e.dependencies && e.dependencies.missingRequiredCount > 0)) && (
                <span className="flex items-center gap-1 text-red-500">
                  <XCircle className="h-3 w-3" />
                  {list.filter((e) => e.dependencies?.inCycle || (e.dependencies && e.dependencies.missingRequiredCount > 0)).length} blocked
                </span>
              )}
            </div>

            {/* Extension rows */}
            {list.map((ext) => (
              <ExtensionRow
                key={ext.extensionId}
                ext={ext}
                isMobile={isMobile}
                onToggleEnable={onToggleEnableForSection}
                isPerformingAction={isPerformingAction}
                onUseLocalSource={onUseLocalSource}
                onRevertToInstalled={onRevertToInstalled}
                onUpdateSettings={onUpdateSettings}
                isSavingSettings={isSavingSettings}
                onUninstallExtension={onUninstallExtension}
                pendingUninstallReport={pendingUninstallReport}
                isUninstalling={isUninstalling}
              />
            ))}
          </div>
        )}
      </div>

      {/* Aggregate lifecycle event log (T21) */}
      <AggregateLifecycleLog events={allLifecycleEvents ?? []} />

      {/* Install trusted local pack */}
      {onInstallExtension && (
        <div className="border border-dashed border-emerald-300 dark:border-emerald-700 rounded-lg p-4 space-y-3">
          <div className="flex items-center gap-2">
            <BadgeCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
            <span className="text-sm font-medium text-emerald-700 dark:text-emerald-300">
              Trusted Local Pack Installation
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            Install a trusted local/test-provided extension pack. These packs
            are sourced from the local development environment and are labeled
            as trusted local code.
          </p>
          <button
            onClick={onInstallExtension}
            disabled={isPerformingAction}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium bg-emerald-600 hover:bg-emerald-700 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isPerformingAction ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Download className="h-3.5 w-3.5" />
            )}
            Install Trusted Local Pack
          </button>
        </div>
      )}

      {/* Trust / security note */}
      {list.length > 0 && (
        <div className="text-xs text-muted-foreground bg-muted/20 rounded-lg p-3 space-y-1">
          <p className="flex items-center gap-1 font-medium text-muted-foreground">
            <Shield className="h-3.5 w-3.5" />
            Trust &amp; Security
          </p>
          <p>
            Installed extensions marked with{" "}
            <Shield className="h-3 w-3 inline text-amber-500" /> are missing
            publisher or license information. Exercise caution when enabling
            untrusted extensions. Extensions labeled{" "}
            <BadgeCheck className="h-3 w-3 inline text-emerald-500" /> Trusted
            Local Code come from the local development environment.
          </p>
        </div>
      )}
    </div>
  );
};

export { ExtensionsSection };
