/**
 * @banodoco/timeline-theme-2rp — top-level barrel.
 *
 * The primary surface is the per-clipType component sub-paths
 * (`./src/effects/<clipType>/component`) — that's what
 * @banodoco/timeline-composition's gen-registry codegen walks. This
 * barrel exists for downstream consumers that want a one-import surface
 * (e.g. tests, manual composition).
 */

export {default as SectionHook} from "./effects/section-hook/component";
export {default as ArtCard} from "./effects/art-card/component";
export {default as CtaCard} from "./effects/cta-card/component";
export {default as ResourceCard} from "./effects/resource-card/component";

import themeJson from "../theme.json" with {type: "json"};
export const themeMetadata = themeJson;
