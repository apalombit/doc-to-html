"""The corpus factory — spec 0020, the level-up's L1b.

It builds the corpus the converter is measured on: pages written from
cards, a validator every page passes before it counts, contact sheets for
looking at variety, real PDF pages admitted through a gate, and the
manifest that deals them into pools. **Nothing here converts a page or is
imported by a Conversion.**

- `browser` — run a script in the corpus's headless Chrome and read back
  what it returns;
- `fonts` — the faces a page may name, each with its class.

`docs/specs/0020-the-corpus.md` is the record: the numbers to hit, the
feature ids, the brief, the validator's checks and the PDF gate.
"""
