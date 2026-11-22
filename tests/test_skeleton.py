"""The page's skeleton, top-down — spec 0025, step 2 (`doc_to_html.skeleton`).

Each rule on a small page of the parser's blocks, boxes on 0-1 of a
1000 x 1000 picture, a line 20 px tall; each test fails without its rule.
"""

from __future__ import annotations

from doc_to_html.adapter import Region
from doc_to_html.ir import BBox
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
