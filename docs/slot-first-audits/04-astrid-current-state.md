# Slot-First M0 Audit 04: Astrid Current State

Generated: 2026-05-20T09:27:35Z

## Scope

This audit covers every file currently present under `supabase/functions/ai-timeline-agent/`. The required legacy-reference search output is recorded verbatim, and every hit file is marked as an M3 work item.

## File Inventory

Command:
```bash
find supabase/functions/ai-timeline-agent -type f | sort
```

Count: 34 files (16 root, 2 `llm/`, 16 `tools/`).

Output:
```
supabase/functions/ai-timeline-agent/command-parser.test.ts
supabase/functions/ai-timeline-agent/command-parser.ts
supabase/functions/ai-timeline-agent/config.ts
supabase/functions/ai-timeline-agent/db.ts
supabase/functions/ai-timeline-agent/index.ts
supabase/functions/ai-timeline-agent/llm/client.ts
supabase/functions/ai-timeline-agent/llm/messages.ts
supabase/functions/ai-timeline-agent/loop.test.ts
supabase/functions/ai-timeline-agent/loop.ts
supabase/functions/ai-timeline-agent/prompts.ts
supabase/functions/ai-timeline-agent/public-sdk.acceptance.test.ts
supabase/functions/ai-timeline-agent/selectedClips.test.ts
supabase/functions/ai-timeline-agent/selectedClips.ts
supabase/functions/ai-timeline-agent/tool-calls.test.ts
supabase/functions/ai-timeline-agent/tool-calls.ts
supabase/functions/ai-timeline-agent/tool-schemas.ts
supabase/functions/ai-timeline-agent/tools/clips.test.ts
supabase/functions/ai-timeline-agent/tools/clips.ts
supabase/functions/ai-timeline-agent/tools/create-task.test.ts
supabase/functions/ai-timeline-agent/tools/create-task.ts
supabase/functions/ai-timeline-agent/tools/delegateToBanodocoAgent.test.ts
supabase/functions/ai-timeline-agent/tools/delegateToBanodocoAgent.ts
supabase/functions/ai-timeline-agent/tools/duplicate-generation.ts
supabase/functions/ai-timeline-agent/tools/generation.ts
supabase/functions/ai-timeline-agent/tools/llm-schema-snapshot.test.ts
supabase/functions/ai-timeline-agent/tools/loras.ts
supabase/functions/ai-timeline-agent/tools/registry.ts
supabase/functions/ai-timeline-agent/tools/session.ts
supabase/functions/ai-timeline-agent/tools/timeline.test.ts
supabase/functions/ai-timeline-agent/tools/timeline.ts
supabase/functions/ai-timeline-agent/tools/transform-image.test.ts
supabase/functions/ai-timeline-agent/tools/transform-image.ts
supabase/functions/ai-timeline-agent/types.ts
supabase/functions/ai-timeline-agent/utils.ts
```

Line-count probe:
```bash
find supabase/functions/ai-timeline-agent -type f | sort | xargs wc -l
```

Output:
```
    81 supabase/functions/ai-timeline-agent/command-parser.test.ts
   326 supabase/functions/ai-timeline-agent/command-parser.ts
    18 supabase/functions/ai-timeline-agent/config.ts
   865 supabase/functions/ai-timeline-agent/db.ts
   104 supabase/functions/ai-timeline-agent/index.ts
   343 supabase/functions/ai-timeline-agent/llm/client.ts
   192 supabase/functions/ai-timeline-agent/llm/messages.ts
   751 supabase/functions/ai-timeline-agent/loop.test.ts
   901 supabase/functions/ai-timeline-agent/loop.ts
   260 supabase/functions/ai-timeline-agent/prompts.ts
   164 supabase/functions/ai-timeline-agent/public-sdk.acceptance.test.ts
   481 supabase/functions/ai-timeline-agent/selectedClips.test.ts
   247 supabase/functions/ai-timeline-agent/selectedClips.ts
    52 supabase/functions/ai-timeline-agent/tool-calls.test.ts
   252 supabase/functions/ai-timeline-agent/tool-calls.ts
   518 supabase/functions/ai-timeline-agent/tool-schemas.ts
   198 supabase/functions/ai-timeline-agent/tools/clips.test.ts
   188 supabase/functions/ai-timeline-agent/tools/clips.ts
   536 supabase/functions/ai-timeline-agent/tools/create-task.test.ts
   624 supabase/functions/ai-timeline-agent/tools/create-task.ts
   414 supabase/functions/ai-timeline-agent/tools/delegateToBanodocoAgent.test.ts
   374 supabase/functions/ai-timeline-agent/tools/delegateToBanodocoAgent.ts
    70 supabase/functions/ai-timeline-agent/tools/duplicate-generation.ts
   434 supabase/functions/ai-timeline-agent/tools/generation.ts
   405 supabase/functions/ai-timeline-agent/tools/llm-schema-snapshot.test.ts
   306 supabase/functions/ai-timeline-agent/tools/loras.ts
   727 supabase/functions/ai-timeline-agent/tools/registry.ts
    28 supabase/functions/ai-timeline-agent/tools/session.ts
   502 supabase/functions/ai-timeline-agent/tools/timeline.test.ts
   863 supabase/functions/ai-timeline-agent/tools/timeline.ts
   124 supabase/functions/ai-timeline-agent/tools/transform-image.test.ts
   157 supabase/functions/ai-timeline-agent/tools/transform-image.ts
   239 supabase/functions/ai-timeline-agent/types.ts
    19 supabase/functions/ai-timeline-agent/utils.ts
 11763 total
```

## Required Legacy-Reference Search

Command:
```bash
rg -l "generation_id|variant_id|generations|generation_variants" supabase/functions/ai-timeline-agent/ | sort
```

Hit-file count: 17

Full output:
```
supabase/functions/ai-timeline-agent/command-parser.ts
supabase/functions/ai-timeline-agent/llm/client.ts
supabase/functions/ai-timeline-agent/loop.test.ts
supabase/functions/ai-timeline-agent/loop.ts
supabase/functions/ai-timeline-agent/prompts.ts
supabase/functions/ai-timeline-agent/selectedClips.test.ts
supabase/functions/ai-timeline-agent/selectedClips.ts
supabase/functions/ai-timeline-agent/tool-schemas.ts
supabase/functions/ai-timeline-agent/tools/clips.test.ts
supabase/functions/ai-timeline-agent/tools/clips.ts
supabase/functions/ai-timeline-agent/tools/create-task.test.ts
supabase/functions/ai-timeline-agent/tools/create-task.ts
supabase/functions/ai-timeline-agent/tools/duplicate-generation.ts
supabase/functions/ai-timeline-agent/tools/generation.ts
supabase/functions/ai-timeline-agent/tools/transform-image.test.ts
supabase/functions/ai-timeline-agent/tools/transform-image.ts
supabase/functions/ai-timeline-agent/types.ts
```

Line-level context command:
```bash
rg -n "generation_id|variant_id|generations|generation_variants" supabase/functions/ai-timeline-agent/ | sort
```

Line-level output:
```
supabase/functions/ai-timeline-agent/command-parser.ts:127:    return { type: "error", message: "Usage: add-media <track> <at> <generation_id> <url> [--type image|video]" };
supabase/functions/ai-timeline-agent/command-parser.ts:147:    return { type: "error", message: "Usage: swap <clipId> <generation_id> <url> [--type image|video]" };
supabase/functions/ai-timeline-agent/llm/client.ts:41:hard = complex creative direction, generating content, duplicating generations, adding media from generations, compound multi-tool workflows (duplicate then add), intricate multi-track choreography, troubleshooting broken timelines, anything requiring deep reasoning
supabase/functions/ai-timeline-agent/loop.test.ts:148:      args: { generation_id: "gen-1", flip_horizontal: true },
supabase/functions/ai-timeline-agent/loop.test.ts:152:      { generation_id: "gen-1", flip_horizontal: true },
supabase/functions/ai-timeline-agent/loop.test.ts:213:      args: { generation_id: "gen-abc" },
supabase/functions/ai-timeline-agent/loop.test.ts:218:      { generation_id: "gen-abc" },
supabase/functions/ai-timeline-agent/loop.test.ts:417:      generation_id: "gen-new",
supabase/functions/ai-timeline-agent/loop.ts:212:    ...(clip.generation_id ? { generationId: clip.generation_id } : {}),
supabase/functions/ai-timeline-agent/loop.ts:326:        ...(generationId ? { generation_id: generationId } : {}),
supabase/functions/ai-timeline-agent/loop.ts:376:  const generationIds = asStringArray(args.generation_ids);
supabase/functions/ai-timeline-agent/loop.ts:383:    return { result: "create_shot requires at least one generation_id." };
supabase/functions/ai-timeline-agent/prompts.ts:183:Use duplicate_generation({"generation_id":"..."}) to copy an existing generation instantly when the user wants a non-destructive derivative or alternate edit path.
supabase/functions/ai-timeline-agent/prompts.ts:201:Step 1: duplicate_generation({"generation_id":"<id>"}) → returns new_generation_id, asset URL, type
supabase/functions/ai-timeline-agent/prompts.ts:202:Step 2 (optional edits): create_task({..., "based_on":"<new_generation_id>", "reference_image_urls":["<asset URL>"]})
supabase/functions/ai-timeline-agent/prompts.ts:203:Step 3 (place on timeline): run(command="add-media <track> <at> <new_generation_id> <asset_url> [--type video]")
supabase/functions/ai-timeline-agent/prompts.ts:207:- add-media <track> <at> <generation_id> <url> [--type video]
supabase/functions/ai-timeline-agent/prompts.ts:248:transform_image({"generation_id":"11111111-1111-1111-1111-111111111111","source_image_url":"https://example.com/source-image.png","flip_horizontal":true})
supabase/functions/ai-timeline-agent/prompts.ts:249:transform_image({"generation_id":"11111111-1111-1111-1111-111111111111","source_image_url":"https://example.com/source-image.png","translate_x":-12,"scale":1.2,"rotation":15})
supabase/functions/ai-timeline-agent/prompts.ts:250:duplicate_generation({"generation_id":"11111111-1111-1111-1111-111111111111"})
supabase/functions/ai-timeline-agent/prompts.ts:251:create_shot({"shot_name":"Hero shots","generation_ids":["gen-1","gen-2"]})
supabase/functions/ai-timeline-agent/prompts.ts:57:    const generationText = typeof clip.generation_id === "string" && clip.generation_id.trim()
supabase/functions/ai-timeline-agent/prompts.ts:58:      ? ` | generation_id=${clip.generation_id}`
supabase/functions/ai-timeline-agent/selectedClips.test.ts:107:      generation_id: 'gen-4',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:119:      generation_id: 'gen-4',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:172:  it('does not treat gallery clip ids as timeline anchors even when variant_id is present', () => {
supabase/functions/ai-timeline-agent/selectedClips.test.ts:182:      generation_id: 'gen-2',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:183:      variant_id: 'variant-2',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:191:      generation_id: 'gen-2',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:192:      variant_id: 'variant-2',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:212:      generation_id: 'gen-1',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:213:      variant_id: 'variant-1',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:224:      generation_id: 'gen-1',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:225:      variant_id: 'variant-1',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:285:        generation_id: 'gen-2',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:286:        variant_id: 'variant-2',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:292:        generation_id: 'gen-3',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:300:        generation_id: 'gen-2',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:301:        variant_id: 'variant-2',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:311:        generation_id: 'gen-3',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:323:  it('adds prompt metadata for clips with generation_id using one batched generations query', async () => {
supabase/functions/ai-timeline-agent/selectedClips.test.ts:344:      { clip_id: 'clip-1', generation_id: 'gen-1', url: 'https://example.com/1.png', media_type: 'image' },
supabase/functions/ai-timeline-agent/selectedClips.test.ts:345:      { clip_id: 'clip-2', generation_id: 'gen-2', url: 'https://example.com/2.png', media_type: 'video' },
supabase/functions/ai-timeline-agent/selectedClips.test.ts:346:      { clip_id: 'clip-3', generation_id: 'gen-1', url: 'https://example.com/3.png', media_type: 'image' },
supabase/functions/ai-timeline-agent/selectedClips.test.ts:348:      { clip_id: 'clip-1', generation_id: 'gen-1', url: 'https://example.com/1.png', media_type: 'image', prompt: 'style prompt' },
supabase/functions/ai-timeline-agent/selectedClips.test.ts:349:      { clip_id: 'clip-2', generation_id: 'gen-2', url: 'https://example.com/2.png', media_type: 'video', prompt: 'fallback prompt' },
supabase/functions/ai-timeline-agent/selectedClips.test.ts:34:  it('keeps clip ids for timeline attachments and includes generation_id when present', () => {
supabase/functions/ai-timeline-agent/selectedClips.test.ts:350:      { clip_id: 'clip-3', generation_id: 'gen-1', url: 'https://example.com/3.png', media_type: 'image', prompt: 'style prompt' },
supabase/functions/ai-timeline-agent/selectedClips.test.ts:353:    expect(fromMock).toHaveBeenCalledWith('generations');
supabase/functions/ai-timeline-agent/selectedClips.test.ts:359:  it('passes clips through unchanged when none have generation_id', async () => {
supabase/functions/ai-timeline-agent/selectedClips.test.ts:362:      variant_id: 'variant-1',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:379:      { clip_id: 'clip-1', generation_id: 'gen-1', url: 'https://example.com/1.png', media_type: 'image' },
supabase/functions/ai-timeline-agent/selectedClips.test.ts:37:      generation_id: 'gen-1',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:380:      { clip_id: 'clip-2', generation_id: 'gen-2', url: 'https://example.com/2.png', media_type: 'video' },
supabase/functions/ai-timeline-agent/selectedClips.test.ts:382:      { clip_id: 'clip-1', generation_id: 'gen-1', url: 'https://example.com/1.png', media_type: 'image' },
supabase/functions/ai-timeline-agent/selectedClips.test.ts:383:      { clip_id: 'clip-2', generation_id: 'gen-2', url: 'https://example.com/2.png', media_type: 'video' },
supabase/functions/ai-timeline-agent/selectedClips.test.ts:38:      variant_id: 'variant-1',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:417:      { clip_id: 'clip-1', generation_id: 'gen-1', url: 'https://example.com/1.png', media_type: 'image' },
supabase/functions/ai-timeline-agent/selectedClips.test.ts:418:      { clip_id: 'clip-2', generation_id: 'gen-2', url: 'https://example.com/2.png', media_type: 'image' },
supabase/functions/ai-timeline-agent/selectedClips.test.ts:420:      { clip_id: 'clip-1', generation_id: 'gen-1', url: 'https://example.com/1.png', media_type: 'image', prompt: 'orchestrator prompt' },
supabase/functions/ai-timeline-agent/selectedClips.test.ts:421:      { clip_id: 'clip-2', generation_id: 'gen-2', url: 'https://example.com/2.png', media_type: 'image', prompt: 'metadata only prompt' },
supabase/functions/ai-timeline-agent/selectedClips.test.ts:43:      generation_id: 'gen-1',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:44:      variant_id: 'variant-1',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:50:  it('preserves the exact timeline clip id while trimming variant_id during normalization', () => {
supabase/functions/ai-timeline-agent/selectedClips.test.ts:53:      generation_id: 'gen-7',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:54:      variant_id: '  variant-7  ',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:59:      generation_id: 'gen-7',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:60:      variant_id: 'variant-7',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:66:  it('accepts gallery attachments with generation_id and synthesizes clip ids', () => {
supabase/functions/ai-timeline-agent/selectedClips.test.ts:69:      generation_id: 'gen-2',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:74:      generation_id: 'gen-2',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:91:      generation_id: 'gen-3',
supabase/functions/ai-timeline-agent/selectedClips.test.ts:97:      generation_id: 'gen-3',
supabase/functions/ai-timeline-agent/selectedClips.ts:111:        ...(clip.generation_id ? { generation_id: clip.generation_id } : {}),
supabase/functions/ai-timeline-agent/selectedClips.ts:112:        ...(clip.variant_id ? { variant_id: clip.variant_id } : {}),
supabase/functions/ai-timeline-agent/selectedClips.ts:126:      ...(clip.generation_id ? { generation_id: clip.generation_id } : {}),
supabase/functions/ai-timeline-agent/selectedClips.ts:127:      ...(clip.variant_id ? { variant_id: clip.variant_id } : {}),
supabase/functions/ai-timeline-agent/selectedClips.ts:150:    const generationId = typeof item.generation_id === "string" ? item.generation_id.trim() : "";
supabase/functions/ai-timeline-agent/selectedClips.ts:151:    const variantId = typeof item.variant_id === "string" && item.variant_id.trim()
supabase/functions/ai-timeline-agent/selectedClips.ts:152:      ? item.variant_id.trim()
supabase/functions/ai-timeline-agent/selectedClips.ts:181:      ...(generationId ? { generation_id: generationId } : {}),
supabase/functions/ai-timeline-agent/selectedClips.ts:182:      ...(variantId ? { variant_id: variantId } : {}),
supabase/functions/ai-timeline-agent/selectedClips.ts:206:      typeof clip.generation_id === "string" && clip.generation_id.trim()
supabase/functions/ai-timeline-agent/selectedClips.ts:207:        ? [clip.generation_id.trim()]
supabase/functions/ai-timeline-agent/selectedClips.ts:217:    .from("generations")
supabase/functions/ai-timeline-agent/selectedClips.ts:240:      clip.generation_id
supabase/functions/ai-timeline-agent/selectedClips.ts:241:        ? promptsByGenerationId.get(clip.generation_id)
supabase/functions/ai-timeline-agent/tool-schemas.ts:155:          generation_id: {
supabase/functions/ai-timeline-agent/tool-schemas.ts:15:      description: "Execute timeline edits through either a legacy command string or a typed transaction batch. Legacy commands: view, move <clipId> <seconds>, split <clipId> <time>, trim <clipId> [--from N] [--to N] [--duration N], delete <clipId>, set <clipId> <property> <value>, add-text <track> <at> <duration> <text>, add-media <track> <at> <generation_id> <url> [--type image|video], swap <clipId> <generation_id> <url> [--type image|video], duplicate <clipId> [count], query, undo, find-issues",
supabase/functions/ai-timeline-agent/tool-schemas.ts:163:          source_variant_id: {
supabase/functions/ai-timeline-agent/tool-schemas.ts:350:          generation_id: {
supabase/functions/ai-timeline-agent/tool-schemas.ts:355:        required: ["generation_id"],
supabase/functions/ai-timeline-agent/tool-schemas.ts:439:          generation_ids: {
supabase/functions/ai-timeline-agent/tool-schemas.ts:445:        required: ["shot_name", "generation_ids"],
supabase/functions/ai-timeline-agent/tools/clips.test.ts:106:        generation_id: 'gen-1',
supabase/functions/ai-timeline-agent/tools/clips.test.ts:140:        { generation_id: 'gen-1', shot_id: 'shot-generated' },
supabase/functions/ai-timeline-agent/tools/clips.test.ts:141:        { generation_id: 'gen-2', shot_id: 'shot-generated' },
supabase/functions/ai-timeline-agent/tools/clips.test.ts:149:        { clip_id: 'gallery-gen-1', url: 'https://example.com/clip-1.png', media_type: 'image', generation_id: 'gen-1' },
supabase/functions/ai-timeline-agent/tools/clips.test.ts:150:        { clip_id: 'gallery-gen-2', url: 'https://example.com/clip-2.png', media_type: 'image', generation_id: 'gen-2' },
supabase/functions/ai-timeline-agent/tools/clips.test.ts:157:    expect(fromMock).toHaveBeenCalledWith('shot_generations');
supabase/functions/ai-timeline-agent/tools/clips.test.ts:158:    expect(selectMock).toHaveBeenCalledWith('shot_id, generation_id');
supabase/functions/ai-timeline-agent/tools/clips.test.ts:159:    expect(inMock).toHaveBeenCalledWith('generation_id', ['gen-1', 'gen-2']);
supabase/functions/ai-timeline-agent/tools/clips.test.ts:168:        new_generation_id: 'gen-new',
supabase/functions/ai-timeline-agent/tools/clips.test.ts:175:      { generation_id: 'gen-source' },
supabase/functions/ai-timeline-agent/tools/clips.test.ts:181:        generation_id: 'gen-clip',
supabase/functions/ai-timeline-agent/tools/clips.test.ts:188:    expect(eqMock).toHaveBeenCalledWith('generation_id', 'gen-source');
supabase/functions/ai-timeline-agent/tools/clips.test.ts:193:      p_generation_id: 'gen-source',
supabase/functions/ai-timeline-agent/tools/clips.test.ts:59:  it('falls back to generation_id when the clip lookup misses', () => {
supabase/functions/ai-timeline-agent/tools/clips.test.ts:62:        { clip_id: 'clip-1', generation_id: 'gen-direct-1' },
supabase/functions/ai-timeline-agent/tools/clips.test.ts:63:        { clip_id: 'gallery-gen-2', generation_id: 'gen-direct-2' },
supabase/functions/ai-timeline-agent/tools/clips.ts:13:  const generationIds = clips.flatMap(({ clip_id, generation_id }) => {
supabase/functions/ai-timeline-agent/tools/clips.ts:15:    const fallbackGenerationId = typeof generation_id === "string" && generation_id.trim()
supabase/functions/ai-timeline-agent/tools/clips.ts:16:      ? generation_id.trim()
supabase/functions/ai-timeline-agent/tools/clips.ts:182:  const rows = Array.from(new Set(args.generationIds)).map((generationId) => ({ shot_id: shotId, generation_id: generationId }));
supabase/functions/ai-timeline-agent/tools/clips.ts:184:    const { error: insertError } = await supabaseAdmin.from("shot_generations").insert(rows);
supabase/functions/ai-timeline-agent/tools/clips.ts:185:    if (insertError) throw new Error(`Failed to attach generations to shot: ${insertError.message}`);
supabase/functions/ai-timeline-agent/tools/clips.ts:31:    .from("shot_generations")
supabase/functions/ai-timeline-agent/tools/clips.ts:32:    .select("shot_id, generation_id")
supabase/functions/ai-timeline-agent/tools/clips.ts:33:    .in("generation_id", uniqueGenerationIds);
supabase/functions/ai-timeline-agent/tools/clips.ts:34:  if (error) throw new Error(`Failed to load shot generations: ${error.message}`);
supabase/functions/ai-timeline-agent/tools/clips.ts:39:    const generationId = typeof row?.generation_id === "string" ? row.generation_id : null;
supabase/functions/ai-timeline-agent/tools/clips.ts:9:  clips: Array<Pick<SelectedClipPayload, "clip_id" | "generation_id">>,
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:208:        generation_id: "gen-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:224:  it("rejects local-mode input generations with a structured error before task creation", async () => {
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:241:        generation_id: "gen-local",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:242:        variant_id: "variant-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:251:      generation_id: "gen-local",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:274:        generation_id: "gen-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:323:        generation_id: "gen-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:349:        generation_id: "gen-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:361:  it("persists source_variant_id and placement_intent for exactly one selected timeline clip", async () => {
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:379:        generation_id: "gen-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:380:        variant_id: "variant-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:389:      source_variant_id: "variant-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:395:          anchor_generation_id: "gen-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:396:          anchor_variant_id: "variant-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:406:  it("omits placement_intent for gallery-only selections while preserving source_variant_id", async () => {
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:419:        generation_id: "gen-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:420:        variant_id: "variant-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:428:      source_variant_id?: string;
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:432:    expect(firstCallArgs.source_variant_id).toBe("variant-1");
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:439:  it("threads source_variant_id and placement_intent for image-upscale requests from a single timeline clip", async () => {
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:43:      if (table !== "generations") {
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:456:        generation_id: "gen-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:457:        variant_id: "variant-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:465:      generation_id: "gen-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:466:      source_variant_id: "variant-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:471:          anchor_generation_id: "gen-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:472:          anchor_variant_id: "variant-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:509:          generation_id: "gen-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:510:          variant_id: "variant-1",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:516:          generation_id: "gen-2",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:517:          variant_id: "variant-2",
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:526:      source_variant_id?: string;
supabase/functions/ai-timeline-agent/tools/create-task.test.ts:530:    expect(firstCallArgs.source_variant_id).toBe("variant-1");
supabase/functions/ai-timeline-agent/tools/create-task.ts:121:    ...(anchor.generation_id ? { anchor_generation_id: anchor.generation_id } : {}),
supabase/functions/ai-timeline-agent/tools/create-task.ts:122:    ...(anchor.variant_id ? { anchor_variant_id: anchor.variant_id } : {}),
supabase/functions/ai-timeline-agent/tools/create-task.ts:133:    generation_id: generationId,
supabase/functions/ai-timeline-agent/tools/create-task.ts:151:    .from("generations")
supabase/functions/ai-timeline-agent/tools/create-task.ts:338:      generation_id: args.generation_id,
supabase/functions/ai-timeline-agent/tools/create-task.ts:448:      ? selectedVideoEntry?.resolvedContext?.generation_id
supabase/functions/ai-timeline-agent/tools/create-task.ts:449:      : selectedReferenceEntries[0]?.resolvedContext?.generation_id));
supabase/functions/ai-timeline-agent/tools/create-task.ts:451:    ? (asTrimmedString(args.source_variant_id) ?? (taskType === "video-enhance"
supabase/functions/ai-timeline-agent/tools/create-task.ts:452:      ? selectedVideoEntry?.resolvedContext?.variant_id
supabase/functions/ai-timeline-agent/tools/create-task.ts:453:      : selectedReferenceEntries[0]?.resolvedContext?.variant_id))
supabase/functions/ai-timeline-agent/tools/create-task.ts:454:    : asTrimmedString(args.source_variant_id);
supabase/functions/ai-timeline-agent/tools/create-task.ts:456:    ? selectedReferenceEntries[0]?.resolvedContext?.generation_id
supabase/functions/ai-timeline-agent/tools/create-task.ts:459:    ...selectedReferenceEntries.map(({ resolvedContext }) => resolvedContext?.generation_id),
supabase/functions/ai-timeline-agent/tools/create-task.ts:460:    selectedVideoEntry?.resolvedContext?.generation_id,
supabase/functions/ai-timeline-agent/tools/create-task.ts:568:        source_variant_id: sourceVariantId ?? undefined,
supabase/functions/ai-timeline-agent/tools/create-task.ts:569:        generation_id: generationId ?? undefined,
supabase/functions/ai-timeline-agent/tools/create-task.ts:618:    source_variant_id: sourceVariantId ?? undefined,
supabase/functions/ai-timeline-agent/tools/create-task.ts:619:    generation_id: generationId ?? undefined,
supabase/functions/ai-timeline-agent/tools/duplicate-generation.ts:11:  const generationId = asTrimmedString(args.generation_id);
supabase/functions/ai-timeline-agent/tools/duplicate-generation.ts:12:  if (!generationId) return { result: "duplicate_generation requires generation_id." };
supabase/functions/ai-timeline-agent/tools/duplicate-generation.ts:27:    .from("shot_generations")
supabase/functions/ai-timeline-agent/tools/duplicate-generation.ts:29:    .eq("generation_id", generationId)
supabase/functions/ai-timeline-agent/tools/duplicate-generation.ts:35:    return { result: `Generation ${generationId} was not found in shot_generations.` };
supabase/functions/ai-timeline-agent/tools/duplicate-generation.ts:49:    p_generation_id: generationId,
supabase/functions/ai-timeline-agent/tools/duplicate-generation.ts:60:  const newGenerationId = asTrimmedString(data.new_generation_id);
supabase/functions/ai-timeline-agent/tools/duplicate-generation.ts:68:    result: `Duplicated ${generationId} -> ${newGenerationId}. Asset: ${location} (type: ${mediaType}). Use new_generation_id as based_on in create_task, or later with add-media to place on the timeline.`,
supabase/functions/ai-timeline-agent/tools/generation.ts:206:  const sourceVariantId = asTrimmedString(args.source_variant_id) ?? asTrimmedString(legacyInput.source_variant_id);
supabase/functions/ai-timeline-agent/tools/generation.ts:219:    ...(sourceVariantId ? { source_variant_id: sourceVariantId } : {}),
supabase/functions/ai-timeline-agent/tools/generation.ts:235:  const sourceVariantId = asTrimmedString(args.source_variant_id) ?? asTrimmedString(legacyInput.source_variant_id);
supabase/functions/ai-timeline-agent/tools/generation.ts:247:    ...(sourceVariantId ? { source_variant_id: sourceVariantId } : {}),
supabase/functions/ai-timeline-agent/tools/generation.ts:25:  source_variant_id?: string;
supabase/functions/ai-timeline-agent/tools/generation.ts:260:  const generationId = asTrimmedString(args.generation_id) ?? asTrimmedString(legacyInput.generation_id);
supabase/functions/ai-timeline-agent/tools/generation.ts:261:  const sourceVariantId = asTrimmedString(args.source_variant_id) ?? asTrimmedString(legacyInput.source_variant_id);
supabase/functions/ai-timeline-agent/tools/generation.ts:267:    ...(generationId ? { generation_id: generationId } : {}),
supabase/functions/ai-timeline-agent/tools/generation.ts:268:    ...(sourceVariantId ? { source_variant_id: sourceVariantId } : {}),
supabase/functions/ai-timeline-agent/tools/generation.ts:26:  generation_id?: string;
supabase/functions/ai-timeline-agent/tools/transform-image.test.ts:107:        generation_id: "gen-1",
supabase/functions/ai-timeline-agent/tools/transform-image.test.ts:33:        generation_id: "gen-1",
supabase/functions/ai-timeline-agent/tools/transform-image.test.ts:44:        generation_id: "gen-1",
supabase/functions/ai-timeline-agent/tools/transform-image.test.ts:69:        generation_id: "gen-1",
supabase/functions/ai-timeline-agent/tools/transform-image.test.ts:76:        generation_id: "gen-1",
supabase/functions/ai-timeline-agent/tools/transform-image.test.ts:84:      { generation_id: "gen-1" },
supabase/functions/ai-timeline-agent/tools/transform-image.test.ts:97:        generation_id: "gen-1",
supabase/functions/ai-timeline-agent/tools/transform-image.test.ts:98:        variant_id: "variant-1",
supabase/functions/ai-timeline-agent/tools/transform-image.ts:101:      ...(asTrimmedString(args.source_variant_id) ? { source_variant_id: asTrimmedString(args.source_variant_id) } : {}),
supabase/functions/ai-timeline-agent/tools/transform-image.ts:10:  source_variant_id?: string;
supabase/functions/ai-timeline-agent/tools/transform-image.ts:141:    generation_id?: string;
supabase/functions/ai-timeline-agent/tools/transform-image.ts:142:    variant_id?: string;
supabase/functions/ai-timeline-agent/tools/transform-image.ts:150:      result: `Created transformed generation ${data.generation_id ?? "unknown"} with variant ${data.variant_id ?? "unknown"}. Asset: ${data.location ?? "unknown"}.`,
supabase/functions/ai-timeline-agent/tools/transform-image.ts:155:    result: `Created transformed variant ${data.variant_id ?? "unknown"} on generation ${data.generation_id ?? "unknown"}${data.is_primary === true ? " and set it as primary" : ""}. Asset: ${data.location ?? "unknown"}${data.variant_name ? ` (${data.variant_name})` : ""}.`,
supabase/functions/ai-timeline-agent/tools/transform-image.ts:38:  const generationId = asTrimmedString(args.generation_id);
supabase/functions/ai-timeline-agent/tools/transform-image.ts:47:      generationId: selectedImages[0].generation_id ?? null,
supabase/functions/ai-timeline-agent/tools/transform-image.ts:63:    return { error: "transform_image requires generation_id, or exactly one selected image clip with a generation_id." };
supabase/functions/ai-timeline-agent/tools/transform-image.ts:8:  generation_id?: string;
supabase/functions/ai-timeline-agent/tools/transform-image.ts:98:      generation_id: generationId,
supabase/functions/ai-timeline-agent/types.ts:105:  generation_id?: string;
supabase/functions/ai-timeline-agent/types.ts:106:  variant_id?: string;
supabase/functions/ai-timeline-agent/types.ts:119:  anchor_generation_id?: string;
supabase/functions/ai-timeline-agent/types.ts:120:  anchor_variant_id?: string;
supabase/functions/ai-timeline-agent/types.ts:90:  generation_id?: string;
supabase/functions/ai-timeline-agent/types.ts:91:  variant_id?: string;
```

## Hit Classification And M3 Work Items

| File | Surface type | Observed legacy surface | M3 action |
| --- | --- | --- | --- |
| `supabase/functions/ai-timeline-agent/command-parser.ts` | command parser | `add-media` and `swap` legacy command grammar accepts `<generation_id>`. | M3: Rewrite command grammar to slot/attempt vocabulary or remove legacy command form. |
| `supabase/functions/ai-timeline-agent/llm/client.ts` | LLM routing prompt | Model difficulty text names generation duplication and adding media from generations. | M3: Update routing criteria to slot/attempt tasks after tool contract changes. |
| `supabase/functions/ai-timeline-agent/loop.test.ts` | test fixture | Loop tests assert `generation_id` arguments flow through tool calls and create-shot behavior. | M3: Rewrite or delete with the loop tool-contract migration. |
| `supabase/functions/ai-timeline-agent/loop.ts` | runtime loop/orchestrator | Maps selected clips to `generationId`, emits `generation_id`, reads `generation_ids`, and returns create-shot generation errors. | M3: Replace selected-clip and create-shot routing with slot/attempt contract. |
| `supabase/functions/ai-timeline-agent/prompts.ts` | system prompt / examples | Selected clip text and examples teach `generation_id`, `duplicate_generation`, `create_shot(generation_ids)`, and add-media placement. | M3: Rewrite prompt examples after M3 tool schemas are slot-first. |
| `supabase/functions/ai-timeline-agent/selectedClips.test.ts` | test fixture | Selected clip tests cover `generation_id`, `variant_id`, and prompt enrichment from `generations`. | M3: Rewrite alongside selected clip normalization; delete assertions tied to legacy table lookup. |
| `supabase/functions/ai-timeline-agent/selectedClips.ts` | runtime selected-clip contract | Normalizes `generation_id`/`variant_id` and enriches prompts by querying `generations`. | M3: Replace with slot/attempt clip identity and prompt source. |
| `supabase/functions/ai-timeline-agent/tool-schemas.ts` | public tool schema | JSON schemas expose `generation_id`, `source_variant_id`, `generation_ids`, legacy add-media command, and duplicate/transform inputs. | M3: Schema migration; this is a public boundary and must change with tests. |
| `supabase/functions/ai-timeline-agent/tools/clips.test.ts` | test fixture | Tests `shot_generations` lookups/inserts and `generation_id` fallback/duplicate behavior. | M3: Rewrite for `shot_slots` or delete if covered by new slot tests. |
| `supabase/functions/ai-timeline-agent/tools/clips.ts` | runtime clip/shot tool | Reads and writes `shot_generations`; maps clip IDs to generation IDs. | M3: Replace with slot-first shot placement APIs. |
| `supabase/functions/ai-timeline-agent/tools/create-task.test.ts` | test fixture | Mocks `generations`, selected clip `generation_id`/`variant_id`, `source_variant_id`, and placement anchors. | M3: Rewrite with typed slot/attempt task payload fixtures. |
| `supabase/functions/ai-timeline-agent/tools/create-task.ts` | runtime task creation | Looks up `generations`, carries `generation_id`, `source_variant_id`, and anchor generation/variant IDs into task payloads. | M3: Replace task payload schema and lookup source with slot/attempt contract. |
| `supabase/functions/ai-timeline-agent/tools/duplicate-generation.ts` | runtime duplicate tool | Looks up `shot_generations`, calls `duplicate_generation`, and returns `new_generation_id`. | M3: Replace with slot/attempt duplicate semantics or remove as legacy-only. |
| `supabase/functions/ai-timeline-agent/tools/generation.ts` | runtime generation task helper | Defines and emits `generation_id` and `source_variant_id` for generation/edit task payloads. | M3: Fold into attempt/task payload model. |
| `supabase/functions/ai-timeline-agent/tools/transform-image.test.ts` | test fixture | Tests transform-image `generation_id`/`variant_id` inputs and outputs. | M3: Rewrite with attempt source and result fixtures. |
| `supabase/functions/ai-timeline-agent/tools/transform-image.ts` | runtime transform tool | Requires or infers `generation_id`, passes `source_variant_id`, and reports generation/variant IDs. | M3: Replace with attempt/slot source identity and output language. |
| `supabase/functions/ai-timeline-agent/types.ts` | shared type contract | Selected clip, source item, placement, and task types expose `generation_id`, `variant_id`, anchor generation/variant IDs. | M3: Contract root; migrate before runtime rewrites. |

## Test Files

Tests inside `ai-timeline-agent/` are part of this audit. M3 must make an explicit rewrite/delete/retain decision for every test after the runtime contract changes; hit tests are presumed rewrite/delete unless the replacement slot-first assertions cover the same behavior.

Total test/acceptance files: 11

Legacy-hit test files: 5

| Test file | M3 handling |
| --- | --- |
| `supabase/functions/ai-timeline-agent/command-parser.test.ts` | no required legacy token hit in this grep; M3 must re-run after parser rewrite and either rewrite, delete, or retain with slot-first-clean assertions |
| `supabase/functions/ai-timeline-agent/loop.test.ts` | legacy hit; M3 rewrite/delete decision required |
| `supabase/functions/ai-timeline-agent/public-sdk.acceptance.test.ts` | no required legacy token hit in this grep; M3 must re-run after public schema rewrite and either rewrite, delete, or retain with slot-first-clean assertions |
| `supabase/functions/ai-timeline-agent/selectedClips.test.ts` | legacy hit; M3 rewrite/delete decision required |
| `supabase/functions/ai-timeline-agent/tool-calls.test.ts` | no required legacy token hit in this grep; M3 must re-run after tool schema rewrite and either rewrite, delete, or retain with slot-first-clean assertions |
| `supabase/functions/ai-timeline-agent/tools/clips.test.ts` | legacy hit; M3 rewrite/delete decision required |
| `supabase/functions/ai-timeline-agent/tools/create-task.test.ts` | legacy hit; M3 rewrite/delete decision required |
| `supabase/functions/ai-timeline-agent/tools/delegateToBanodocoAgent.test.ts` | no required legacy token hit in this grep; M3 must re-run after tool schema rewrite and either rewrite, delete, or retain with slot-first-clean assertions |
| `supabase/functions/ai-timeline-agent/tools/llm-schema-snapshot.test.ts` | no required legacy token hit in this grep; M3 must regenerate or update after slot-first tool schemas land |
| `supabase/functions/ai-timeline-agent/tools/timeline.test.ts` | no required legacy token hit in this grep; M3 must re-run after timeline tool rewrite and either rewrite, delete, or retain with slot-first-clean assertions |
| `supabase/functions/ai-timeline-agent/tools/transform-image.test.ts` | legacy hit; M3 rewrite/delete decision required |

## M3 Burn-Down Notes

- The shared type root is `types.ts`; migrate it first so runtime files stop reintroducing compatibility aliases.
- Public schemas live in `tool-schemas.ts`; M3 must update prompts, parser strings, and tests in the same change as schema updates.
- `selectedClips.ts`, `tools/clips.ts`, and `tools/duplicate-generation.ts` still depend on `generations` or `shot_generations` as data sources. These are slot-first cutover blockers until rewritten.
- Tests with no direct hit remain in scope for M3 because adjacent runtime contract rewrites can invalidate them even if this grep did not match.
