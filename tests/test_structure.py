"""The page's structure, read off its pixels and its boxes — spec 0008, step 1.

**The expected answers were written down before the code**, and they are page
facts, not a reference IR: which parts of each source are columns read down
and which are a grid of copies read across, read out of the source HTML in
headless Chrome. A split is where the source's own containers meet, to within
`SPLIT_TOLERANCE`. A region's top and bottom are each a window between two
printed lines — the last line centre above the source's container and the
first inside it, and the same below — because what a region must get right is
which lines it holds, all of its own and none of its neighbours'.

The boxes are the Zones' boxes in `tests/frozen/q5-result/`, committed. They
are today's layout front's on 14 of 15 documents; `statement_0006`'s differ by
the one sliver Zone N3 removed. Run over `debug/runs/F1-sweep`'s boxes instead,
every answer here was identical on 2026-10-10.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from doc_to_html.corpus import SOURCES, SWEEP
from doc_to_html.ir import BBox, Block, Document, Kind, Role, Source, Zone, cell
from doc_to_html.preprocess import rectify
from doc_to_html.render import render
from doc_to_html.structure import Flow, Region, alike, cut_at_edges, structure
from doc_to_html.style import measure

REPO = Path(__file__).resolve().parent.parent
FLOOR = REPO / "tests" / "frozen" / "q5-result" / "documents"

SPLIT_TOLERANCE = 0.03


@dataclass(frozen=True)
class Expected:
    flow: Flow
    splits: tuple[float, ...]
    top: tuple[float, float]
    bottom: tuple[float, float]
    rows: int = 1


EXPECTED: dict[str, list[Expected]] = {
    # `aside` 0-310px of 900, `main` the rest, both the page's full height.
    "cv_0013": [Expected(Flow.COLUMNS, (0.344,), (0.000, 0.048), (0.931, 1.000))],
    # `.grid`, three columns of `1fr` with gaps at 299-315 and 585-601px.
    "catalogue_0015": [
        Expected(Flow.GRID, (0.341, 0.659), (0.059, 0.130), (0.883, 0.960), rows=3)],
    # `.tiles`, four `flex:1` tiles; then `.split`, `main` 34-617 and `aside`
    # 643-966px, which ends at 610px while `main` runs on to 864.
    "darkdeck_0009": [
        Expected(Flow.GRID, (0.264, 0.500, 0.737), (0.145, 0.206), (0.268, 0.333)),
        Expected(Flow.COLUMNS, (0.630,), (0.268, 0.333), (0.883, 0.959)),
    ],
    # `.columns`, three `.col`s with a rule down the right of the first two.
    "newsletter_0008": [
        Expected(Flow.COLUMNS, (0.346, 0.676), (0.337, 0.411), (0.892, 0.955))],
    # `.parties`, two identical bordered `.party` panels side by side — the one
    # grid of copies on the ten documents that are not targets.
    "nonlatin_0014": [Expected(Flow.GRID, (0.500,), (0.136, 0.210), (0.357, 0.416))],
    # Two columns, `.cols`, with nothing drawn between them: a whitespace
    # gutter, which A2 §7 measured cannot be told from a two-column table's.
    # The pixels cannot decide, so it stays single; step 3 asks the model.
    "menu_0012": [],
    "invoice_0001": [],
    "invoice_0002": [],
    "sample_table_0003": [],
    "sample_css_0004": [],
    "sample_semantic_0005": [],
    "statement_0006": [],
    "form_0007": [],
    "receipt_0010": [],
    "report_0011": [],
}


def boxes_of(name: str) -> list[BBox]:
    html = (FLOOR / f"{name}.html").read_text(encoding="utf-8")
    found = re.search(r'id="doc-ir">(.*?)</script>', html, re.S)
    assert found, f"{name}: no embedded IR"
    document = Document.from_json(found.group(1).replace("<\\/", "</"))
    return [zone.bbox for zone in document.zones if zone.bbox is not None]


def regions_of(name: str) -> list[Region]:
    rectified = rectify(REPO / SOURCES[name].png)
    plain = rectified.plain if rectified.plain is not None else rectified.image
    ground = measure(plain, inverted=rectified.inverted).page_bg
    return structure(plain, boxes_of(name), ground=ground,
                     inverted=rectified.inverted)


class TestTheCorpusPages:
    def test_every_sweep_document_has_its_answer_written_down(self) -> None:
        assert set(EXPECTED) == set(SWEEP)

    def test_each_page_reads_as_its_source_is_laid_out(self) -> None:
        wrong: list[str] = []
        for name, expected in EXPECTED.items():
            found = [r for r in regions_of(name) if r.flow is not Flow.SINGLE]
            if len(found) != len(expected):
                wrong.append(f"{name}: {len(found)} regions, expected "
                             f"{len(expected)}: {found}")
                continue
            for region, want in zip(found, expected):
                if (region.flow is not want.flow
                        or region.lanes != len(want.splits) + 1
                        or region.rows != want.rows):
                    wrong.append(f"{name}: {region} is not {want}")
                    continue
                if any(abs(got - at) > SPLIT_TOLERANCE
                       for got, at in zip(region.splits, want.splits)):
                    wrong.append(f"{name}: splits {region.splits}, expected "
                                 f"{want.splits}")
                if not (want.top[0] <= region.top <= want.top[1]
                        and want.bottom[0] <= region.bottom <= want.bottom[1]):
                    wrong.append(f"{name}: y {region.top:.3f}-{region.bottom:.3f} "
                                 f"outside {want.top} / {want.bottom}")
        assert not wrong, "\n".join(wrong)

    def test_the_regions_cover_each_page_once_top_to_bottom(self) -> None:
        for name in EXPECTED:
            regions = regions_of(name)
            assert regions[0].top == 0.0 and regions[-1].bottom == 1.0, name
            for upper, lower in zip(regions, regions[1:]):
                assert upper.bottom == lower.top, name


def page_with_panel(height: int = 400, width: int = 600) -> np.ndarray:
    """A white page with a bordered panel down the right of its top half."""
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    image[40:200, 400:402] = 40
    image[40:200, 578:580] = 40
    image[40:42, 400:580] = 40
    image[198:200, 400:580] = 40
    return image


class TestAPanelIsAColumnOnlyWhenTheContentBesideItRunsOn:
    """The distinction `darkdeck_0009`'s aside and `sample_semantic_0005`'s
    TL;DR panel turn on: a panel beside one block is a float, and a Band
    already draws it; a panel beside two stacked blocks is a column."""

    PANEL_TEXT = BBox(0.68, 0.12, 0.95, 0.45)

    def test_a_panel_beside_one_block_is_not_a_column(self) -> None:
        beside = BBox(0.05, 0.12, 0.62, 0.45)
        regions = structure(page_with_panel(), [beside, self.PANEL_TEXT],
                            ground=(255, 255, 255))
        assert [r.flow for r in regions] == [Flow.SINGLE]

    def test_a_panel_beside_two_stacked_blocks_is_a_column(self) -> None:
        stack = [BBox(0.05, 0.12, 0.62, 0.25), BBox(0.05, 0.30, 0.62, 0.70)]
        regions = structure(page_with_panel(), [*stack, self.PANEL_TEXT],
                            ground=(255, 255, 255))
        columns = [r for r in regions if r.flow is Flow.COLUMNS]
        assert len(columns) == 1
        assert columns[0].splits == (400 / 600,)
        assert columns[0].top <= 0.12 and columns[0].bottom >= 0.70


def prose(text: str, box: BBox, band: int, column: int) -> Zone:
    return Zone(kind=Kind.PROSE, band=band, column=column, bbox=box,
                blocks=[Block(kind="paragraph", lines=[cell(text)])],
                complete=True)


def sidebar_page(regions: list[Region]) -> Document:
    """A sidebar beside a main column, each two items deep — the shape Bands
    interleave: Band 0 is `Contact | Experience`, Band 1 `Skills | Education`."""
    return Document(
        source=Source(path="page.png", sha256="0", width=900, height=700),
        zones=[
            prose("Contact", BBox(0.02, 0.05, 0.30, 0.20), 0, 0),
            prose("Experience", BBox(0.38, 0.05, 0.97, 0.45), 0, 1),
            prose("Skills", BBox(0.02, 0.25, 0.30, 0.40), 1, 0),
            prose("Education", BBox(0.38, 0.50, 0.97, 0.90), 1, 1),
        ],
        regions=regions)


class TestTheIRCarriesTheStructure:
    """Spec 0008, step 2: `Document.regions`, and the renderer reading it."""

    COLUMNS = Region(0.0, 1.0, Flow.COLUMNS, (0.344,))

    def test_regions_survive_the_round_trip(self) -> None:
        regions = [Region(0.0, 0.1), Region(0.1, 0.9, Flow.GRID, (0.341, 0.659), rows=3),
                   Region(0.9, 1.0)]
        document = sidebar_page(regions)
        assert Document.from_json(document.to_json()).regions == regions

    def test_an_ir_written_before_regions_reads_back_with_none(self) -> None:
        raw = json.loads(sidebar_page([]).to_json())
        del raw["regions"]
        assert Document.from_json(json.dumps(raw)).regions == []

    def test_a_columns_region_is_read_lane_by_lane(self) -> None:
        html = render(sidebar_page([self.COLUMNS]))
        html = html[:html.index('id="doc-ir"')]
        order = [html.index(word) for word in
                 ("Contact", "Skills", "Experience", "Education")]
        assert order == sorted(order)

    def test_without_one_the_page_is_drawn_band_by_band(self) -> None:
        """Byte for byte as before: a `grid` or `single` region draws Bands."""
        plain = render(sidebar_page([]))
        assert render(sidebar_page([Region(0.0, 1.0)])).replace(
            '"regions":[{"top":0.0,"bottom":1.0,"flow":"single","splits":[],"rows":1}]',
            '"regions":[]') == plain
        body = plain[:plain.index('id="doc-ir"')]
        order = [body.index(word) for word in
                 ("Contact", "Experience", "Skills", "Education")]
        assert order == sorted(order)

    def test_a_lane_whose_zones_share_a_fill_is_painted_with_it(self) -> None:
        document = sidebar_page([self.COLUMNS])
        for zone in document.zones[0::2]:
            zone.fill = (38, 51, 63)
        html = render(document)
        assert 'class="lane" style="flex:34.4 1 0;background:rgb(38,51,63)"' in html
        assert 'class="lane" style="flex:65.6 1 0"' in html


def zones_of(name: str) -> list[Zone]:
    html = (FLOOR / f"{name}.html").read_text(encoding="utf-8")
    found = re.search(r'id="doc-ir">(.*?)</script>', html, re.S)
    assert found
    return Document.from_json(found.group(1).replace("<\\/", "</")).zones


class TestTheStructureShapesTheBoxes:
    """Spec 0008, step 3."""

    def test_the_catalogue_title_is_cut_out_of_the_first_card(self) -> None:
        rectified = rectify(REPO / SOURCES["catalogue_0015"].png)
        zones = zones_of("catalogue_0015")
        grid = next(r for r in regions_of("catalogue_0015") if r.flow is Flow.GRID)
        cut = cut_at_edges(rectified.image, zones, regions_of("catalogue_0015"))

        assert len(cut) == len(zones) + 1
        for zone in cut:
            assert zone.bbox is not None
            assert not zone.bbox.top < grid.top < zone.bbox.bottom
        title = [z for z in cut if z.bbox and z.bbox.bottom < grid.top and z.bbox.left < 0.1]
        assert len(title) == 1 and title[0].band == 0 and title[0].role is Role.HEADER
        cards = [z for z in cut if z.bbox and grid.holds(z.bbox)]
        assert len(cards) == 9
        assert all(card.role is Role.BODY for card in cards)

    def test_a_page_where_nothing_crosses_an_edge_is_left_as_it_is(self) -> None:
        rectified = rectify(REPO / SOURCES["cv_0013"].png)
        zones = zones_of("cv_0013")
        assert cut_at_edges(rectified.image, zones, regions_of("cv_0013")) is zones

    def test_a_grids_copies_take_the_kind_most_of_them_were_given(self) -> None:
        grid = [Region(0.0, 1.0, Flow.GRID, (0.5,), rows=2)]
        boxes = [BBox(0.0, 0.0, 0.4, 0.4), BBox(0.6, 0.0, 1.0, 0.4),
                 BBox(0.0, 0.6, 0.4, 1.0), BBox(0.6, 0.6, 1.0, 1.0)]
        kinds = [Kind.PAIRS, Kind.TABLE, Kind.PAIRS, Kind.PROSE]
        zones = [Zone(kind=kind, bbox=box) for kind, box in zip(kinds, boxes)]
        assert alike(zones, grid) == {1: Kind.PAIRS, 3: Kind.PAIRS}

    def test_a_tie_names_no_majority(self) -> None:
        grid = [Region(0.0, 1.0, Flow.GRID, (0.5,))]
        zones = [Zone(kind=Kind.PAIRS, bbox=BBox(0.0, 0.0, 0.4, 1.0)),
                 Zone(kind=Kind.TABLE, bbox=BBox(0.6, 0.0, 1.0, 1.0))]
        assert alike(zones, grid) == {}

    def test_only_a_grid_votes(self) -> None:
        columns = [Region(0.0, 1.0, Flow.COLUMNS, (0.5,))]
        zones = [Zone(kind=Kind.PAIRS, bbox=BBox(0.0, 0.0, 0.4, 0.4)),
                 Zone(kind=Kind.PAIRS, bbox=BBox(0.0, 0.5, 0.4, 0.9)),
                 Zone(kind=Kind.TABLE, bbox=BBox(0.6, 0.0, 1.0, 1.0))]
        assert alike(zones, columns) == {}
