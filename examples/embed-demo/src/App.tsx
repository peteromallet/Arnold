import type { ReactNode } from 'react';
import { useState } from 'react';
import { BrowserVideoEditorProvider } from '@/tools/video-editor/browser-provider.ts';
import { EmbedDemoSidebar } from './EmbedDemoSidebar';
import { createEmbedDemoServices } from './demoServices';
import { EMBED_DEMO_TIMELINE_ID, EMBED_DEMO_TIMELINE_NAME } from './demoTimeline';

function DemoLayout({ children }: { children: ReactNode }) {
  return (
    <div className="embed-demo-shell">
      <EmbedDemoSidebar />
      <div className="embed-demo-stage">{children}</div>
    </div>
  );
}

export function App() {
  const [services] = useState(() => createEmbedDemoServices());

  return (
    <BrowserVideoEditorProvider
      dataProvider={services.dataProvider}
      timelineId={EMBED_DEMO_TIMELINE_ID}
      timelineName={EMBED_DEMO_TIMELINE_NAME}
      effectCatalog={services.effectCatalog}
      assetResolver={services.assetResolver}
    >
      <DemoLayout>
        <main className="embed-demo-custom-shell">
          <div className="embed-demo-hero">
            <span className="embed-demo-kicker">Public hooks only</span>
            <h2>Build a custom host around the supported browser provider.</h2>
            <p>
              This embed demo skips the internal Reigh shell and drives the timeline through
              <code> useVideoEditorTimeline()</code> and <code>useVideoEditorCommands()</code>.
            </p>
          </div>
        </main>
      </DemoLayout>
    </BrowserVideoEditorProvider>
  );
}

export default App;
