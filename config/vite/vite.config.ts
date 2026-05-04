import { defineConfig, createLogger } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import {
  manualVendorChunk,
  PREVIEW_ALLOWED_HOSTS,
  resolveVitePort,
} from "./policy";

const logger = createLogger();
const originalWarn = logger.warn.bind(logger);
logger.warn = (msg, options) => {
  if (msg.includes('postcss.parse') && msg.includes('from')) return;
  originalWarn(msg, options);
};

export default defineConfig(() => {
  const port = resolveVitePort(process.env.PORT);

  return {
    customLogger: logger,
    server: {
      host: "::",
      port: port,
      // Sprint 5: allow Vite to read from the sibling banodoco-workspace
      // (timeline-theme-2rp file: link).
      fs: {
        allow: [path.resolve(__dirname, "../../../..")],
      },
    },
    preview: {
      host: "0.0.0.0",
      port: port,
      allowedHosts: [...PREVIEW_ALLOWED_HOSTS],
    },
    plugins: [
      react(),
    ].filter(Boolean),
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "../../src"),
        // Sprint 5: deduplicate React / Remotion / @banodoco/* across the
        // linked timeline-composition + timeline-theme-* packages so a
        // single React runtime drives the @remotion/player preview.
        "react": path.resolve(__dirname, "../../node_modules/react"),
        "react-dom": path.resolve(__dirname, "../../node_modules/react-dom"),
        "remotion": path.resolve(__dirname, "../../node_modules/remotion"),
        "@remotion/layout-utils": path.resolve(__dirname, "../../node_modules/@remotion/layout-utils"),
        "@banodoco/timeline-composition/registry.generated": path.resolve(
          __dirname,
          "../../node_modules/@banodoco/timeline-composition/typescript/src/registry.generated.ts",
        ),
        "@banodoco/timeline-composition/theme-api": path.resolve(
          __dirname,
          "../../node_modules/@banodoco/timeline-composition/typescript/src/theme-api.ts",
        ),
        "@banodoco/timeline-composition": path.resolve(__dirname, "../../node_modules/@banodoco/timeline-composition"),
        // Workspace-primitive aliases (mirrors banodoco shell webpack-alias.mjs).
        // Vendored into reigh-app/vendor/ so the Docker build context can resolve them
        // — the original ../../../../banodoco-workspace paths sit outside the build context.
        "@workspace-effects": path.resolve(__dirname, "../../vendor/banodoco-effects"),
        "@workspace-animations": path.resolve(__dirname, "../../vendor/banodoco-animations"),
        "@workspace-transitions": path.resolve(__dirname, "../../vendor/banodoco-transitions"),
      },
      dedupe: ['react', 'react-dom', 'react-reconciler', 'remotion', '@banodoco/timeline-composition', '@banodoco/timeline-theme-2rp'],
    },
    build: {
      outDir: "dist",
      sourcemap: true,
      rollupOptions: {
        output: {
          manualChunks: manualVendorChunk,
        }
      }
    },
    optimizeDeps: {
      exclude: ["@ffmpeg/ffmpeg", "@ffmpeg/util"],
    },
  };
});
