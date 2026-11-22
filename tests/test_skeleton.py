"""The page's skeleton, top-down — spec 0025, step 2 (`doc_to_html.skeleton`),
the page laid out from it, step 3 (`adapter.laid_out`), and a grid read
as a table, step 4 (`parser_first.with_grids`, `readable`), and one size
per role in a table, step 5 (`parser_first.table_sizes`).

Each rule on a small page of the parser's blocks, boxes on 0-1 of a
1000 x 1000 picture, a line 20 px tall; each test fails without its rule.
"""

from __future__ import annotations

import re

from doc_to_html.adapter import Region, laid_out, regions_of
from doc_to_html.ir import (BBox, Cell, Document, Flow, Furniture, Kind, Look, Region as IRRegion,
                            Reading, Row, RowRole, Source, Zone)
from doc_to_html.parser_first import readable, table_sizes, with_grids
from doc_to_html.render import render
from doc_to_html.skeleton import Part, check, skeleton


def block(index: int, box: tuple[float, float, float, float], label: str = "text",
          content: str = "words") -> Region:
    return Region(index, label, BBox(*box), "" if label == "image" else content)


def parts(root: Part, kind: str) -> list[tuple[int, ...]]:
    return [p.blocks for p in root.walk() if p.kind == kind]


class TestTheOrderChoosesTheCut:
    def test_two_columns_read_column_by_column_are_columns_not_rows(self) -> None:
        # Two gaps across (40 and 50 px) line up in both columns and are
        # wider than the gutter (20 px); the order reads each column through.
        spans = [((0.10, 0.13), (0.12, 0.16)), ((0.20, 0.22), (0.22, 0.25)),
                 ((0.30, 0.32), (0.33, 0.36))]
        left = [block(i, (0.05, l[0], 0.49, l[1])) for i, (l, _) in enumerate(spans)]
        right = [block(3 + i, (0.51, r[0], 0.95, r[1])) for i, (_, r) in enumerate(spans)]
        root = skeleton(left + right)
        assert (0, 1, 2, 3, 4, 5) in parts(root, "columns")
        assert {(0, 1, 2), (3, 4, 5)} <= set(parts(root, "rows"))

    def test_label_value_rows_read_across_are_never_a_column_of_labels(self) -> None:
        # Touching rows, no gap across; read label, value, label, value.
        regions = []
        for row in range(3):
            top = 0.1 + 0.02 * row
            regions += [block(2 * row, (0.05, top, 0.2, top + 0.02)),
                        block(2 * row + 1, (0.3, top, 0.6, top + 0.02))]
        root = skeleton(regions)
        assert not parts(root, "columns")
        assert [p.note for p in root.walk() if p.kind == "flat"] == [
            "no cut: down against the order (3 > 0)"]

    def test_rows_of_fields_with_gaps_between_them_are_a_grid(self) -> None:
        regions = []
        for row in range(3):
            top = 0.1 + 0.05 * row
            regions += [block(2 * row, (0.05, top, 0.2, top + 0.02)),
                        block(2 * row + 1, (0.3, top, 0.6, top + 0.02))]
        root = skeleton(regions)
        assert parts(root, "grid") == [(0, 1, 2, 3, 4, 5)]


class TestDrawnBoxes:
    def test_a_box_drawn_round_two_blocks_is_one_part(self) -> None:
        regions = [block(0, (0.05, 0.1, 0.45, 0.3)),
                   block(1, (0.6, 0.1, 0.9, 0.12)), block(2, (0.6, 0.2, 0.9, 0.22))]
        root = skeleton(regions, [BBox(0.55, 0.08, 0.95, 0.25)])
        assert parts(root, "box") == [(1, 2)]

    def test_a_legend_on_the_frames_top_edge_is_inside_it(self) -> None:
        # c0093's SIGN HERE: its centre just above the frame's top rule.
        regions = [block(0, (0.08, 0.19, 0.3, 0.21)), block(1, (0.08, 0.25, 0.9, 0.27)),
                   block(2, (0.08, 0.35, 0.9, 0.37)), block(3, (0.08, 0.7, 0.9, 0.72))]
        root = skeleton(regions, [BBox(0.05, 0.2005, 0.95, 0.6)])
        assert parts(root, "box") == [(0, 1, 2)]

    def test_a_frame_round_every_block_is_the_pages_one_part(self) -> None:
        regions = [block(0, (0.1, 0.1, 0.8, 0.12)), block(1, (0.1, 0.2, 0.8, 0.22))]
        root = skeleton(regions, [BBox(0.05, 0.05, 0.85, 0.3)])
        assert parts(root, "box") == [(0, 1)]


class TestLiftingIsALastResort:
    def test_a_full_width_line_under_a_row_is_its_own_row(self) -> None:
        # c0514: the certificate number under the date, seal and signature.
        regions = [block(0, (0.2, 0.7, 0.33, 0.8), content="12 September\nDate"),
                   block(1, (0.45, 0.7, 0.55, 0.8), "image"),
                   block(2, (0.64, 0.7, 0.82, 0.8), content="Name\nDirector"),
                   block(3, (0.2, 0.84, 0.8, 0.86))]
        root = skeleton(regions)
        assert parts(root, "columns") == [(0, 1, 2)]
        assert [c.blocks for c in root.children[0].children] == [(0, 1, 2), (3,)]

    def test_a_caption_is_never_lifted_into_another_column_than_its_figure(self) -> None:
        # c0541: the caption under the chart is read after the sidebar's
        # first block; lifted to that side it would leave its chart.
        regions = [block(0, (0.05, 0.1, 0.6, 0.4), "chart"),
                   block(1, (0.7, 0.1, 0.95, 0.12)),
                   block(2, (0.05, 0.42, 0.9, 0.44), "figure_title"),
                   block(3, (0.7, 0.15, 0.95, 0.17))]
        root = skeleton(regions)
        assert [c.blocks for c in root.children[0].children] == [(0, 1, 3), (2,)]


class TestThePagesEdges:
    def test_a_page_number_set_with_the_header_is_its_top_row(self) -> None:
        regions = [block(0, (0.05, 0.02, 0.3, 0.04), "header"),
                   block(1, (0.9, 0.02, 0.95, 0.04), "number"),
                   block(2, (0.05, 0.1, 0.95, 0.12)), block(3, (0.05, 0.2, 0.95, 0.22))]
        root = skeleton(regions)
        assert [c.blocks for c in root.children] == [(0, 1), (2, 3)]


class TestTheCheck:
    def test_parts_overlapping_on_their_blocks_are_kept_flat(self) -> None:
        regions = [block(0, (0.1, 0.1, 0.5, 0.3)), block(1, (0.4, 0.2, 0.9, 0.4))]
        boxes = {r.index: r.box for r in regions}
        rows = Part("rows", BBox(0.1, 0.1, 0.9, 0.4), (0, 1),
                    [Part("block", boxes[0], (0,)), Part("block", boxes[1], (1,))])
        root = check(Part("page", rows.box, (0, 1), [rows]), regions, boxes, {})
        assert root.children[0].kind == "flat"
        assert root.children[0].note == "check: two parts overlap"


# ---- step 3: laid out from the skeleton (`adapter.laid_out`) ----------------------

def raw(index: int, box: tuple[float, float, float, float], label: str = "text",
        content: str = "words") -> dict[str, object]:
    return {"index": index, "label": label, "content": "" if label == "image" else content,
            "bbox_2d": [round(v * 1000) for v in box]}


def laid(entries: list[dict[str, object]], drawn: list[BBox] = ()) -> tuple[Document, list]:
    regions = regions_of(entries)
    source = Source(path="page.png", sha256="0", width=1000, height=1000)
    return laid_out(entries, skeleton(regions, drawn), source, drawn)


class TestLaidOutFromTheSkeleton:
    def test_a_lane_holding_several_zones_is_a_banded_columns_region(self) -> None:
        entries = [raw(0, (0.05, 0.10, 0.30, 0.12), "paragraph_title", "LEFT"),
                   raw(1, (0.05, 0.30, 0.30, 0.50), "image"),
                   raw(2, (0.40, 0.10, 0.95, 0.12), "paragraph_title", "RIGHT"),
                   raw(3, (0.40, 0.35, 0.95, 0.60), "image")]
        document, _ = laid(entries)
        (lanes,) = [r for r in document.regions if r.flow is Flow.COLUMNS]
        assert lanes.banded and lanes.splits == (0.4,)
        bands = [(z.band, z.column) for z in document.zones]
        assert bands == sorted(bands) and len({b for b, _ in bands}) == 4

    def test_a_drawn_box_is_not_one_zone_across_a_picture(self) -> None:
        # c0511's stub: its card rule joined the times above the barcode to
        # the number under it, and the Zone was drawn beside the barcode.
        entries = [raw(0, (0.05, 0.10, 0.25, 0.12), content="Doors open"),
                   raw(1, (0.05, 0.13, 0.25, 0.15), content="6.30 pm"),
                   raw(2, (0.05, 0.20, 0.25, 0.30), "image"),
                   raw(3, (0.05, 0.31, 0.25, 0.33), content="0048213"),
                   raw(4, (0.40, 0.10, 0.95, 0.12), content="Main")]
        document, _ = laid(entries, [BBox(0.03, 0.08, 0.30, 0.40)])
        texts = [" ".join(c.text for b in z.blocks for c in b.lines) for z in document.zones]
        assert "0048213" in texts and not any("6.30 pm" in t and "0048213" in t for t in texts)

    def test_a_box_round_a_banded_region_frames_every_zone_in_it(self) -> None:
        entries = [raw(0, (0.10, 0.10, 0.40, 0.12), "paragraph_title", "A"),
                   raw(1, (0.10, 0.20, 0.40, 0.40), "image"),
                   raw(2, (0.50, 0.10, 0.90, 0.12), "paragraph_title", "B"),
                   raw(3, (0.50, 0.20, 0.90, 0.40), "image")]
        # The left lane's own box is inside the frame: the frame wins, as
        # c0511's ticket does over its stub.
        frame = BBox(0.05, 0.05, 0.95, 0.45)
        document, frames = laid(entries, [frame, BBox(0.08, 0.08, 0.42, 0.42)])
        assert [r.banded for r in document.regions if r.flow is Flow.COLUMNS] == [True]
        assert frames == [frame] * len(document.zones)


class TestBandedIsWrittenOnlyWhereSet:
    def held(self, label: str, content: str) -> dict[str, tuple[int, int]]:
        entries = [raw(0, (0.05, 0.05, 0.95, 0.07), "paragraph_title", "HEAD"),
                   raw(1, (0.05, 0.10, 0.10, 0.16), "image"),
                   raw(2, (0.05, 0.10, 0.50, 0.30), label, content),
                   raw(3, (0.55, 0.10, 0.95, 0.30), "text", "beside")]
        document, _ = laid(entries)
        return {z.kind.value: (z.band, z.column) for z in document.zones[1:3]}

    def test_a_picture_inside_text_is_banded_under_it(self) -> None:
        # c0407's drop capital: banded where it stands, a column beside its
        # paragraph, the paragraph a word a line.
        places = self.held("text", "A paragraph round its drop capital")
        assert places["figure"][0] > places["prose"][0]

    def test_a_picture_inside_a_table_stays_where_it_stands(self) -> None:
        # c0008's number badges, moved under their table, scattered.
        places = self.held("table", "<table><tr><td>9</td><td>Total</td></tr></table>")
        assert places["figure"][0] == places["table"][0]

    def test_a_fill_round_a_banded_row_is_no_lane_s_own(self) -> None:
        # probe_datasheet: the header strip's VERIDIAN lane, inset from the
        # strip's left edge, pressed the title's lane to a word a line.
        entries = [raw(0, (0.05, 0.03, 0.20, 0.05), "header"),
                   raw(1, (0.05, 0.07, 0.45, 0.11), "paragraph_title"),
                   raw(2, (0.85, 0.09, 0.95, 0.11), "header"), raw(3, (0.05, 0.30, 0.95, 0.32))]
        document, _ = laid(entries, [BBox(0.0, 0.0, 1.0, 0.14)])
        assert any(r.banded for r in document.regions)
        ink = (11, 58, 91)
        for zone in document.zones[:3]:
            zone.fill = ink
            for line in (cell for b in zone.blocks for cell in b.lines):
                line.bbox = zone.bbox
        document.furniture = [Furniture("fill", BBox(0.0, 0.0, 1.0, 0.14), color=ink)]
        lanes = re.findall(r'class="lane" style="([^"]*)"', render(document))
        pads = [float(v) for style in lanes for padding in re.findall(r"padding:([^;]*)", style)
                for v in re.findall(r"(\d+)px", padding)]
        assert len(lanes) == 2 and max(pads, default=0) < 100

    def test_today_s_regions_are_written_as_before(self) -> None:
        source = Source(path="page.png", sha256="0", width=1000, height=1000)
        plain = Document(source=source, regions=[IRRegion(top=0.0, bottom=1.0)])
        assert "banded" not in plain.to_data()["regions"][0]
        banded = Document(source=source, regions=[
            IRRegion(top=0.0, bottom=1.0, flow=Flow.COLUMNS, splits=(0.5,), banded=True)])
        assert Document.from_json(banded.to_json()).regions[0].banded


# ---- step 4: a grid read as a table (`parser_first`, 3c) -------------------------

class TestAGridReadAsATable:
    fragments = [raw(0, (0.05, 0.10, 0.20, 0.12), content="Name"),
                 raw(1, (0.30, 0.10, 0.50, 0.12), content="Relationship"),
                 raw(2, (0.05, 0.13, 0.20, 0.15), content="Peter Whitlock"),
                 raw(3, (0.30, 0.13, 0.50, 0.15), content="Father"),
                 raw(4, (0.05, 0.30, 0.95, 0.32), content="Below")]

    def grid(self, content: str) -> dict[str, object]:
        return {"blocks": [0, 1, 2, 3], "bbox_2d": [50, 100, 500, 150], "content": content}

    def test_its_fragments_give_way_to_the_table_in_their_place(self) -> None:
        table = ("<table><tr><td>Name</td><td>Relationship</td></tr>"
                 "<tr><td>Peter Whitlock</td><td>Father</td></tr></table>")
        out = with_grids(self.fragments, [self.grid(table)])
        assert [(r["index"], r["label"]) for r in out] == [(4, "text"), (0, "table")]

    def test_a_table_dropping_a_word_keeps_the_fragments(self) -> None:
        # c0024: the header's exam number, dropped by the table mode.
        table = "<table><tr><td>Name</td><td>Relationship</td></tr></table>"
        assert with_grids(self.fragments, [self.grid(table)]) == self.fragments

    def test_a_grid_holding_a_picture_larger_than_a_mark_is_not_read(self) -> None:
        # c0012's signature beside its date; c0008's tick boxes are marks.
        regions = {r.index: r for r in regions_of(self.fragments + [
            raw(5, (0.60, 0.10, 0.62, 0.12), "image"), raw(6, (0.60, 0.20, 0.80, 0.25), "image")])}
        assert readable([0, 1, 5], regions, (1000, 1000))
        assert not readable([0, 1, 6], regions, (1000, 1000))

    def test_a_pictures_content_is_not_a_word_the_table_must_hold(self) -> None:
        fragments = self.fragments[:4] + [{**raw(5, (0.21, 0.10, 0.29, 0.15), "image"),
                                           "content": "```markdown\n\n```"}]
        table = ("<table><tr><td>Name</td><td>Relationship</td></tr>"
                 "<tr><td>Peter Whitlock</td><td>Father</td></tr></table>")
        grid = {"blocks": [0, 1, 2, 3, 5], "bbox_2d": [50, 100, 500, 150], "content": table}
        assert [r["label"] for r in with_grids(fragments, [grid])] == ["table"]


# ---- step 5: one size per role (`parser_first.table_sizes`, 3e) ------------------

class TestOneSizePerRoleInATable:
    def table(self, header: list[float | None], rows: list[list[float | None]]) -> Zone:
        def cells(sizes: list[float | None]) -> list[Cell]:
            return [Cell(readings=[Reading(engine="glm-ocr", text="x")],
                         look=None if size is None else Look(size=size))
                    for size in sizes]
        return Zone(kind=Kind.TABLE, rows=[Row(role=RowRole.HEADER, cells=cells(header))]
                    + [Row(role=RowRole.DATA, cells=cells(row)) for row in rows])

    def sizes(self, zone: Zone) -> list[list[float | None]]:
        table_sizes(Document(source=Source(path="p.png", sha256="0", width=1, height=1),
                             zones=[zone]))
        return [[c.look.size if c.look else None for c in row.cells] for row in zone.rows]

    def test_a_cell_off_its_column_is_drawn_at_the_column_s_size(self) -> None:
        # c0198's backordered row at 0.50 among rows at 1.00.
        zone = self.table([1.0, 1.0], [[1.0, 1.0], [0.5, 0.5], [1.0, 1.12], [None, 1.0]])
        assert self.sizes(zone)[1:] == [[1.0, 1.0]] * 4

    def test_a_header_too_short_for_its_columns_takes_the_role_s_size(self) -> None:
        # c0198's `Ship` at 0.62 among headers at 1.00.
        zone = self.table([1.0, 1.0, 0.62, 1.0], [[1.0, 1.0, 1.0, 1.0]])
        assert self.sizes(zone)[0] == [1.0, 1.0, 1.0, 1.0]

    def test_a_column_keeps_a_size_of_its_own(self) -> None:
        zone = self.table([1.0, 1.0], [[1.0, 1.5], [1.0, 1.5], [1.0, 1.38]])
        assert [row[1] for row in self.sizes(zone)[1:]] == [1.5, 1.5, 1.5]

    def test_a_row_printed_larger_keeps_its_size(self) -> None:
        # c0177's `Totale 3.295,22 €` at 1.67 among rows at 1.00, beside
        # the `PAGAMENTO` note the parser's table puts in its row.
        zone = self.table([1.0, 1.0, 1.0], [[1.0, 1.0, 1.0]] * 3 + [[1.0, 1.67, 1.67]])
        assert self.sizes(zone)[-1] == [1.0, 1.67, 1.67]

    def test_one_cell_above_its_peers_is_drawn_at_theirs(self) -> None:
        # c0112's `Type` header at 1.38 among headers at 1.00.
        zone = self.table([1.0, 1.38, 1.0], [[1.0, 1.0, 1.0]] * 3)
        assert self.sizes(zone)[0] == [1.0, 1.0, 1.0]
