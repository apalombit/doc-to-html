# Probes may target a re-read, but never supply the expected value

A Probe's finding may direct **where** to look again — which cells are implicated, at what resolution, with which Engine. A Probe's expected value must never enter a prompt.

Concretely: `"re-read the Amount column, rows 3-5, from this upscaled crop"` is allowed. `"this column should total 385.00, re-read it"` is not.

## Why

A failed Probe cannot tell you which number is wrong. If line items read 800, 75, 10 against a stated total of 385, the failure is identical whether a line item was misread or the total was. Injecting the expected value silently assumes the former: the model bends whichever number it can until the arithmetic reconciles. When the stated total was the misread one, a correct line item gets "corrected" into a wrong one, every check then passes, and the failure signal is gone. That is worse than the original error, because it is no longer detectable.

A Probe is a test. Supplying the expected value hands over the answer key, after which a passing Probe tells you the model can copy a number — not that it read the page.

## Consequences

Someone will notice that Probe pass rates improve when this rule is broken, and that improvement is exactly the symptom the rule exists to prevent. Pass rate is only meaningful while the model has never been told what would make it pass.

Showing a Draft render beside the Source Image for comparison is not covered by this rule and remains allowed — it presents evidence, not an answer.
