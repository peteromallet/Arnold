import { defineConfig } from 'vitest/config';
import path from 'path';
import fs from 'fs';

const projectRoot = path.resolve(__dirname, '../..');
const timelineCompositionRegistryPath = path.resolve(
  projectRoot,
  'node_modules/@banodoco/timeline-composition/typescript/src/registry.generated.ts',
);
const timelineCompositionThemeApiPath = path.resolve(
  projectRoot,
  'node_modules/@banodoco/timeline-composition/typescript/src/theme-api.ts',
);

const resolvedTimelineCompositionRegistryPath = fs.existsSync(timelineCompositionRegistryPath)
  ? timelineCompositionRegistryPath
  : path.resolve(projectRoot, 'examples/embed-demo/stubs/timeline-composition/registry.generated.ts');

const resolvedTimelineCompositionThemeApiPath = fs.existsSync(timelineCompositionThemeApiPath)
  ? timelineCompositionThemeApiPath
  : path.resolve(projectRoot, 'examples/embed-demo/stubs/timeline-composition/theme-api.tsx');

export default defineConfig({
  root: projectRoot,
  resolve: {
    alias: {
      '@': path.resolve(projectRoot, 'src'),
      '@reigh/editor-sdk': path.resolve(projectRoot, 'src/sdk'),
      'fake-indexeddb': path.resolve(projectRoot, 'vendor/fake-indexeddb/index.js'),
      // Sprint 5: deduplicate react / remotion / @banodoco/* across linked
      // packages. The timeline-theme-2rp peer-dep package lives at a
      // file: link outside this app's node_modules tree; Vite's nearest-
      // node_modules resolution would otherwise pick up the package's
      // own copies (or fail when none exists). Pinning these to the
      // app's node_modules guarantees a single React/Remotion runtime.
      'react': path.resolve(projectRoot, 'node_modules/react'),
      'react-dom': path.resolve(projectRoot, 'node_modules/react-dom'),
      'remotion': path.resolve(projectRoot, 'node_modules/remotion'),
      '@remotion/layout-utils': path.resolve(projectRoot, 'node_modules/@remotion/layout-utils'),
      '@banodoco/timeline-composition/registry.generated': resolvedTimelineCompositionRegistryPath,
      '@banodoco/timeline-composition/theme-api': resolvedTimelineCompositionThemeApiPath,
      '@banodoco/timeline-composition': path.resolve(projectRoot, 'node_modules/@banodoco/timeline-composition'),
      '@banodoco/timeline-schema': path.resolve(projectRoot, 'node_modules/@banodoco/timeline-schema/typescript/dist/src/index.js'),
      // Sprint 5: workspace-primitive aliases for the linked packages.
      // The composition package's animations.generated / transitions.generated
      // / effects.generated import via these aliases. Reigh's bundler needs
      // them to resolve; Banodoco's webpack already does the same.
      '@workspace-effects': path.resolve(projectRoot, 'vendor/banodoco-effects'),
      '@workspace-animations': path.resolve(projectRoot, 'vendor/banodoco-animations'),
      '@workspace-transitions': path.resolve(projectRoot, 'vendor/banodoco-transitions'),
    },
    dedupe: [
      'react',
      'react-dom',
      'remotion',
      '@remotion/layout-utils',
      '@banodoco/timeline-composition',
      '@banodoco/timeline-theme-2rp',
    ],
  },
  esbuild: {
    jsx: 'automatic',
    jsxImportSource: 'react',
    // Sprint 5: also transform JSX in linked workspace packages so the
    // physically-moved TimelineComposition / theme-2rp components compile.
    include: [/\.[jt]sx?$/, /banodoco-workspace\/.*\.[jt]sx?$/],
    loader: 'tsx',
  },
  server: {
    fs: {
      // Allow Vite to read from sibling banodoco-workspace.
      allow: [path.resolve(projectRoot, '..', '..')],
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    include: ['src/sdk/__tests__/*.test.{ts,tsx}'],
    exclude: ['supabase/functions/**'],
    setupFiles: [path.resolve(projectRoot, 'src/test/setup.ts')],
  },
});
