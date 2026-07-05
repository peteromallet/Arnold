// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RouteCompletionDashboard } from '@/tools/video-editor/components/RouteCompletionDashboard/RouteCompletionDashboard.tsx';
import type { RouteCompletionDashboardProps } from '@/tools/video-editor/components/RouteCompletionDashboard/RouteCompletionDashboard.tsx';
import type { RenderArtifact } from '@/sdk/video/rendering/artifacts.ts';
import type { RenderRoute, RenderBlocker } from '@reigh/editor-sdk';
import type {
  VideoEditorPlannerNextActionDescriptor,
  VideoEditorProcessDescriptor,
} from '@/tools/video-editor/runtime/extensionSurface.ts';
import type { RenderRoutePlan, RouteArtifactCompletionRecord } from '@/tools/video-editor/runtime/renderPlanner.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SIDECAR_ROUTE: RenderRoute = 'sidecar-export';
const BROWSER_ROUTE: RenderRoute = 'browser-export';

function makeArtifact(overrides: Partial<RenderArtifact> = {}): RenderArtifact {
  return {
    id: 'artifact.test.metadata-json',
    route: SIDECAR_ROUTE,
    locator: {
      kind: 'artifact-store',
      uri: 'artifact://exports/test/metadata.json',
      mimeType: 'application/json',
      contentSha256: 'a'.repeat(64),
    },
    mediaKind: 'json',
    producerExtensionId: 'com.reigh.test',
    consumedMaterialRefs: [],
    determinism: 'process-dependent',
    boundary: {
      source: 'sidecar-process',
      target: 'export-output',
      route: SIDECAR_ROUTE,
      failureBehavior: 'block-export',
    },
    manifest: {
      profile: 'sidecar',
      schemaVersion: 1,
      id: 'manifest.test.metadata-json',
      artifactId: 'artifact.test.metadata-json',
      route: SIDECAR_ROUTE,
      determinism: 'process-dependent',
      producerExtensionId: 'com.reigh.test',
      locator: {
        kind: 'artifact-store',
        uri: 'artifact://exports/test/metadata.json',
        mimeType: 'application/json',
        contentSha256: 'a'.repeat(64),
      },
      consumedMaterialRefs: [],
      sidecars: [],
      inputHashes: {},
      createdAt: '2026-07-05T00:00:00.000Z',
    },
    ...overrides,
  };
}

function makeArtifactCompletion(
  overrides: Partial<RouteArtifactCompletionRecord> = {},
): RouteArtifactCompletionRecord {
  return {
    status: 'complete',
    requiredProfiles: ['sidecar'],
    completeProfiles: ['sidecar'],
    incompleteProfiles: [],
    blockedProfiles: [],
    profiles: [{
      profile: 'sidecar',
      status: 'complete',
      requiredBy: [{ source: 'output-format', outputFormatId: 'metadata-json-sidecar' }],
      artifacts: [makeArtifact()],
      sidecars: [],
      issues: [],
    }],
    ...overrides,
  };
}

function makeRoutePlan(overrides: Partial<RenderRoutePlan> = {}): RenderRoutePlan {
  return {
    route: SIDECAR_ROUTE,
    blockerCount: 0,
    findingCount: 0,
    blocked: false,
    requiredCapabilities: ['json-rpc', 'sidecar-export'],
    determinism: 'process-dependent',
    blockers: [],
    diagnostics: [],
    outputFormatIds: ['metadata-json-sidecar'],
    processRequirements: [{
      processId: 'com.reigh.test.example-analyzer',
      operationId: 'exportMetadataJson',
      routeScope: {
        source: 'process-operation',
        mode: 'explicit-routes',
        routes: [SIDECAR_ROUTE],
      },
      requiredCapabilities: ['json-rpc', 'sidecar-export'],
    }],
    nextActions: [],
    artifactCompletion: makeArtifactCompletion(),
    ...overrides,
  };
}

function makeProcessDescriptor(
  overrides: Partial<VideoEditorProcessDescriptor> = {},
): VideoEditorProcessDescriptor {
  return {
    id: 'com.reigh.test.example-analyzer',
    processId: 'com.reigh.test.example-analyzer',
    extensionId: 'com.reigh.test',
    contributionId: 'example-analyzer',
    label: 'Example Analyzer',
    protocol: 'stdio-jsonrpc',
    spec: {
      id: 'com.reigh.test.example-analyzer',
      label: 'Example Analyzer',
      version: '1.0.0',
      spawn: { command: 'example-analyzer' },
      operations: [{
        id: 'exportMetadataJson',
        label: 'Export Metadata JSON',
        routes: [SIDECAR_ROUTE],
        requiredCapabilities: [],
      }],
    },
    operations: [{
      id: 'exportMetadataJson',
      label: 'Export Metadata JSON',
      routes: [SIDECAR_ROUTE],
      routeScope: {
        source: 'process-operation',
        mode: 'explicit-routes',
        routes: [SIDECAR_ROUTE],
      },
    }],
    routeRequirements: [{
      routes: [SIDECAR_ROUTE],
      routeScope: {
        source: 'process-operation',
        mode: 'explicit-routes',
        routes: [SIDECAR_ROUTE],
      },
      requiredCapabilities: [],
      processId: 'com.reigh.test.example-analyzer',
      operationId: 'exportMetadataJson',
      determinism: 'process-dependent',
    }],
    availableRoutes: [SIDECAR_ROUTE],
    blockers: [],
    nextActions: [],
    requiredBy: [],
    ...overrides,
  };
}

function makeExtensionRuntime(overrides: Partial<RouteCompletionDashboardProps['extensionRuntime']> = {}) {
  return {
    config: { processes: [], ...overrides.config },
    processes: [makeProcessDescriptor()],
    settingsDefaults: {},
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('RouteCompletionDashboard', () => {
  // -----------------------------------------------------------------------
  // Complete state
  // -----------------------------------------------------------------------

  it('renders the route name and complete status badge', () => {
    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan({
          artifactCompletion: makeArtifactCompletion({ status: 'complete' }),
        })}
        extensionRuntime={makeExtensionRuntime()}
      />,
    );

    expect(screen.getByTestId(`route-completion-dashboard-${SIDECAR_ROUTE}`)).toBeDefined();
    expect(screen.getByTestId(`route-completion-status-${SIDECAR_ROUTE}`)).toHaveTextContent('complete');
    expect(screen.getByText('unblocked')).toBeDefined();
  });

  it('renders artifact and sidecar listings for a complete route', () => {
    const sidecar = {
      id: 'sidecar.test.manifest',
      filename: 'metadata-export.manifest.json',
      mimeType: 'application/json',
      kind: 'manifest' as const,
      locator: {
        kind: 'artifact-store' as const,
        uri: 'artifact://sidecars/test/manifest.json',
        mimeType: 'application/json',
        contentSha256: 'b'.repeat(64),
      },
    };

    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan({
          artifactCompletion: makeArtifactCompletion({
            status: 'complete',
            profiles: [{
              profile: 'sidecar',
              status: 'complete',
              requiredBy: [{ source: 'output-format', outputFormatId: 'metadata-json-sidecar' }],
              artifacts: [makeArtifact()],
              sidecars: [sidecar],
              issues: [],
            }],
          }),
        })}
        extensionRuntime={makeExtensionRuntime()}
      />,
    );

    expect(screen.getByTestId('route-completion-profile-sidecar')).toHaveTextContent('complete');
    expect(screen.getByTestId('route-completion-artifact-artifact.test.metadata-json')).toHaveTextContent('artifact.test.metadata-json');
    expect(screen.getByTestId('route-completion-sidecar-sidecar.test.manifest')).toHaveTextContent('metadata-export.manifest.json');
  });

  it('shows output format IDs and evidence source count', () => {
    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan()}
        extensionRuntime={makeExtensionRuntime()}
      />,
    );

    expect(screen.getByText(/output formats:/)).toBeDefined();
    expect(screen.getByText(/evidence sources:/)).toBeDefined();
  });

  it('shows process lifecycle badge for a ready process', () => {
    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan()}
        extensionRuntime={makeExtensionRuntime()}
        processStatuses={[{
          processId: 'com.reigh.test.example-analyzer',
          state: 'ready',
          label: 'Example Analyzer',
          message: 'Process is ready.',
        }]}
      />,
    );

    expect(screen.getByTestId('route-completion-process-com.reigh.test.example-analyzer')).toBeDefined();
    expect(screen.getByTestId('route-completion-process-status-com.reigh.test.example-analyzer')).toHaveTextContent('ready');
  });

  // -----------------------------------------------------------------------
  // Incomplete state
  // -----------------------------------------------------------------------

  it('renders incomplete status badge for an incomplete route', () => {
    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan({
          artifactCompletion: makeArtifactCompletion({
            status: 'incomplete',
            completeProfiles: [],
            incompleteProfiles: ['sidecar'],
            profiles: [{
              profile: 'sidecar',
              status: 'incomplete',
              requiredBy: [{ source: 'output-format', outputFormatId: 'metadata-json-sidecar' }],
              artifacts: [],
              sidecars: [],
              issues: ['Artifact has not been generated yet.'],
            }],
          }),
        })}
        extensionRuntime={makeExtensionRuntime()}
      />,
    );

    expect(screen.getByTestId(`route-completion-status-${SIDECAR_ROUTE}`)).toHaveTextContent('incomplete');
    expect(screen.getByTestId('route-completion-profile-sidecar')).toHaveTextContent('incomplete');
    expect(screen.getByText('Artifact has not been generated yet.')).toBeDefined();
  });

  it('shows no artifacts message when no artifacts are present', () => {
    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan({
          artifactCompletion: makeArtifactCompletion({
            status: 'incomplete',
            completeProfiles: [],
            incompleteProfiles: ['sidecar'],
            profiles: [{
              profile: 'sidecar',
              status: 'incomplete',
              requiredBy: [{ source: 'output-format', outputFormatId: 'metadata-json-sidecar' }],
              artifacts: [],
              sidecars: [],
              issues: [],
            }],
          }),
        })}
        extensionRuntime={makeExtensionRuntime()}
      />,
    );

    expect(screen.getByText('No artifacts attached for this route yet.')).toBeDefined();
    expect(screen.getByText('No sidecars attached for this route yet.')).toBeDefined();
  });

  // -----------------------------------------------------------------------
  // Blocked state
  // -----------------------------------------------------------------------

  it('renders blocked status badge and blocker count', () => {
    const blocker: RenderBlocker = {
      id: 'planner.test.blocked',
      severity: 'error',
      route: SIDECAR_ROUTE,
      reason: 'process-dependent',
      message: 'Route is blocked due to missing process.',
    };

    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan({
          blocked: true,
          blockerCount: 1,
          findingCount: 1,
          blockers: [blocker],
          artifactCompletion: makeArtifactCompletion({
            status: 'blocked',
            completeProfiles: [],
            blockedProfiles: ['sidecar'],
            profiles: [{
              profile: 'sidecar',
              status: 'blocked',
              requiredBy: [{ source: 'output-format', outputFormatId: 'metadata-json-sidecar' }],
              artifacts: [],
              sidecars: [],
              issues: ['Artifact evidence is missing.'],
            }],
          }),
        })}
        extensionRuntime={makeExtensionRuntime()}
      />,
    );

    expect(screen.getByTestId(`route-completion-status-${SIDECAR_ROUTE}`)).toHaveTextContent('blocked');
    expect(screen.getByText('1 blocker')).toBeDefined();
    expect(screen.getByText('Route is blocked due to missing process.')).toBeDefined();
    expect(screen.getByText('Artifact evidence is missing.')).toBeDefined();
  });

  it('renders blocker action card for a route-scoped blocker', () => {
    const blocker: RenderBlocker = {
      id: 'planner.test.blocked',
      severity: 'error',
      route: SIDECAR_ROUTE,
      reason: 'process-dependent',
      message: 'Requires the Example Analyzer process.',
      detail: {
        code: 'planner/process-dependent',
        nextAction: {
          kind: 'start-process',
          label: 'Start Process',
          message: 'Start the process.',
        },
      },
    };

    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan({
          blocked: true,
          blockerCount: 1,
          findingCount: 1,
          blockers: [blocker],
          artifactCompletion: makeArtifactCompletion({
            status: 'blocked',
            completeProfiles: [],
            blockedProfiles: ['sidecar'],
            profiles: [{
              profile: 'sidecar',
              status: 'blocked',
              requiredBy: [{ source: 'output-format', outputFormatId: 'metadata-json-sidecar' }],
              artifacts: [],
              sidecars: [],
              issues: [],
            }],
          }),
        })}
        extensionRuntime={makeExtensionRuntime()}
      />,
    );

    expect(screen.getByText('Requires the Example Analyzer process.')).toBeDefined();
  });

  it('renders next actions section with route-scoped actions', () => {
    const action: VideoEditorPlannerNextActionDescriptor = {
      kind: 'start-process',
      route: SIDECAR_ROUTE,
      processId: 'com.reigh.test.example-analyzer',
      label: 'Start Example Analyzer',
      message: 'Start the trusted local process.',
    };

    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan({
          nextActions: [action],
        })}
        extensionRuntime={makeExtensionRuntime()}
      />,
    );

    // The action card renders with the action message
    expect(screen.getByText('Start the trusted local process.')).toBeDefined();
  });

  // -----------------------------------------------------------------------
  // Route-filtered states
  // -----------------------------------------------------------------------

  it('filters out blockers from unrelated routes', () => {
    const sidecarBlocker: RenderBlocker = {
      id: 'planner.test.sidecar-blocked',
      severity: 'error',
      route: SIDECAR_ROUTE,
      reason: 'process-dependent',
      message: 'Sidecar-export blocker.',
    };
    const browserBlocker: RenderBlocker = {
      id: 'planner.test.browser-blocked',
      severity: 'error',
      route: BROWSER_ROUTE,
      reason: 'route-unsupported',
      message: 'Unrelated browser blocker.',
    };

    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan({
          blocked: true,
          blockerCount: 1,
          findingCount: 1,
          blockers: [sidecarBlocker],
        })}
        plannerResult={{
          blockers: [sidecarBlocker, browserBlocker],
          nextActions: [],
        }}
        extensionRuntime={makeExtensionRuntime()}
      />,
    );

    // The sidecar blocker should be visible
    expect(screen.getByText('Sidecar-export blocker.')).toBeDefined();
    // The unrelated browser blocker should NOT be visible
    expect(screen.queryByText('Unrelated browser blocker.')).toBeNull();
  });

  it('filters out next actions from unrelated routes', () => {
    const sidecarAction: VideoEditorPlannerNextActionDescriptor = {
      kind: 'start-process',
      route: SIDECAR_ROUTE,
      processId: 'com.reigh.test.example-analyzer',
      label: 'Start Process for Sidecar',
      message: 'Start sidecar process.',
    };
    const browserAction: VideoEditorPlannerNextActionDescriptor = {
      kind: 'select-route',
      route: BROWSER_ROUTE,
      label: 'Select browser export',
      message: 'Unrelated browser action.',
    };

    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan({
          nextActions: [sidecarAction],
        })}
        plannerResult={{
          blockers: [],
          nextActions: [sidecarAction, browserAction],
        }}
        extensionRuntime={makeExtensionRuntime()}
      />,
    );

    expect(screen.getByText('Start sidecar process.')).toBeDefined();
    expect(screen.queryByText('Unrelated browser action.')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Select browser export' })).toBeNull();
  });

  it('shows no actions message when there are no route-scoped blockers or actions', () => {
    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan({
          blockers: [],
          nextActions: [],
        })}
        extensionRuntime={makeExtensionRuntime()}
      />,
    );

    expect(screen.getByText('No route-scoped repair actions are pending.')).toBeDefined();
  });

  // -----------------------------------------------------------------------
  // Process filtering
  // -----------------------------------------------------------------------

  it('filters process entries to only those scoped to the selected route', () => {
    const otherProcessDescriptor = makeProcessDescriptor({
      id: 'com.reigh.test.other-process',
      processId: 'com.reigh.test.other-process',
      label: 'Other Process',
      operations: [{
        id: 'otherOp',
        label: 'Other Op',
        routes: [BROWSER_ROUTE],
        routeScope: {
          source: 'process-operation',
          mode: 'explicit-routes',
          routes: [BROWSER_ROUTE],
        },
      }],
      routeRequirements: [{
        routes: [BROWSER_ROUTE],
        routeScope: {
          source: 'process-operation',
          mode: 'explicit-routes',
          routes: [BROWSER_ROUTE],
        },
        requiredCapabilities: [],
        processId: 'com.reigh.test.other-process',
        operationId: 'otherOp',
        determinism: 'deterministic',
      }],
    });

    const runtime = makeExtensionRuntime();
    const processes = [...(runtime.processes ?? []), otherProcessDescriptor];

    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan({
          processRequirements: [{
            processId: 'com.reigh.test.example-analyzer',
            operationId: 'exportMetadataJson',
            routeScope: {
              source: 'process-operation',
              mode: 'explicit-routes',
              routes: [SIDECAR_ROUTE],
            },
            requiredCapabilities: [],
          }],
        })}
        extensionRuntime={{ ...runtime, processes }}
        processStatuses={[
          {
            processId: 'com.reigh.test.example-analyzer',
            state: 'ready',
            label: 'Example Analyzer',
            message: 'Ready.',
          },
          {
            processId: 'com.reigh.test.other-process',
            state: 'ready',
            label: 'Other Process',
            message: 'Ready.',
          },
        ]}
      />,
    );

    // Sidecar-scoped process should be visible
    expect(screen.getByTestId('route-completion-process-com.reigh.test.example-analyzer')).toBeDefined();
    // Browser-scoped process should be filtered out
    expect(screen.queryByTestId('route-completion-process-com.reigh.test.other-process')).toBeNull();
  });

  // -----------------------------------------------------------------------
  // onAction callback
  // -----------------------------------------------------------------------

  it('invokes onAction when a blocker action card button is clicked', () => {
    const onAction = vi.fn();
    const blocker: RenderBlocker = {
      id: 'planner.test.blocked',
      severity: 'error',
      route: SIDECAR_ROUTE,
      reason: 'process-dependent',
      message: 'Requires process.',
      detail: {
        code: 'planner/process-dependent',
        nextAction: {
          kind: 'start-process',
          route: SIDECAR_ROUTE,
          processId: 'com.reigh.test.example-analyzer',
          label: 'Start Process',
          message: 'Start the process.',
        },
      },
    };

    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan({
          blocked: true,
          blockerCount: 1,
          findingCount: 1,
          blockers: [blocker],
        })}
        extensionRuntime={makeExtensionRuntime()}
        onAction={onAction}
      />,
    );

    const button = screen.getByRole('button', { name: 'Start Process' });
    fireEvent.click(button);
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  // -----------------------------------------------------------------------
  // Determinism display
  // -----------------------------------------------------------------------

  it('renders determinism status in the header', () => {
    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan({ determinism: 'process-dependent' })}
        extensionRuntime={makeExtensionRuntime()}
      />,
    );

    expect(screen.getByText(/Determinism:/)).toBeDefined();
    expect(screen.getByText(/process-dependent/)).toBeDefined();
  });

  // -----------------------------------------------------------------------
  // Capabilities display
  // -----------------------------------------------------------------------

  it('renders required capabilities in the header', () => {
    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan({
          requiredCapabilities: ['json-rpc', 'sidecar-export'],
        })}
        extensionRuntime={makeExtensionRuntime()}
      />,
    );

    expect(screen.getByText(/Capabilities: json-rpc, sidecar-export/)).toBeDefined();
  });

  it('shows fallback text when no capabilities are declared', () => {
    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan({ requiredCapabilities: [] })}
        extensionRuntime={makeExtensionRuntime()}
      />,
    );

    expect(screen.getByText('No additional capabilities declared.')).toBeDefined();
  });

  // -----------------------------------------------------------------------
  // Edge cases
  // -----------------------------------------------------------------------

  it('renders without plannerResult using route plan blockers directly', () => {
    const blocker: RenderBlocker = {
      id: 'planner.test.direct-blocker',
      severity: 'error',
      route: SIDECAR_ROUTE,
      reason: 'process-dependent',
      message: 'Direct blocker.',
    };

    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan({
          blocked: true,
          blockerCount: 1,
          findingCount: 1,
          blockers: [blocker],
        })}
        extensionRuntime={makeExtensionRuntime()}
      />,
    );

    expect(screen.getByText('Direct blocker.')).toBeDefined();
  });

  it('renders without extensionRuntime showing no processes', () => {
    render(
      <RouteCompletionDashboard
        routePlan={makeRoutePlan()}
      />,
    );

    expect(screen.getByText('No route-scoped process requirements for this selection.')).toBeDefined();
  });
});
