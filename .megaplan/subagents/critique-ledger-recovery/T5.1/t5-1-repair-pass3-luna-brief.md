# GPT-5.6 Luna implementation — T5.1 repair pass 3

Continue from exact clean commit `7c254f7f0d15ba4e835a6fe7cae40b47d29ef7cd`
in `/private/tmp/arnold-critique-recovery-t5-1-20260802`. Start only when a
mutation slot is free. Read the full pass-3 independent review when written.
Preserve the 88-probe closed-world verifier and all factual evidence fixes.

Close the remaining candidate-identity gap without a self-referential commit:

- the command-line verifier must require explicit out-of-band `--expected-head`,
  `--expected-tree`, and `--expected-parent` values (or an equivalently strict
  typed expected-identity object) with no current-HEAD/default fallback;
- the library API must require the same immutable expected identity and compare
  it to independently executed Git object reads before trusting any manifest,
  checkout bytes, changed paths, or claimed receipt;
- the expected values must not come from the candidate manifest/receipt/source
  itself, and all output must echo them plus the observed values and equality;
- the post-commit workflow is: commit scoped code/evidence, compute exact
  commit/tree/parent externally, run the verifier with those exact arguments,
  independently rehash from Git objects without importing candidate code, and
  write the result artifact outside the candidate commit. If code is amended,
  repeat with the new identity;
- reject absent/wrong/forked/swapped head/tree/parent, a same-parent/same-path
  different commit, manifest claims that disagree, and imported-function or Git
  output substitution. Where in-process monkeypatching means the verifier
  process itself is compromised, the independent no-import verifier/result must
  detect disagreement; document the trust split precisely rather than claiming
  impossible self-authentication.

Add regressions reproducing the pass-3 forged head/tree acceptance, exact-arg
omission and substitutions, and independent external comparison. Run all 88
tamper probes, new hostile cases, static/diff/Git integrity checks. Do not alter
or resolve any of the four `OWNER_DECISION_PENDING` outcomes, authorize T5.2,
contact cloud/providers, or claim formal completion.

Commit scoped work, leave clean, and write exact commit/tree/parent, commands,
hashes, tests, limitations and four pending decisions to:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T5.1/t5-1-repair-pass3-result.md`.
