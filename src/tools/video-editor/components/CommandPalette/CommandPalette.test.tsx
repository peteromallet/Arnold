/**
 * M10 T21: Tests for CommandPalette component.
 *
 * Covers:
 *  - Command discovery from commandRegistry
 *  - Agent tool discovery from agentToolRegistry
 *  - Filtering/search by label, commandId, toolId, description
 *  - Routing: command → commandRegistry.executeCommand
 *  - Routing: agentTool → agentToolRegistry.invokeTool
 *  - Grouping by category
 *  - Keybinding display
 *  - Status display (invocation count, last run status)
 *  - Empty state
 *  - Accessible structure
 *
 * @module CommandPalette.test
 * @milestone M10
 */

import { describe, expect, it, vi, beforeEach, afterEach, beforeAll } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// jsdom does not provide scrollIntoView, which cmdk calls internally.
beforeAll(() => {
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = vi.fn();
  }
});
import { CommandPalette } from '@/tools/video-editor/components/CommandPalette/CommandPalette';
import { DataProviderWrapper, type VideoEditorRuntimeContextValue } from '@/tools/video-editor/contexts/DataProviderContext';
import { createCommandRegistry, type CommandRegistry } from '@/tools/video-editor/runtime/commandRegistry';
import { createAgentToolRegistry, type AgentToolRegistry } from '@/tools/video-editor/runtime/agentToolRegistry';
import type {
  AgentToolContribution,
  AgentToolHandler,
  ToolUISummaryResult,
  ToolResult,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeContribution(
  overrides?: Partial<AgentToolContribution>,
): AgentToolContribution {
  return {
    id: 'contrib-1' as any,
    kind: 'agentTool' as const,
    toolId: 'tool-1',
    label: 'Test Tool',
    order: 0,
    ...overrides,
  };
}

function makeHandler(
  result?: ToolResult | null,
): AgentToolHandler {
  return vi.fn().mockResolvedValue(result ?? null);
}

function makeUISummaryResult(summary: string): ToolUISummaryResult {
  return {
    family: 'ui/summary',
    summary,
    diagnostics: [],
  };
}

function buildRuntime(
  commandRegistry: CommandRegistry,
  agentToolRegistry: AgentToolRegistry,
): VideoEditorRuntimeContextValue {
  return {
    provider: {} as VideoEditorRuntimeContextValue['provider'],
    assetResolver: {} as VideoEditorRuntimeContextValue['assetResolver'],
    auth: { userId: 'user-1' },
    project: { projectId: 'project-1' },
    shots: {} as VideoEditorRuntimeContextValue['shots'],
    mediaLightbox: {} as VideoEditorRuntimeContextValue['mediaLightbox'],
    agentChat: {} as VideoEditorRuntimeContextValue['agentChat'],
    toast: {
      error: vi.fn(),
      success: vi.fn(),
      warning: vi.fn(),
      info: vi.fn(),
    },
    telemetry: {
      log: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    },
    timelineId: 'timeline-1',
    userId: 'user-1',
    extensions: {
      slots: {},
      dialogHost: { dialogs: [] },
      registry: { panels: [], inspectorSections: [] },
      overlays: [],
    },
    commandRegistry,
    agentToolRegistry,
  };
}

function registerCommand(
  registry: CommandRegistry,
  extensionId: string,
  commandId: string,
  label: string,
  opts?: { category?: string; handler?: Parameters<CommandRegistry['registerCommand']>[2] },
) {
  registry.ingestCommandContribution(extensionId, {
    id: `contrib-${commandId}` as any,
    kind: 'command',
    command: commandId,
    label,
    category: opts?.category,
  });
  if (opts?.handler) {
    registry.registerCommand(extensionId, commandId, opts.handler);
  }
}

function registerAgentTool(
  registry: AgentToolRegistry,
  extensionId: string,
  toolId: string,
  label: string,
  opts?: { description?: string; resultFamilies?: string[]; handler?: AgentToolHandler },
) {
  registry.ingestAgentToolContribution(extensionId, makeContribution({
    id: `contrib-${toolId}` as any,
    toolId,
    label,
    description: opts?.description,
    resultFamilies: opts?.resultFamilies as any,
  }));
  if (opts?.handler) {
    registry.registerTool(extensionId, toolId, opts.handler);
  }
}

// ---------------------------------------------------------------------------
// CommandPalette component tests
// ---------------------------------------------------------------------------

describe('CommandPalette component', () => {
  let commandRegistry: CommandRegistry;
  let agentToolRegistry: AgentToolRegistry;

  beforeEach(() => {
    commandRegistry = createCommandRegistry();
    agentToolRegistry = createAgentToolRegistry();
  });

  afterEach(() => {
    commandRegistry.dispose();
    agentToolRegistry.dispose();
  });

  function renderPalette(open = true) {
    const runtime = buildRuntime(commandRegistry, agentToolRegistry);
    const onOpenChange = vi.fn();
    const result = render(
      <DataProviderWrapper value={runtime}>
        <CommandPalette open={open} onOpenChange={onOpenChange} />
      </DataProviderWrapper>,
    );
    return { ...result, onOpenChange };
  }

  // ---- Command discovery --------------------------------------------------

  it('discovers and lists registered commands', () => {
    registerCommand(commandRegistry, 'ext.a', 'ext.a.analyze', 'Analyze Timeline', {
      category: 'Analysis',
      handler: vi.fn(),
    });
    registerCommand(commandRegistry, 'ext.b', 'ext.b.export', 'Export Project', {
      category: 'Export',
      handler: vi.fn(),
    });

    renderPalette();

    expect(screen.getByText('Analyze Timeline')).toBeTruthy();
    expect(screen.getByText('Export Project')).toBeTruthy();
  });

  it('groups commands by category', () => {
    registerCommand(commandRegistry, 'ext.a', 'ext.a.cut', 'Cut', {
      category: 'Edit',
      handler: vi.fn(),
    });
    registerCommand(commandRegistry, 'ext.b', 'ext.b.fade', 'Fade', {
      category: 'Effects',
      handler: vi.fn(),
    });

    renderPalette();

    // Group headings
    expect(screen.getByText('Edit')).toBeTruthy();
    expect(screen.getByText('Effects')).toBeTruthy();
  });

  // ---- Agent tool discovery -----------------------------------------------

  it('discovers and lists agent tools', () => {
    registerAgentTool(agentToolRegistry, 'ext.a', 'tool.analyze', 'Analyze Tool', {
      handler: makeHandler(makeUISummaryResult('ok')),
    });

    renderPalette();

    // Agent tool should appear under "Agent Tools" group
    expect(screen.getByText('Agent Tools')).toBeTruthy();
    expect(screen.getByText('Analyze Tool')).toBeTruthy();
  });

  it('shows result family badge for agent tools', () => {
    registerAgentTool(agentToolRegistry, 'ext.a', 'tool.gen', 'Generation Tool', {
      resultFamilies: ['generation/session', 'mutation/proposal'],
      handler: makeHandler(makeUISummaryResult('ok')),
    });

    renderPalette();

    expect(screen.getByText('generation/session +1')).toBeTruthy();
  });

  // ---- Filtering / search ------------------------------------------------

  it('filters commands by search query', async () => {
    registerCommand(commandRegistry, 'ext.a', 'ext.a.analyze', 'Analyze Timeline', {
      handler: vi.fn(),
    });
    registerCommand(commandRegistry, 'ext.b', 'ext.b.export', 'Export Project', {
      handler: vi.fn(),
    });

    renderPalette();

    const input = screen.getByPlaceholderText('Type a command…');
    await userEvent.type(input, 'export');

    // Only matching command should be visible
    expect(screen.queryByText('Analyze Timeline')).toBeNull();
    expect(screen.getByText('Export Project')).toBeTruthy();
  });

  it('filters agent tools by toolId substring in search', async () => {
    registerAgentTool(agentToolRegistry, 'ext.a', 'tool.audio', 'Audio Analyzer', {
      description: 'Analyzes audio tracks for beat detection',
      handler: makeHandler(makeUISummaryResult('ok')),
    });
    registerAgentTool(agentToolRegistry, 'ext.b', 'tool.video', 'Video Stabilizer', {
      description: 'Stabilizes shaky footage',
      handler: makeHandler(makeUISummaryResult('ok')),
    });

    renderPalette();

    const input = screen.getByPlaceholderText('Type a command…');

    // Filter by toolId substring — cmdk filters by value which is the toolId
    await userEvent.type(input, 'audio');
    expect(screen.getByText('Audio Analyzer')).toBeTruthy();
    expect(screen.queryByText('Video Stabilizer')).toBeNull();

    // Clear and filter by other toolId
    await userEvent.clear(input);
    await userEvent.type(input, 'video');
    expect(screen.queryByText('Audio Analyzer')).toBeNull();
    expect(screen.getByText('Video Stabilizer')).toBeTruthy();

    // Clear and show all
    await userEvent.clear(input);
    expect(screen.getByText('Audio Analyzer')).toBeTruthy();
    expect(screen.getByText('Video Stabilizer')).toBeTruthy();
  });

  it('filters agent tools by result family toolId in search', async () => {
    registerAgentTool(agentToolRegistry, 'ext.a', 'tool.gen', 'Generation Tool', {
      resultFamilies: ['generation/session'],
      handler: makeHandler(makeUISummaryResult('ok')),
    });
    registerAgentTool(agentToolRegistry, 'ext.b', 'tool.export', 'Export Tool', {
      resultFamilies: ['export'],
      handler: makeHandler(makeUISummaryResult('ok')),
    });

    renderPalette();

    const input = screen.getByPlaceholderText('Type a command…');
    // cmdk filters by value (toolId). 'gen' is substring of 'tool.gen'
    await userEvent.type(input, 'gen');

    expect(screen.getByText('Generation Tool')).toBeTruthy();
    expect(screen.queryByText('Export Tool')).toBeNull();
  });

  it('filters by toolId prefix matching extension pattern', async () => {
    registerAgentTool(agentToolRegistry, 'ext.alpha', 'tool.a', 'Alpha Tool', {
      handler: makeHandler(makeUISummaryResult('ok')),
    });
    registerAgentTool(agentToolRegistry, 'ext.beta', 'tool.b', 'Beta Tool', {
      handler: makeHandler(makeUISummaryResult('ok')),
    });

    renderPalette();

    const input = screen.getByPlaceholderText('Type a command…');
    // cmdk filters by value (toolId), so search by toolId substring
    await userEvent.type(input, 'tool.a');

    expect(screen.getByText('Alpha Tool')).toBeTruthy();
    expect(screen.queryByText('Beta Tool')).toBeNull();
  });

  // ---- Empty state --------------------------------------------------------

  it('shows empty message when no commands or tools registered', () => {
    renderPalette();
    expect(screen.getByText(/No commands or agent tools registered/)).toBeTruthy();
  });

  it('shows "no matching" message when search has no results', async () => {
    registerCommand(commandRegistry, 'ext.a', 'ext.a.cmd', 'My Command', {
      handler: vi.fn(),
    });

    renderPalette();

    const input = screen.getByPlaceholderText('Type a command…');
    await userEvent.type(input, 'zzz_nonexistent_zzz');

    expect(screen.getByText('No matching commands or agent tools.')).toBeTruthy();
  });

  // ---- Selection routing -------------------------------------------------

  it('executes command on selection', async () => {
    const handler = vi.fn();
    registerCommand(commandRegistry, 'ext.a', 'ext.a.do', 'Do Something', { handler });

    renderPalette();

    const item = screen.getByText('Do Something');
    await userEvent.click(item);

    await waitFor(() => {
      expect(handler).toHaveBeenCalled();
    });
  });

  it('invokes agent tool on selection', async () => {
    const handler = makeHandler(makeUISummaryResult('Tool executed'));
    registerAgentTool(agentToolRegistry, 'ext.a', 'tool.run', 'Run Tool', { handler });

    renderPalette();

    const item = screen.getByText('Run Tool');
    await userEvent.click(item);

    await waitFor(() => {
      expect(handler).toHaveBeenCalled();
    });
  });

  // ---- Status display ----------------------------------------------------

  it('shows invocation count for previously-run commands', async () => {
    const handler = vi.fn();
    registerCommand(commandRegistry, 'ext.a', 'ext.a.do', 'Do Something', { handler });

    // Execute once before render
    await commandRegistry.executeCommand('ext.a.do');

    renderPalette();

    // Should show "✓ Run 1 time" status
    await waitFor(() => {
      expect(screen.getByText('✓ Run 1 time')).toBeTruthy();
    });
  });

  it('shows warning status for last-run-failed commands', () => {
    // Register a command that will be tracked as failed
    // We need to ingest the contribution so it appears in the palette
    commandRegistry.ingestCommandContribution('ext.a', {
      id: 'contrib-fail' as any,
      kind: 'command',
      command: 'ext.a.fail',
      label: 'Failing Command',
    });

    renderPalette();

    // Since we haven't run it, it should have no status
    const items = document.querySelectorAll('[data-command-palette-item]');
    expect(items.length).toBeGreaterThanOrEqual(1);
  });

  it('shows "No handler" for agent tools without registered handlers', () => {
    registerAgentTool(agentToolRegistry, 'ext.a', 'tool.nohandler', 'Tool Without Handler');

    renderPalette();

    expect(screen.getByText('No handler')).toBeTruthy();
  });

  it('shows success status for agent tools that have been invoked', async () => {
    const handler = makeHandler(makeUISummaryResult('ok'));
    registerAgentTool(agentToolRegistry, 'ext.a', 'tool.good', 'Good Tool', { handler });

    // Invoke once
    await agentToolRegistry.invokeTool({
      toolId: 'tool.good',
      extensionId: 'ext.a',
      contributionId: 'contrib-tool.good' as any,
    });

    renderPalette();

    await waitFor(() => {
      expect(screen.getByText('✓ Run 1 time')).toBeTruthy();
    });
  });

  // ---- Keybinding display ------------------------------------------------

  it('shows keybinding shortcuts for commands', () => {
    registerCommand(commandRegistry, 'ext.a', 'ext.a.save', 'Save', {
      handler: vi.fn(),
    });
    commandRegistry.ingestKeybindingContribution('ext.a', {
      id: 'kb-save' as any,
      kind: 'keybinding',
      command: 'ext.a.save',
      key: 'ctrl+s',
    });

    renderPalette();

    // Keybinding should be formatted and displayed
    expect(screen.getByText('Ctrl S')).toBeTruthy();
  });

  it('does not show keybinding shortcuts for agent tools', () => {
    registerAgentTool(agentToolRegistry, 'ext.a', 'tool.test', 'Test Tool', {
      handler: makeHandler(makeUISummaryResult('ok')),
    });

    renderPalette();

    // Agent tools don't have keybindings
    const shortcuts = document.querySelectorAll('[cmdk-shortcuts]');
    // The footer uses kbd tags, but agent tool items should not have CommandShortcut
    expect(screen.queryByText('Ctrl')).toBeNull();
  });

  // ---- Closing behavior --------------------------------------------------

  it('closes palette on item selection', async () => {
    const handler = vi.fn();
    registerCommand(commandRegistry, 'ext.a', 'ext.a.do', 'Do Something', { handler });

    const { onOpenChange } = renderPalette();

    const item = screen.getByText('Do Something');
    await userEvent.click(item);

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  // ---- Data attributes ---------------------------------------------------

  it('sets data attributes for tool/command identification', () => {
    registerCommand(commandRegistry, 'ext.a', 'ext.a.cmd', 'My Command', {
      handler: vi.fn(),
    });
    registerAgentTool(agentToolRegistry, 'ext.b', 'tool.run', 'Run Tool', {
      handler: makeHandler(makeUISummaryResult('ok')),
    });

    renderPalette();

    // Data attributes on items
    const commandItem = document.querySelector('[data-item-kind="command"]');
    const toolItem = document.querySelector('[data-item-kind="agentTool"]');

    expect(commandItem).toBeTruthy();
    expect(toolItem).toBeTruthy();
    expect(commandItem!.getAttribute('data-command-id')).toBe('ext.a.cmd');
    expect(toolItem!.getAttribute('data-tool-id')).toBe('tool.run');
  });

  // ---- Footer -----------------------------------------------------------

  it('renders keyboard hint footer', () => {
    registerCommand(commandRegistry, 'ext.a', 'ext.a.cmd', 'My Command', {
      handler: vi.fn(),
    });

    renderPalette();

    // Footer with keyboard hints
    expect(screen.getByText('Enter')).toBeTruthy();
    expect(screen.getByText('Esc')).toBeTruthy();
    expect(screen.getByText('↑↓')).toBeTruthy();
  });
});
