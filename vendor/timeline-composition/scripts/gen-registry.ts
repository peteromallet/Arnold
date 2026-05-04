#!/usr/bin/env -S npx --yes tsx
/**
 * Sprint 5 — generate `src/registry.generated.ts`.
 *
 * Discovery (directory-as-plugin pattern, mirrors tools/effects_catalog.py:139-155):
 *
 *   1. Reigh-side install: walk `node_modules/@banodoco/timeline-theme-*`
 *      (one or more theme packages installed as `file:` deps). For each
 *      package, read `theme.json` then enumerate
 *      `<pkg>/src/effects/<clipType>/component.tsx`.
 *
 *   2. Banodoco-side in-tree: walk `<workspace-root>/themes/<id>/effects/`.
 *      Used when the package is consumed from inside the banodoco-workspace
 *      directly — the build-time theme content lives here, not under
 *      node_modules. Detected when the workspace marker file
 *      (`<workspace-root>/themes/`) is present.
 *
 * The emitted file maps clipType → component import path. Reigh's
 * TimelineRenderer.tsx looks up clipType via this registry; the Banodoco
 * composition uses its own `effects.generated.ts` (codegenned by
 * gen_effect_registry.py) for its in-bundle rendering.
 *
 * Drift gate: pass `--check` to assert the regenerated file matches what's
 * on disk. Used by `scripts/ci-timeline-composition.sh`.
 */

import {readdirSync, readFileSync, statSync, writeFileSync, existsSync} from "node:fs";
import {dirname, join, relative, resolve} from "node:path";
import {fileURLToPath} from "node:url";

const __dirname_ = dirname(fileURLToPath(import.meta.url));
// scripts/ → package root one level up.
const PKG_DIR = resolve(__dirname_, "..");
const SRC_DIR = join(PKG_DIR, "typescript", "src");
const OUTPUT = join(SRC_DIR, "registry.generated.ts");

// Resolve workspace root by walking up from the package directory until
// we find a `themes/` directory (banodoco-workspace marker). If we don't
// find one we're being consumed from inside Reigh's node_modules — fall
// back to package-local discovery only.
function findWorkspaceRoot(start: string): string | null {
  let dir = start;
  for (let i = 0; i < 6; i += 1) {
    if (existsSync(join(dir, "themes")) && existsSync(join(dir, "tools"))) {
      return dir;
    }
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

// Find any `node_modules/@banodoco/timeline-theme-*` packages from PKG_DIR
// upward. When run inside banodoco-workspace this returns the linked
// timeline-theme-2rp; when run inside reigh-app's install it returns each
// installed theme package.
function findInstalledThemePackages(start: string): string[] {
  const found: string[] = [];
  let dir = start;
  for (let i = 0; i < 8; i += 1) {
    const ns = join(dir, "node_modules", "@banodoco");
    if (existsSync(ns)) {
      try {
        for (const entry of readdirSync(ns)) {
          if (!entry.startsWith("timeline-theme-")) continue;
          const pkgPath = join(ns, entry);
          if (statSync(pkgPath).isDirectory()) {
            found.push(pkgPath);
          }
        }
      } catch {
        // ignore
      }
    }
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return found;
}

type RegistryEntry = {
  clipType: string;
  themeId: string;
  componentName: string;
  importSpecifier: string;
  // For provenance/debug
  source: string;
};

function componentName(clipType: string, themeId: string): string {
  const camel = clipType
    .split("-")
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join("");
  const themeCamel = themeId
    .replace(/[^a-z0-9]/gi, "_")
    .split("_")
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join("");
  // Identifiers cannot start with a digit (theme ids like "2rp" do).
  // Prefix with `Theme_` to keep names valid JS identifiers.
  const safeTheme = /^[A-Za-z_]/.test(themeCamel) ? themeCamel : `Theme${themeCamel}`;
  return `${safeTheme}_${camel}`;
}

function scanPackageEffects(pkgDir: string): {themeId: string; effects: string[]} | null {
  const themeJsonPath = join(pkgDir, "theme.json");
  if (!existsSync(themeJsonPath)) return null;
  let themeJson: {id?: string};
  try {
    themeJson = JSON.parse(readFileSync(themeJsonPath, "utf8"));
  } catch {
    return null;
  }
  const themeId = themeJson.id;
  if (typeof themeId !== "string" || !themeId) return null;
  const effectsDir = join(pkgDir, "src", "effects");
  if (!existsSync(effectsDir)) return {themeId, effects: []};
  const effects: string[] = [];
  for (const entry of readdirSync(effectsDir)) {
    const componentPath = join(effectsDir, entry, "component.tsx");
    if (existsSync(componentPath)) effects.push(entry);
  }
  return {themeId, effects: effects.sort()};
}

function scanInTreeThemes(workspaceRoot: string): Array<{themeId: string; effects: string[]; root: string}> {
  const themesDir = join(workspaceRoot, "themes");
  if (!existsSync(themesDir)) return [];
  const out: Array<{themeId: string; effects: string[]; root: string}> = [];
  for (const entry of readdirSync(themesDir)) {
    const themeRoot = join(themesDir, entry);
    if (!statSync(themeRoot).isDirectory()) continue;
    const themeJsonPath = join(themeRoot, "theme.json");
    if (!existsSync(themeJsonPath)) continue;
    let themeJson: {id?: string};
    try {
      themeJson = JSON.parse(readFileSync(themeJsonPath, "utf8"));
    } catch {
      continue;
    }
    const themeId = themeJson.id ?? entry;
    const effectsDir = join(themeRoot, "effects");
    const effects: string[] = [];
    if (existsSync(effectsDir)) {
      for (const child of readdirSync(effectsDir)) {
        const cmp = join(effectsDir, child, "component.tsx");
        if (existsSync(cmp)) effects.push(child);
      }
    }
    out.push({themeId, effects: effects.sort(), root: themeRoot});
  }
  return out.sort((a, b) => a.themeId.localeCompare(b.themeId));
}

function buildEntries(): RegistryEntry[] {
  const entries: RegistryEntry[] = [];
  const installed = findInstalledThemePackages(PKG_DIR);
  for (const pkgDir of installed) {
    const scanned = scanPackageEffects(pkgDir);
    if (!scanned) continue;
    // Import from package name. Read the package.json `name`.
    let pkgName = "";
    try {
      const pj = JSON.parse(readFileSync(join(pkgDir, "package.json"), "utf8"));
      pkgName = pj.name ?? "";
    } catch {
      continue;
    }
    if (!pkgName) continue;
    for (const clipType of scanned.effects) {
      entries.push({
        clipType,
        themeId: scanned.themeId,
        componentName: componentName(clipType, scanned.themeId),
        importSpecifier: `${pkgName}/src/effects/${clipType}/component`,
        source: `installed:${pkgName}`,
      });
    }
  }
  // In-tree themes (banodoco-workspace consumption). These are NOT emitted
  // as registry entries when an installed package already covers the same
  // clipType — the installed package wins (mirrors theme-overrides logic in
  // effects_catalog.py:147-152).
  const seen = new Set(entries.map((e) => `${e.themeId}:${e.clipType}`));
  const wsRoot = findWorkspaceRoot(PKG_DIR);
  if (wsRoot) {
    const inTree = scanInTreeThemes(wsRoot);
    for (const t of inTree) {
      for (const clipType of t.effects) {
        const key = `${t.themeId}:${clipType}`;
        if (seen.has(key)) continue;
        const rel = relative(SRC_DIR, join(t.root, "effects", clipType, "component"));
        const importSpec = rel.startsWith(".") ? rel : `./${rel}`;
        entries.push({
          clipType,
          themeId: t.themeId,
          componentName: componentName(clipType, t.themeId),
          importSpecifier: importSpec,
          source: `in-tree:themes/${t.themeId}`,
        });
        seen.add(key);
      }
    }
  }
  // Stable sort: clipType then themeId.
  return entries.sort((a, b) => {
    if (a.clipType !== b.clipType) return a.clipType.localeCompare(b.clipType);
    return a.themeId.localeCompare(b.themeId);
  });
}

function dedupeByClipType(entries: RegistryEntry[]): RegistryEntry[] {
  // First-write-wins per clipType: if multiple themes claim the same
  // clipType, the first-encountered (alphabetic by theme) becomes the
  // registry entry. Reigh and Banodoco accept that the first installed
  // theme owns ambiguous clipTypes; downstream we surface the others as
  // aliases. Sprint 5 v1: just take the first.
  const seen = new Set<string>();
  return entries.filter((e) => {
    if (seen.has(e.clipType)) return false;
    seen.add(e.clipType);
    return true;
  });
}

function render(entries: RegistryEntry[]): string {
  const deduped = dedupeByClipType(entries);
  const imports = deduped.map(
    (e) => `import ${e.componentName} from '${e.importSpecifier}';`,
  );
  const tableEntries = deduped.map(
    (e) =>
      `  '${e.clipType}': {component: ${e.componentName}, themeId: '${e.themeId}', source: '${e.source}'},`,
  );
  const ids = deduped.map((e) => `'${e.clipType}'`).join(", ");
  const lines = [
    "// DO NOT EDIT — generated by packages/timeline-composition/scripts/gen-registry.ts.",
    "// Discovery walks node_modules/@banodoco/timeline-theme-* (Reigh-side) and",
    "// themes/<id>/effects/ (Banodoco-side). Drift gate: scripts/ci-timeline-composition.sh",
    "// runs gen-registry --check pre-test.",
    "",
    // Use `unknown` for the component type so we don't impose a specific",
    // EffectProps shape — theme components are typed against their own",
    // params, and the dispatch in TimelineRenderer / TimelineComposition",
    // narrows at the call site.",
    "/* eslint-disable @typescript-eslint/no-explicit-any */",
    ...imports,
    "",
    "export type ThemePackageRegistryEntry = {",
    "  component: any;",
    "  themeId: string;",
    "  source: string;",
    "};",
    "",
    `export const THEME_PACKAGE_CLIP_TYPES = [${ids}] as const;`,
    "export type ThemePackageClipType = typeof THEME_PACKAGE_CLIP_TYPES[number];",
    "",
    "export const THEME_PACKAGE_REGISTRY: Record<ThemePackageClipType, ThemePackageRegistryEntry> = {",
    ...tableEntries,
    "};",
    "",
  ];
  return lines.join("\n");
}

function main(): void {
  const checkOnly = process.argv.includes("--check");
  const entries = buildEntries();
  const next = render(entries);
  if (checkOnly) {
    const cur = existsSync(OUTPUT) ? readFileSync(OUTPUT, "utf8") : "";
    if (cur === next) {
      console.log("registry.generated.ts up-to-date");
      process.exit(0);
    }
    console.error("registry.generated.ts is stale. Run `npm run gen-registry`.");
    process.exit(1);
  }
  writeFileSync(OUTPUT, next, "utf8");
  console.log(`Wrote ${relative(PKG_DIR, OUTPUT)} (${entries.length} entr${entries.length === 1 ? "y" : "ies"} pre-dedupe).`);
}

main();
