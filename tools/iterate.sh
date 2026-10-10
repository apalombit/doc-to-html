#!/usr/bin/env bash
#
# One turn of the prompt-iteration loop, from scratch.
#
#     tools/iterate.sh 03-some-label                 # one document
#     FIXTURE=iterate tools/iterate.sh 11-baseline    # the five, ~20 min
#     FIXTURE=sweep tools/iterate.sh 12-gate          # all fifteen, ~1¾ hours
#     FIXTURE=invoice_0001,cv_0013 tools/iterate.sh 13-two
#
# Runs the whole document against a real model — every pass, no shortcuts, about
# seven minutes each on the 8 GB M1, from 2 to 16 — then draws what came back. Everything lands
# in one directory per turn, and that directory carries the prompt that produced
# it, so two turns can be compared months later without a git archaeology session.
#
#     debug/runs/<label>/
#       classify_prompt_sent.txt the classify prompt, snapshotted before the run
#       ollama_ps_before.txt     proof nothing else was resident
#       ollama_ps_after.txt      proof our own model got the GPU, or did not
#       fixtures.txt             which documents this turn covered
#       bakeoff.stdout.txt       what converted and what did not, per document
#       bakeoff.stderr.txt       per-pass timings
#       dump/<model>/<fixture>/  every raw answer, and the prompt beside it
#       report.html              source vs render, every document  <- start here
#       scores.json              the six axes, for the next run to diff against
#       index.html               the per-document contact sheet
#       *.png                    the same pictures as files
#
# **`report.html` is the review surface.** One page, every document, source
# left and render right at matched width, scores above each pair and the delta
# against the previous run. `index.html` is the other question — how one
# document was converted, step by step — and both come out of the same run.
#
# One fixture keeps the flat layout. A set puts the per-document contact sheet
# and pictures under <label>/<fixture>/ instead, with the report still at the
# top covering all of them.
#
# Memory presents as latency: with an unrelated model resident one layout pass
# took 180s and timed out, against 4.5s alone. This refuses to run rather than
# record a meaningless number.

set -euo pipefail

LABEL="${1:?usage: tools/iterate.sh <label>, e.g. 03-fewer-fields}"
# One fixture, a comma-separated set, or "all". A prompt is a single input shared
# by every document, so a change measured on one and never checked against the
# rest is a change of unknown sign: runs 01-10 were all invoice_0001, and what
# ten edits did to the other four was never once measured.
FIXTURE="${FIXTURE:-invoice_0001}"
MODEL="${MODEL:-qwen3-vl:4b}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/debug/runs/$LABEL"
cd "$ROOT"

# A split name, "all", or a comma-separated list — `doc_to_html.corpus` is the
# one place that says what those mean, so this script and the bake-off cannot
# disagree about which documents a run covered.
FIXTURES="$(python -c "
from doc_to_html.corpus import names
print(' '.join(names('$FIXTURE')))")"
COUNT="$(printf '%s\n' $FIXTURES | wc -l | tr -d ' ')"

if [ -e "$OUT" ]; then
    echo "refusing to overwrite $OUT — pick a new label" >&2
    exit 1
fi

# The residency guard is about *local* memory, which is the binding constraint on
# the 8 GB M1. A run against a remote host has none, so skip it — and skip it via
# the local address explicitly, because OLLAMA_HOST reaches the `ollama` CLI too:
# exporting a cloud host once sent `ollama ps` at ollama.com, where it failed and
# took the whole script down with it under `set -e`.
HOST="${OLLAMA_HOST:-http://localhost:11434}"
case "$HOST" in
    *localhost*|*127.0.0.1*|*0.0.0.0*) LOCAL=yes ;;
    *) LOCAL=no ;;
esac

if [ "$LOCAL" = yes ]; then
    # Our own model left over from the previous turn is not contamination, but a
    # warm start is not comparable with a cold one, so unload it rather than
    # refuse. Any *other* model resident is someone else's business and makes the
    # numbers noise: an unrelated llama3.2:3b once turned a 4.5s layout pass into
    # a 180s timeout.
    if OLLAMA_HOST="$HOST" ollama ps 2>/dev/null | tail -n +2 | grep -q "^${MODEL%%:*}"; then
        echo "unloading our own $MODEL from the previous turn, for a cold start" >&2
        OLLAMA_HOST="$HOST" ollama stop "$MODEL" >/dev/null 2>&1 || true
        sleep 3
    fi

    resident="$(OLLAMA_HOST="$HOST" ollama ps 2>&1 | tail -n +2 || true)"
    if [ -n "$resident" ]; then
        echo "another model is resident in Ollama, so timings would be noise:" >&2
        echo "$resident" >&2
        echo "run 'ollama stop <model>' first" >&2
        exit 1
    fi
else
    echo "remote host $HOST — skipping the local residency guard." >&2
    echo "NOTE: timings from this run are not comparable with local ones." >&2
fi

mkdir -p "$OUT"
OLLAMA_HOST="$HOST" ollama ps > "$OUT/ollama_ps_before.txt" 2>&1 || true
echo "$HOST" > "$OUT/host.txt"
# The prompts this turn was taken under, so the directory stays self-describing
# when one of them is edited. No layout prompt: geometry comes from a detector
# and makes no model call at all.
python -c "
from doc_to_html.engines.ollama import CLASSIFY_PROMPT
open('$OUT/classify_prompt_sent.txt','w').write(CLASSIFY_PROMPT)"
git rev-parse HEAD > "$OUT/commit.txt" 2>/dev/null || true

# No `layout_long_edge.txt` any more: it recorded what the vision layout pass
# was downscaled to, and that pass is gone (spec 0007's queue, Q4). The
# detector is given the whole rectified page.
echo "=> $LABEL: $MODEL over $COUNT fixture(s), from scratch." \
     "Expect ~7 minutes each." >&2
printf '%s\n' $FIXTURES > "$OUT/fixtures.txt"
# Every DTH_* this turn was taken under, so the directory stays self-describing
# when the default moves under it. DTH_SNAP_ZONES is the reason this exists: it
# changes the geometry every later pass is handed, and without it recorded here
# the only trace of an experimental arm is the coordinates in zones_used.json.
env | grep '^DTH_' | sort > "$OUT/dth_env.txt" || true

# One process for the whole set, so the model is loaded once. Only the first
# fixture is therefore a cold start; the rest run warm, and their timings are not
# comparable with a single-fixture run's. Mismatch counts are unaffected, and on
# a multi-fixture run those are the point.
DTH_LOG_LEVEL=INFO python -m doc_to_html.bakeoff \
    --fixtures "${FIXTURES// /,}" --models "$MODEL" --dump "$OUT/dump" \
    > "$OUT/bakeoff.stdout.txt" 2> "$OUT/bakeoff.stderr.txt" || true

# The guard above proves no *other* model was resident. It cannot prove our own
# model got the GPU: Ollama decides the CPU/GPU split when it loads the model,
# which is after the guard has run, and under memory pressure it silently offloads
# part of the model to CPU. Measured: the same layout pass on the same page took
# 59.4s at 100% GPU and 224.8s at 41%/59% CPU/GPU, and returned a byte-identical
# answer. Without this the run directory records the 3.8x and explains none of it.
# Ollama keeps the model resident for a few minutes, so ask now, not before.
if [ "$LOCAL" = yes ]; then
    OLLAMA_HOST="$HOST" ollama ps > "$OUT/ollama_ps_after.txt" 2>&1 || true
    if grep -q "CPU" "$OUT/ollama_ps_after.txt" 2>/dev/null; then
        echo "WARNING: $MODEL was partly on the CPU for this run:" >&2
        sed -n '2p' "$OUT/ollama_ps_after.txt" >&2
        echo "Timings are not comparable with a run that had the whole GPU." >&2
        echo "What the model answered is unaffected." >&2
    fi
fi

# The contact sheet is per document. One fixture keeps the flat layout the loop
# has always had; a set gets one subdirectory each, with the acceptance table at
# the top covering all of them.
for fixture in $FIXTURES; do
    if [ "$COUNT" = 1 ]; then dest="$OUT"; else dest="$OUT/$fixture"; mkdir -p "$dest"; fi
    # The corpus names each document's Source Image, so the set needs no table.
    source="${SOURCE:-$(python -c "
from doc_to_html.corpus import SOURCES
print(SOURCES['$fixture'].png)")}"
    # Its stderr is kept, not discarded. Run 69 converted all five fixtures and
    # produced no contact sheet for any of them: the diagnostic refused, said why
    # on stderr, and `2>/dev/null || true` threw the sentence away — leaving five
    # empty geometry.txt files and no sign that anything had gone wrong. A tool
    # that cannot draw the run is not fatal, but it must be audible.
    # No `--expected`: the committed reference IR is gone with the harness that
    # scored against it, and the panels it fed are skipped when it is absent.
    if ! python tools/inspect_run.py \
        "$OUT/dump/${MODEL//:/_}/$fixture" \
        --source "$source" \
        --out "$dest" > "$dest/geometry.txt" 2>"$dest/geometry.stderr.txt"
    then
        echo "WARNING: no contact sheet for $fixture:" >&2
        sed 's/^/  /' "$dest/geometry.stderr.txt" >&2
    fi
done

# The comparison report — the thing that actually gets reviewed. Built after
# the conversions so it can score every document the run produced, and against
# the newest previous run's scores.json so the T1 ratchet has something to
# ratchet against. Its stderr is kept for the same reason the contact sheet's
# is: a review surface that silently failed to build is worse than one that
# says why.
if ! python -m doc_to_html.report "$OUT" --model "$MODEL" \
        > "$OUT/report.stdout.txt" 2>"$OUT/report.stderr.txt"
then
    echo "WARNING: no comparison report:" >&2
    sed 's/^/  /' "$OUT/report.stderr.txt" >&2
fi

cat "$OUT/bakeoff.stdout.txt"
echo
if [ "$COUNT" = 1 ]; then
    cat "$OUT/geometry.txt"
    sheet="$OUT/index.html"
else
    for fixture in $FIXTURES; do
        echo "--- $fixture"
        sed 's/^/  /' "$OUT/$fixture/geometry.txt" 2>/dev/null || true
    done
    sheet="$OUT/<fixture>/index.html"
fi
cat <<EOF

------------------------------------------------------------------
report        $OUT/report.html      <- open this
scores        $OUT/scores.json
raw dump      $OUT/dump/${MODEL//:/_}/
per-document  $sheet
------------------------------------------------------------------
EOF
