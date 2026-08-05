# Doubt Lens (Adversarial)

This is the doubt cycle from `bmad-custom-pr-review`'s adversarial review, implemented as a
regular lens (`after = "correctness"` in `lenses.toml`) — **not** a separate harness. It receives
`correctness`'s findings as input and tries to refute each one before it's reported.

## What to do

For each finding the `correctness` lens produced:

1. **Try to refute it.** Re-read the actual code path the finding cites. Ask: is the
   `trigger_condition` actually reachable? Does the code already guard against it somewhere the
   original finding missed (an earlier validation, a type system guarantee, a caller-side
   invariant)? Default to **refuted = true if uncertain** — this lens exists to kill
   plausible-but-wrong findings, not to rubber-stamp them.
2. **Confirm survivors independently.** For a finding that survives refutation, verify it once more
   from a different angle than the original: if `correctness` reasoned from the diff, check the
   full file; if it reasoned about one call site, check other call sites for the same pattern.
3. Do not invent new findings here — this lens's job is adversarial verification of `correctness`'s
   output, not independent discovery. New issues found while doubting belong to whichever lens
   actually owns them (open a `security`/`resilience`/`style` finding as appropriate instead).

## Output

Emit one record per input finding: the original finding's `location`, whether it was
`refuted` (true/false) and why, and — only for survivors — re-emit the finding with
`lens: "doubt"` alongside the fields it inherited from `correctness` (`location`,
`trigger_condition`, `guard_snippet`, `potential_consequence`). Refuted findings are not reported
to the Coordinator; only survivors are.

## Why this matters

A finding that sounds right but doesn't reproduce wastes triage time and erodes trust in the
review output. This lens is the one place in the pipeline whose entire job is trying to make
findings go away — it should feel adversarial, not collegial.
