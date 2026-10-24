# The corpus — spec 0020

Built by spec 0020 ([`../docs/specs/0020-the-corpus.md`](../docs/specs/0020-the-corpus.md)),
the level-up's L1b. Each page is an HTML file and the picture converted
from it. **The vault's pages are written here like any other, and nobody
converts one, or opens one's conversion, until a milestone**
(`docs/level-up.md` §4.3).

```
fonts.json           the faces a page may name, each with its class (tools/corpus_fonts.py)
taxonomy.json        families, kinds, feature ids and priors, style families,
                     languages and shares, widths
brief.md             what every writer is given (spec §B)
cards.json           every card, with the seed it was drawn with
pages/<id>.html      the page, or a PDF page's twin
pages/<id>.png       the picture converted: a screenshot, or the PDF's render
pdf/<id>.pdf         a real PDF page, one page
pdf/<id>.source.json its provenance and licence
manifest.json        id → pool, family, kind, features, language, width,
                     origin, hashes
l3-subset.txt        the limited baseline set, 36 panel pages
```

Contact sheets go to `debug/corpus-sheets/`, which is gitignored and
rebuilt on demand. The 21 keep their files in `example/` and the ten probe
pages theirs in `docs/level-up-probe/src/`; the manifest points at them
where they are.

A PDF page's **twin** is its HTML redraw, the ground truth for the words,
lines and structure. It is unrelated to `tools/twins.py`'s photographed
copies (spec 0018, B0).
