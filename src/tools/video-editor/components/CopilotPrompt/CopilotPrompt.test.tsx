/**
 * M10 T20: Tests for CopilotPrompt and competing chat surface detection.
 *
 * Covers:
 *  - diagnoseCompetingChatSurface: detects competing chat surfaces in agentTool contributions
 *  - filterCopilotTools: filters registry snapshot to copilot-eligible tools
 *  - CopilotPrompt component: rendering, tool selection, context trimming,
 *    confirmation, history tracking, empty states
 *
 * @module CopilotPrompt.test
 * @milestone M10
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CopilotPrompt, diagnoseCompetingChatSurface, filterCopilotTools } from '@/tools/video-editor/components/CopilotPrompt/CopilotPrompt';
import { createAgentToolRegistry } from '@/tools/video-editor/runtime/agentToolRegistry';
import type { AgentToolRegistry } from '@/tools/video-editor/runtime/agentToolRegistry';
import type {
  AgentToolContribution,
  AgentToolHandler,
  AgentToolInvocationRequest,
  ToolResult,
  ToolUISummaryResult,
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
    description: 'A test tool',
    order: 0,
    ...overrides,
  };
}

function makeHandler(
  result?: ToolResult | null,
  throwError?: Error,
): AgentToolHandler {
  return vi.fn().mockImplementation(async (_request: AgentToolInvocationRequest) => {
    if (throwError) throw throwError;
    return result ?? null;
  });
}

function makeUISummaryResult(summary: string, overrides?: Partial<ToolUISummaryResult>): ToolUISummaryResult {
  return {
    family: 'ui/summary',
    summary,
    diagnostics: [],
    ...overrides,
  };
}

function setupRegistry(): AgentToolRegistry {
  return createAgentToolRegistry();
}

function registerCopilotTool(
  registry: AgentToolRegistry,
  extensionId: string,
  toolId: string,
  label: string,
  description?: string,
  resultFamilies?: string[],
): void {
  const contrib = makeContribution({
    id: `contrib-${toolId}` as any,
    toolId,
    label,
    description,
    resultFamilies: resultFamilies as any,
  });
  registry.ingestAgentToolContribution(extensionId, contrib);

  const handler = makeHandler(
    makeUISummaryResult(`Result from ${label}: analysis complete.`),
  );
  registry.registerTool(extensionId, toolId, handler);
}

// ---------------------------------------------------------------------------
// diagnoseCompetingChatSurface
// ---------------------------------------------------------------------------

describe('diagnoseCompetingChatSurface', () => {
  it('returns null for non-chat tools', () => {
    const snapshot = createAgentToolRegistry().getSnapshot();
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext.test', makeContribution({
      id: 'contrib-1' as any,
      toolId: 'my.tool.analyze',
      label: 'Analyze Timeline',
      description: 'Analyzes the current timeline',
    }));
    const tools = registry.getSnapshot().tools;

    for (const tool of tools) {
      const result = diagnoseCompetingChatSurface(tool);
      if (tool.toolId === 'my.tool.analyze') {
        expect(result).toBeNull();
      }
    }
  });

  it('detects chat-like tool IDs', () => {
    const registry = createAgentToolRegistry();
    const chatIds = ['chat', 'copilot', 'assistant', 'conversation'];

    for (const id of chatIds) {
      registry.ingestAgentToolContribution('ext.test', makeContribution({
        id: `contrib-${id}` as any,
        toolId: id,
        label: `${id} tool`,
      }));
    }

    const tools = registry.getSnapshot().tools;
    for (const tool of tools) {
      if (chatIds.includes(tool.toolId)) {
        const result = diagnoseCompetingChatSurface(tool);
        expect(result).not.toBeNull();
        expect(result!.code).toBe('agent-tool/competing-chat-surface');
        expect(result!.severity).toBe('warning');
      }
    }
  });

  it('detects dot-suffixed chat IDs like .chat or .copilot', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext.test', makeContribution({
      id: 'contrib-dot' as any,
      toolId: 'com.example.chat',
      label: 'Example Chat',
    }));
    registry.ingestAgentToolContribution('ext.test', makeContribution({
      id: 'contrib-dot2' as any,
      toolId: 'my.copilot',
      label: 'My Copilot',
    }));

    const tools = registry.getSnapshot().tools;
    for (const tool of tools) {
      const result = diagnoseCompetingChatSurface(tool);
      if (tool.toolId === 'com.example.chat' || tool.toolId === 'my.copilot') {
        expect(result).not.toBeNull();
        expect(result!.code).toBe('agent-tool/competing-chat-surface');
      }
    }
  });

  it('detects hyphen-suffixed chat IDs like -assistant', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext.test', makeContribution({
      id: 'contrib-hyphen' as any,
      toolId: 'my-assistant',
      label: 'My Assistant',
    }));

    const tool = registry.getSnapshot().tools[0];
    const result = diagnoseCompetingChatSurface(tool);
    expect(result).not.toBeNull();
    expect(result!.code).toBe('agent-tool/competing-chat-surface');
  });

  it('detects label keywords suggesting chat surfaces', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext.test', makeContribution({
      id: 'contrib-label' as any,
      toolId: 'my.analyzer',
      label: 'Chat Copilot Tool',
    }));

    const tool = registry.getSnapshot().tools[0];
    const result = diagnoseCompetingChatSurface(tool);
    expect(result).not.toBeNull();
    expect(result!.code).toBe('agent-tool/competing-chat-surface');
  });

  it('detects description phrases explicitly claiming chat surfaces', () => {
    const registry = createAgentToolRegistry();
    const phrases = [
      'chat interface',
      'copilot panel',
      'assistant panel',
      'conversation ui',
      'chat surface',
      'copilot surface',
      'own copilot',
      'custom assistant',
    ];

    for (let i = 0; i < phrases.length; i++) {
      registry.ingestAgentToolContribution('ext.test', makeContribution({
        id: `contrib-${i}` as any,
        toolId: `tool-${i}`,
        label: `Tool ${i}`,
        description: `This is a ${phrases[i]} for the editor.`,
      }));
    }

    const tools = registry.getSnapshot().tools;
    for (const tool of tools) {
      const result = diagnoseCompetingChatSurface(tool);
      expect(result).not.toBeNull();
      expect(result!.severity).toBe('error');
      expect(result!.code).toBe('agent-tool/competing-chat-surface');
    }
  });

  it('does not flag tools with single benign keyword', () => {
    const registry = createAgentToolRegistry();
    // "chat" in label alone shouldn't flag (needs 2+ keywords or ID match)
    registry.ingestAgentToolContribution('ext.test', makeContribution({
      id: 'contrib-safe' as any,
      toolId: 'my.data.analyzer',
      label: 'Data Analysis Chat',
    }));

    const tool = registry.getSnapshot().tools[0];
    const result = diagnoseCompetingChatSurface(tool);
    // Single "chat" keyword in label with no ID match = no flag
    expect(result).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// filterCopilotTools
// ---------------------------------------------------------------------------

describe('filterCopilotTools', () => {
  it('returns empty tools when registry has no copilot tools', () => {
    const registry = createAgentToolRegistry();
    const snapshot = registry.getSnapshot();
    const result = filterCopilotTools(snapshot);
    expect(result.tools).toHaveLength(0);
    expect(result.chatSurfaceDiagnostics).toHaveLength(0);
  });

  it('filters to only handler-equipped tools', () => {
    const registry = createAgentToolRegistry();

    // Contrib with no handler
    registry.ingestAgentToolContribution('ext.a', makeContribution({
      id: 'contrib-a' as any,
      toolId: 'tool.a',
      label: 'Tool A',
      resultFamilies: ['ui/summary'] as any,
    }));

    // Contrib with handler
    registry.ingestAgentToolContribution('ext.b', makeContribution({
      id: 'contrib-b' as any,
      toolId: 'tool.b',
      label: 'Tool B',
      resultFamilies: ['ui/summary'] as any,
    }));
    registry.registerTool('ext.b', 'tool.b', makeHandler(makeUISummaryResult('ok')));

    const result = filterCopilotTools(registry.getSnapshot());
    expect(result.tools).toHaveLength(1);
    expect(result.tools[0].toolId).toBe('tool.b');
  });

  it('filters out tools without copilot-compatible result families', () => {
    const registry = createAgentToolRegistry();

    registry.ingestAgentToolContribution('ext.a', makeContribution({
      id: 'contrib-a' as any,
      toolId: 'tool.a',
      label: 'Tool A',
      resultFamilies: ['material/artifact'] as any,
    }));
    registry.registerTool('ext.a', 'tool.a', makeHandler(makeUISummaryResult('ok')));

    const result = filterCopilotTools(registry.getSnapshot());
    expect(result.tools).toHaveLength(0);
  });

  it('includes tools with copilot-compatible result families', () => {
    const registry = createAgentToolRegistry();

    const families = ['ui/summary', 'mutation/proposal', 'enrichment/search', 'export', 'generation/session'];
    for (let i = 0; i < families.length; i++) {
      const extId = `ext.${i}`;
      const toolId = `tool.${i}`;
      registry.ingestAgentToolContribution(extId, makeContribution({
        id: `contrib-${i}` as any,
        toolId,
        label: `Tool ${i}`,
        resultFamilies: [families[i]] as any,
      }));
      registry.registerTool(extId, toolId, makeHandler(makeUISummaryResult(`Result ${i}`)));
    }

    const result = filterCopilotTools(registry.getSnapshot());
    expect(result.tools).toHaveLength(5);
  });

  it('includes tools with no result family restriction', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext.a', makeContribution({
      id: 'contrib-a' as any,
      toolId: 'tool.a',
      label: 'Tool A',
      resultFamilies: undefined,
    }));
    registry.registerTool('ext.a', 'tool.a', makeHandler(makeUISummaryResult('ok')));

    const result = filterCopilotTools(registry.getSnapshot());
    expect(result.tools).toHaveLength(1);
  });

  it('diagnoses competing chat surfaces', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext.bad', makeContribution({
      id: 'contrib-chat' as any,
      toolId: 'chat',
      label: 'Chat',
      resultFamilies: ['ui/summary'] as any,
    }));
    registry.registerTool('ext.bad', 'chat', makeHandler(makeUISummaryResult('chat result')));

    const result = filterCopilotTools(registry.getSnapshot());
    // Warning-level: still included but diagnosed
    expect(result.tools).toHaveLength(1);
    expect(result.chatSurfaceDiagnostics).toHaveLength(1);
    expect(result.chatSurfaceDiagnostics[0].code).toBe('agent-tool/competing-chat-surface');
  });

  it('excludes error-level chat surfaces entirely', () => {
    const registry = createAgentToolRegistry();
    registry.ingestAgentToolContribution('ext.bad', makeContribution({
      id: 'contrib-chat-ui' as any,
      toolId: 'my.tool',
      label: 'My Tool',
      description: 'Provides a chat interface for the editor.',
      resultFamilies: ['ui/summary'] as any,
    }));
    registry.registerTool('ext.bad', 'my.tool', makeHandler(makeUISummaryResult('ok')));

    const result = filterCopilotTools(registry.getSnapshot());
    // Error-level: excluded from routing
    expect(result.tools).toHaveLength(0);
    expect(result.chatSurfaceDiagnostics).toHaveLength(1);
    expect(result.chatSurfaceDiagnostics[0].severity).toBe('error');
  });
});

// ---------------------------------------------------------------------------
// CopilotPrompt component
// ---------------------------------------------------------------------------

describe('CopilotPrompt component', () => {
  let registry: AgentToolRegistry;

  beforeEach(() => {
    registry = createAgentToolRegistry();
  });

  afterEach(() => {
    registry.dispose();
  });

  function renderPrompt() {
    return render(
      <CopilotPrompt
        agentToolRegistry={registry}
        onClose={vi.fn()}
      />,
    );
  }

  it('renders empty state when no copilot tools', () => {
    renderPrompt();
    expect(screen.getByText('No copilot-compatible tools registered.')).toBeTruthy();
  });

  it('renders tool selector when copilot tools exist', () => {
    registerCopilotTool(registry, 'ext.a', 'tool.analyze', 'Analyze Tool', 'Analyzes the timeline', ['ui/summary']);

    renderPrompt();
    // Should show the tool label in the selector
    expect(screen.getByText('Analyze Tool')).toBeTruthy();
  });

  it('shows prompt input area', () => {
    registerCopilotTool(registry, 'ext.a', 'tool.analyze', 'Analyze Tool', 'Analyzes', ['ui/summary']);
    renderPrompt();

    const input = screen.getByPlaceholderText('Ask Analyze Tool…');
    expect(input).toBeTruthy();
    expect((input as HTMLTextAreaElement).getAttribute('aria-label')).toBe('Copilot prompt input');
  });

  it('sends prompt on button click', async () => {
    const handler = vi.fn().mockResolvedValue(
      makeUISummaryResult('Analysis complete: 3 clips found.'),
    );
    registry.ingestAgentToolContribution('ext.a', makeContribution({
      id: 'contrib-a' as any,
      toolId: 'tool.analyze',
      label: 'Analyze Tool',
      resultFamilies: ['ui/summary'] as any,
    }));
    registry.registerTool('ext.a', 'tool.analyze', handler);

    renderPrompt();
    const input = screen.getByPlaceholderText('Ask Analyze Tool…');
    await userEvent.type(input, 'Analyze my timeline');

    const sendBtn = screen.getByText('Send');
    await userEvent.click(sendBtn);

    await waitFor(() => {
      expect(handler).toHaveBeenCalled();
    });
  });

  it('displays history entries', async () => {
    const handler = vi.fn().mockResolvedValue(
      makeUISummaryResult('Analysis complete: 5 clips, 3 tracks.'),
    );
    registry.ingestAgentToolContribution('ext.a', makeContribution({
      id: 'contrib-a' as any,
      toolId: 'tool.analyze',
      label: 'Analyze Tool',
      resultFamilies: ['ui/summary'] as any,
    }));
    registry.registerTool('ext.a', 'tool.analyze', handler);

    renderPrompt();

    // Show history
    const historyBtn = screen.getByLabelText(/Show history/);
    await userEvent.click(historyBtn);

    // Send a prompt
    const input = screen.getByPlaceholderText('Ask Analyze Tool…');
    await userEvent.type(input, 'Analyze please');
    const sendBtn = screen.getByText('Send');
    await userEvent.click(sendBtn);

    await waitFor(() => {
      expect(screen.getByText('Analyze please')).toBeTruthy();
    });
  });

  it('shows context settings panel', async () => {
    registerCopilotTool(registry, 'ext.a', 'tool.test', 'Test Tool', 'Testing', ['ui/summary']);
    renderPrompt();

    const contextBtn = screen.getByLabelText(/Context:/);
    await userEvent.click(contextBtn);

    expect(screen.getByText('Timeline Snapshot')).toBeTruthy();
    expect(screen.getByText('Current Selection')).toBeTruthy();
    expect(screen.getByText('Project Metadata')).toBeTruthy();
  });

  it('allows toggling context checkboxes', async () => {
    registerCopilotTool(registry, 'ext.a', 'tool.test', 'Test Tool', 'Testing', ['ui/summary']);
    renderPrompt();

    const contextBtn = screen.getByLabelText(/Context:/);
    await userEvent.click(contextBtn);

    const timelineCheckbox = screen.getByLabelText('Include Timeline Snapshot');
    expect(timelineCheckbox).toBeChecked();

    await userEvent.click(timelineCheckbox);
    expect(timelineCheckbox).not.toBeChecked();
  });

  it('shows chat surface diagnostics when competing tools exist', () => {
    registerCopilotTool(registry, 'ext.a', 'tool.good', 'Good Tool', 'A good tool', ['ui/summary']);
    // Add a competing chat-like tool
    registry.ingestAgentToolContribution('ext.bad', makeContribution({
      id: 'contrib-chat' as any,
      toolId: 'copilot',
      label: 'Copilot',
      resultFamilies: ['ui/summary'] as any,
    }));
    registry.registerTool('ext.bad', 'copilot', makeHandler(makeUISummaryResult('chat result')));

    renderPrompt();
    expect(screen.getByText('1')).toBeTruthy(); // The chat diag count badge
  });

  it('handles keyboard shortcut for send', async () => {
    const handler = vi.fn().mockResolvedValue(
      makeUISummaryResult('Done.'),
    );
    registry.ingestAgentToolContribution('ext.a', makeContribution({
      id: 'contrib-a' as any,
      toolId: 'tool.test',
      label: 'Test Tool',
      resultFamilies: ['ui/summary'] as any,
    }));
    registry.registerTool('ext.a', 'tool.test', handler);

    renderPrompt();
    const input = screen.getByPlaceholderText('Ask Test Tool…');
    await userEvent.type(input, 'test prompt');

    // Ctrl+Enter should not work with userEvent (needs metaKey)
    // Use fireEvent for keyboard shortcut
    fireEvent.keyDown(input, { key: 'Enter', metaKey: true });

    await waitFor(() => {
      expect(handler).toHaveBeenCalled();
    });
  });

  it('clears history on clear button', async () => {
    const handler = vi.fn().mockResolvedValue(
      makeUISummaryResult('Done.'),
    );
    registry.ingestAgentToolContribution('ext.a', makeContribution({
      id: 'contrib-a' as any,
      toolId: 'tool.test',
      label: 'Test Tool',
      resultFamilies: ['ui/summary'] as any,
    }));
    registry.registerTool('ext.a', 'tool.test', handler);

    renderPrompt();

    // Show history
    const historyBtn = screen.getByLabelText(/Show history/);
    await userEvent.click(historyBtn);

    // Send a prompt
    const input = screen.getByPlaceholderText('Ask Test Tool…');
    await userEvent.type(input, 'test');
    const sendBtn = screen.getByText('Send');
    await userEvent.click(sendBtn);

    await waitFor(() => {
      expect(screen.queryByText('test')).toBeTruthy();
    });

    // Clear
    const clearBtn = screen.getByLabelText('Clear history');
    await userEvent.click(clearBtn);

    expect(screen.getByText('No invocation history yet.')).toBeTruthy();
  });

  it('handles invocation error gracefully', async () => {
    const handler = vi.fn().mockRejectedValue(new Error('Network failure'));
    registry.ingestAgentToolContribution('ext.a', makeContribution({
      id: 'contrib-a' as any,
      toolId: 'tool.test',
      label: 'Test Tool',
      resultFamilies: ['ui/summary'] as any,
    }));
    registry.registerTool('ext.a', 'tool.test', handler);

    renderPrompt();
    const input = screen.getByPlaceholderText('Ask Test Tool…');
    await userEvent.type(input, 'test');
    const sendBtn = screen.getByText('Send');
    await userEvent.click(sendBtn);

    await waitFor(() => {
      expect(screen.getByText(/Network failure/)).toBeTruthy();
    });
  });

  it('renders accessible structure', () => {
    registerCopilotTool(registry, 'ext.a', 'tool.test', 'Test Tool', 'Testing', ['ui/summary']);
    renderPrompt();

    const region = screen.getByRole('region', { name: 'Copilot prompt' });
    expect(region).toBeTruthy();
    expect(region.getAttribute('data-video-editor-copilot-prompt')).toBe('true');
  });

  it('disables send when prompt is empty', () => {
    registerCopilotTool(registry, 'ext.a', 'tool.test', 'Test Tool', 'Testing', ['ui/summary']);
    renderPrompt();

    const sendBtn = screen.getByText('Send');
    expect(sendBtn).toBeDisabled();
  });

  it('enables send when prompt has text', async () => {
    registerCopilotTool(registry, 'ext.a', 'tool.test', 'Test Tool', 'Testing', ['ui/summary']);
    renderPrompt();

    const input = screen.getByPlaceholderText('Ask Test Tool…');
    await userEvent.type(input, 'Hello');

    const sendBtn = screen.getByText('Send');
    expect(sendBtn).not.toBeDisabled();
  });

  it('shows tool selector dropdown', async () => {
    registerCopilotTool(registry, 'ext.a', 'tool.alpha', 'Alpha Tool', 'First tool', ['ui/summary']);
    registerCopilotTool(registry, 'ext.b', 'tool.beta', 'Beta Tool', 'Second tool', ['mutation/proposal']);

    renderPrompt();
    const toolSelector = screen.getByLabelText(/Tool:/);
    await userEvent.click(toolSelector);

    // Both tool labels appear in the dropdown (multiple matches including selected)
    expect(screen.getAllByText('Alpha Tool').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Beta Tool').length).toBeGreaterThanOrEqual(1);
  });
});
