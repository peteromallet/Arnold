/**
 * ExtensionStatusDrawer — Read-only extension status inventory and drawer UI.
 *
 * Derives a read-only inventory from `extensionRuntime.extensions`, normalized
 * contribution registries, inactive/disabled/failed entries, provider-scoped
 * diagnostics, and export/render blocker diagnostics.
 *
 * Excludes install/uninstall/enable/disable/settings controls — this is a
 * pure observation surface.
 *
 * Accessibility:
 * - `role="dialog"` with `aria-label="Extension status"`
 * - `aria-live="polite"` on the summary for screen-reader updates
 * - Interactive elements have accessible labels
 * - Focus is trapped in the drawer when open (via autoFocus on close button)
 */

import {
  useCallback,
  useMemo,
  useState,
  useSyncExternalStore,
} from 'react';
import {
  X,
  ChevronDown,
  ChevronRight,
  Puzzle,
  AlertCircle,
  AlertTriangle,
  Info,
  Zap,
  ShieldX,
} from 'lucide-react';
import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext';
import type {
  Diagnostic,
  ContributionKind,
} from '@reigh/editor-sdk';
import {
  BlockerActionCard,
  normalizeBlockerActionCardNextAction,
} from '@/tools/video-editor/components/BlockerActionCard.tsx';
import type {
  InactiveReservedContribution,
  PackageStateInventoryEntry,
} from '@/tools/video-editor/runtime/extensionSurface';
import type { CommandRegistry, CommandRegistrySnapshot } from '@/tools/video-editor/runtime/commandRegistry';
import { useEffectRegistrySnapshot } from '@/tools/video-editor/effects/registry/EffectRegistryContext';

// ---------------------------------------------------------------------------
// Inventory types
// ---------------------------------------------------------------------------

/** Per-contribution status in the read-only inventory. */
export type ContributionInventoryStatus =
  | 'active'      // Bridged, actively participating in the runtime
  | 'inactive'    // Kind not yet bridged in this milestone
  | 'failed';     // Has a render/contribution-error diagnostic

/** A single contribution entry in the inventory. */
export interface ContributionInventoryEntry {
  readonly contributionId: string;
  readonly kind: ContributionKind;
  readonly label?: string;
  readonly status: ContributionInventoryStatus;
  /** Milestone that activates this kind (only populated when inactive). */
  readonly milestone?: string;
  /** Slot name (only for slot contributions). */
  readonly slot?: string;
  /** Diagnostics scoped to this contribution. */
  readonly diagnostics: readonly Diagnostic[];
}

/** A single extension entry in the inventory. */
export interface ExtensionInventoryEntry {
  readonly extensionId: string;
  readonly label: string;
  readonly version: string;
  readonly description?: string;
  readonly contributions: readonly ContributionInventoryEntry[];
  readonly diagnostics: readonly Diagnostic[];
  readonly hasErrors: boolean;
  readonly hasWarnings: boolean;
}

/** M7: Per-effect blocker detail surfaced in the drawer. */
export interface EffectBlockerDetail {
  readonly effectId: string;
  readonly provenance: string;
  readonly status: string;
  /** Route names that are blocked for this effect. */
  readonly blockedRoutes: readonly string[];
  /** Route names that have unknown support. */
  readonly unknownRoutes: readonly string[];
  /** Owner extension that registered the effect. */
  readonly ownerExtensionId?: string;
}

/** Summary counts for the inventory. */
export interface ExtensionStatusSummary {
  readonly totalExtensions: number;
  readonly activeExtensions: number;
  readonly failedExtensions: number;
  readonly inactiveExtensions: number;
  readonly totalContributions: number;
  readonly activeContributions: number;
  readonly inactiveContributions: number;
  readonly errorDiagnostics: number;
  readonly warningDiagnostics: number;
  readonly infoDiagnostics: number;
  readonly exportBlockers: number;
  /** M5: Planner-compatible blocker diagnostics published by renderPlanner. */
  readonly plannerBlockers: number;
  readonly renderBlockers: number;
  /** M4: Total commands registered in the command registry. */
  readonly commandCount: number;
  /** M4: Total keybindings registered. */
  readonly keybindingCount: number;
  /** M4: Total context menu items registered. */
  readonly contextMenuCount: number;
  /** M4: Commands whose most recent invocation threw or rejected. */
  readonly commandsFailedLastRun: number;
  /** M5: Effect records currently loaded in the provider-scoped registry. */
  readonly effectRecordCount: number;
  /** M5: Effect records that block browser export. */
  readonly effectBrowserExportBlockers: number;
  /** M5: Supported renderability capability declarations across effect records. */
  readonly effectSupportedRoutes: number;
  /** M5: Blocked renderability capability declarations across effect records. */
  readonly effectBlockedRoutes: number;
  /** M5: Unknown renderability capability declarations across effect records. */
  readonly effectUnknownRoutes: number;
  /** M7: Per-effect blocker details for drawer surfacing. */
  readonly effectBlockerDetails: readonly EffectBlockerDetail[];
}

/** Complete read-only inventory derived from extension runtime state. */
export interface ExtensionStatusInventory {
  readonly extensions: readonly ExtensionInventoryEntry[];
  readonly summary: ExtensionStatusSummary;
  /** Export-blocker diagnostics (code starts with 'export/' and severity error). */
  readonly exportBlockers: readonly Diagnostic[];
  /** Planner blocker diagnostics synced from renderPlanner. */
  readonly plannerBlockers: readonly Diagnostic[];
  /** Render-blocker diagnostics (render/missing-renderer or render/contribution-error, severity error). */
  readonly renderBlockers: readonly Diagnostic[];
  /** Timestamp when the inventory was derived. */
  readonly derivedAt: number;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const EMPTY_INVENTORY: ExtensionStatusInventory = Object.freeze({
  extensions: Object.freeze([]),
  summary: Object.freeze({
    totalExtensions: 0,
    activeExtensions: 0,
    failedExtensions: 0,
    inactiveExtensions: 0,
    totalContributions: 0,
    activeContributions: 0,
    inactiveContributions: 0,
    errorDiagnostics: 0,
    warningDiagnostics: 0,
    infoDiagnostics: 0,
    exportBlockers: 0,
    plannerBlockers: 0,
    renderBlockers: 0,
    commandCount: 0,
    keybindingCount: 0,
    contextMenuCount: 0,
    commandsFailedLastRun: 0,
    effectRecordCount: 0,
    effectBrowserExportBlockers: 0,
    effectSupportedRoutes: 0,
    effectBlockedRoutes: 0,
    effectUnknownRoutes: 0,
    effectBlockerDetails: Object.freeze([]),
  }),
  exportBlockers: Object.freeze([]),
  plannerBlockers: Object.freeze([]),
  renderBlockers: Object.freeze([]),
  derivedAt: 0,
});

const EMPTY_DIAGNOSTICS: readonly Diagnostic[] = Object.freeze([]);

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Derive a read-only extension status inventory from the current runtime.
 *
 * Consumes {@link useVideoEditorRuntime} and returns a frozen, memoized
 * inventory. The inventory reflects:
 * - Extension manifests and their contribution declarations
 * - Normalized contribution registries (which are active)
 * - Inactive reserved contributions (kinds not yet bridged)
 * - Provider-scoped diagnostics (errors, warnings, info)
 * - Export and render blocker diagnostics
 *
 * Does NOT expose install/uninstall/enable/disable/settings controls.
 */
export function useExtensionStatusInventory(): ExtensionStatusInventory {
  const { extensionRuntime, diagnosticCollection, commandRegistry } = useVideoEditorRuntime();
  const effectRegistrySnapshot = useEffectRegistrySnapshot();
  const diagnostics = useSyncExternalStore(
    useCallback((listener) => {
      if (!diagnosticCollection) return () => {};
      const handle = diagnosticCollection.subscribe(listener);
      return () => handle.dispose();
    }, [diagnosticCollection]),
    useCallback(() => diagnosticCollection?.getSnapshot() ?? EMPTY_DIAGNOSTICS, [diagnosticCollection]),
    () => EMPTY_DIAGNOSTICS,
  );

  return useMemo(() => {
    const packageInventory = extensionRuntime?.packageStateInventory ?? [];
    if (!extensionRuntime || (extensionRuntime.extensions.length === 0 && packageInventory.length === 0)) {
      return EMPTY_INVENTORY;
    }

    const runtime = extensionRuntime;

    const allDiagnostics: readonly Diagnostic[] = diagnostics;

    // Snapshot the command registry once per inventory derivation.
    let commandSnapshot: CommandRegistrySnapshot | undefined;
    if (commandRegistry) {
      commandSnapshot = commandRegistry.getSnapshot();
    }

    // ---- Resolve per-contribution status ----------------------------------

    /** Build a set of (extensionId, contributionId) pairs that are inactive. */
    const inactiveSet = new Set<string>();
    const inactiveByExtContrib = new Map<string, InactiveReservedContribution>();
    for (const r of runtime.inactiveReserved) {
      const key = `${r.extensionId}::${r.contributionId}`;
      inactiveSet.add(key);
      inactiveByExtContrib.set(key, r);
    }

    /** Build a set of contribution IDs that appear in the normalized registries (active). */
    const activeContribIds = new Set<string>();
    for (const slotKey of Object.keys(runtime.config.slots)) {
      activeContribIds.add(slotKey);
    }
    for (const d of runtime.config.dialogHost.dialogs) {
      activeContribIds.add(d.id);
    }
    for (const p of runtime.config.registry.panels) {
      activeContribIds.add(p.id);
    }
    for (const s of runtime.config.registry.inspectorSections) {
      activeContribIds.add(s.id);
    }

    // ---- Build extension entries ------------------------------------------

    const extensions: ExtensionInventoryEntry[] = runtime.extensions.map((ext) => {
      const extId = ext.manifest.id as string;
      const extDiags = allDiagnostics.filter((d) => d.extensionId === extId);
      const manifestContribs = ext.manifest.contributions ?? [];

      const contributions: ContributionInventoryEntry[] = manifestContribs.map((contrib) => {
        const contribId = contrib.id as string;
        const key = `${extId}::${contribId}`;
        const contribDiags = extDiags.filter((d) => d.contributionId === contribId);
        const hasRenderError = contribDiags.some(
          (d) => d.severity === 'error' && d.code === 'render/contribution-error',
        );

        let status: ContributionInventoryStatus;
        if (hasRenderError) {
          status = 'failed';
        } else if (inactiveSet.has(key)) {
          status = 'inactive';
        } else {
          status = 'active';
        }

        const inactiveEntry = inactiveByExtContrib.get(key);

        return {
          contributionId: contribId,
          kind: contrib.kind,
          label: contrib.label,
          status,
          milestone: inactiveEntry?.milestone,
          slot: contrib.slot,
          diagnostics: Object.freeze(contribDiags),
        };
      });

      return {
        extensionId: extId,
        label: ext.manifest.label,
        version: ext.manifest.version,
        description: ext.manifest.description,
        contributions: Object.freeze(contributions),
        diagnostics: Object.freeze(extDiags),
        hasErrors: extDiags.some((d) => d.severity === 'error'),
        hasWarnings: extDiags.some((d) => d.severity === 'warning'),
      };
    });

    // ---- Augment with non-active packages from packageStateInventory ----
    const activeExtensionIds = new Set(runtime.extensions.map((e) => e.manifest.id as string));
    for (const psi of packageInventory) {
      // Only add entries for packages not already represented as active extensions
      if (activeExtensionIds.has(psi.extensionId)) continue;

      const meta = psi.packageMetadata;
      const extId = psi.extensionId;
      const extDiags = allDiagnostics.filter((d) => d.extensionId === extId);

      // Map package state to error/warning signals
      const isError = psi.packageState === 'invalid'
        || psi.packageState === 'incompatible'
        || psi.packageState === 'runtime-error';
      const isWarning = psi.packageState === 'disabled-by-user'
        || psi.packageState === 'duplicate'
        || psi.packageState === 'settings-error';

      extensions.push({
        extensionId: extId,
        label: meta?.label ?? extId,
        version: meta?.version ?? '0.0.0',
        description: meta?.description,
        contributions: Object.freeze([]),
        diagnostics: Object.freeze(extDiags),
        hasErrors: isError,
        hasWarnings: isWarning,
      });
    }

    // ---- Compute blockers --------------------------------------------------

    const exportBlockers: Diagnostic[] = [];
    const plannerBlockers: Diagnostic[] = [];
    const renderBlockers: Diagnostic[] = [];
    for (const d of allDiagnostics) {
      if (d.severity === 'error') {
        if (d.code.startsWith('export/')) {
          exportBlockers.push(d);
        }
        if (d.detail?.source === 'render-planner' || d.code.startsWith('planner/')) {
          plannerBlockers.push(d);
        }
        if (d.code === 'render/missing-renderer' || d.code === 'render/contribution-error') {
          renderBlockers.push(d);
        }
      }
    }

    // ---- Compute summary ---------------------------------------------------

    // M4: Derive command registry statistics from the snapshot.
    let commandCount = 0;
    let keybindingCount = 0;
    let contextMenuCount = 0;
    let commandsFailedLastRun = 0;
    if (commandSnapshot) {
      commandCount = commandSnapshot.commands.length;
      keybindingCount = commandSnapshot.keybindings.length;
      contextMenuCount = commandSnapshot.contextMenuItems.length;
      for (const cmd of commandSnapshot.commands) {
        const status = commandSnapshot.getStatus(cmd.commandId);
        if (!status.lastRunOk && status.lastRunAt > 0) {
          commandsFailedLastRun++;
        }
      }
    }
    const effectRecordCount = effectRegistrySnapshot.records.length;
    const effectBrowserExportBlockers = effectRegistrySnapshot.records.filter((record) => {
      if (record.status !== 'active') return true;
      const capability = record.renderability.capabilities.find((item) => item.route === 'browser-export');
      return capability?.status !== 'supported';
    }).length;
    const effectCapabilities = effectRegistrySnapshot.records.flatMap((record) => record.renderability.capabilities);
    const effectSupportedRoutes = effectCapabilities.filter((capability) => capability.status === 'supported').length;
    const effectBlockedRoutes = effectCapabilities.filter((capability) => capability.status === 'blocked').length;
    const effectUnknownRoutes = effectCapabilities.filter((capability) => capability.status === 'unknown').length;

    // M7: Build per-effect blocker details for drawer surfacing.
    const effectBlockerDetails: EffectBlockerDetail[] = [];
    for (const record of effectRegistrySnapshot.records) {
      const blockedRoutes: string[] = [];
      const unknownRoutes: string[] = [];
      for (const cap of record.renderability.capabilities) {
        if (cap.status === 'blocked') {
          blockedRoutes.push(cap.route);
        } else if (cap.status === 'unknown') {
          unknownRoutes.push(cap.route);
        }
      }
      // Include records that have any blocked/unknown routes, or inactive/error status.
      if (blockedRoutes.length > 0 || unknownRoutes.length > 0 || record.status !== 'active') {
        effectBlockerDetails.push({
          effectId: record.effectId,
          provenance: record.provenance,
          status: record.status,
          blockedRoutes: Object.freeze(blockedRoutes),
          unknownRoutes: Object.freeze(unknownRoutes),
          ownerExtensionId: record.ownerExtensionId,
        });
      }
    }

    const summary: ExtensionStatusSummary = {
      totalExtensions: extensions.length,
      activeExtensions: extensions.filter(
        (e) => !e.hasErrors && !e.contributions.some((c) => c.status === 'failed'),
      ).length,
      failedExtensions: extensions.filter((e) => e.hasErrors).length,
      inactiveExtensions: runtime.inactiveReserved.length > 0
        ? new Set(runtime.inactiveReserved.map((r) => r.extensionId)).size
        : 0,
      totalContributions: extensions.reduce((sum, e) => sum + e.contributions.length, 0),
      activeContributions: extensions.reduce(
        (sum, e) => sum + e.contributions.filter((c) => c.status === 'active').length,
        0,
      ),
      inactiveContributions: runtime.inactiveReserved.length,
      errorDiagnostics: allDiagnostics.filter((d) => d.severity === 'error').length,
      warningDiagnostics: allDiagnostics.filter((d) => d.severity === 'warning').length,
      infoDiagnostics: allDiagnostics.filter((d) => d.severity === 'info').length,
      exportBlockers: exportBlockers.length,
      plannerBlockers: plannerBlockers.length,
      renderBlockers: renderBlockers.length,
      commandCount,
      keybindingCount,
      contextMenuCount,
      commandsFailedLastRun,
      effectRecordCount,
      effectBrowserExportBlockers,
      effectSupportedRoutes,
      effectBlockedRoutes,
      effectUnknownRoutes,
      effectBlockerDetails: Object.freeze(effectBlockerDetails),
    };

    return {
      extensions: Object.freeze(extensions),
      summary: Object.freeze(summary),
      exportBlockers: Object.freeze(exportBlockers),
      plannerBlockers: Object.freeze(plannerBlockers),
      renderBlockers: Object.freeze(renderBlockers),
      derivedAt: Date.now(),
    };
  }, [extensionRuntime, diagnostics, commandRegistry, effectRegistrySnapshot]);
}

// ---------------------------------------------------------------------------
// Severity styling helpers
// ---------------------------------------------------------------------------

const SEVERITY_ICON = {
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
} as const;

const SEVERITY_COLOR = {
  error: 'text-red-400',
  warning: 'text-yellow-400',
  info: 'text-blue-400',
} as const;

const SEVERITY_BG = {
  error: 'bg-red-500/10 border-red-500/30',
  warning: 'bg-yellow-500/10 border-yellow-500/30',
  info: 'bg-blue-500/10 border-blue-500/30',
} as const;

const STATUS_LABEL: Record<ContributionInventoryStatus, string> = {
  active: 'Active',
  inactive: 'Inactive',
  failed: 'Failed',
};

const STATUS_COLOR: Record<ContributionInventoryStatus, string> = {
  active: 'text-emerald-400',
  inactive: 'text-zinc-500',
  failed: 'text-red-400',
};

function blockCardDetailValue(diagnostic: Diagnostic, key: 'nextAction' | 'repairAction'): unknown {
  return diagnostic.detail?.[key];
}

function BlockerCardSection({
  title,
  diagnostics,
}: {
  title: string;
  diagnostics: readonly Diagnostic[];
}) {
  if (diagnostics.length === 0) return null;

  return (
    <div className="border-b border-white/5 px-3 py-2">
      <div className="mb-2">
        <span className="text-[10px] font-medium uppercase tracking-wider text-zinc-500">
          {title}
        </span>
      </div>
      <div className="space-y-2">
        {diagnostics.map((diagnostic) => (
          <BlockerActionCard
            key={diagnostic.id}
            severity={diagnostic.severity}
            code={diagnostic.code}
            message={diagnostic.message}
            nextAction={normalizeBlockerActionCardNextAction(
              blockCardDetailValue(diagnostic, 'repairAction') ?? blockCardDetailValue(diagnostic, 'nextAction'),
            )}
          />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component props
// ---------------------------------------------------------------------------

export interface ExtensionStatusDrawerProps {
  /** Called when the drawer is dismissed. */
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SummaryBar({ inventory }: { inventory: ExtensionStatusInventory }) {
  const { summary } = inventory;

  const items: { label: string; value: number; icon: typeof Puzzle; color: string }[] = [
    { label: 'Extensions', value: summary.totalExtensions, icon: Puzzle, color: 'text-zinc-300' },
    {
      label: 'Active',
      value: summary.activeExtensions,
      icon: Zap,
      color: 'text-emerald-400',
    },
    {
      label: 'Failed',
      value: summary.failedExtensions,
      icon: AlertCircle,
      color: summary.failedExtensions > 0 ? 'text-red-400' : 'text-zinc-500',
    },
    {
      label: 'Inactive',
      value: summary.inactiveExtensions,
      icon: Info,
      color: summary.inactiveExtensions > 0 ? 'text-zinc-400' : 'text-zinc-600',
    },
  ];

  const diagItems: { label: string; value: number; color: string }[] = [
    { label: 'Errors', value: summary.errorDiagnostics, color: 'text-red-400' },
    { label: 'Warnings', value: summary.warningDiagnostics, color: 'text-yellow-400' },
    { label: 'Info', value: summary.infoDiagnostics, color: 'text-blue-400' },
  ];

  // M4: Command registry stats row (only shown when commands are present).
  const hasCommands = summary.commandCount > 0
    || summary.keybindingCount > 0
    || summary.contextMenuCount > 0;
  const hasEffectRegistryRecords = summary.effectRecordCount > 0;

  const cmdItems: { label: string; value: number; color: string }[] = [
    { label: 'Commands', value: summary.commandCount, color: 'text-zinc-300' },
    { label: 'Keybindings', value: summary.keybindingCount, color: 'text-zinc-400' },
    { label: 'Menus', value: summary.contextMenuCount, color: 'text-zinc-400' },
  ];

  return (
    <div
      className="border-b border-white/10 px-3 py-2"
      aria-live="polite"
      aria-label={`Extension summary: ${summary.totalExtensions} extensions, ${summary.totalContributions} contributions, ${summary.errorDiagnostics} errors, ${summary.warningDiagnostics} warnings`}
    >
      {/* Extension counts */}
      <div className="flex flex-wrap items-center gap-3">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <div
              key={item.label}
              className="flex items-center gap-1"
              data-video-editor-extension-summary={item.label.toLowerCase()}
            >
              <Icon className={`h-3 w-3 ${item.color}`} aria-hidden="true" />
              <span className="text-[10px] text-zinc-500">{item.label}</span>
              <span className={`text-[11px] font-medium ${item.color} tabular-nums`}>
                {item.value}
              </span>
            </div>
          );
        })}
      </div>

      {/* Diagnostic counts */}
      <div className="mt-1 flex flex-wrap items-center gap-2">
        {diagItems.map((item) => (
          <div key={item.label} className="flex items-center gap-0.5">
            <span className={`h-1.5 w-1.5 rounded-full ${item.color.replace('text-', 'bg-')}`} aria-hidden="true" />
            <span className="text-[10px] text-zinc-600">{item.label}</span>
            <span className={`text-[10px] font-medium ${item.color} tabular-nums`}>{item.value}</span>
          </div>
        ))}

        {/* Blockers */}
        {summary.exportBlockers > 0 && (
          <div className="flex items-center gap-0.5">
            <ShieldX className="h-2.5 w-2.5 text-red-400" aria-hidden="true" />
            <span className="text-[10px] text-zinc-600">Export blockers</span>
            <span className="text-[10px] font-medium text-red-400 tabular-nums">
              {summary.exportBlockers}
            </span>
          </div>
        )}
        {summary.plannerBlockers > 0 && (
          <div className="flex items-center gap-0.5" data-video-editor-planner-summary="blockers">
            <ShieldX className="h-2.5 w-2.5 text-red-400" aria-hidden="true" />
            <span className="text-[10px] text-zinc-600">Planner blockers</span>
            <span className="text-[10px] font-medium text-red-400 tabular-nums">
              {summary.plannerBlockers}
            </span>
          </div>
        )}
        {summary.renderBlockers > 0 && (
          <div className="flex items-center gap-0.5">
            <AlertCircle className="h-2.5 w-2.5 text-red-400" aria-hidden="true" />
            <span className="text-[10px] text-zinc-600">Render blockers</span>
            <span className="text-[10px] font-medium text-red-400 tabular-nums">
              {summary.renderBlockers}
            </span>
          </div>
        )}
      </div>

      {/* M4: Command registry stats */}
      {hasCommands && (
        <div className="mt-1.5 flex flex-wrap items-center gap-2 border-t border-white/5 pt-1.5">
          {cmdItems.map((item) => (
            <div
              key={item.label}
              className="flex items-center gap-1"
              data-video-editor-command-summary={item.label.toLowerCase()}
            >
              <span className={`text-[10px] font-medium ${item.color} tabular-nums`}>
                {item.value}
              </span>
              <span className="text-[10px] text-zinc-600">{item.label}</span>
            </div>
          ))}
          {summary.commandsFailedLastRun > 0 && (
            <div
              className="flex items-center gap-0.5"
              data-video-editor-command-summary="failed-last-run"
            >
              <AlertCircle className="h-2 w-2 text-red-400" aria-hidden="true" />
              <span className="text-[10px] font-medium text-red-400 tabular-nums">
                {summary.commandsFailedLastRun}
              </span>
              <span className="text-[10px] text-zinc-600">failed last run</span>
            </div>
          )}
        </div>
      )}

      {hasEffectRegistryRecords && (
        <div className="mt-1.5 flex flex-wrap items-center gap-2 border-t border-white/5 pt-1.5">
          <div className="flex items-center gap-1" data-video-editor-effect-registry-summary="records">
            <span className="text-[10px] font-medium text-zinc-300 tabular-nums">
              {summary.effectRecordCount}
            </span>
            <span className="text-[10px] text-zinc-600">Effects</span>
          </div>
          <div className="flex items-center gap-1" data-video-editor-effect-registry-summary="browser-export-blockers">
            <span className={`text-[10px] font-medium tabular-nums ${summary.effectBrowserExportBlockers > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
              {summary.effectBrowserExportBlockers}
            </span>
            <span className="text-[10px] text-zinc-600">Effect export blockers</span>
          </div>
          <div className="flex items-center gap-1" data-video-editor-effect-renderability-summary="supported">
            <span className="text-[10px] font-medium text-emerald-400 tabular-nums">
              {summary.effectSupportedRoutes}
            </span>
            <span className="text-[10px] text-zinc-600">supported routes</span>
          </div>
          <div className="flex items-center gap-1" data-video-editor-effect-renderability-summary="blocked">
            <span className={`text-[10px] font-medium tabular-nums ${summary.effectBlockedRoutes > 0 ? 'text-red-400' : 'text-zinc-500'}`}>
              {summary.effectBlockedRoutes}
            </span>
            <span className="text-[10px] text-zinc-600">blocked routes</span>
          </div>
          {summary.effectUnknownRoutes > 0 && (
            <div className="flex items-center gap-1" data-video-editor-effect-renderability-summary="unknown">
              <span className="text-[10px] font-medium text-yellow-400 tabular-nums">
                {summary.effectUnknownRoutes}
              </span>
              <span className="text-[10px] text-zinc-600">unknown routes</span>
            </div>
          )}
        </div>
      )}

      {/* M7: Per-effect blocker details */}
      {summary.effectBlockerDetails.length > 0 && (
        <div className="mt-1.5 border-t border-white/5 pt-1.5">
          <div className="mb-1">
            <span className="text-[9px] font-medium text-zinc-500 uppercase tracking-wider">
              Effect Route Blockers
            </span>
          </div>
          <div className="flex flex-col gap-1">
            {summary.effectBlockerDetails.map((detail) => (
              <div
                key={detail.effectId}
                className="flex flex-wrap items-center gap-1.5 rounded bg-zinc-800/50 px-1.5 py-1"
                data-video-editor-effect-blocker-detail={detail.effectId}
              >
                <span className="text-[10px] font-medium text-zinc-300 truncate max-w-[160px]">
                  {detail.effectId}
                </span>
                {detail.status !== 'active' && (
                  <span className={`text-[9px] font-medium uppercase ${detail.status === 'error' ? 'text-red-400' : 'text-zinc-500'}`}>
                    {detail.status}
                  </span>
                )}
                <span className="text-[9px] text-zinc-600">{detail.provenance}</span>
                {detail.blockedRoutes.length > 0 && (
                  <span className="text-[9px] text-red-400">
                    blocked: {detail.blockedRoutes.join(', ')}
                  </span>
                )}
                {detail.unknownRoutes.length > 0 && (
                  <span className="text-[9px] text-yellow-400">
                    unknown: {detail.unknownRoutes.join(', ')}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ContributionBadge({ status }: { status: ContributionInventoryStatus }) {
  return (
    <span
      className={`inline-block rounded px-1 py-0 text-[9px] font-medium uppercase tracking-wider ${STATUS_COLOR[status]} bg-zinc-800`}
      data-video-editor-contribution-status={status}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}

function ExtensionCard({
  entry,
  defaultExpanded,
}: {
  entry: ExtensionInventoryEntry;
  defaultExpanded: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const toggle = useCallback(() => setExpanded((prev) => !prev), []);

  const errorCount = entry.diagnostics.filter((d) => d.severity === 'error').length;
  const warningCount = entry.diagnostics.filter((d) => d.severity === 'warning').length;

  return (
    <div
      className="border-b border-white/5 last:border-b-0"
      data-video-editor-extension-entry={entry.extensionId}
    >
      {/* Extension header */}
      <button
        type="button"
        onClick={toggle}
        className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-white/5 transition-colors"
        aria-expanded={expanded}
        aria-label={`${entry.label} — ${entry.contributions.length} contributions`}
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3 shrink-0 text-zinc-500" aria-hidden="true" />
        ) : (
          <ChevronRight className="h-3 w-3 shrink-0 text-zinc-500" aria-hidden="true" />
        )}

        <Puzzle className="h-3.5 w-3.5 shrink-0 text-zinc-400" aria-hidden="true" />

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-medium text-zinc-200 truncate">{entry.label}</span>
            <span className="text-[10px] text-zinc-600 tabular-nums">v{entry.version}</span>
          </div>
          {!expanded && entry.description && (
            <p className="text-[10px] text-zinc-500 truncate mt-0.5">{entry.description}</p>
          )}
        </div>

        {/* Status indicators */}
        <div className="flex items-center gap-1 shrink-0">
          <span
            className="rounded-full bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400 tabular-nums"
            title={`${entry.contributions.length} contributions`}
          >
            {entry.contributions.length}
          </span>
          {errorCount > 0 && (
            <span
              className="inline-flex items-center gap-0.5 rounded-full bg-red-500/10 px-1.5 py-0.5 text-[10px] text-red-400 tabular-nums"
              title={`${errorCount} error${errorCount === 1 ? '' : 's'}`}
            >
              <AlertCircle className="h-2 w-2" aria-hidden="true" />
              {errorCount}
            </span>
          )}
          {warningCount > 0 && (
            <span
              className="inline-flex items-center gap-0.5 rounded-full bg-yellow-500/10 px-1.5 py-0.5 text-[10px] text-yellow-400 tabular-nums"
              title={`${warningCount} warning${warningCount === 1 ? '' : 's'}`}
            >
              <AlertTriangle className="h-2 w-2" aria-hidden="true" />
              {warningCount}
            </span>
          )}
        </div>
      </button>

      {/* Extension body */}
      {expanded && (
        <div className="border-t border-white/5">
          {/* Description (when expanded) */}
          {entry.description && (
            <div className="px-3 py-1.5">
              <p className="text-[10px] text-zinc-500">{entry.description}</p>
            </div>
          )}

          {/* Contributions */}
          {entry.contributions.length > 0 && (
            <div className="border-t border-white/5">
              <div className="px-3 py-1">
                <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">
                  Contributions
                </span>
              </div>
              <div className="flex flex-col">
                {entry.contributions.map((contrib) => {
                  const contribErrorCount = contrib.diagnostics.filter(
                    (d) => d.severity === 'error',
                  ).length;
                  const contribWarnCount = contrib.diagnostics.filter(
                    (d) => d.severity === 'warning',
                  ).length;

                  return (
                    <div
                      key={contrib.contributionId}
                      className="border-t border-white/5 px-3 py-1.5 hover:bg-white/5 transition-colors"
                      data-video-editor-contribution-entry={contrib.contributionId}
                      data-video-editor-contribution-kind={contrib.kind}
                    >
                      <div className="flex items-center gap-1.5">
                        <span className="text-[11px] text-zinc-300 break-all">
                          {contrib.label ?? contrib.contributionId}
                        </span>
                        <ContributionBadge status={contrib.status} />

                        {contrib.slot && (
                          <span className="text-[9px] text-zinc-600 font-mono">
                            {contrib.slot}
                          </span>
                        )}

                        {contrib.milestone && contrib.status === 'inactive' && (
                          <span className="text-[9px] text-zinc-600">
                            activates in {contrib.milestone}
                          </span>
                        )}
                      </div>

                      {/* Contribution diagnostics summary */}
                      {(contribErrorCount > 0 || contribWarnCount > 0) && (
                        <div className="mt-0.5 flex items-center gap-1.5">
                          {contribErrorCount > 0 && (
                            <span className="text-[9px] text-red-400 tabular-nums">
                              {contribErrorCount} error{contribErrorCount === 1 ? '' : 's'}
                            </span>
                          )}
                          {contribWarnCount > 0 && (
                            <span className="text-[9px] text-yellow-400 tabular-nums">
                              {contribWarnCount} warning{contribWarnCount === 1 ? '' : 's'}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* No contributions */}
          {entry.contributions.length === 0 && (
            <div className="px-3 py-2">
              <span className="text-[10px] text-zinc-600 italic">No contributions declared.</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

/**
 * A slide-out drawer displaying read-only extension status inventory.
 *
 * Derives inventory via {@link useExtensionStatusInventory} and renders
 * extensions grouped with their contribution statuses, diagnostic counts,
 * and blocker summaries.
 *
 * Excludes install/uninstall/enable/disable/settings controls.
 */
export function ExtensionStatusDrawer({ onClose }: ExtensionStatusDrawerProps) {
  const inventory = useExtensionStatusInventory();

  const hasExtensions = inventory.extensions.length > 0;

  return (
    <div
      role="dialog"
      aria-label="Extension status"
      aria-modal="true"
      data-video-editor-extension-status-drawer="true"
      className="flex flex-col rounded-lg border border-white/10 bg-zinc-900 text-xs text-zinc-200 shadow-2xl"
      style={{ maxHeight: '70vh', minWidth: '340px', maxWidth: '480px' }}
    >
      {/* ---- Header -------------------------------------------------------- */}
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-2">
        <div className="flex items-center gap-2">
          <Puzzle className="h-3.5 w-3.5 text-zinc-400" aria-hidden="true" />
          <span className="font-medium text-zinc-300">Extension Status</span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded p-0.5 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300 transition-colors"
          aria-label="Close extension status drawer"
          autoFocus
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* ---- Summary bar ---------------------------------------------------- */}
      <SummaryBar inventory={inventory} />

      <BlockerCardSection title="Export Blockers" diagnostics={inventory.exportBlockers} />
      <BlockerCardSection title="Planner Blockers" diagnostics={inventory.plannerBlockers} />

      {/* ---- Extension list ------------------------------------------------- */}
      <div
        className="overflow-y-auto"
        role="log"
        aria-live="polite"
        aria-label={`${inventory.extensions.length} extension${inventory.extensions.length === 1 ? '' : 's'}`}
        aria-relevant="additions removals"
      >
        {!hasExtensions ? (
          <div className="flex flex-col items-center gap-1.5 px-4 py-8 text-center">
            <Puzzle className="h-5 w-5 text-zinc-700" aria-hidden="true" />
            <p className="text-[11px] text-zinc-600">No extensions loaded.</p>
          </div>
        ) : (
          <div className="flex flex-col">
            {inventory.extensions.map((entry) => (
              <ExtensionCard
                key={entry.extensionId}
                entry={entry}
                defaultExpanded={entry.hasErrors}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
