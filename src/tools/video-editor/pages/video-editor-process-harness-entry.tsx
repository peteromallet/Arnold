import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import '@/index.css';
import VideoEditorProcessesHarnessPage from '@/tools/video-editor/pages/VideoEditorProcessesHarnessPage.tsx';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Process harness root element not found.');
}

createRoot(rootElement).render(
  <BrowserRouter>
    <VideoEditorProcessesHarnessPage />
  </BrowserRouter>,
);
