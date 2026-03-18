"""Tests for parse diagnostics utility."""
from app.utils.parse_diagnostics import compute_diagnostics


class TestComputeDiagnostics:
    """Tests for compute_diagnostics function."""

    def test_empty_text(self):
        result = compute_diagnostics("")
        assert result["non_empty"] is False
        assert result["char_count"] == 0
        assert result["printable_ratio"] == 0.0
        assert result["suspected_cid"] is False
        assert result["token_count"] == 0

    def test_normal_text(self):
        text = "Hello world. This is a normal document with some text content."
        result = compute_diagnostics(text)
        assert result["non_empty"] is True
        assert result["char_count"] == len(text)
        assert result["printable_ratio"] > 0.9
        assert result["suspected_cid"] is False
        assert result["token_count"] > 0

    def test_cid_detection(self):
        # Fewer than 6 CID sequences — not suspected
        text = "(cid:0)(cid:1)(cid:2)(cid:3)(cid:4) some text"
        result = compute_diagnostics(text)
        assert result["suspected_cid"] is False

        # 6+ CID sequences — suspected
        text = "(cid:0)(cid:1)(cid:2)(cid:3)(cid:4)(cid:5)(cid:6) garbage"
        result = compute_diagnostics(text)
        assert result["suspected_cid"] is True

    def test_table_markers_in_text(self):
        text = "| Column A | Column B | Column C |\n| --- | --- | --- |"
        result = compute_diagnostics(text)
        assert result["has_table_markers"] is True

    def test_table_markers_in_markdown(self):
        text = "Some plain text"
        markdown = "| Col A | Col B |\n| --- | --- |"
        result = compute_diagnostics(text, markdown=markdown)
        assert result["has_table_markers"] is True

    def test_no_table_markers(self):
        text = "Just a simple paragraph without any tables."
        result = compute_diagnostics(text)
        assert result["has_table_markers"] is False

    def test_heading_markers(self):
        text = "plain text"
        markdown = "# Heading 1\n\nSome content\n\n## Heading 2"
        result = compute_diagnostics(text, markdown=markdown)
        assert result["has_heading_markers"] is True

    def test_no_heading_markers(self):
        text = "plain text"
        markdown = "Just a paragraph without headings"
        result = compute_diagnostics(text, markdown=markdown)
        assert result["has_heading_markers"] is False

    def test_empty_pages(self):
        text = "[Page 1]\nContent on page 1\n[Page 2]\n\n[Page 3]\nContent on page 3"
        result = compute_diagnostics(text)
        assert result["empty_pages"] == 1  # Page 2 is empty

    def test_no_page_markers(self):
        text = "Just text without page markers"
        result = compute_diagnostics(text)
        assert result["empty_pages"] == 0
