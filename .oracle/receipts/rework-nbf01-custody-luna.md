# NBF-01 custody rework receipt — RW-CUSTODY

- Executor model: GPT-5.6 Luna (`codex:gpt-5.6-luna`)
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Immutable source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Historical custody SHA retained and labeled: `f8725af516da8d4249eb0d63563c37776d80daf8`
- `.oracle/custody.md` digest before: `29f7ad58cfa9057ccc02006d70fede01ab5f4a38a3e351acd762a545ed3ae608`
- `.oracle/custody.md` digest after: `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`

RW-CUSTODY made the evidence-only labeling correction: the original
`f8725af516da8d4249eb0d63563c37776d80daf8` capture is explicitly historical,
and `798c50619204010ed3f4297fbb57988fe9381924` is the current immutable source
base for the resumed run. No source, tests, tasklist, plan, status, commit, or
push was changed.
