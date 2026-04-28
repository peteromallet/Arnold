export interface TimelineAgentToolDefinition {
  type: "function";
  function: {
    name: string;
    description: string;
    parameters: Record<string, unknown>;
  };
}

export const TIMELINE_AGENT_TOOLS: TimelineAgentToolDefinition[] = [
  {
    type: "function",
    function: {
      name: "run",
      description: "Execute a timeline editing command. Commands: view, move <clipId> <seconds>, split <clipId> <time>, trim <clipId> [--from N] [--to N] [--duration N], delete <clipId>, set <clipId> <property> <value>, add-text <track> <at> <duration> <text>, add-media <track> <at> <generation_id> <url> [--type image|video], swap <clipId> <generation_id> <url> [--type image|video], duplicate <clipId> [count], query, undo, find-issues",
      parameters: {
        type: "object",
        properties: {
          command: { type: "string", description: "The command to execute" },
        },
        required: ["command"],
        additionalProperties: false,
      },
    },
  },
  {
    // Sprint 4 (SD-018): themed-clip params editor. Use this for editing
    // clip-level params blobs like {kicker, title, subtitle} on themed
    // effects (section-hook, art-card, etc.). Numeric media properties
    // (volume/speed/opacity/x/y/width/height) still go through `run` →
    // set_clip_property.
    type: "function",
    function: {
      name: "set_params",
      description:
        "Edit a themed clip's `params` object (e.g. kicker, title, subtitle on a section-hook clip). Shallow-merges the patch into the clip's existing params. Pass null for a key to clear it. Use this — not `run set_clip_property` — for any non-numeric themed-effect parameter.",
      parameters: {
        type: "object",
        properties: {
          clipId: {
            type: "string",
            description: "Target clip ID.",
          },
          params: {
            type: "object",
            description: "Patch object merged into the clip's params. Keys with null are deleted.",
            additionalProperties: true,
          },
        },
        required: ["clipId", "params"],
        additionalProperties: false,
      },
    },
  },
  {
    // Sprint 4 (SD-018): switch the active timeline theme.
    type: "function",
    function: {
      name: "set_theme",
      description:
        "Switch the timeline's active theme (e.g. \"2rp\", \"arca-gidan\"). Existing themed clips referencing the old theme's clipType may need remapping; the tool warns the user when this happens.",
      parameters: {
        type: "object",
        properties: {
          themeId: {
            type: "string",
            description: "Theme slug to activate.",
          },
        },
        required: ["themeId"],
        additionalProperties: false,
      },
    },
  },
  {
    // Sprint 4 (SD-018): layered theme overrides without re-authoring.
    type: "function",
    function: {
      name: "set_theme_overrides",
      description:
        "Deep-merge a theme_overrides patch onto the timeline (e.g. {visual: {canvas: {fps: 60}}}). Use to tweak palette / typography / canvas / pacing without forking the theme. Pass null at any depth to clear that key.",
      parameters: {
        type: "object",
        properties: {
          overrides: {
            type: "object",
            description: "Patch object deep-merged into theme_overrides. Null values clear keys at any depth.",
            additionalProperties: true,
          },
        },
        required: ["overrides"],
        additionalProperties: false,
      },
    },
  },
  {
    type: "function",
    function: {
      name: "transform_image",
      description: "Apply an exact deterministic transform to an existing image and save it as a new variant or standalone generation. Use for flips, rotations, zoom/reposition, and other geometric edits that must preserve the source image exactly.",
      parameters: {
        type: "object",
        properties: {
          generation_id: {
            type: "string",
            description: "Source generation ID. If omitted, the tool can fall back to exactly one selected image clip.",
          },
          source_image_url: {
            type: "string",
            description: "Optional explicit source image URL. Prefer copying the selected clip URL exactly when available.",
          },
          source_variant_id: {
            type: "string",
            description: "Optional source variant ID when transforming a non-primary variant.",
          },
          translate_x: {
            type: "number",
            description: "Horizontal move as a percentage of image width. 0 means centered.",
          },
          translate_y: {
            type: "number",
            description: "Vertical move as a percentage of image height. 0 means centered.",
          },
          scale: {
            type: "number",
            description: "Zoom factor. 1 = original size, 1.5 = 150%, 0.75 = 75%.",
          },
          rotation: {
            type: "number",
            description: "Rotation in degrees.",
          },
          flip_horizontal: {
            type: "boolean",
            description: "Mirror left-to-right.",
          },
          flip_vertical: {
            type: "boolean",
            description: "Mirror top-to-bottom.",
          },
          as_new: {
            type: "boolean",
            description: "When true, create a standalone generation instead of a variant. Defaults to false.",
          },
          make_primary: {
            type: "boolean",
            description: "When false, keep the new variant non-primary. Defaults to true for variant outputs.",
          },
          variant_name: {
            type: "string",
            description: "Optional label for the created variant.",
          },
        },
        additionalProperties: false,
      },
    },
  },
  {
    type: "function",
    function: {
      name: "create_task",
      description: "Create a generation task from text or selected reference media.",
      parameters: {
        type: "object",
        properties: {
          task_type: {
            type: "string",
            enum: [
              "text-to-image",
              "style-transfer",
              "subject-transfer",
              "style-character-transfer",
              "scene-transfer",
              "image-to-video",
              "image-to-image",
              "magic-edit",
              "image-upscale",
              "video-enhance",
              "character-animate",
            ],
          },
          prompt: {
            type: "string",
            description:
              "Generation instruction. Required for text-to-image, style-transfer, subject-transfer, style-character-transfer, scene-transfer, image-to-video, image-to-image, and magic-edit. Optional for image-upscale, video-enhance, and character-animate.",
          },
          model: {
            type: "string",
            enum: ["qwen-image", "qwen-image-2512", "z-image", "wan-2.2", "ltx-2.3", "ltx-2.3-fast"],
            description:
              "Optional model choice. Text-to-image models: qwen-image, qwen-image-2512, z-image. Image-to-video models: wan-2.2, ltx-2.3, ltx-2.3-fast.",
          },
          reference_image_urls: {
            type: "array",
            items: { type: "string" },
            description:
              "Reference image URLs chosen from the selected media context. Use for style-transfer, subject-transfer, style-character-transfer, scene-transfer, image-to-video, image-to-image, magic-edit, image-upscale, and character-animate's character image.",
          },
          reference_mode: {
            type: "string",
            enum: ["style", "subject", "style-character", "scene"],
            description:
              "Optional override for the reference behavior used by transfer tasks when it should differ from the task_type default.",
          },
          video_url: {
            type: "string",
            description:
              "Selected video clip URL. Use for video-enhance and for character-animate's motion reference video.",
          },
          strength: {
            type: "number",
            description: "Optional image-to-image strength from 0 to 1. Higher values make larger changes.",
          },
          count: {
            type: "number",
            description:
              "Number of outputs to request for text-to-image, style-transfer, subject-transfer, style-character-transfer, scene-transfer, image-to-image, or magic-edit tasks.",
          },
          variation_intent: {
            type: "string",
            description:
              "Optional. When count > 1, describes the axis the user wants varied across the N prompts. Derive from the user's chat phrasing: 'different lighting' -> 'different lighting conditions', 'try other angles' -> 'different camera angles', 'different characters' -> 'different characters'. Leave empty when the user just wants more of the same — the system will produce N linguistic rewrites of the same concept by default.",
          },
          based_on: {
            type: "string",
            description: "Generation ID this task derives from. Overrides auto-detected value from selected clips.",
          },
          as_new: {
            type: "boolean",
            description: "When true, create a standalone generation instead of a variant of the source image. Leave unset for normal image-to-image or magic-edit requests unless the user explicitly asks for a standalone or detached result. Defaults to false.",
          },
          make_primary: {
            type: "boolean",
            description: "When false, keep a source-derived variant non-primary. For image-to-image and magic-edit variants, defaults to true.",
          },
          shot_name: { type: "string", description: "Optional shot name to use if a new shot must be created." },
          amount_of_motion: {
            type: "number",
            description: "Motion intensity 0-100 for image-to-video. Higher = more motion.",
          },
          steps: {
            type: "number",
            description: "Inference steps for image-to-video. Model-dependent (wan-2.2: 6, ltx-2.3: 30, ltx-2.3-fast: 8).",
          },
          guidance_scale: {
            type: "number",
            description: "Guidance scale for image-to-video (LTX models only).",
          },
          enhance_prompt: {
            type: "boolean",
            description: "Auto-enhance prompts for image-to-video.",
          },
          turbo_mode: {
            type: "boolean",
            description: "Turbo mode for wan-2.2 image-to-video (faster, lower quality).",
          },
          timeline_placement: {
            type: "object",
            description: "Optional post-task placement intent. Include only when the user explicitly asks to place the generated result after or in place of a selected timeline clip.",
            properties: {
              timeline_id: {
                type: "string",
                description: "Timeline ID that should receive the generated media.",
              },
              source_clip_id: {
                type: "string",
                description: "Selected source clip that anchors placement.",
              },
              target_track: {
                type: "string",
                description: "Track to insert onto.",
              },
              insertion_time: {
                type: "number",
                description: "Timeline insertion point in seconds.",
              },
              intent: {
                type: "string",
                enum: ["after_source", "replace"],
                description: "Whether to insert after the source clip or replace it.",
              },
            },
            required: ["timeline_id", "source_clip_id", "target_track", "insertion_time", "intent"],
            additionalProperties: false,
          },
        },
        required: ["task_type"],
        additionalProperties: false,
      },
    },
  },
  {
    type: "function",
    function: {
      name: "duplicate_generation",
      description: "Duplicate an existing generation instantly and return the new generation ID plus asset URL.",
      parameters: {
        type: "object",
        properties: {
          generation_id: {
            type: "string",
            description: "Generation ID to duplicate as a new generation record.",
          },
        },
        required: ["generation_id"],
        additionalProperties: false,
      },
    },
  },
  {
    type: "function",
    function: {
      name: "search_loras",
      description: "Search the LoRA catalog by name, tag, or description. Returns matching LoRAs with paths and metadata.",
      parameters: {
        type: "object",
        properties: {
          query: {
            type: "string",
            description: "Search text matched against LoRA name, tags, description, and related metadata.",
          },
          base_model: {
            type: "string",
            enum: ["wan", "qwen", "ltx", "z-image"],
            description: "Optional base model filter for narrowing LoRA results.",
          },
        },
        required: ["query"],
        additionalProperties: false,
      },
    },
  },
  {
    type: "function",
    function: {
      name: "set_lora",
      description: "Add, remove, or update a LoRA in active settings. For video travel: modifies shot LoRAs. For image generation: modifies project LoRAs.",
      parameters: {
        type: "object",
        properties: {
          action: {
            type: "string",
            enum: ["add", "remove", "update_strength"],
            description: "Whether to add a LoRA, remove it, or change its strength.",
          },
          lora_path: {
            type: "string",
            description: "Canonical LoRA file path to add, remove, or update.",
          },
          lora_name: {
            type: "string",
            description: "Optional LoRA display name, mainly used when adding a new LoRA.",
          },
          strength: {
            type: "number",
            description: "Optional LoRA strength from 0 to 2.",
          },
          target: {
            type: "string",
            enum: ["video-travel", "image-generation"],
            description: "Which settings scope to modify.",
          },
          trigger_word: {
            type: "string",
            description: "Optional trigger word associated with the LoRA.",
          },
          low_noise_path: {
            type: "string",
            description: "Optional low-noise LoRA path for multi-stage LoRAs.",
          },
        },
        required: ["action", "lora_path", "target"],
        additionalProperties: false,
      },
    },
  },
  {
    type: "function",
    function: {
      name: "create_shot",
      description: "Create a named shot and group existing generation IDs into it.",
      parameters: {
        type: "object",
        properties: {
          shot_name: {
            type: "string",
            description: "Name for the shot to create.",
          },
          generation_ids: {
            type: "array",
            items: { type: "string" },
            description: "Existing generation IDs to attach to the shot.",
          },
        },
        required: ["shot_name", "generation_ids"],
        additionalProperties: false,
      },
    },
  },
  {
    type: "function",
    function: {
      name: "get_tasks",
      description:
        "Fetch recent tasks for this project. Use to check task status, see errors, or find completed generation outputs.",
      parameters: {
        type: "object",
        properties: {
          status: {
            type: "string",
            enum: ["Queued", "In Progress", "Complete", "Failed", "Cancelled"],
            description: "Filter by task status. Omit to see all recent tasks.",
          },
          task_id: {
            type: "string",
            description: "Fetch a specific task by ID. When provided, other filters are ignored.",
          },
          limit: {
            type: "number",
            description: "Max tasks to return (default 10, max 50).",
          },
        },
        additionalProperties: false,
      },
    },
  },
];
