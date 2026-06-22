"""Poem form registration."""

from __future__ import annotations

from . import Form, Provocation, ProvocationCatalog, ProvocateurVoice, register


VOICES = (
    ProvocateurVoice(
        id="formalist",
        persona_text="Line hawk: protect image sequence, turn pressure, silence, and the close's earned charge.",
        vector_bias=("cut", "force"),
    ),
    ProvocateurVoice(
        id="iconoclast",
        persona_text="Risk hawk: attack tasteful vagueness, expose the evasion, and demand one embarrassing concrete choice.",
        vector_bias=("spark", "force"),
    ),
    ProvocateurVoice(
        id="audience",
        persona_text="Reader hawk: read for one alert stranger who needs stakes, texture, and a reason to stay.",
        vector_bias=("spark", "cut"),
    ),
)


register(
    Form(
        id="poem",
        display_name="Poem",
        output_extension=".md",
        beat_ids=("opening_image", "turn", "close"),
        prep_checklist=(
            "Name the governing image.",
            "Find the abstract word most likely to weaken the poem.",
            "Mark where the poem turns or refuses to turn.",
        ),
        stance_voice_hint=(
            "Write as the poet defending a live choice. Name the provocation, the image or turn you chose, "
            "and the refusal behind it."
        ),
        provocateur_voices=VOICES,
        provocations=ProvocationCatalog(
            cuts=(
                Provocation(
                    id="poem-cut-abstraction",
                    vector="cut",
                    subtype="strip_abstraction",
                    prompt_text="Cut the most abstract word. Replace its job with an image, sound, or physical act.",
                    targets=("opening_image", "turn"),
                ),
                Provocation(
                    id="poem-cut-prettiest-line",
                    vector="cut",
                    subtype="kill_darling",
                    prompt_text="Cut the prettiest line. If the poem loses nothing, it was decoration.",
                    targets=("opening_image", "close"),
                ),
                Provocation(
                    id="poem-cut-explained-feeling",
                    vector="cut",
                    subtype="expose_unsaid",
                    prompt_text="Cut the line that names the feeling. Make the next room, object, or weather confess it instead.",
                    targets=("turn", "close"),
                ),
            ),
            forces=(
                Provocation(
                    id="poem-force-halve",
                    vector="force",
                    subtype="compress",
                    prompt_text="Halve it. Keep only the image, the turn, and the close that cannot be paraphrased.",
                    targets=("opening_image", "turn", "close"),
                ),
                Provocation(
                    id="poem-force-no-i",
                    vector="force",
                    subtype="generative_constraint",
                    prompt_text="Remove every first-person pronoun. Let the poem reveal its speaker by pressure, not declaration.",
                    targets=("opening_image", "turn"),
                ),
                Provocation(
                    id="poem-force-close-first",
                    vector="force",
                    subtype="reorder",
                    prompt_text="Move the closing image to the first line. Write a new close that has learned something sharper.",
                    targets=("opening_image", "close"),
                ),
            ),
            sparks=(
                Provocation(
                    id="poem-spark-hostile-object",
                    vector="spark",
                    subtype="hostile_gift",
                    prompt_text="A cracked blue mug belongs in this poem. Refuse it cleanly or make it unavoidable.",
                    targets=("opening_image", "turn"),
                ),
                Provocation(
                    id="poem-spark-confession",
                    vector="spark",
                    subtype="inversion",
                    prompt_text="Write the version of this that is a confession, not a performance.",
                    targets=("turn", "close"),
                ),
                Provocation(
                    id="poem-spark-recipe",
                    vector="spark",
                    subtype="forced_transplant",
                    prompt_text="Steal the structure of a recipe: ingredient, instruction, heat, waiting, serving.",
                    targets=("opening_image", "turn", "close"),
                ),
                Provocation(
                    id="poem-spark-dickinson-dash",
                    vector="spark",
                    subtype="borrowed_move",
                    prompt_text="Borrow Emily Dickinson's interrupting dash: let syntax fracture where the poem is most certain.",
                    targets=("turn", "close"),
                ),
            ),
        ),
    )
)
