import { useState } from 'react';
import { useVideoEditorCommands, useVideoEditorHost, useVideoEditorTimeline } from '@/tools/video-editor/browser-provider.ts';
import { validateSequenceDraft } from '@/tools/video-editor/sequence.ts';
import { EMBED_DEMO_ASSET_KEYS } from './demoTimeline';

function formatStatusMessage(message: string) {
  return message.replace(/_/g, ' ');
}

export function EmbedDemoSidebar() {
  const host = useVideoEditorHost();
  const timeline = useVideoEditorTimeline();
  const commands = useVideoEditorCommands();
  const [message, setMessage] = useState('Ready. Insert a trusted sequence clip or replace a selection.');

  const handleInsertSequence = async () => {
    const validation = validateSequenceDraft({
      clipType: 'section-hook',
      hold: 3,
      params: {
        title: 'Build on the public SDK',
      },
    });

    if (!validation.ok) {
      setMessage(validation.errors.map((error) => error.message).join(' '));
      return;
    }

    const result = await commands.applySequenceDraft(validation.draft, { mode: 'insert' });
    setMessage(result.ok ? `Inserted ${result.clipId}.` : `Insert failed: ${formatStatusMessage(result.error)}.`);
  };

  const handleReplaceSelection = async () => {
    const validation = validateSequenceDraft({
      clipType: 'resource-card',
      hold: 3,
      params: {
        title: 'Example asset callout',
        previewAssetKeys: [...EMBED_DEMO_ASSET_KEYS],
      },
    }, { allowedAssetKeys: EMBED_DEMO_ASSET_KEYS });

    if (!validation.ok) {
      setMessage(validation.errors.map((error) => error.message).join(' '));
      return;
    }

    const result = await commands.applySequenceDraft(validation.draft, { mode: 'replace' });
    setMessage(result.ok ? `Replaced the selection with ${result.clipId}.` : `Replace failed: ${formatStatusMessage(result.error)}.`);
  };

  return (
    <aside className="embed-demo-sidebar">
      <div className="embed-demo-kicker">Standalone Host</div>
      <h1>Embed Demo</h1>
      <p className="embed-demo-copy">
        This panel is mounted with <code>renderLayout</code> and reads the editor through the supported browser hooks only.
      </p>

      <dl className="embed-demo-stats">
        <div>
          <dt>Timeline</dt>
          <dd>{timeline.timelineName}</dd>
        </div>
        <div>
          <dt>Timeline ID</dt>
          <dd>{host.timelineId}</dd>
        </div>
        <div>
          <dt>Clips</dt>
          <dd>{timeline.config?.clips.length ?? 0}</dd>
        </div>
        <div>
          <dt>Selection</dt>
          <dd>{timeline.selectedClipIds.length === 0 ? 'none' : timeline.selectedClipIds.join(', ')}</dd>
        </div>
        <div>
          <dt>Save</dt>
          <dd>{timeline.saveStatus}</dd>
        </div>
        <div>
          <dt>Render</dt>
          <dd>{timeline.renderStatus}</dd>
        </div>
      </dl>

      <div className="embed-demo-actions">
        <button type="button" onClick={() => commands.togglePlayPause()}>
          Play / Pause
        </button>
        <button type="button" onClick={() => commands.seek(Math.max(0, timeline.currentTime - 1))}>
          Seek -1s
        </button>
        <button type="button" onClick={() => commands.seek(timeline.currentTime + 1)}>
          Seek +1s
        </button>
        <button type="button" onClick={() => void handleInsertSequence()}>
          Insert section hook
        </button>
        <button
          type="button"
          disabled={timeline.selectedClipIds.length === 0}
          onClick={() => void handleReplaceSelection()}
        >
          Replace selection
        </button>
      </div>

      <p className="embed-demo-message">{message}</p>
    </aside>
  );
}
