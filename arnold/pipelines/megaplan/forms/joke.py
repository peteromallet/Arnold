"""Joke form registration."""

from __future__ import annotations

from . import Form, Provocation, ProvocationCatalog, ProvocateurVoice, register


VOICES = (
    ProvocateurVoice(
        id="formalist",
        persona_text="Structure hawk: protect economy, escalation, setup-payoff clarity, and the button's load-bearing job.",
        vector_bias=("cut", "force"),
    ),
    ProvocateurVoice(
        id="iconoclast",
        persona_text="Risk hawk: attack the safe choice, expose the lie, and demand the joke make a move someone could hate.",
        vector_bias=("spark", "force"),
    ),
    ProvocateurVoice(
        id="audience",
        persona_text="Room hawk: watch one named listener getting bored, confused, or delighted beat by beat.",
        vector_bias=("spark", "cut"),
    ),
)


register(
    Form(
        id="joke",
        display_name="Joke",
        output_extension=".md",
        beat_ids=("opening", "inciting", "obstacle", "turn", "button"),
        prep_checklist=(
            "Name the comic premise and the primary criterion.",
            "Identify the beat that currently carries the biggest laugh.",
            "Mark the safest or most replaceable beat before selecting provocations.",
        ),
        stance_voice_hint=(
            "Write like the person responsible for the laugh, not a critic explaining it. "
            "Name the provocation and the comic bet you now stand behind."
        ),
        provocateur_voices=VOICES,
        provocations=ProvocationCatalog(
            cuts=(
                Provocation(
                    id="joke-cut-darling",
                    vector="cut",
                    subtype="kill_darling",
                    prompt_text=(
                        "Cut the line you would fight hardest to keep. If the joke is worse, you were right; "
                        "if it is the same, you killed a darling."
                    ),
                    targets=("button", "turn"),
                ),
                Provocation(
                    id="joke-cut-explanation",
                    vector="cut",
                    subtype="strip_explanation",
                    prompt_text="Remove the sentence that explains why the joke is funny. Make the behavior carry it.",
                    targets=("opening", "turn"),
                ),
                Provocation(
                    id="joke-cut-softener",
                    vector="cut",
                    subtype="expose_risk",
                    prompt_text="Cut the apology, qualifier, or wink that protects the joke from being judged.",
                    targets=("opening", "button"),
                ),
            ),
            forces=(
                Provocation(
                    id="joke-force-halve",
                    vector="force",
                    subtype="compress",
                    prompt_text="Halve it. Write the line or beat that survives and rebuild only what earns its place.",
                    targets=("opening", "button"),
                ),
                Provocation(
                    id="joke-force-button-first",
                    vector="force",
                    subtype="reorder",
                    prompt_text="Put the button's logic in the first beat, then find a stranger final turn.",
                    targets=("opening", "button"),
                ),
                Provocation(
                    id="joke-force-silent",
                    vector="force",
                    subtype="generative_constraint",
                    prompt_text="No character may explain the premise. The object, action, or status game must do the talking.",
                    targets=("inciting", "obstacle", "turn"),
                ),
            ),
            sparks=(
                Provocation(
                    id="absurdist",
                    vector="spark",
                    subtype="borrowed_lens",
                    prompt_text="Push the scene into boldly illogical but still playable behavior.",
                    targets=("turn", "button"),
                ),
                Provocation(
                    id="twist_ending",
                    vector="spark",
                    subtype="inversion",
                    prompt_text="Force a late reveal or reversal that recontextualizes the scene's final beat.",
                    targets=("turn", "button"),
                ),
                Provocation(
                    id="hyper_specific_detail",
                    vector="spark",
                    subtype="sensory_escalation",
                    prompt_text="Make the comedy land through oddly precise, concrete particulars.",
                    targets=("opening", "obstacle"),
                ),
                Provocation(
                    id="genre_swap",
                    vector="spark",
                    subtype="forced_transplant",
                    prompt_text="Make the scene suddenly obey the logic, tone, or stakes of a different genre.",
                    targets=("inciting", "turn"),
                ),
                Provocation(
                    id="subtext_inversion",
                    vector="spark",
                    subtype="inversion",
                    prompt_text="Flip what the scene is secretly about without changing the surface action.",
                    targets=("obstacle", "turn"),
                ),
                Provocation(
                    id="prop_as_character",
                    vector="spark",
                    subtype="hostile_gift",
                    prompt_text="Turn an object into an active comic presence with intention or status.",
                    targets=("inciting", "obstacle"),
                ),
                Provocation(
                    id="bathos",
                    vector="spark",
                    subtype="borrowed_move",
                    prompt_text="Crash lofty emotion, stakes, or rhetoric into something humiliatingly mundane.",
                    targets=("turn", "button"),
                ),
                Provocation(
                    id="scale_shift",
                    vector="spark",
                    subtype="substitution",
                    prompt_text="Distort the scene by making the stakes or framing wildly too big or too small.",
                    targets=("opening", "turn"),
                ),
                Provocation(
                    id="narrator_reveal",
                    vector="spark",
                    subtype="hostile_gift",
                    prompt_text="Add a telling frame, hidden storyteller, or point-of-view reveal that snaps the scene into a stranger shape.",
                    targets=("opening", "button"),
                ),
            ),
        ),
    )
)
