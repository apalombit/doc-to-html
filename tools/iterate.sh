#!/usr/bin/env bash
#
# One turn of the prompt-iteration loop, from scratch.
#
#     tools/iterate.sh 03-some-label
#
# Runs the whole document against a real model — every pass, no shortcuts, about
# five minutes on the 8 GB M1 — then draws what came back. Everything lands in
# one directory per turn, and that directory carries the prompt that produced it,
# so two turns can be compared months later without a git archaeology session.
#
#     debug/runs/<label>/
#       layout_prompt_sent.txt   the layout prompt, snapshotted before the run
#       ollama_ps_before.txt     proof nothing else was resident
#       bakeoff.stdout.txt       the acceptance table and mismatches
#       bakeoff.stderr.txt       per-pass timings
#       dump/<model>/<fixture>/  every raw answer, and the prompt beside it
#       index.html               the contact sheet — start here
#       *.png                    the same pictures as files
#
# Memory presents as latency: with an unrelated model resident one layout pass
# took 180s and timed out, against 4.5s alone. This refuses to run rather than
# record a meaningless number.

set -euo pipefail

LABEL="${1:?usage: tools/iterate.sh <label>, e.g. 03-fewer-fields}"
FIXTURE="${FIXTURE:-invoice_0001}"
MODEL="${MODEL:-qwen3-vl:4b}"
SOURCE="${SOURCE:-example/invoice.png}"
# Exported so the run and the diagnostic agree about what the model was shown.
LONG_EDGE="${DTH_LAYOUT_LONG_EDGE:-512}"
export DTH_LAYOUT_LONG_EDGE="$LONG_EDGE"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/debug/runs/$LABEL"
cd "$ROOT"

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

echo "=> $LABEL: $MODEL over $FIXTURE at layout long edge $LONG_EDGE, from " \
     "scratch. Expect ~5 minutes." >&2
echo "$LONG_EDGE" > "$OUT/layout_long_edge.txt"

DTH_LOG_LEVEL=INFO python -m doc_to_html.bakeoff \
    --fixtures "$FIXTURE" --models "$MODEL" --dump "$OUT/dump" \
    > "$OUT/bakeoff.stdout.txt" 2> "$OUT/bakeoff.stderr.txt" || true

python tools/inspect_run.py \
    "$OUT/dump/${MODEL//:/_}/$FIXTURE" \
    --source "$SOURCE" \
    --expected "tests/fixtures/$FIXTURE.expected.json" \
    --long-edge "$LONG_EDGE" \
    --out "$OUT" > "$OUT/geometry.txt" 2>/dev/null || true

cat "$OUT/bakeoff.stdout.txt"
echo
cat "$OUT/geometry.txt"
cat <<EOF

------------------------------------------------------------------
prompt used   $OUT/layout_prompt_sent.txt
raw dump      $OUT/dump/${MODEL//:/_}/$FIXTURE
diagnostic    $OUT/index.html      <- open this
------------------------------------------------------------------
EOF
