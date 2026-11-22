# GLM-OCR — how it works, what it gives us, what we can control

Reference for arm D2 (spec 0023 built it, spec 0024 mended our side of
it) and for spec 0025, which builds the page's structure on top of it.
**Every fact here was read on 2026-11-22**, from the SDK's own code
(`glmocr` 0.1.5 in `~/.venvs/glmocr`, `transformers` 5.22.2) and from
the parser's recorded output for the 231 dev pages,
`debug/runs/L5-D2-dev/dump/glm-ocr_latest/<page>/00_regions.json`
(gitignored; keep that run, it is the offline loop's input). Our
settings are in `parser/glmocr.yaml`; our wrapper is
`tools/glmocr_parse.py`; the adapter is `src/doc_to_html/adapter.py`.

---

## 1. The pipeline, step by step

```
page picture
 → layout model  PP-DocLayoutV3 (PaddlePaddle/PP-DocLayoutV3_safetensors), on the CPU
                 boxes, a label each, a confidence, a mask, and a reading order
 → post-processing (glmocr/utils/layout_postprocess_utils.py)
     threshold 0.3                        weaker boxes dropped
     NMS (iou_same 0.6, iou_diff 0.98)    overlapping duplicates dropped
     a picture box over 93% of a portrait page (82% landscape) dropped
     **a box 80% or more inside another is deleted** (mode `large`, every
       label but `reference`, which is `small`); pictures, seals and charts
       are kept even when inside
     sorted by the model's reading order
 → one crop per box, each read by the reader (glm-ocr:latest via Ollama:
     GLM4, 0.9B, with a 0.4B CLIP image encoder; temperature 0)
     the prompt by label: `Text Recognition:`, `Table Recognition:`,
     `Formula Recognition:`; charts and pictures are not read
 → result formatter: hyphenated text blocks joined, a formula number
     joined to its formula, bullets formatted
 → our file, one entry per box: `index` (the reading order), `label`,
     `content`, `bbox_2d` (0–1000), `polygon` (a rectangle: `use_polygon`
     is off)
```

**The reading order is learned.** PP-DocLayoutV3 has an order head
(`order_logits`, a score for every pair of boxes, turned into
`order_seq` in `transformers/models/pp_doclayout_v3/image_processing_pp_doclayout_v3.py`).
It is not a sort by position.

**Crops reach the reader at the page's own resolution.** `smart_resize`
(`glmocr/utils/image_utils.py`) keeps each crop inside
[`min_pixels` 12544, `max_pixels` 71372800] in multiples of 28 px; only
a crop under about 112 × 112 px is enlarged. Small type in a large box
stays small.

## 2. Its 25 labels

`abstract`, `algorithm`, `aside_text`, `chart`, `content` (a table of
contents), `display_formula`, `doc_title`, `figure_title` (a caption),
`footer`, `footer_image`, `footnote`, `formula_number`, `header`,
`header_image`, `image`, `inline_formula`, `number` (a page number),
`paragraph_title`, `reference`, `reference_content`, `seal`, `table`,
`text`, `vertical_text`, `vision_footnote`.

On the 231 dev pages, 5,126 boxes, a median of 19 a page (82 at most):

| label | boxes | label | boxes |
|---|---|---|---|
| text | 3144 | vision_footnote | 78 |
| paragraph_title | 737 | doc_title | 75 |
| header | 298 | header_image | 56 |
| table | 258 | footnote | 48 |
| image | 156 | figure_title | 47 |
| footer | 147 | number, chart, content | 26, 16, 16 |

**No label is a container.** There is no card, panel, column, section
or sidebar box; `aside_text` is a sidebar's *text* (1 box on dev).

## 3. What it does not give us

- **Containers and nesting.** The post-processing deletes every box
  80% inside another. On dev, 37 boxes inside another survive, 34 of
  them pictures (inside a table 16, inside text 12, inside a title 6:
  c0399's drop cap). **The page arrives as a flat list of its smallest
  blocks, by design.**
- **Where each line or word sits.** One box a block; `locate` and
  tesseract find the lines again from the pixels.
- **Styling.** Bold and italic are rarely marked (below); no size, no
  colour, no fill, no frame.
- **Confidence.** The layout model scores every box; our file does not
  keep it.

## 4. What it gives that we use, and what we do not

| signal | on dev | used today |
|---|---|---|
| **reading order** | differs from a top-to-bottom, left-to-right sort on 174 of 231 pages; jumps back up to a column on the right 390 times on 141 pages, so it reads column by column | **no**: `adapter.groups_of` sorts by position; the order only sorts the finished groups |
| **role labels** (`doc_title` vs `paragraph_title`, `header`, `footer`, `number`, `figure_title`, `footnote`, `aside_text`) | every page | partly: titles (both as one kind of heading), figures, header and footer |
| **table structure** | `<th>` 472 on 68 pages; `colspan` 376 on 78; `rowspan` 25 on 12 | yes, `adapter.rows_of` |
| **line breaks the page sets** (the reader joins wrapped lines itself) | `\n` 970 on 168 pages | yes |
| **bullets** | 363 on 62 pages | yes |
| raised and lowered marks | `<sup>` or `^{` 157 on 51 pages; `<sub>` or `_{` 35 on 14 | yes |
| maths | `$` 859 on 106 pages | yes (`adapter._maths`) |
| tick-box characters | 251 on 27 pages, 161 of them in tables | yes |
| **bold and italic** | `**` 17 on 13 pages; `<strong>` 30, in tables only, on 10; italic 9 | yes, but **too rare to rely on**: dev loses bold on 164 pages |

## 5. What we can control

All in `parser/glmocr.yaml`. **Two kinds, and they must not be mixed
up:**

**Settings that change what it reads** (the parser's own; the rules keep
them as shipped unless Alessandro says otherwise):

| setting | today | probed |
|---|---|---|
| `layout.threshold`, `threshold_by_class` | 0.3, none | 0.2 (spec 0024 §7): 65 lost words found, 27 invented, mixed by eye: dropped |
| `layout_merge_bboxes_mode` (per label: `large`, `small`, `union`) | `large`, `reference` `small` | — **`union` would keep nested boxes for the reader too: every word inside read twice. Do not.** |
| `layout_nms`, `layout_unclip_ratio` | on, 1.0 | — |
| `label_task_mapping` (text, table, formula, skip, abandon) | every label read (round 8) | — |
| `page_loader.min_pixels` / `max_pixels` | 12544 / 71372800 | — (the crop-only enlargement below) |
| `repetition_penalty`, `max_tokens` | 1.1, 8192 | 1.0 (§7): did not hold on a second sample: dropped |
| the page enlarged ×2 before parsing | — | §7: small type read far better, but c0072's table region lost and c0008's table repeating empty cells: dropped as is |

**Ways to get more without changing what it reads:**

1. **Its reading order**: already in our file, free.
2. **Its layout model alone.** `glmocr.layout.LayoutDetector` runs
   without the reader; before `apply_layout_postprocess` it holds every
   candidate box with its score, label, mask (`polygon_points`) and
   `order_seq`, the nested boxes the post-processing deletes included.
   A few seconds a page on the CPU, no model call to Ollama. **Not yet
   measured**: the model has no container label, so nested candidates
   are other cuts of the same text (one block of two paragraphs, or
   two), not cards.
3. **Its reader on a crop we choose, in the mode we choose.** The page
   loader builds a request from any image with a task prompt; a part of
   the page we know is a grid can be read with `Table Recognition:`,
   whatever its boxes' labels.
4. **Masks** (`use_polygon: true`): a block's own shape, not its
   rectangle. The same layout pass.
5. **Crops enlarged, the page left alone** (`min_pixels` raised, or an
   enlarging step before the reader): the ×2 probe's gain on small type
   without moving the layout. A reading change, parked behind spec 0025.

**Not pulled**: `transformers` 5.22.2 also carries PP-DocLayoutV4 (no
mask branch); its weights are not on this machine and its labels are
unread. A different layout model is a change to the parser: his call.

## 6. What this means for our side

- **Structure is ours to build.** The parser hands over leaves in a
  learned order; cards, panels, columns and sidebars come from the
  pixels (drawn frames, fills and rules: `parser_first.containers`,
  `furniture`) and from the empty gaps between blocks.
- **The order is a signal we throw away.** It already says which
  blocks belong together and in which direction a part is read.
- **The roles are free structure and free typography**: the page's
  edges (`header`, `footer`, `number`), a caption's figure
  (`figure_title`), a sidebar (`aside_text`), and one size per role.
- **Its table mode is its strongest structural reader**, so a grid of
  fields is better read whole as a table than pieced together from
  fragments.

Spec 0025 builds on all four.
