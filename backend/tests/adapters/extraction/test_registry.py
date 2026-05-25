"""Tests for extraction adapter registry."""
import pytest
from app.adapters.extraction.registry import get_known_extractors, get_extractor


class TestGetKnownExtractors:
    def test_returns_all_adapters_unconditionally(self):
        extractors = get_known_extractors()
        methods = [e["extraction_method"] for e in extractors]
        assert "llamaextract" in methods
        assert "ollama" in methods

    def test_each_entry_has_required_keys(self):
        for e in get_known_extractors():
            assert "extraction_method" in e
            assert "name" in e
            assert "description" in e
            assert "config_schema" in e

    def test_no_settings_dependency(self):
        import app.adapters.extraction.registry as registry_module
        assert not hasattr(registry_module, "settings")
        result = get_known_extractors()
        assert isinstance(result, list)

    def test_result_is_stable(self):
        # Same list returned on repeated calls — no side effects
        assert get_known_extractors() == get_known_extractors()


class TestGetExtractor:
    def test_unknown_method_raises(self):
        with pytest.raises(ValueError, match="Unknown extraction method"):
            get_extractor("nonexistent_method", {})

    def test_llamaextract_uses_credentials_api_key(self):
        extractor = get_extractor("llamaextract", {"api_key": "test-key-123"})
        assert extractor.extractor_type == "llamaextract"

    def test_llamaextract_works_with_empty_credentials(self):
        # Empty credentials dict is valid — adapter handles absent key internally
        extractor = get_extractor("llamaextract", {})
        assert extractor is not None

    def test_no_settings_read_in_factory(self):
        import app.adapters.extraction.registry as registry_module
        assert not hasattr(registry_module, "settings")
        extractor = get_extractor("llamaextract", {"api_key": "k"})
        assert extractor.extractor_type == "llamaextract"


class TestLlamaExtractConfigSchema:
    def test_config_schema_has_extraction_target(self):
        extractor = next(
            e for e in get_known_extractors()
            if e["extraction_method"] == "llamaextract"
        )
        props = extractor["config_schema"]["properties"]
        assert "extraction_target" in props
        assert props["extraction_target"]["enum"] == ["PER_DOC", "PER_PAGE"]

    def test_config_schema_has_confidence_scores(self):
        extractor = next(
            e for e in get_known_extractors()
            if e["extraction_method"] == "llamaextract"
        )
        props = extractor["config_schema"]["properties"]
        assert "confidence_scores" in props
        assert props["confidence_scores"]["type"] == "boolean"
