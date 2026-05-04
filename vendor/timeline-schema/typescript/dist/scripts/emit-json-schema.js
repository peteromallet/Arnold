import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { zodToJsonSchema } from "zod-to-json-schema";
import { TimelineConfig, TimelineClip, Theme, ThemeOverrides, TimelineOutput, AssetEntry, } from "../src/schemas.js";
const here = dirname(fileURLToPath(import.meta.url));
// dist/scripts/ -> packages/timeline-schema/
const pkgRoot = resolve(here, "../../..");
function inline(schema) {
    const obj = schema;
    const { $schema: _drop, ...rest } = obj;
    void _drop;
    return rest;
}
const fullSchema = {
    $schema: "http://json-schema.org/draft-07/schema#",
    $ref: "#/definitions/TimelineConfig",
    definitions: {
        TimelineConfig: inline(zodToJsonSchema(TimelineConfig, { $refStrategy: "none" })),
        TimelineClip: inline(zodToJsonSchema(TimelineClip, { $refStrategy: "none" })),
        Theme: inline(zodToJsonSchema(Theme, { $refStrategy: "none" })),
        ThemeOverrides: inline(zodToJsonSchema(ThemeOverrides, { $refStrategy: "none" })),
        TimelineOutput: inline(zodToJsonSchema(TimelineOutput, { $refStrategy: "none" })),
        AssetEntry: inline(zodToJsonSchema(AssetEntry, { $refStrategy: "none" })),
    },
};
const pkgOutDir = resolve(pkgRoot, "python/banodoco_timeline_schema");
mkdirSync(pkgOutDir, { recursive: true });
const pkgOutPath = resolve(pkgOutDir, "timeline.schema.json");
writeFileSync(pkgOutPath, JSON.stringify(fullSchema, null, 2) + "\n", "utf8");
const tsOutDir = resolve(pkgRoot, "typescript/dist");
mkdirSync(tsOutDir, { recursive: true });
writeFileSync(resolve(tsOutDir, "timeline.schema.json"), JSON.stringify(fullSchema, null, 2) + "\n", "utf8");
console.log(`wrote ${pkgOutPath}`);
//# sourceMappingURL=emit-json-schema.js.map