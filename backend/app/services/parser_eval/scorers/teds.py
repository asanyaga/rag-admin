"""Tree-Edit-Distance-based Similarity (TEDS) for HTML tables.

A table is parsed into a tree (table -> tr -> td/th, each cell carrying normalized
text + colspan/rowspan). APTED computes the minimum edit distance; TEDS normalizes
it to 1 - distance / max(nodes_a, nodes_b), so 1.0 = identical, 0.0 = fully different.
Cell-text differences contribute a fractional rename cost via normalized string
similarity, so a single misread cell barely dents the score.
"""
from __future__ import annotations

import difflib
import re
from collections import Counter
from html.parser import HTMLParser

from apted import APTED, Config

_WS = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WS.sub(" ", (text or "").strip()).lower()


def _to_int(value: str | None, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


class _Node:
    def __init__(self, tag: str, colspan: int = 1, rowspan: int = 1, text: str = ""):
        self.name = tag            # apted may read .name; keep it in sync with tag
        self.tag = tag
        self.colspan = colspan
        self.rowspan = rowspan
        self.text = text
        self.children: list["_Node"] = []


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.root = _Node("table")
        self._row: _Node | None = None
        self._cell: _Node | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = _Node("tr")
            self.root.children.append(self._row)
        elif tag in ("td", "th"):
            if self._row is None:
                self._row = _Node("tr")
                self.root.children.append(self._row)
            a = dict(attrs)
            self._cell = _Node(tag, _to_int(a.get("colspan"), 1), _to_int(a.get("rowspan"), 1))
            self._row.children.append(self._cell)

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._cell = None
        elif tag == "tr":
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.text += data


def _parse(html: str) -> _Node:
    parser = _TableParser()
    parser.feed(html or "")
    for row in parser.root.children:
        for cell in row.children:
            cell.text = _normalize(cell.text)
    return parser.root


def _count(node: _Node) -> int:
    return 1 + sum(_count(child) for child in node.children)


class _TedsConfig(Config):
    def __init__(self, structure_only: bool = False):
        self.structure_only = structure_only

    def children(self, node):
        return node.children

    def insert(self, node):
        return 1.0

    def delete(self, node):
        return 1.0

    def rename(self, node1, node2):
        if (node1.tag != node2.tag or node1.colspan != node2.colspan
                or node1.rowspan != node2.rowspan):
            return 1.0
        if self.structure_only:
            return 0.0
        if node1.tag in ("td", "th") and node1.text != node2.text:
            return 1.0 - difflib.SequenceMatcher(None, node1.text, node2.text).ratio()
        return 0.0


def teds(html_a: str, html_b: str, *, structure_only: bool = False) -> float:
    tree_a, tree_b = _parse(html_a), _parse(html_b)
    denom = max(_count(tree_a), _count(tree_b))
    if denom == 0:
        return 1.0
    distance = APTED(tree_a, tree_b, _TedsConfig(structure_only)).compute_edit_distance()
    return max(0.0, 1.0 - distance / denom)


def cell_count(html: str) -> int:
    root = _parse(html)
    return sum(len(row.children) for row in root.children)


def _cell_texts(html: str) -> Counter:
    root = _parse(html)  # _parse already normalizes each cell's text
    return Counter(cell.text for row in root.children for cell in row.children
                   if cell.tag in ("td", "th"))


def cell_content_f1(html_a: str, html_b: str) -> float:
    a, b = _cell_texts(html_a), _cell_texts(html_b)
    total = sum(a.values()) + sum(b.values())
    if total == 0:
        return 1.0
    if not a or not b:
        return 0.0
    intersection = sum((a & b).values())  # multiset intersection
    return 2 * intersection / total
