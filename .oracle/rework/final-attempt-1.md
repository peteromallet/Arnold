# Rework tasklist — final attempt 1 (from FinalA/FinalB)
1. [normal] _redact misses real key shapes (sk-ant-api03-, sk-proj-, sk-or-v1-, xai-) and flow
   never threads the accepted key into verify_route/wire failure output. Fix: prefer repo's
   agentbox.redaction.redact_text (check its patterns) or widen regex; pass secrets=[key] into
   verify_route from _configure_provider; redact key in wire_api_key failure detail. Tests for
   each shape.
2. [normal] preflight option [4] continue branch unreachable (env-only re-check vs store-based
   persistence). Fix: after flow exit 0, re-check readiness via detect.scan_providers READY for
   the failing slots' providers; if all previously-missing slots now ready -> continue launch,
   else exit 7 unchanged. Update docs/onboarding.md wording if needed. Fix the fake_run_flow
   test to model reality (flow does NOT set env).
3. [normal] models.yml read-modify-write unlocked -> concurrent first-run launches can drop a
   provider block. Fix: fcntl.flock on a lockfile in agent dir around merge critical section
   (both cli_proxy and static models.yml writes); test two-process contention via subprocess or
   threaded flock simulation.
4. [normal] guards miss -r resume alias (and -r= prefix). Fix + extend parametrize.
5. [trivial] remove dead omp_bin parameter from run_flow/offer_and_repreflight (verify no caller
   passes it; doctor/preflight call sites included).
Acceptance: all fixed; full onboarding suite + touched suites green; no new findings on these paths.
