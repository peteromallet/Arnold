import { z } from "zod";
export declare const TextAlignment: z.ZodEnum<["left", "center", "right"]>;
export declare const TrackKind: z.ZodEnum<["visual", "audio"]>;
export declare const TrackFit: z.ZodEnum<["cover", "contain", "manual"]>;
export declare const TrackBlendMode: z.ZodEnum<["normal", "multiply", "screen", "overlay", "darken", "lighten", "soft-light", "hard-light"]>;
export declare const TimelineEffect: z.ZodObject<{
    fade_in: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
    fade_out: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
}, "strip", z.ZodTypeAny, {
    fade_in?: number | undefined;
    fade_out?: number | undefined;
}, {
    fade_in?: number | undefined;
    fade_out?: number | undefined;
}>;
export declare const ClipEntrance: z.ZodObject<{
    type: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    duration: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
    intensity: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
    params: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
}, "strip", z.ZodTypeAny, {
    params?: Record<string, any> | undefined;
    type?: string | undefined;
    duration?: number | undefined;
    intensity?: number | undefined;
}, {
    params?: Record<string, any> | undefined;
    type?: string | undefined;
    duration?: number | undefined;
    intensity?: number | undefined;
}>;
export declare const ClipExit: z.ZodObject<{
    type: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    duration: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
    intensity: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
    params: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
}, "strip", z.ZodTypeAny, {
    params?: Record<string, any> | undefined;
    type?: string | undefined;
    duration?: number | undefined;
    intensity?: number | undefined;
}, {
    params?: Record<string, any> | undefined;
    type?: string | undefined;
    duration?: number | undefined;
    intensity?: number | undefined;
}>;
export declare const ClipContinuous: z.ZodObject<{
    type: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    intensity: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
    params: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
}, "strip", z.ZodTypeAny, {
    params?: Record<string, any> | undefined;
    type?: string | undefined;
    intensity?: number | undefined;
}, {
    params?: Record<string, any> | undefined;
    type?: string | undefined;
    intensity?: number | undefined;
}>;
export declare const ClipTransition: z.ZodObject<{
    type: z.ZodString;
    duration: z.ZodNumber;
}, "strip", z.ZodTypeAny, {
    type: string;
    duration: number;
}, {
    type: string;
    duration: number;
}>;
export declare const ClipTransitionReference: z.ZodObject<{
    id: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    type: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    duration: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
    durationFrames: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
    params: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
}, "strip", z.ZodTypeAny, {
    params?: Record<string, any> | undefined;
    type?: string | undefined;
    duration?: number | undefined;
    id?: string | undefined;
    durationFrames?: number | undefined;
}, {
    params?: Record<string, any> | undefined;
    type?: string | undefined;
    duration?: number | undefined;
    id?: string | undefined;
    durationFrames?: number | undefined;
}>;
export declare const TextClipData: z.ZodObject<{
    content: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    fontFamily: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    fontSize: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
    color: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    align: z.ZodOptional<z.ZodOptional<z.ZodEnum<["left", "center", "right"]>>>;
    bold: z.ZodOptional<z.ZodOptional<z.ZodBoolean>>;
    italic: z.ZodOptional<z.ZodOptional<z.ZodBoolean>>;
}, "strip", z.ZodTypeAny, {
    content?: string | undefined;
    fontFamily?: string | undefined;
    fontSize?: number | undefined;
    color?: string | undefined;
    align?: "left" | "center" | "right" | undefined;
    bold?: boolean | undefined;
    italic?: boolean | undefined;
}, {
    content?: string | undefined;
    fontFamily?: string | undefined;
    fontSize?: number | undefined;
    color?: string | undefined;
    align?: "left" | "center" | "right" | undefined;
    bold?: boolean | undefined;
    italic?: boolean | undefined;
}>;
export declare const TimelineClip: z.ZodObject<{
    id: z.ZodString;
    at: z.ZodNumber;
    track: z.ZodString;
    source_uuid: z.ZodOptional<z.ZodString>;
    clipType: z.ZodOptional<z.ZodString>;
    asset: z.ZodOptional<z.ZodString>;
    from: z.ZodOptional<z.ZodNumber>;
    to: z.ZodOptional<z.ZodNumber>;
    speed: z.ZodOptional<z.ZodNumber>;
    hold: z.ZodOptional<z.ZodNumber>;
    volume: z.ZodOptional<z.ZodNumber>;
    x: z.ZodOptional<z.ZodNumber>;
    y: z.ZodOptional<z.ZodNumber>;
    width: z.ZodOptional<z.ZodNumber>;
    height: z.ZodOptional<z.ZodNumber>;
    cropTop: z.ZodOptional<z.ZodNumber>;
    cropBottom: z.ZodOptional<z.ZodNumber>;
    cropLeft: z.ZodOptional<z.ZodNumber>;
    cropRight: z.ZodOptional<z.ZodNumber>;
    opacity: z.ZodOptional<z.ZodNumber>;
    text: z.ZodOptional<z.ZodObject<{
        content: z.ZodOptional<z.ZodOptional<z.ZodString>>;
        fontFamily: z.ZodOptional<z.ZodOptional<z.ZodString>>;
        fontSize: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
        color: z.ZodOptional<z.ZodOptional<z.ZodString>>;
        align: z.ZodOptional<z.ZodOptional<z.ZodEnum<["left", "center", "right"]>>>;
        bold: z.ZodOptional<z.ZodOptional<z.ZodBoolean>>;
        italic: z.ZodOptional<z.ZodOptional<z.ZodBoolean>>;
    }, "strip", z.ZodTypeAny, {
        content?: string | undefined;
        fontFamily?: string | undefined;
        fontSize?: number | undefined;
        color?: string | undefined;
        align?: "left" | "center" | "right" | undefined;
        bold?: boolean | undefined;
        italic?: boolean | undefined;
    }, {
        content?: string | undefined;
        fontFamily?: string | undefined;
        fontSize?: number | undefined;
        color?: string | undefined;
        align?: "left" | "center" | "right" | undefined;
        bold?: boolean | undefined;
        italic?: boolean | undefined;
    }>>;
    entrance: z.ZodOptional<z.ZodObject<{
        type: z.ZodOptional<z.ZodOptional<z.ZodString>>;
        duration: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
        intensity: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
        params: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
    }, "strip", z.ZodTypeAny, {
        params?: Record<string, any> | undefined;
        type?: string | undefined;
        duration?: number | undefined;
        intensity?: number | undefined;
    }, {
        params?: Record<string, any> | undefined;
        type?: string | undefined;
        duration?: number | undefined;
        intensity?: number | undefined;
    }>>;
    exit: z.ZodOptional<z.ZodObject<{
        type: z.ZodOptional<z.ZodOptional<z.ZodString>>;
        duration: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
        intensity: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
        params: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
    }, "strip", z.ZodTypeAny, {
        params?: Record<string, any> | undefined;
        type?: string | undefined;
        duration?: number | undefined;
        intensity?: number | undefined;
    }, {
        params?: Record<string, any> | undefined;
        type?: string | undefined;
        duration?: number | undefined;
        intensity?: number | undefined;
    }>>;
    continuous: z.ZodOptional<z.ZodObject<{
        type: z.ZodOptional<z.ZodOptional<z.ZodString>>;
        intensity: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
        params: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
    }, "strip", z.ZodTypeAny, {
        params?: Record<string, any> | undefined;
        type?: string | undefined;
        intensity?: number | undefined;
    }, {
        params?: Record<string, any> | undefined;
        type?: string | undefined;
        intensity?: number | undefined;
    }>>;
    transition: z.ZodOptional<z.ZodUnion<[z.ZodObject<{
        type: z.ZodString;
        duration: z.ZodNumber;
    }, "strip", z.ZodTypeAny, {
        type: string;
        duration: number;
    }, {
        type: string;
        duration: number;
    }>, z.ZodObject<{
        id: z.ZodOptional<z.ZodOptional<z.ZodString>>;
        type: z.ZodOptional<z.ZodOptional<z.ZodString>>;
        duration: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
        durationFrames: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
        params: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
    }, "strip", z.ZodTypeAny, {
        params?: Record<string, any> | undefined;
        type?: string | undefined;
        duration?: number | undefined;
        id?: string | undefined;
        durationFrames?: number | undefined;
    }, {
        params?: Record<string, any> | undefined;
        type?: string | undefined;
        duration?: number | undefined;
        id?: string | undefined;
        durationFrames?: number | undefined;
    }>, z.ZodString]>>;
    effects: z.ZodOptional<z.ZodUnion<[z.ZodArray<z.ZodObject<{
        fade_in: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
        fade_out: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
    }, "strip", z.ZodTypeAny, {
        fade_in?: number | undefined;
        fade_out?: number | undefined;
    }, {
        fade_in?: number | undefined;
        fade_out?: number | undefined;
    }>, "many">, z.ZodRecord<z.ZodString, z.ZodNumber>]>>;
    params: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    generation: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    pool_id: z.ZodOptional<z.ZodString>;
    clip_order: z.ZodOptional<z.ZodNumber>;
}, "strip", z.ZodTypeAny, {
    at: number;
    id: string;
    track: string;
    params?: Record<string, any> | undefined;
    source_uuid?: string | undefined;
    clipType?: string | undefined;
    asset?: string | undefined;
    from?: number | undefined;
    to?: number | undefined;
    speed?: number | undefined;
    hold?: number | undefined;
    volume?: number | undefined;
    x?: number | undefined;
    y?: number | undefined;
    width?: number | undefined;
    height?: number | undefined;
    cropTop?: number | undefined;
    cropBottom?: number | undefined;
    cropLeft?: number | undefined;
    cropRight?: number | undefined;
    opacity?: number | undefined;
    text?: {
        content?: string | undefined;
        fontFamily?: string | undefined;
        fontSize?: number | undefined;
        color?: string | undefined;
        align?: "left" | "center" | "right" | undefined;
        bold?: boolean | undefined;
        italic?: boolean | undefined;
    } | undefined;
    entrance?: {
        params?: Record<string, any> | undefined;
        type?: string | undefined;
        duration?: number | undefined;
        intensity?: number | undefined;
    } | undefined;
    exit?: {
        params?: Record<string, any> | undefined;
        type?: string | undefined;
        duration?: number | undefined;
        intensity?: number | undefined;
    } | undefined;
    continuous?: {
        params?: Record<string, any> | undefined;
        type?: string | undefined;
        intensity?: number | undefined;
    } | undefined;
    transition?: string | {
        type: string;
        duration: number;
    } | {
        params?: Record<string, any> | undefined;
        type?: string | undefined;
        duration?: number | undefined;
        id?: string | undefined;
        durationFrames?: number | undefined;
    } | undefined;
    effects?: {
        fade_in?: number | undefined;
        fade_out?: number | undefined;
    }[] | Record<string, number> | undefined;
    generation?: Record<string, any> | undefined;
    pool_id?: string | undefined;
    clip_order?: number | undefined;
}, {
    at: number;
    id: string;
    track: string;
    params?: Record<string, any> | undefined;
    source_uuid?: string | undefined;
    clipType?: string | undefined;
    asset?: string | undefined;
    from?: number | undefined;
    to?: number | undefined;
    speed?: number | undefined;
    hold?: number | undefined;
    volume?: number | undefined;
    x?: number | undefined;
    y?: number | undefined;
    width?: number | undefined;
    height?: number | undefined;
    cropTop?: number | undefined;
    cropBottom?: number | undefined;
    cropLeft?: number | undefined;
    cropRight?: number | undefined;
    opacity?: number | undefined;
    text?: {
        content?: string | undefined;
        fontFamily?: string | undefined;
        fontSize?: number | undefined;
        color?: string | undefined;
        align?: "left" | "center" | "right" | undefined;
        bold?: boolean | undefined;
        italic?: boolean | undefined;
    } | undefined;
    entrance?: {
        params?: Record<string, any> | undefined;
        type?: string | undefined;
        duration?: number | undefined;
        intensity?: number | undefined;
    } | undefined;
    exit?: {
        params?: Record<string, any> | undefined;
        type?: string | undefined;
        duration?: number | undefined;
        intensity?: number | undefined;
    } | undefined;
    continuous?: {
        params?: Record<string, any> | undefined;
        type?: string | undefined;
        intensity?: number | undefined;
    } | undefined;
    transition?: string | {
        type: string;
        duration: number;
    } | {
        params?: Record<string, any> | undefined;
        type?: string | undefined;
        duration?: number | undefined;
        id?: string | undefined;
        durationFrames?: number | undefined;
    } | undefined;
    effects?: {
        fade_in?: number | undefined;
        fade_out?: number | undefined;
    }[] | Record<string, number> | undefined;
    generation?: Record<string, any> | undefined;
    pool_id?: string | undefined;
    clip_order?: number | undefined;
}>;
export declare const TrackDefinition: z.ZodObject<{
    id: z.ZodString;
    kind: z.ZodEnum<["visual", "audio"]>;
    label: z.ZodString;
    scale: z.ZodOptional<z.ZodNumber>;
    fit: z.ZodOptional<z.ZodEnum<["cover", "contain", "manual"]>>;
    opacity: z.ZodOptional<z.ZodNumber>;
    volume: z.ZodOptional<z.ZodNumber>;
    muted: z.ZodOptional<z.ZodBoolean>;
    blendMode: z.ZodOptional<z.ZodEnum<["normal", "multiply", "screen", "overlay", "darken", "lighten", "soft-light", "hard-light"]>>;
}, "strip", z.ZodTypeAny, {
    id: string;
    kind: "visual" | "audio";
    label: string;
    volume?: number | undefined;
    opacity?: number | undefined;
    scale?: number | undefined;
    fit?: "cover" | "contain" | "manual" | undefined;
    muted?: boolean | undefined;
    blendMode?: "normal" | "multiply" | "screen" | "overlay" | "darken" | "lighten" | "soft-light" | "hard-light" | undefined;
}, {
    id: string;
    kind: "visual" | "audio";
    label: string;
    volume?: number | undefined;
    opacity?: number | undefined;
    scale?: number | undefined;
    fit?: "cover" | "contain" | "manual" | undefined;
    muted?: boolean | undefined;
    blendMode?: "normal" | "multiply" | "screen" | "overlay" | "darken" | "lighten" | "soft-light" | "hard-light" | undefined;
}>;
export declare const PinnedShotGroup: z.ZodObject<{
    shotId: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    trackId: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    clipIds: z.ZodOptional<z.ZodOptional<z.ZodArray<z.ZodString, "many">>>;
    mode: z.ZodOptional<z.ZodOptional<z.ZodEnum<["images", "video"]>>>;
    videoAssetKey: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    imageClipSnapshot: z.ZodOptional<z.ZodOptional<z.ZodArray<z.ZodRecord<z.ZodString, z.ZodAny>, "many">>>;
}, "strip", z.ZodTypeAny, {
    shotId?: string | undefined;
    trackId?: string | undefined;
    clipIds?: string[] | undefined;
    mode?: "images" | "video" | undefined;
    videoAssetKey?: string | undefined;
    imageClipSnapshot?: Record<string, any>[] | undefined;
}, {
    shotId?: string | undefined;
    trackId?: string | undefined;
    clipIds?: string[] | undefined;
    mode?: "images" | "video" | undefined;
    videoAssetKey?: string | undefined;
    imageClipSnapshot?: Record<string, any>[] | undefined;
}>;
export declare const ThemeOverrides: z.ZodObject<{
    visual: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
    generation: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
    voice: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
    audio: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
    pacing: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
}, "strip", z.ZodTypeAny, {
    visual?: Record<string, any> | undefined;
    audio?: Record<string, any> | undefined;
    generation?: Record<string, any> | undefined;
    voice?: Record<string, any> | undefined;
    pacing?: Record<string, any> | undefined;
}, {
    visual?: Record<string, any> | undefined;
    audio?: Record<string, any> | undefined;
    generation?: Record<string, any> | undefined;
    voice?: Record<string, any> | undefined;
    pacing?: Record<string, any> | undefined;
}>;
export declare const TimelineOutput: z.ZodObject<{
    resolution: z.ZodString;
    fps: z.ZodNumber;
    file: z.ZodString;
    background: z.ZodOptional<z.ZodNullable<z.ZodString>>;
    background_scale: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
}, "strip", z.ZodTypeAny, {
    resolution: string;
    fps: number;
    file: string;
    background?: string | null | undefined;
    background_scale?: number | null | undefined;
}, {
    resolution: string;
    fps: number;
    file: string;
    background?: string | null | undefined;
    background_scale?: number | null | undefined;
}>;
export declare const AssetEntry: z.ZodObject<{
    file: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    url: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    etag: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    content_sha256: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    url_expires_at: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    type: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    duration: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
    resolution: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    fps: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
    generationId: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    variantId: z.ZodOptional<z.ZodOptional<z.ZodString>>;
    thumbnailUrl: z.ZodOptional<z.ZodOptional<z.ZodString>>;
}, "strip", z.ZodTypeAny, {
    type?: string | undefined;
    duration?: number | undefined;
    resolution?: string | undefined;
    fps?: number | undefined;
    file?: string | undefined;
    url?: string | undefined;
    etag?: string | undefined;
    content_sha256?: string | undefined;
    url_expires_at?: string | undefined;
    generationId?: string | undefined;
    variantId?: string | undefined;
    thumbnailUrl?: string | undefined;
}, {
    type?: string | undefined;
    duration?: number | undefined;
    resolution?: string | undefined;
    fps?: number | undefined;
    file?: string | undefined;
    url?: string | undefined;
    etag?: string | undefined;
    content_sha256?: string | undefined;
    url_expires_at?: string | undefined;
    generationId?: string | undefined;
    variantId?: string | undefined;
    thumbnailUrl?: string | undefined;
}>;
export declare const TimelineConfig: z.ZodObject<{
    theme: z.ZodOptional<z.ZodString>;
    clips: z.ZodArray<z.ZodObject<{
        id: z.ZodString;
        at: z.ZodNumber;
        track: z.ZodString;
        source_uuid: z.ZodOptional<z.ZodString>;
        clipType: z.ZodOptional<z.ZodString>;
        asset: z.ZodOptional<z.ZodString>;
        from: z.ZodOptional<z.ZodNumber>;
        to: z.ZodOptional<z.ZodNumber>;
        speed: z.ZodOptional<z.ZodNumber>;
        hold: z.ZodOptional<z.ZodNumber>;
        volume: z.ZodOptional<z.ZodNumber>;
        x: z.ZodOptional<z.ZodNumber>;
        y: z.ZodOptional<z.ZodNumber>;
        width: z.ZodOptional<z.ZodNumber>;
        height: z.ZodOptional<z.ZodNumber>;
        cropTop: z.ZodOptional<z.ZodNumber>;
        cropBottom: z.ZodOptional<z.ZodNumber>;
        cropLeft: z.ZodOptional<z.ZodNumber>;
        cropRight: z.ZodOptional<z.ZodNumber>;
        opacity: z.ZodOptional<z.ZodNumber>;
        text: z.ZodOptional<z.ZodObject<{
            content: z.ZodOptional<z.ZodOptional<z.ZodString>>;
            fontFamily: z.ZodOptional<z.ZodOptional<z.ZodString>>;
            fontSize: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
            color: z.ZodOptional<z.ZodOptional<z.ZodString>>;
            align: z.ZodOptional<z.ZodOptional<z.ZodEnum<["left", "center", "right"]>>>;
            bold: z.ZodOptional<z.ZodOptional<z.ZodBoolean>>;
            italic: z.ZodOptional<z.ZodOptional<z.ZodBoolean>>;
        }, "strip", z.ZodTypeAny, {
            content?: string | undefined;
            fontFamily?: string | undefined;
            fontSize?: number | undefined;
            color?: string | undefined;
            align?: "left" | "center" | "right" | undefined;
            bold?: boolean | undefined;
            italic?: boolean | undefined;
        }, {
            content?: string | undefined;
            fontFamily?: string | undefined;
            fontSize?: number | undefined;
            color?: string | undefined;
            align?: "left" | "center" | "right" | undefined;
            bold?: boolean | undefined;
            italic?: boolean | undefined;
        }>>;
        entrance: z.ZodOptional<z.ZodObject<{
            type: z.ZodOptional<z.ZodOptional<z.ZodString>>;
            duration: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
            intensity: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
            params: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
        }, "strip", z.ZodTypeAny, {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            duration?: number | undefined;
            intensity?: number | undefined;
        }, {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            duration?: number | undefined;
            intensity?: number | undefined;
        }>>;
        exit: z.ZodOptional<z.ZodObject<{
            type: z.ZodOptional<z.ZodOptional<z.ZodString>>;
            duration: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
            intensity: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
            params: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
        }, "strip", z.ZodTypeAny, {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            duration?: number | undefined;
            intensity?: number | undefined;
        }, {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            duration?: number | undefined;
            intensity?: number | undefined;
        }>>;
        continuous: z.ZodOptional<z.ZodObject<{
            type: z.ZodOptional<z.ZodOptional<z.ZodString>>;
            intensity: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
            params: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
        }, "strip", z.ZodTypeAny, {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            intensity?: number | undefined;
        }, {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            intensity?: number | undefined;
        }>>;
        transition: z.ZodOptional<z.ZodUnion<[z.ZodObject<{
            type: z.ZodString;
            duration: z.ZodNumber;
        }, "strip", z.ZodTypeAny, {
            type: string;
            duration: number;
        }, {
            type: string;
            duration: number;
        }>, z.ZodObject<{
            id: z.ZodOptional<z.ZodOptional<z.ZodString>>;
            type: z.ZodOptional<z.ZodOptional<z.ZodString>>;
            duration: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
            durationFrames: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
            params: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
        }, "strip", z.ZodTypeAny, {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            duration?: number | undefined;
            id?: string | undefined;
            durationFrames?: number | undefined;
        }, {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            duration?: number | undefined;
            id?: string | undefined;
            durationFrames?: number | undefined;
        }>, z.ZodString]>>;
        effects: z.ZodOptional<z.ZodUnion<[z.ZodArray<z.ZodObject<{
            fade_in: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
            fade_out: z.ZodOptional<z.ZodOptional<z.ZodNumber>>;
        }, "strip", z.ZodTypeAny, {
            fade_in?: number | undefined;
            fade_out?: number | undefined;
        }, {
            fade_in?: number | undefined;
            fade_out?: number | undefined;
        }>, "many">, z.ZodRecord<z.ZodString, z.ZodNumber>]>>;
        params: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
        generation: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
        pool_id: z.ZodOptional<z.ZodString>;
        clip_order: z.ZodOptional<z.ZodNumber>;
    }, "strip", z.ZodTypeAny, {
        at: number;
        id: string;
        track: string;
        params?: Record<string, any> | undefined;
        source_uuid?: string | undefined;
        clipType?: string | undefined;
        asset?: string | undefined;
        from?: number | undefined;
        to?: number | undefined;
        speed?: number | undefined;
        hold?: number | undefined;
        volume?: number | undefined;
        x?: number | undefined;
        y?: number | undefined;
        width?: number | undefined;
        height?: number | undefined;
        cropTop?: number | undefined;
        cropBottom?: number | undefined;
        cropLeft?: number | undefined;
        cropRight?: number | undefined;
        opacity?: number | undefined;
        text?: {
            content?: string | undefined;
            fontFamily?: string | undefined;
            fontSize?: number | undefined;
            color?: string | undefined;
            align?: "left" | "center" | "right" | undefined;
            bold?: boolean | undefined;
            italic?: boolean | undefined;
        } | undefined;
        entrance?: {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            duration?: number | undefined;
            intensity?: number | undefined;
        } | undefined;
        exit?: {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            duration?: number | undefined;
            intensity?: number | undefined;
        } | undefined;
        continuous?: {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            intensity?: number | undefined;
        } | undefined;
        transition?: string | {
            type: string;
            duration: number;
        } | {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            duration?: number | undefined;
            id?: string | undefined;
            durationFrames?: number | undefined;
        } | undefined;
        effects?: {
            fade_in?: number | undefined;
            fade_out?: number | undefined;
        }[] | Record<string, number> | undefined;
        generation?: Record<string, any> | undefined;
        pool_id?: string | undefined;
        clip_order?: number | undefined;
    }, {
        at: number;
        id: string;
        track: string;
        params?: Record<string, any> | undefined;
        source_uuid?: string | undefined;
        clipType?: string | undefined;
        asset?: string | undefined;
        from?: number | undefined;
        to?: number | undefined;
        speed?: number | undefined;
        hold?: number | undefined;
        volume?: number | undefined;
        x?: number | undefined;
        y?: number | undefined;
        width?: number | undefined;
        height?: number | undefined;
        cropTop?: number | undefined;
        cropBottom?: number | undefined;
        cropLeft?: number | undefined;
        cropRight?: number | undefined;
        opacity?: number | undefined;
        text?: {
            content?: string | undefined;
            fontFamily?: string | undefined;
            fontSize?: number | undefined;
            color?: string | undefined;
            align?: "left" | "center" | "right" | undefined;
            bold?: boolean | undefined;
            italic?: boolean | undefined;
        } | undefined;
        entrance?: {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            duration?: number | undefined;
            intensity?: number | undefined;
        } | undefined;
        exit?: {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            duration?: number | undefined;
            intensity?: number | undefined;
        } | undefined;
        continuous?: {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            intensity?: number | undefined;
        } | undefined;
        transition?: string | {
            type: string;
            duration: number;
        } | {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            duration?: number | undefined;
            id?: string | undefined;
            durationFrames?: number | undefined;
        } | undefined;
        effects?: {
            fade_in?: number | undefined;
            fade_out?: number | undefined;
        }[] | Record<string, number> | undefined;
        generation?: Record<string, any> | undefined;
        pool_id?: string | undefined;
        clip_order?: number | undefined;
    }>, "many">;
    tracks: z.ZodOptional<z.ZodArray<z.ZodObject<{
        id: z.ZodString;
        kind: z.ZodEnum<["visual", "audio"]>;
        label: z.ZodString;
        scale: z.ZodOptional<z.ZodNumber>;
        fit: z.ZodOptional<z.ZodEnum<["cover", "contain", "manual"]>>;
        opacity: z.ZodOptional<z.ZodNumber>;
        volume: z.ZodOptional<z.ZodNumber>;
        muted: z.ZodOptional<z.ZodBoolean>;
        blendMode: z.ZodOptional<z.ZodEnum<["normal", "multiply", "screen", "overlay", "darken", "lighten", "soft-light", "hard-light"]>>;
    }, "strip", z.ZodTypeAny, {
        id: string;
        kind: "visual" | "audio";
        label: string;
        volume?: number | undefined;
        opacity?: number | undefined;
        scale?: number | undefined;
        fit?: "cover" | "contain" | "manual" | undefined;
        muted?: boolean | undefined;
        blendMode?: "normal" | "multiply" | "screen" | "overlay" | "darken" | "lighten" | "soft-light" | "hard-light" | undefined;
    }, {
        id: string;
        kind: "visual" | "audio";
        label: string;
        volume?: number | undefined;
        opacity?: number | undefined;
        scale?: number | undefined;
        fit?: "cover" | "contain" | "manual" | undefined;
        muted?: boolean | undefined;
        blendMode?: "normal" | "multiply" | "screen" | "overlay" | "darken" | "lighten" | "soft-light" | "hard-light" | undefined;
    }>, "many">>;
    pinnedShotGroups: z.ZodOptional<z.ZodArray<z.ZodObject<{
        shotId: z.ZodOptional<z.ZodOptional<z.ZodString>>;
        trackId: z.ZodOptional<z.ZodOptional<z.ZodString>>;
        clipIds: z.ZodOptional<z.ZodOptional<z.ZodArray<z.ZodString, "many">>>;
        mode: z.ZodOptional<z.ZodOptional<z.ZodEnum<["images", "video"]>>>;
        videoAssetKey: z.ZodOptional<z.ZodOptional<z.ZodString>>;
        imageClipSnapshot: z.ZodOptional<z.ZodOptional<z.ZodArray<z.ZodRecord<z.ZodString, z.ZodAny>, "many">>>;
    }, "strip", z.ZodTypeAny, {
        shotId?: string | undefined;
        trackId?: string | undefined;
        clipIds?: string[] | undefined;
        mode?: "images" | "video" | undefined;
        videoAssetKey?: string | undefined;
        imageClipSnapshot?: Record<string, any>[] | undefined;
    }, {
        shotId?: string | undefined;
        trackId?: string | undefined;
        clipIds?: string[] | undefined;
        mode?: "images" | "video" | undefined;
        videoAssetKey?: string | undefined;
        imageClipSnapshot?: Record<string, any>[] | undefined;
    }>, "many">>;
    theme_overrides: z.ZodOptional<z.ZodObject<{
        visual: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
        generation: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
        voice: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
        audio: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
        pacing: z.ZodOptional<z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>>;
    }, "strip", z.ZodTypeAny, {
        visual?: Record<string, any> | undefined;
        audio?: Record<string, any> | undefined;
        generation?: Record<string, any> | undefined;
        voice?: Record<string, any> | undefined;
        pacing?: Record<string, any> | undefined;
    }, {
        visual?: Record<string, any> | undefined;
        audio?: Record<string, any> | undefined;
        generation?: Record<string, any> | undefined;
        voice?: Record<string, any> | undefined;
        pacing?: Record<string, any> | undefined;
    }>>;
    generation_defaults: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    output: z.ZodOptional<z.ZodObject<{
        resolution: z.ZodString;
        fps: z.ZodNumber;
        file: z.ZodString;
        background: z.ZodOptional<z.ZodNullable<z.ZodString>>;
        background_scale: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    }, "strip", z.ZodTypeAny, {
        resolution: string;
        fps: number;
        file: string;
        background?: string | null | undefined;
        background_scale?: number | null | undefined;
    }, {
        resolution: string;
        fps: number;
        file: string;
        background?: string | null | undefined;
        background_scale?: number | null | undefined;
    }>>;
}, "strip", z.ZodTypeAny, {
    clips: {
        at: number;
        id: string;
        track: string;
        params?: Record<string, any> | undefined;
        source_uuid?: string | undefined;
        clipType?: string | undefined;
        asset?: string | undefined;
        from?: number | undefined;
        to?: number | undefined;
        speed?: number | undefined;
        hold?: number | undefined;
        volume?: number | undefined;
        x?: number | undefined;
        y?: number | undefined;
        width?: number | undefined;
        height?: number | undefined;
        cropTop?: number | undefined;
        cropBottom?: number | undefined;
        cropLeft?: number | undefined;
        cropRight?: number | undefined;
        opacity?: number | undefined;
        text?: {
            content?: string | undefined;
            fontFamily?: string | undefined;
            fontSize?: number | undefined;
            color?: string | undefined;
            align?: "left" | "center" | "right" | undefined;
            bold?: boolean | undefined;
            italic?: boolean | undefined;
        } | undefined;
        entrance?: {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            duration?: number | undefined;
            intensity?: number | undefined;
        } | undefined;
        exit?: {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            duration?: number | undefined;
            intensity?: number | undefined;
        } | undefined;
        continuous?: {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            intensity?: number | undefined;
        } | undefined;
        transition?: string | {
            type: string;
            duration: number;
        } | {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            duration?: number | undefined;
            id?: string | undefined;
            durationFrames?: number | undefined;
        } | undefined;
        effects?: {
            fade_in?: number | undefined;
            fade_out?: number | undefined;
        }[] | Record<string, number> | undefined;
        generation?: Record<string, any> | undefined;
        pool_id?: string | undefined;
        clip_order?: number | undefined;
    }[];
    theme?: string | undefined;
    tracks?: {
        id: string;
        kind: "visual" | "audio";
        label: string;
        volume?: number | undefined;
        opacity?: number | undefined;
        scale?: number | undefined;
        fit?: "cover" | "contain" | "manual" | undefined;
        muted?: boolean | undefined;
        blendMode?: "normal" | "multiply" | "screen" | "overlay" | "darken" | "lighten" | "soft-light" | "hard-light" | undefined;
    }[] | undefined;
    pinnedShotGroups?: {
        shotId?: string | undefined;
        trackId?: string | undefined;
        clipIds?: string[] | undefined;
        mode?: "images" | "video" | undefined;
        videoAssetKey?: string | undefined;
        imageClipSnapshot?: Record<string, any>[] | undefined;
    }[] | undefined;
    theme_overrides?: {
        visual?: Record<string, any> | undefined;
        audio?: Record<string, any> | undefined;
        generation?: Record<string, any> | undefined;
        voice?: Record<string, any> | undefined;
        pacing?: Record<string, any> | undefined;
    } | undefined;
    generation_defaults?: Record<string, unknown> | undefined;
    output?: {
        resolution: string;
        fps: number;
        file: string;
        background?: string | null | undefined;
        background_scale?: number | null | undefined;
    } | undefined;
}, {
    clips: {
        at: number;
        id: string;
        track: string;
        params?: Record<string, any> | undefined;
        source_uuid?: string | undefined;
        clipType?: string | undefined;
        asset?: string | undefined;
        from?: number | undefined;
        to?: number | undefined;
        speed?: number | undefined;
        hold?: number | undefined;
        volume?: number | undefined;
        x?: number | undefined;
        y?: number | undefined;
        width?: number | undefined;
        height?: number | undefined;
        cropTop?: number | undefined;
        cropBottom?: number | undefined;
        cropLeft?: number | undefined;
        cropRight?: number | undefined;
        opacity?: number | undefined;
        text?: {
            content?: string | undefined;
            fontFamily?: string | undefined;
            fontSize?: number | undefined;
            color?: string | undefined;
            align?: "left" | "center" | "right" | undefined;
            bold?: boolean | undefined;
            italic?: boolean | undefined;
        } | undefined;
        entrance?: {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            duration?: number | undefined;
            intensity?: number | undefined;
        } | undefined;
        exit?: {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            duration?: number | undefined;
            intensity?: number | undefined;
        } | undefined;
        continuous?: {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            intensity?: number | undefined;
        } | undefined;
        transition?: string | {
            type: string;
            duration: number;
        } | {
            params?: Record<string, any> | undefined;
            type?: string | undefined;
            duration?: number | undefined;
            id?: string | undefined;
            durationFrames?: number | undefined;
        } | undefined;
        effects?: {
            fade_in?: number | undefined;
            fade_out?: number | undefined;
        }[] | Record<string, number> | undefined;
        generation?: Record<string, any> | undefined;
        pool_id?: string | undefined;
        clip_order?: number | undefined;
    }[];
    theme?: string | undefined;
    tracks?: {
        id: string;
        kind: "visual" | "audio";
        label: string;
        volume?: number | undefined;
        opacity?: number | undefined;
        scale?: number | undefined;
        fit?: "cover" | "contain" | "manual" | undefined;
        muted?: boolean | undefined;
        blendMode?: "normal" | "multiply" | "screen" | "overlay" | "darken" | "lighten" | "soft-light" | "hard-light" | undefined;
    }[] | undefined;
    pinnedShotGroups?: {
        shotId?: string | undefined;
        trackId?: string | undefined;
        clipIds?: string[] | undefined;
        mode?: "images" | "video" | undefined;
        videoAssetKey?: string | undefined;
        imageClipSnapshot?: Record<string, any>[] | undefined;
    }[] | undefined;
    theme_overrides?: {
        visual?: Record<string, any> | undefined;
        audio?: Record<string, any> | undefined;
        generation?: Record<string, any> | undefined;
        voice?: Record<string, any> | undefined;
        pacing?: Record<string, any> | undefined;
    } | undefined;
    generation_defaults?: Record<string, unknown> | undefined;
    output?: {
        resolution: string;
        fps: number;
        file: string;
        background?: string | null | undefined;
        background_scale?: number | null | undefined;
    } | undefined;
}>;
export declare const Theme: z.ZodObject<{
    id: z.ZodString;
    visual: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    generation: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    voice: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    audio: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    pacing: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
}, "passthrough", z.ZodTypeAny, z.objectOutputType<{
    id: z.ZodString;
    visual: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    generation: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    voice: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    audio: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    pacing: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
}, z.ZodTypeAny, "passthrough">, z.objectInputType<{
    id: z.ZodString;
    visual: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    generation: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    voice: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    audio: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    pacing: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
}, z.ZodTypeAny, "passthrough">>;
export type TimelineClipT = z.infer<typeof TimelineClip>;
export type TimelineConfigT = z.infer<typeof TimelineConfig>;
export type ThemeT = z.infer<typeof Theme>;
export type ThemeOverridesT = z.infer<typeof ThemeOverrides>;
export type TimelineOutputT = z.infer<typeof TimelineOutput>;
export type AssetEntryT = z.infer<typeof AssetEntry>;
//# sourceMappingURL=schemas.d.ts.map