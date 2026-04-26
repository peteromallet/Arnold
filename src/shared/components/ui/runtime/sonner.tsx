import { Toast } from "@base-ui/react/toast";
import { ToastItem, toast } from "@/shared/components/ui/toast";
import { getToastManager } from '@/shared/runtime/toastRuntime';
import { UI_Z_LAYERS } from '@/shared/lib/uiLayers';

interface ToasterProps {
  /** Max toasts visible at once. @default 3 */
  limit?: number;
  /** Default timeout in ms. @default 5000 */
  timeout?: number;
}

function ToastList() {
  const { toasts } = Toast.useToastManager();

  return (
    <Toast.Viewport
      // pointer-events-none so the bottom-right region (which sits at
      // z-TOAST_VIEWPORT, above the action pane / chat) doesn't block clicks
      // when no toast is visible. Individual ToastItems re-enable pointer
      // events with their own `pointer-events-auto`.
      className="fixed bottom-0 right-0 flex max-h-screen w-full flex-col gap-2 p-4 pointer-events-none md:max-w-[420px]"
      style={{ zIndex: UI_Z_LAYERS.TOAST_VIEWPORT }}
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </Toast.Viewport>
  );
}

const Toaster = ({ limit = 3, timeout = 5000 }: ToasterProps = {}) => {
  const toastManager = getToastManager();

  return (
    <Toast.Provider toastManager={toastManager} timeout={timeout} limit={limit}>
      <ToastList />
    </Toast.Provider>
  );
};

export { Toaster, toast };
