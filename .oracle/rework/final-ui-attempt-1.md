# Rework tasklist — final-ui attempt 1 (from FinalUIA/FinalUIB)
1. [normal] _omp_supports_onboard false-positives on pre-onboard builds (omp dispatcher exits 0
   printing launch help for unknown subcommands). Fix: supported ONLY if exit==0 AND probe
   output contains the onboard help marker ("detect-first provider onboarding"); everything
   else -> unsupported -> Python flow. Update stub tests (marker text required); add explicit
   unknown-command-output regression stub.
2. [normal] fork scan.ts: models.yml entries without an apiKey must NOT count as ready
   (unverifiable override rows). Fix + test.
Acceptance: both fixed; Arnold onboarding suite + fork suites green.
