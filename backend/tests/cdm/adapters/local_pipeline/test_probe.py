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
