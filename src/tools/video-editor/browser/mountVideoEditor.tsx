import { createRoot, type Root } from 'react-dom/client';
import { BrowserVideoEditor, type BrowserVideoEditorProps } from '@/tools/video-editor/browser/BrowserVideoEditor.tsx';

export interface MountedVideoEditor {
  update(nextProps: BrowserVideoEditorProps): void;
  unmount(): void;
}

/**
 * @publicContract
 * Imperative browser bootstrap for embedding the editor into a host DOM node.
 */
export function mountVideoEditor(
  container: Element,
  props: BrowserVideoEditorProps,
): MountedVideoEditor {
  const root: Root = createRoot(container);

  const render = (nextProps: BrowserVideoEditorProps) => {
    root.render(<BrowserVideoEditor {...nextProps} />);
  };

  render(props);

  return {
    update(nextProps) {
      render(nextProps);
    },
    unmount() {
      root.unmount();
    },
  };
}
