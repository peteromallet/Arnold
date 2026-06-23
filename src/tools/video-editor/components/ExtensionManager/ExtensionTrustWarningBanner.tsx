import { AlertTriangle } from 'lucide-react';

export function ExtensionTrustWarningBanner() {
  return (
    <div
      className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-3 py-2 text-xs text-yellow-200"
      role="note"
      aria-label="Extension trust warning"
      data-video-editor-extension-trust-warning="true"
    >
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-yellow-400" aria-hidden="true" />
        <div className="min-w-0">
          <div className="font-medium text-yellow-100">Trusted extension code</div>
          <div className="mt-0.5 text-yellow-200/80">
            Extensions run as trusted, unsandboxed code. Manifest permissions are declarative and are not enforced at runtime.
          </div>
        </div>
      </div>
    </div>
  );
}
