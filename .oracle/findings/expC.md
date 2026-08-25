# Area C — choke points + doctor (Explorer C)
CP1 agentbox_adapter.py L200-204 MegaplanChainLaunchError('credential_preflight_failed') — headless context.
CP2 preflight.py preflight_or_raise() L373-414 — exits 7 both modes; ALREADY renders a TTY 4-option menu at L325-370 with UNIMPLEMENTED handlers → cleanest local-path insertion point for the offer.
CP3 execution_environment.py preflight_phase() L156-171 — git provenance/isolation only, NOT credential gate.
CP4 workers/omp.py L1232-1246 — CliError('authentication') inside worker subprocess (too late/deep for offer).
Doctors: megaplan observability/doctor.py handle_doctor() L794 (plan/repo/adaptive_critique modes, no cred checks); agentbox/doctor.py checkup() L30 (checks credentials ROOT exists only); strategy doctor L1021. Registration: megaplan cli/__init__.py parser L649 dispatch L2917/L3732; agentbox cli.py L176-180/L304-305. Local CLI path cli/run.py _validate_profile_for_run() L628-640 calls preflight_or_raise catching SystemExit.
TWO independent preflight systems: agentbox chain manifest vs local profile-slot env check (exit 7). Third worker-level env gate in omp.py.
