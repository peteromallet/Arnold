#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

const rootDir = process.cwd();
const targetEntries = [
  'src/tools/video-editor/core',
  'src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.tsx',
  'src/tools/video-editor/components/TimelineEditorShellCore.tsx',
];

const forbiddenImports = [
  {
    label: 'ProjectContext',
    pattern: /from\s+['"]@\/shared\/contexts\/ProjectContext['"]/g,
  },
  {
    label: 'ShotsContext',
    pattern: /from\s+['"]@\/shared\/contexts\/ShotsContext['"]/g,
  },
  {
    label: 'AgentChatContext',
    pattern: /from\s+['"]@\/shared\/contexts\/AgentChatContext['"]/g,
  },
  {
    label: 'react-router-dom',
    pattern: /from\s+['"]react-router-dom['"]/g,
  },
  {
    label: '@/domains/media-lightbox',
    pattern: /from\s+['"]@\/domains\/media-lightbox(?:\/[^'"]*)?['"]/g,
  },
];

function collectTargetFiles(entryPath: string, files: string[] = []) {
  const absolutePath = path.join(rootDir, entryPath);
  if (!fs.existsSync(absolutePath)) {
    return files;
  }

  const stats = fs.statSync(absolutePath);
  if (stats.isDirectory()) {
    for (const child of fs.readdirSync(absolutePath, { withFileTypes: true })) {
      if (child.name.startsWith('.')) continue;
      collectTargetFiles(path.join(entryPath, child.name), files);
    }
    return files;
  }

  if (!absolutePath.endsWith('.ts') && !absolutePath.endsWith('.tsx')) {
    return files;
  }
  if (absolutePath.endsWith('.test.ts') || absolutePath.endsWith('.test.tsx')) {
    return files;
  }

  files.push(absolutePath);
  return files;
}

const files = targetEntries.flatMap((entry) => collectTargetFiles(entry));
const failures: Array<{ file: string; label: string; count: number }> = [];

for (const file of files) {
  const content = fs.readFileSync(file, 'utf8');
  for (const rule of forbiddenImports) {
    const count = content.match(rule.pattern)?.length ?? 0;
    if (count > 0) {
      failures.push({
        file: path.relative(rootDir, file),
        label: rule.label,
        count,
      });
    }
  }
}

if (failures.length > 0) {
  console.error('[video-editor-core-imports] FAILED: forbidden host imports found in headless core files.');
  for (const failure of failures) {
    console.error(`  - ${failure.file}: ${failure.label} (${failure.count})`);
  }
  process.exit(1);
}

console.log(`[video-editor-core-imports] OK: ${files.length} headless core file(s) passed the host import boundary check.`);
