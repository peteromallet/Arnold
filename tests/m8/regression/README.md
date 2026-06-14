# M8 Regression Package

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

This package holds reusable fixtures for the hard acceptance regressions that
motivate M8. The exact historical SHAs are not recorded in-repo yet, so the
helpers name the failure class and ticket until those references can be added.

The four motivating failure classes are:

1. Raw `additionalProperties` acceptance where structural validation should
   reject undeclared payload keys before downstream logic sees them.
2. Model budget overflow escaping the seam without a typed failure contract or
   explicit budget diagnostic.
3. Malformed named-output capture where `capture_step_output` accepted the wrong
   shape instead of fail-closing with a structural error.
4. Suspended child contracts not propagating suspension to the parent reduce
   result under the `MAX_WINS` status lattice.

`helpers.py` centralizes small schema payloads, `ContractResult` factories, and
assertion helpers so later M8 regression tests can stay focused on the specific
failure under test.
