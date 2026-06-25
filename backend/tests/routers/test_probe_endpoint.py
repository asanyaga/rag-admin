"""Smoke test: probe endpoint returns a DocumentProfile-shaped response."""
from datetime import datetime, timezone


def test_profile_dict_shape_matches_endpoint_contract():
    """Verify DocumentProfile serialises to the JSON shape the endpoint returns."""
    from app.cdm.adapters.local_pipeline.probe import DocumentProfile

    profile = DocumentProfile(
        source_document_id="doc-abc",
        filename="test.pdf",
        page_count=1,
        pages=[],
        has_text_layer=True,
        has_scanned_pages=False,
        has_cid_corruption=False,
        table_signal=False,
        recommended_tools=["fitz"],
        duration_ms=10,
        probed_at=datetime(2026, 6, 25, tzinfo=timezone.utc),
    )

    data = profile.model_dump(mode="json")
    assert data["page_count"] == 1
    assert data["has_text_layer"] is True
    assert data["recommended_tools"] == ["fitz"]
    assert data["filename"] == "test.pdf"
    assert data["source_document_id"] == "doc-abc"
    assert isinstance(data["probed_at"], str)  # JSON-serialisable
