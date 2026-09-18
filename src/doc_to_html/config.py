"""The only layer that reads the environment.

Every model, host, key and timeout a Conversion uses resolves here, so changing
which model does extraction is an edit to `.env` rather than to Python. That is
what makes a bake-off across models a configuration exercise, and what makes
Ollama Cloud reachable without touching code.

Two properties are load-bearing:

*Everything has a default in code.* An empty environment produces a working
configuration, so the suite and a fresh clone behave identically.

*Every resolved value remembers where it came from.* An operator asking why a
run used the wrong model should not have to read source to find out — see
`describe()` and the `config` CLI command.

Nothing outside this module reads an environment variable. Two places that do is
two places to look when a setting does not take effect.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, TypeVar

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_LAYOUT_MODEL = "qwen3-vl:4b"
DEFAULT_EXTRACT_MODEL = "qwen3-vl:4b"
DEFAULT_AUDIT_MODEL = "qwen3-vl:4b"
"""A placeholder, and the one default that is knowingly wrong for its job.

Nothing loads this today: `_audit` is a no-op, `OllamaEngine.audit_coverage`
raises, and no code path reaches either. So the value names a model that is
never sent anywhere, and pointing it at the model already on disk keeps
`doc-to-html config` describing a machine that exists — an 8GB box has no room
for a second vision family it never calls.

**It must be re-pointed before the Coverage Audit is built.** The audit is the
only safeguard that catches *absent* content, and it is worth something only
from a different model family: asking the model that missed a block whether it
missed a block shares the blind spot that caused the miss. Left at this value it
would self-audit, pass, and report confidence it has not earned — worse than not
running, because a silent no-op is at least honest about being one.

`test_the_coverage_audit_is_still_unwired` fails the moment the audit is
implemented, which is the moment this needs deciding rather than inheriting."""

DEFAULT_CLASSIFY_MODEL = "qwen3-vl:4b"
"""The same model as layout and extraction, deliberately, for now.

**What this default costs, stated plainly.** Issue #13 asked two models the Kind
question about `invoice_0001`'s Zone 4 — a shaded heading row over a data row —
three times each at two resolutions. `qwen3-vl:4b` answered `pairs` six times
out of six, including at the full-resolution crop where the shading is plainly
legible. `qwen3.5:4b` answered `pairs` at layout scale and `table` at the crop.
So with this default, splitting the pass fixes Zone 1, whose problem is being
asked about as one of seven regions rather than on its own, and leaves Zone 4
wrong. Two mismatches becomes one, not zero.

**Why take that anyway.** `qwen3.5:4b` has never run the layout pass, never been
measured on the other four fixtures, and never converted a document end to end;
naming two Kinds correctly in a standalone probe is not evidence it can do the
job. Shipping it as a default on that basis would be generalising from one
measurement on one fixture, which is the mistake 0001 records twice. One model
in every role also costs one model load per document rather than two, since two
vision models will not stay resident in 8GB together.

What #15 actually bought is that this is a *setting*: `DTH_CLASSIFY_MODEL` picks
the classifier independently of the layout and extraction models, so evaluating
models per step — and combinations across steps — is configuration rather than
code. That evaluation is issue #19."""
DEFAULT_NUM_CTX = 8192
DEFAULT_TIMEOUT_S = 180.0
DEFAULT_LOG_LEVEL = "INFO"

DEFAULT_LENIENT_DECODING = False
"""Whether to repair a response that ignored the schema it was given.

Off, because every local Ollama model honours `format` and a repair path that is
never exercised is a place for bugs to hide. On, it is the only way to reach a
cloud vision model: none of them honour `format`. See `engines/lenient.py`."""

DEFAULT_SNAP_ZONES = True
"""Whether to move each Zone's box onto its own ink before classifying it.

**On**, so the default configuration is the one that was measured: run 49 took
`invoice_0001` to zero mismatches with this set, and a default that cannot
reproduce the project's own headline number is a trap.

What the snap buys, against run 43 — the same page, the same byte-identical
layout answer, no snap:

- **Geometry, yes.** 0.56 IoU against the true rectangles becomes 0.91, `covered`
  0.82 becomes 0.99, `splits` 46 becomes 0.
- **Kinds, no.** All six classifications come back identical from snapped and
  unsnapped crops, across two runs. Run 42 found the same from the true
  rectangles: perfect geometry moves no Kind on this document.

**It was off for two years of this file's history and for a real reason.** Runs
39 and 45 both converted with it on, weeks apart, and both went 3 mismatches to
6 the same way — `table row 2 has 0 cells but the header has 2`, losing Zone 5
and the column-sum Probe. Reproducible, so the snapped crop caused it rather
than a decoder glitch.

**Two later changes removed that cost, and both are measured.** Zero-cell rows
are now dropped before the table width check (`wire._without_empty_rows`), and
`DTH_TABLE_GRID_HINT` stops the model emitting the spurious row at all — run 49's
raw answers carry no empty row on either table. The condition Gate 1 was missing
— *no Zone that previously converted stops converting* — is met: run 49 has zero
Failures and every Zone complete.

**What this is not.** Measured on one fixture. Run 36 found geometry broken on
four of the five, so what the snap does to those is unknown, and `invoice_0002`
returns no geometry to snap at all. See `orchestrator.snapped_or_original` and
spec 0004."""

DEFAULT_TABLE_GRID_HINT = True
"""Whether to tell the table Extractor how many rows and columns it is filling.

**On**, because it is the change that took `invoice_0001` to zero mismatches and
it passed a four-condition gate written before the run. `extract_zone` measures
the crop it is about to send — `preprocess.table_grid`, an ink projection, no
model call — and states the counts in the prompt.

**What it is aimed at.** `invoice_0001`'s Zone 4 is two printed lines, 841x59px,
its two columns ~800px apart. It comes back as four rows, each cut in half, and
the header-only repair in `wire.py` fixes half of that. Two prompt attempts have
failed to move it: run 13 forbade the header split in as many words, and run 48
added the general case and returned output **byte-identical** to the run before.

**Why a third attempt is not just a fourth wording.** The two failures were
*behavioural* instructions — don't split, keep a line together — and the model is
not deciding to split; it does not read the two ends of the line as one row, so
there is no decision for an instruction to bear on. A count is a different kind
of statement, and the model demonstrably honours that kind: the prompt already
says "give every data row the same number of cells as the header row" and every
row it returns has exactly the right number of cells. It obeys *how many cells*
while ignoring *which line they belong to*.

**Run 49 measured it, and it worked — `invoice_0001` converts with 0 mismatches
for the first time.** All four pre-registered gate conditions held:

| | before (run 48) | with the grid stated (run 49) |
|---|---|---|
| zone 4 | 4 rows, every one cut in half | **2 rows**, `['Payment Method','Check #']` / `['Check','1000']` |
| zone 5 | header split, one spurious empty row | **5 clean rows**, header whole |
| mismatches | 1 | **0** |
| render / skeletons / failures | 25/25, 0, 0 | 25/25, 0, 0 |

The effect is larger than the target. It was aimed at Zone 4's data row and it
also stopped the header split that four runs could not talk this model out of,
and the empty row that cost two runs their table. Both tables now come back
correct at source, and `wire.py`'s repairs did not need to fire.

**What defaulting this on is and is not backed by.** One run, one fixture, and
the four other fixtures have not been converted against it. That is a deliberate
call rather than an oversight: it is the only change measured to take this
document to zero, the gate it passed included *no Zone that previously converted
stops converting*, and every check behind it still runs because the grid is
stated rather than enforced.

The one known inaccuracy in the ruler is corrected rather than shipped.
`table_grid` counts bands of ink, and a Zone's Title is a printed line that is not
a row — `sample_table_0003` prints "Population and GDP (millions of USD)" above
its grid and measured 17 against a true 16. `with_grid` subtracts for a titled
Zone. Neither of `invoice_0001`'s tables carries a Title, so run 49's numbers are
unaffected by that correction and did not need re-taking.

**That subtraction had never fired in production until `DTH_CAPTION_PASS`.** It
is gated on `bool(zone.title)`, and `title` came back `None` from all 36 of run
69's classify calls, so `sample_table_0003` was asked for 17 rows on a 16-row
table and returned a spurious trailing `header`. Both of that fixture's
mismatches trace to it."""

DEFAULT_CAPTION_PASS = True
"""Whether to ask each Zone for its Title before asking what Kind it is.

**On since run 82**, measured one flag apart against run 81 re-scored. It is the
largest single improvement this corpus has recorded: **23 findings to 12**, with
`sample_table_0003` and `invoice_0001` both full matches and **11 Titles written,
every one of them correct**.

| fixture | 81 | 82 |
|---|---|---|
| `invoice_0001` | **match** | **match** |
| `invoice_0002` | 9 | **4** |
| `sample_semantic_0005` | 8 | **6** |
| `sample_css_0004` | 4 | **2** |
| `sample_table_0003` | 2 | **match** |
| total | 23 | **12** |

Geometry did not move, which is the check that the pass stayed in its lane:
`covered` 1.00, `splits` 0, `doubles` `[0, 3, 0, 0, 1]`, 6 geometry findings
either way. No Failures and no Caveats on any fixture.

**Ten of the thirteen Title findings were reachable, and all ten landed** — the
count was derived before the run from `caption_band` and `aligns_to_grid`, which
are arithmetic, and it came back exact. The three that were never reachable are
Zones the ink refuses to ask about; see `preprocess.caption_band`.

**What it bought beyond its own category**, and both were predicted by the
docstrings rather than discovered:

- **`sample_table_0003` went to a full match**, taking a Row Roles finding with
  it. `with_grid(titled=)` subtracts the caption line from the stated row count,
  and it had never once fired in production because `zone.title` was always
  `None` — that fixture reported 17 rows against a true 16. A Title is worth more
  than its own mismatch.
- **`invoice_0002`'s payment panel changed Kind**, `table` to `pairs`, because
  withholding the caption band takes away the shaded bar that satisfies
  `CLASSIFY_PROMPT`'s "top row set apart" test. Still not `prose`, so it is still
  a finding — but it moved for exactly the stated reason.

**`invoice_0001` is the gate this had to pass, and the interesting part is that
it wrote nothing.** Its reference carries no Titles at all across 6 Zones; three
of them are asked, and the model answered `content` or `header` on all three
while `aligns_to_grid` vetoed the two grid headings. The Probe still reconciles
at 385.00.

**What it is aimed at.** `zone.title` has never been populated on any fixture:
36 classify calls in run 69, 36 empty titles, on crops where the caption is
plainly legible. Asked as its own question against those same crops, the same
model answered correctly 4 times out of 4. The Title is worth more than its own
11 mismatches because `with_grid(titled=...)` is dead while it is `None` — see
`DEFAULT_TABLE_GRID_HINT` above.

**Why a second call rather than a fifth wording.** The two questions want
opposite pixels. The Title needs the caption band in frame; the Kind is
measurably wrong while it is there, because a shaded caption bar satisfies
`CLASSIFY_PROMPT`'s own "top row set apart" test for a table. Cropping the band
off moved 2 of 3 `invoice_0002` panels from `table` to the correct `pairs`; a
prompt clause explaining the difference moved 0 of 6. One call cannot show both
frames.

**What bounds the risk.** `preprocess.caption_band` returns `None` unless the
crop holds a second band of ink, so a Zone that is only a heading — 20 of run
69's 36 crops — is never asked and never stripped. The cost is +16 calls on that
geometry, not +36.

**Measured. Run 71 failed its gate; run 72 passes it on every condition but one.**
`FIXTURE=all` with `DTH_LAYOUT_DETECTOR=heron`:

| fixture | run 69 | run 71 | run 72 |
|---|---|---|---|
| `invoice_0001` | **0, match** | 8 | **0, match** |
| `invoice_0002` | 20 | 20 | 20 |
| `sample_css_0004` | 10 | 10 | 10 |
| `sample_semantic_0005` | 14 | 15 | 15 |
| `sample_table_0003` | 2 | **0, match** | **0, match** |
| total | 46 | 53 | **45** |
| full matches | 1 | 1 | **2** |

Run 72 restores `invoice_0001` completely — the Probe reconciles at 385.00 again
— and keeps `sample_table_0003`. Geometry is untouched in both runs: `covered`
1.00, `splits` 0, `doubles` 0/3/0/1/0, identical to run 69.

**The one condition run 72 missed, and how it was resolved — this is the part
worth carrying forward.** Run 72 failed *no fixture rises above its run-69
count*: `sample_semantic_0005` went 14 → 15, gaining "Benefits" as a correct
Title and picking up two the reference did not want, "The Weekly Digest" and
"Why semantic HTML matters". Both were real captions of the boxes the detector
produced; the reference split each of those boxes in two, so neither half
carried a Title. The diagnosis at the time was *the pass is right about the
pixels it is shown and the pixels are wrong* — and it was correct.

**Nothing about this pass was changed to fix that. The grouping was.** Spec
0006 merged exactly those two boxes, and the reference now asks for "The Weekly
Digest" by name; the fixture question about "Why semantic HTML matters" was
settled the same way, in its favour. Both are among the eleven Titles run 82
wrote correctly. **A pass can be blocked by a fault in a different pass, and
switching it on again is the only way to find out it is no longer blocked** —
this one sat off for ten runs after it was already right.

Run 71's failure and how it was diagnosed is kept below, because the shape of it
is the reusable part.

**Why it fails: to this model, "is this line a heading?" and "is this a table's
header row?" are one question — and `CAPTION_PROMPT` asked it in the same words
`CLASSIFY_PROMPT` uses.** One says a table's top row is "set apart — shaded,
ruled off, or in bold"; the other asks whether the first line is "set apart from
what follows by being bold, larger, shaded, or alone above the rest". A header
row satisfies both, so `is_heading: true` is the correct answer to what was
actually asked. On `invoice_0001` that took `"Item"` and `"Payment Method"` — the
first cells of two header rows — as Titles and cut them off. Zone 4 became a
single data row and classified `pairs`; Zone 5 lost its summary row and with it
the column-sum Probe.

**What it got right, and it is not nothing.** `sample_table_0003` reaches a full
match because the Title finally arrives and revives `with_grid(titled=True)`.
`invoice_0002`'s panels return "Company Details" and "Customer Details" on the
right panels — they score as mismatches only because that page comes back as 9
Zones against a reference of 10, so every index after the first shifts. And
geometry is untouched: `covered` 1.00 and `splits` 0 on all five, `doubles`
unchanged.

**Two changes answer that, and both are in.**

*The schema, not the wording.* `CaptionResponse` now offers three answers —
`caption`, `header`, `content` — where it offered a boolean. The boolean was
answered `true` on 8 of 8 crops because the model had nowhere to put "that is a
grid's heading row"; offered the option, it takes it. Measured 4/11 → 8/11 over
the crops run 71 got wrong and right. See `wire.CaptionResponse`, which also
records why `header` and `content` share one behaviour and must not be collapsed
back.

*A counted fact, as the next lever was always going to be.* A heading row has one
cell per column of the values beneath it; a caption spans the region and ignores
that grid. `CaptionBand.aligns_to_grid` compares the two column counts for
equality — no threshold — and the Orchestrator lets it **refuse** a caption the
model proposed. It may never assert one: a refused caption costs a Title, while a
false one cost run 71 a Kind, a summary row and a Probe, so the veto is pointed
only at the expensive side. Measured over 16 real Zone crops: 2 true positives —
`invoice_0001`'s two tables — and **0 false positives**.

Run 72a, `invoice_0001` alone with the schema change and before the veto: **8 →
2**, the Probe reconciling at 385.00 again and Zone 5 whole. The two survivors
were Zone 4's Kind and its Title, both from the one crop where the model still
answers `caption` — the page's hardest case, which `engines.ollama` has recorded
since spec 0003: "`Payment Method` genuinely does label the `Check` beneath it,
while `Item` names a column." The veto is aimed exactly there, and in run 72 it
**fired once across all five fixtures**, on that Zone, refusing "Payment Method"
at 2 columns against 2. Nothing else in the corpus tripped it."""

DEFAULT_DERIVE_BANDS = False
"""Whether a Zone's Band and column come from its box rather than from the model.

**Off**, following `DTH_SNAP_ZONES`: a change to geometry ships off until a live
Conversion has been measured with it, and no run has ever completed with this on.

**What it fixes.** Band numbering is the part of the layout answer this project
has watched break most often — five of the six changes ever made to
`LAYOUT_PROMPT` broke it, each time as collateral on a change that never
mentioned it. It is also the one part fully determined by something the model
already gives correctly: the boxes. Runs 55 and 56 are the clearest case. Both
returned sane boxes and correctly alternating columns, and both failed to
increment the Band index between the first two rows — every Zone landing in Band
0 with columns `[0, 1, 0, 1]` — which cost `invoice_0001` and `invoice_0002`
their whole Conversion for a duplicated integer.

**What it is measured against.** `wire.bands_from_boxes` reproduces the
hand-authored Band and column numbering of all five fixtures from their boxes
alone, and reproduces run 50's numbering — the model's own answer on the document
that converts at zero mismatches — so switching it on costs that run nothing. The
naive rule it replaces, merging on any vertical overlap, matched three of five.

**What it is not measured against: a live Conversion.** Run 57 was to be that and
was stopped before it finished. Until one completes, the evidence is offline
only, which is exactly the situation `DTH_SNAP_ZONES`' own docstring describes as
the reason a geometry default waits.

**What turning it on changes besides the numbers.** `validate_bands` stops being
able to reject a layout for its Band numbering, because the numbering then comes
from the boxes it is checked against. A document that would have been thrown away
converts instead. That is the intent, and it is also a real loss of a signal that
has caught genuine nonsense before."""

DEFAULT_LAYOUT_REGION_HINT = False
"""Whether to tell the layout pass how many regions the page holds, at most.

**Off**, because a default is a claim about every document and this is measured
on two. `DTH_TABLE_GRID_HINT` shipped off and was flipped only once a run had
passed a gate written before it; this follows that order.

**What it is aimed at.** `invoice_0002` has boxed panels containing label/value
rows, so "what counts as one region" is under-determined. `qwen3-vl:4b` resolves
it downward and returns a synthetic 18x4 lattice — **72 regions, all `pairs`, for
a page with 10** — which overruns the token budget, is retried at twice it, and
is then rejected by `validate_bands`. The page has never converted.

**Why a count rather than better wording.** `LAYOUT_PROMPT` already forbids this
in as many words: "The columns inside a table or a pairs region are that region's
own business and are not regions themselves." It is ignored, exactly as the two
behavioural instructions about splitting a table row were ignored in runs 13 and
48. This model complies with *how many* and ignores *which* — which is the whole
finding behind `DEFAULT_TABLE_GRID_HINT`, applied one pass earlier.

**Stated as a ceiling, not as a target.** `preprocess.count_regions` overcounts:
8 for `invoice_0001`'s true 6, 11 for `invoice_0002`'s true 10. An exact count
would push a page the model already gets right into splitting regions to reach
the number, and `invoice_0001` at 0 mismatches is the thing that must not move.
A bound has no such pull — 6 is already under 8 — while still capping a runaway.
See `engines.ollama.with_regions`.

**Unmeasured.** Nothing has been run with this on. Read
`preprocess.REGION_GAP` for what the ruler is calibrated against, which is two
fixtures and not the other three."""

DEFAULT_LAYOUT_DETECTOR = "heron"
"""Which trained detector finds the Zones, or empty for the vision model.

**`heron`**, because the vision model cannot do this job and the two runs that
say so were taken against each other, one flag apart, on the same machine and the
same day. `doclayout_yolo` is the other name; see `engines.detector`.

**The measurement this default rests on**, all five fixtures, `qwen3-vl:4b`:

| fixture | VLM (`""`) | `heron` |
|---|---|---|
| `invoice_0001` | 4 off | **match** |
| `invoice_0002` | **MappingError** | 18 off |
| `sample_css_0004` | 9 off | 10 off |
| `sample_semantic_0005` | **MappingError** | 14 off |
| `sample_table_0003` | **MappingError** | 2 off |
| | 0 matched, 3 never convert | 44 total, 1 match, all five convert |

**The VLM path crashes on three of five fixtures**, all three in Band 0 — two
Zones sharing a column, or two Zones that do not overlap vertically being called
side by side. It also loses `invoice_0001`'s column-sum Probe. There is no
reading of that table on which the vision model is the better default.

**Why it fails, structurally.** At `DTH_LAYOUT_LONG_EDGE=384` Qwen3-VL resolves
the whole page into roughly 12x8 visual tokens and then decodes box coordinates
as text, with no localization objective anywhere in the loop. Three prompt
instructions have been measured ignored and resolution changed nothing across
2.25x the linear pixels. `engines/detector.py` has the full account.

**On the detector path `covered` is 1.00 and `splits` is 0 on all five**, so
nothing is ever lost — every remaining mismatch is content that arrived and was
mis-grouped or mis-named. Inference is well under a second on the CPU, and this
flag removes the layout model call entirely.

**What it over-counts, and why that is the recoverable direction.** It returns
more Zones than the reference on the two dense fixtures, each one a heading box
sitting above its own content or a run of list items belonging to one list. With
coverage at 1.00 nothing is lost, only mis-grouped: a Zone too many renders as
two blocks, where a Zone missing loses content for good. `doubles` is the field
that catches the opposite error, and it reads 3 on `invoice_0002`.

**`DTH_LAYOUT_LONG_EDGE` is gone.** It existed only to set the resolution of
the vision layout pass, it had no docstring, it shipped at a value no recorded
run used, and spec 0007 Thread 0 retired the pass it served. The detector never
read it. `preprocess.LAYOUT_LONG_EDGE` is the remaining constant and it is not
a setting."""

DEFAULT_DETECTOR_CONFIDENCE = 0.0
"""Confidence floor for the layout detector, or 0 for the detector's own.

Zero rather than a number, because the right threshold is a property of the
model and not of the pipeline: `heron` wants 0.40 and `doclayout_yolo` 0.15, and
each is recorded on its own class with what was measured at it. This exists so a
sweep does not need a code edit."""

DEFAULT_HEADING_RULE = "relative"
"""How the detector decides a heading belongs to the region under it.

`absolute` is `engines.detector.HEADING_GAP`, a fitted fraction of page height.
`relative` is `HEADING_GAP_RATIO` — the gap below the heading against the gap
above it — bounded by `HEADING_GAP_MAX`.

**Ships `relative` since run 81**, having been measured live first — run 78
against 76, then as part of the shipped pair in 81. `absolute` remains reachable
and is a strictly worse rule: re-derived pre-snap against the fixtures' own Zone
contents it is wrong on 4 of the corpus's 14 headings, where `relative` is wrong
on 2.

**What the offline evidence says**, which is why the flag exists at all rather
than the constant simply being replaced. Geometry is deterministic, so this is a
prediction and not a result — findings counted the way `acceptance.compare`
counts them, against the reference rectangles as they now stand:

| fixture | `absolute` | `relative` |
|---|---|---|
| `invoice_0001` | 0 | 0 |
| `invoice_0002` | 5 | 5 |
| `sample_table_0003` | 0 | 0 |
| `sample_css_0004` | 4 | **2** |
| `sample_semantic_0005` | 7 | 7 |

`covered` stays 1.00, `splits` 0 and `doubles` unchanged on all five either way.
The whole of the difference is `sample_css_0004`'s two cards ceasing to be split
off their own headings. **Expect its total not to fall by two**: those two Zones
become comparable for the first time, and no pass writes `zone.title` on the
shipped path, so the finding moves from geometry to Title rather than
disappearing. That is the point — a Title finding is one `DTH_CAPTION_PASS` can
act on, and a split region is not."""

DEFAULT_PREFER_CONTAINER = True
"""Whether to adopt a sub-threshold container over the stack of boxes it holds.

**On since run 81**, measured live one flag apart first — run 80 against 79 took
the corpus from 23 findings to 21 and geometry from 11 to 6, with every gate
holding and **ten fewer model calls**.

**Why it ships alongside `DTH_HEADING_RULE=relative` rather than instead of it.**
The two tie on the count — 6 geometry findings with either alone and with both —
but not in the output: `sample_css_0004` keeps its first card split under this
rule alone and is whole with both, the zone-count finding simply standing in for
the split finding. Equal totals were not equal answers, and only reading the
documents showed it.

**What it is for.** Five of the nine geometry findings left on the corpus are
over-splits whose right container is already in the detector's pool, scoring 0.05
to 0.27 against a 0.40 threshold — so `outermost` never saw it. See
`engines.detector.prefer_container`.

Derived offline against run 79's references, with `DTH_HEADING_RULE=relative`:

| fixture | off | on |
|---|---|---|
| `invoice_0001` | 0 | 0 |
| `invoice_0002` | 2 | 2 |
| `sample_table_0003` | 0 | 0 |
| `sample_css_0004` | 2 | 2 |
| `sample_semantic_0005` | 5 | **2** |
| | **9** | **6** |

`covered` 1.00, `splits` 0 and `doubles` unchanged on all five either way."""

DOTENV = Path(".env")
"""Looked for in the working directory. Absent is the normal case, not an error."""

ENVIRONMENT = "environment"
DEFAULT = "default"


class ConfigError(ValueError):
    """A value was set but could not be used. Always names the variable."""


@dataclass(frozen=True)
class Setting:
    """One resolved value and its provenance."""

    name: str
    value: str
    source: str
    """`environment`, `default`, or the path of the dotenv file it came from."""

    secret: bool = False

    @property
    def shown(self) -> str:
        """The value as it is safe to print."""
        if not self.value:
            return "(unset)"
        return "(set, redacted)" if self.secret else self.value


@dataclass(frozen=True)
class Settings:
    """Everything resolved, plus where each value came from."""

    ollama_host: str = DEFAULT_OLLAMA_HOST
    ollama_api_key: str = ""
    layout_model: str = DEFAULT_LAYOUT_MODEL
    classify_model: str = DEFAULT_CLASSIFY_MODEL
    extract_model: str = DEFAULT_EXTRACT_MODEL
    audit_model: str = DEFAULT_AUDIT_MODEL
    num_ctx: int = DEFAULT_NUM_CTX
    timeout_s: float = DEFAULT_TIMEOUT_S
    log_level: str = DEFAULT_LOG_LEVEL
    lenient_decoding: bool = DEFAULT_LENIENT_DECODING
    snap_zones: bool = DEFAULT_SNAP_ZONES
    table_grid_hint: bool = DEFAULT_TABLE_GRID_HINT
    caption_pass: bool = DEFAULT_CAPTION_PASS
    layout_region_hint: bool = DEFAULT_LAYOUT_REGION_HINT
    derive_bands: bool = DEFAULT_DERIVE_BANDS
    layout_detector: str = DEFAULT_LAYOUT_DETECTOR
    detector_confidence: float = DEFAULT_DETECTOR_CONFIDENCE
    heading_rule: str = DEFAULT_HEADING_RULE
    prefer_container: bool = DEFAULT_PREFER_CONTAINER

    origins: dict[str, Setting] = field(default_factory=dict)
    """Variable name -> what resolved and from where. Declaration order."""


def read_dotenv(path: Path) -> dict[str, str]:
    """Parse `KEY=value` lines. Missing file yields nothing.

    Deliberately not python-dotenv: this is the whole of the format the project
    documents, and a dependency for it would be larger than the parser.
    """
    if not path.is_file():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, raw = line.partition("=")
        values[name.strip()] = raw.strip().strip("'\"")
    return values


T = TypeVar("T", int, float)


def _number(setting: Setting, cast: Callable[[str], T]) -> T:
    """Parse a numeric setting, naming the variable and its source if it will not.

    Generic in the target type so callers do not re-cast what was just cast —
    `int(_number(s, int))` reads as though the parse were untrustworthy.
    """
    try:
        return cast(setting.value)
    except ValueError as error:
        raise ConfigError(
            f"{setting.name}={setting.value!r} from {setting.source} "
            f"is not a {getattr(cast, '__name__', cast)}"
        ) from error


def _flag(setting: Setting) -> bool:
    """Parse a boolean setting, accepting what people actually type.

    Named values only: an unrecognised string is a mistake worth reporting rather
    than quietly falling back to false, which is how a run silently ignores the
    thing it was configured to do.
    """
    value = setting.value.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off", ""):
        return False
    raise ConfigError(
        f"{setting.name}={setting.value!r} from {setting.source} is not a boolean"
    )


HEADING_RULES = ("absolute", "relative")
"""The two values `DTH_HEADING_RULE` accepts. See `DEFAULT_HEADING_RULE`."""


def _heading_rule(setting: Setting) -> str:
    """Parse the heading rule, naming the alternatives when it will not.

    Named values and nothing else, following `_flag`. This one earns the strict
    reading twice over: it chooses between two segmentations of the page, and a
    typo that fell back to the default would produce a run that looks like the
    arm it was launched as and measures the arm it was not — which is the single
    failure mode `debug/runs/<label>/dth_env.txt` exists to prevent.
    """
    value = setting.value.strip().lower()
    if value in HEADING_RULES:
        return value
    raise ConfigError(
        f"{setting.name}={setting.value!r} from {setting.source} is not one of "
        f"{', '.join(HEADING_RULES)}"
    )


def load(
    env: Mapping[str, str] | None = None,
    *,
    dotenv_path: Path | None = None,
) -> Settings:
    """Resolve settings. Environment wins, then the dotenv file, then the default.

    A dotenv file records what a workstation usually wants; an exported variable
    is a deliberate act for one run, so it takes precedence.

    An empty string counts as unset. `DTH_NUM_CTX=` in a dotenv file reads as
    "I left this alone", not as a value that then fails to parse.
    """
    environ = os.environ if env is None else env
    dotenv = DOTENV if dotenv_path is None else dotenv_path
    from_file = read_dotenv(dotenv)

    def resolve(name: str, default: object, *, secret: bool = False) -> Setting:
        if environ.get(name):
            return Setting(name, environ[name], ENVIRONMENT, secret)
        if from_file.get(name):
            return Setting(name, from_file[name], str(dotenv), secret)
        return Setting(name, str(default), DEFAULT, secret)

    origins = {
        setting.name: setting
        for setting in (
            resolve("OLLAMA_HOST", DEFAULT_OLLAMA_HOST),
            resolve("OLLAMA_API_KEY", "", secret=True),
            resolve("DTH_LAYOUT_MODEL", DEFAULT_LAYOUT_MODEL),
            resolve("DTH_CLASSIFY_MODEL", DEFAULT_CLASSIFY_MODEL),
            resolve("DTH_EXTRACT_MODEL", DEFAULT_EXTRACT_MODEL),
            resolve("DTH_AUDIT_MODEL", DEFAULT_AUDIT_MODEL),
            resolve("DTH_NUM_CTX", DEFAULT_NUM_CTX),
            resolve("DTH_TIMEOUT_S", DEFAULT_TIMEOUT_S),
            resolve("DTH_LOG_LEVEL", DEFAULT_LOG_LEVEL),
            resolve("DTH_LENIENT_DECODING", DEFAULT_LENIENT_DECODING),
            resolve("DTH_SNAP_ZONES", DEFAULT_SNAP_ZONES),
            resolve("DTH_TABLE_GRID_HINT", DEFAULT_TABLE_GRID_HINT),
            resolve("DTH_CAPTION_PASS", DEFAULT_CAPTION_PASS),
            resolve("DTH_LAYOUT_REGION_HINT", DEFAULT_LAYOUT_REGION_HINT),
            resolve("DTH_DERIVE_BANDS", DEFAULT_DERIVE_BANDS),
            resolve("DTH_LAYOUT_DETECTOR", DEFAULT_LAYOUT_DETECTOR),
            resolve("DTH_DETECTOR_CONFIDENCE", DEFAULT_DETECTOR_CONFIDENCE),
            resolve("DTH_HEADING_RULE", DEFAULT_HEADING_RULE),
            resolve("DTH_PREFER_CONTAINER", DEFAULT_PREFER_CONTAINER),
        )
    }

    return Settings(
        ollama_host=origins["OLLAMA_HOST"].value,
        ollama_api_key=origins["OLLAMA_API_KEY"].value,
        layout_model=origins["DTH_LAYOUT_MODEL"].value,
        classify_model=origins["DTH_CLASSIFY_MODEL"].value,
        extract_model=origins["DTH_EXTRACT_MODEL"].value,
        audit_model=origins["DTH_AUDIT_MODEL"].value,
        num_ctx=_number(origins["DTH_NUM_CTX"], int),
        timeout_s=_number(origins["DTH_TIMEOUT_S"], float),
        log_level=origins["DTH_LOG_LEVEL"].value,
        lenient_decoding=_flag(origins["DTH_LENIENT_DECODING"]),
        snap_zones=_flag(origins["DTH_SNAP_ZONES"]),
        table_grid_hint=_flag(origins["DTH_TABLE_GRID_HINT"]),
        caption_pass=_flag(origins["DTH_CAPTION_PASS"]),
        layout_region_hint=_flag(origins["DTH_LAYOUT_REGION_HINT"]),
        derive_bands=_flag(origins["DTH_DERIVE_BANDS"]),
        layout_detector=origins["DTH_LAYOUT_DETECTOR"].value,
        detector_confidence=_number(origins["DTH_DETECTOR_CONFIDENCE"], float),
        heading_rule=_heading_rule(origins["DTH_HEADING_RULE"]),
        prefer_container=_flag(origins["DTH_PREFER_CONTAINER"]),
        origins=origins,
    )


def configure_logging(settings: Settings) -> None:
    """Apply DTH_LOG_LEVEL.

    Resolved since the configuration layer was built and read by nothing until a
    180-second vision pass produced no output at all and no way to tell a slow
    model from a dead one. INFO gets one line per pass, plus a heartbeat while one
    is in flight.
    """
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def describe(settings: Settings) -> list[str]:
    """One aligned line per variable: name, value, where it came from."""
    width = max(len(name) for name in settings.origins)
    return [
        f"{setting.name:<{width}}  {setting.shown:<28}  {setting.source}"
        for setting in settings.origins.values()
    ]
