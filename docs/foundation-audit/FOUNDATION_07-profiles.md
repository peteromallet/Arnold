First read `FOUNDATION_PREAMBLE.md` (shared context + output rules). Obey it.

## YOUR SUBSYSTEM: the profiles / model-resolution system (`profiles/`, ~1453 LOC)

Every pack depends on profile resolution (which model runs which phase). The brief notes
`VALID_PHASE_KEYS` is HARDCODED to planning's phases — "a legacy quirk to clean up but not move."
That hardcoding is a foundational coupling: a "phase-agnostic platform" whose profile system only
knows planning's phase names. Dig in.

Investigate (cite path:line):
- `profiles/` package: how profiles are defined, loaded, validated, resolved per phase/step.
  Find `VALID_PHASE_KEYS` and everything that references it. What breaks if a *discovered pack*
  (creative/doc, or a new pack) has phases NOT in `VALID_PHASE_KEYS`? Does validation reject them,
  silently ignore, or crash?
- `resolve_agent_mode`, `phase_model`, per-phase model overrides — how does a profile map to the
  pipeline's actual Step names? Is there a name-matching assumption (Step.name == phase key)?
- How do creative/doc packs get their models resolved TODAY if the profile system is planning-keyed?
  (This reveals whether discovered packs already work around a planning-shaped profile system —
  evidence of latent incompatibility.)
- Profile precedence, defaults, `recommended_profiles`/`default_profile` metadata, robustness
  interaction. Any global/singleton profile state?

Key question: is the profile system genuinely pipeline-agnostic, or is it a planning-phase-shaped
system that the brief under-rates as "a quirk to clean up"? If discovered packs already have to
fight it, that's a foundational blocker for "any pack, same contract." Quantify how planning-coupled
the profile layer really is and what a truly pack-agnostic profile resolution would require.
