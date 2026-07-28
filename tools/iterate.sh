#!/usr/bin/env bash
#
# One turn of the prompt-iteration loop, from scratch.
#
#     tools/iterate.sh 03-some-label
#     FIXTURE=all tools/iterate.sh 11-baseline        # every fixture
#     FIXTURE=invoice_0001,invoice_0002 tools/iterate.sh 12-two
#
# Runs the whole document against a real model — every pass, no shortcuts, about
# three minutes each on the 8 GB M1 — then draws what came back. Everything lands
# in one directory per turn, and that directory carries the prompt that produced
# it, so two turns can be compared months later without a git archaeology session.
#
#     debug/runs/<label>/
#       layout_prompt_sent.txt   the layout prompt, snapshotted before the run
#       ollama_ps_before.txt     proof nothing else was resident
#       ollama_ps_after.txt      proof our own model got the GPU, or did not
#       fixtures.txt             which documents this turn covered
#       bakeoff.stdout.txt       the acceptance table and mismatches, all fixtures
#       bakeoff.stderr.txt       per-pass timings
#       dump/<model>/<fixture>/  every raw answer, and the prompt beside it
#       index.html               the contact sheet — start here
#       *.png                    the same pictures as files
#
# One fixture keeps that flat layout. A set puts the contact sheet and pictures
# under <label>/<fixture>/ instead, with the acceptance table still at the top.
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
# Exported so the run and the diagnostic agree about what the model was shown.
# The default is read from config rather than written here: this script records
# the number into layout_long_edge.txt and hands it to inspect_run.py, so a third
# copy of the literal would let a retune silently stamp every run directory with
# a figure the run was not taken at — the one thing these directories exist to
# make impossible.
LONG_EDGE="${DTH_LAYOUT_LONG_EDGE:-$(python -c \
    'from doc_to_html.config import DEFAULT_LAYOUT_LONG_EDGE as d; print(d)')}"
export DTH_LAYOUT_LONG_EDGE="$LONG_EDGE"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/debug/runs/$LABEL"
cd "$ROOT"

if [ "$FIXTURE" = all ]; then
    FIXTURE="$(ls tests/fixtures/*.expected.json \
               | sed 's|.*/||; s|\.expected\.json$||' | paste -sd, -)"
fi
FIXTURES="${FIXTURE//,/ }"
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
python -c "from doc_to_html.engines.ollama import LAYOUT_PROMPT
open('$OUT/layout_prompt_sent.txt','w').write(LAYOUT_PROMPT)"
git rev-parse HEAD > "$OUT/commit.txt" 2>/dev/null || true

echo "=> $LABEL: $MODEL over $COUNT fixture(s) at layout long edge $LONG_EDGE," \
     "from scratch. Expect ~3 minutes each." >&2
echo "$LONG_EDGE" > "$OUT/layout_long_edge.txt"
printf '%s\n' $FIXTURES > "$OUT/fixtures.txt"

# One process for the whole set, so the model is loaded once. Only the first
# fixture is therefore a cold start; the rest run warm, and their timings are not
# comparable with a single-fixture run's. Mismatch counts are unaffected, and on
# a multi-fixture run those are the point.
DTH_LOG_LEVEL=INFO python -m doc_to_html.bakeoff \
    --fixtures "$FIXTURE" --models "$MODEL" --dump "$OUT/dump" \
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
    # Each expected IR names its own Source Image, so the set needs no table here.
    source="${SOURCE:-$(python -c "import json,sys
print(json.load(open('tests/fixtures/$fixture.expected.json'))['source']['path'])")}"
    python tools/inspect_run.py \
        "$OUT/dump/${MODEL//:/_}/$fixture" \
        --source "$source" \
        --expected "tests/fixtures/$fixture.expected.json" \
        --long-edge "$LONG_EDGE" \
        --out "$dest" > "$dest/geometry.txt" 2>/dev/null || true
done

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
prompt used   $OUT/layout_prompt_sent.txt
raw dump      $OUT/dump/${MODEL//:/_}/
diagnostic    $sheet      <- open this
------------------------------------------------------------------
EOF
