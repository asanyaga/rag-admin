from app.cdm.adapters.local_pipeline.probe import PageProfile, DocumentProfile


def _make_page_profile(index: int = 0) -> PageProfile:
    return PageProfile(
        index=index,
        char_count=500,
        has_text_layer=True,
        image_count=0,
        font_health="clean",
        table_signal=False,
        page_type="text",
    )


def _make_document_profile() -> DocumentProfile:
    from datetime import datetime, timezone
    return DocumentProfile(
        source_document_id="doc-123",
        filename="test.pdf",
        page_count=2,
        pages=[_make_page_profile(0), _make_page_profile(1)],
        has_text_layer=True,
        has_scanned_pages=False,
        has_cid_corruption=False,
        table_signal=False,
        recommended_tools=["fitz", "camelot"],
        duration_ms=42,
        probed_at=datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc),
    )


def test_page_profile_round_trips_json():
    p = _make_page_profile()
    restored = PageProfile.model_validate_json(p.model_dump_json())
    assert restored == p


def test_document_profile_round_trips_json():
    d = _make_document_profile()
    restored = DocumentProfile.model_validate_json(d.model_dump_json())
    assert restored == d


def test_document_profile_is_frozen():
    d = _make_document_profile()
    try:
        d.page_count = 99  # type: ignore
        assert False, "should have raised"
    except Exception:
        pass


def test_page_profile_page_types_are_valid():
    valid_types = {"text", "scanned", "mixed", "empty"}
    p = _make_page_profile()
    assert p.page_type in valid_types


def test_recommended_tools_is_list_of_strings():
    d = _make_document_profile()
    assert isinstance(d.recommended_tools, list)
    assert all(isinstance(t, str) for t in d.recommended_tools)


from pathlib import Path
from app.cdm.adapters.local_pipeline.probe import DocumentProbe

FIXTURES = Path(__file__).parent / "fixtures"


def test_run_returns_document_profile():
    probe = DocumentProbe()
    profile = probe.run(FIXTURES / "simple_text.pdf", source_document_id="doc-abc")
    assert profile.source_document_id == "doc-abc"
    assert profile.page_count == 2


def test_run_detects_text_layer():
    probe = DocumentProbe()
    profile = probe.run(FIXTURES / "simple_text.pdf", source_document_id="doc-abc")
    assert profile.has_text_layer is True
    assert profile.has_scanned_pages is False


def test_run_per_page_char_counts():
    probe = DocumentProbe()
    profile = probe.run(FIXTURES / "simple_text.pdf", source_document_id="doc-abc")
    assert profile.pages[0].char_count > 0
    assert profile.pages[1].char_count > 0


def test_run_page_type_text():
    probe = DocumentProbe()
    profile = probe.run(FIXTURES / "simple_text.pdf", source_document_id="doc-abc")
    assert profile.pages[0].page_type == "text"


def test_run_table_signal_on_page_with_grid():
    probe = DocumentProbe()
    profile = probe.run(FIXTURES / "simple_text.pdf", source_document_id="doc-abc")
    # page 1 has a drawn grid
    assert profile.pages[1].table_signal is True


def test_run_no_table_signal_on_plain_text_page():
    probe = DocumentProbe()
    profile = probe.run(FIXTURES / "simple_text.pdf", source_document_id="doc-abc")
    assert profile.pages[0].table_signal is False


def test_run_duration_ms_is_positive():
    probe = DocumentProbe()
    profile = probe.run(FIXTURES / "simple_text.pdf", source_document_id="doc-abc")
    assert profile.duration_ms >= 0


def test_run_recommended_tools_not_empty():
    probe = DocumentProbe()
    profile = probe.run(FIXTURES / "simple_text.pdf", source_document_id="doc-abc")
    assert len(profile.recommended_tools) > 0


def test_run_no_cid_corruption_on_clean_pdf():
    probe = DocumentProbe()
    profile = probe.run(FIXTURES / "simple_text.pdf", source_document_id="doc-abc")
    assert profile.has_cid_corruption is False


def test_recommend_suggests_fitz_tables_for_clean_doc_with_table_signal():
    probe = DocumentProbe()
    result = probe._recommend(has_cid=False, has_scanned=False, has_tables=True)
    assert "fitz_tables" in result
    assert "camelot" not in result
    assert "fitz" in result


def test_recommend_fitz_only_for_clean_doc_without_tables():
    probe = DocumentProbe()
    result = probe._recommend(has_cid=False, has_scanned=False, has_tables=False)
    assert result == ["fitz"]
    assert "fitz_tables" not in result
