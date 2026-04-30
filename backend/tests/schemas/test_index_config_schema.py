import pytest
from pydantic import ValidationError as PydanticValidationError

from app.schemas.index import IndexConfig


def _valid_config_kwargs(**overrides):
    base = {
        "parser": "llamaparse",
        "parse_config_hash": "h" * 64,
        "source_representation": "full_text",
        "chunking_strategy": "recursive_character",
        "chunk_size": 500,
        "chunk_overlap": 50,
        "chunk_unit": "characters",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
    }
    base.update(overrides)
    return base


def test_index_config_default_source_representation_is_full_text():
    cfg = IndexConfig.model_validate(_valid_config_kwargs())
    assert cfg.source_representation == "full_text"


def test_index_config_rejects_legacy_raw_text():
    with pytest.raises(PydanticValidationError, match="source_representation"):
        IndexConfig.model_validate(_valid_config_kwargs(source_representation="raw_text"))


def test_index_config_requires_parser_and_parse_config_hash():
    with pytest.raises(PydanticValidationError, match="parser and parse_config_hash"):
        IndexConfig.model_validate(_valid_config_kwargs(parser=None))
    with pytest.raises(PydanticValidationError, match="parser and parse_config_hash"):
        IndexConfig.model_validate(_valid_config_kwargs(parse_config_hash=None))


def test_index_config_full_markdown_requires_markdown_strategy():
    with pytest.raises(PydanticValidationError, match="full_markdown"):
        IndexConfig.model_validate(_valid_config_kwargs(
            source_representation="full_markdown",
            chunking_strategy="recursive_character",
        ))


def test_index_config_full_text_accepts_recursive_character():
    cfg = IndexConfig.model_validate(_valid_config_kwargs(
        source_representation="full_text",
        chunking_strategy="recursive_character",
    ))
    assert cfg.chunking_strategy == "recursive_character"


def test_index_config_block_requires_block_strategy():
    cfg = IndexConfig.model_validate(_valid_config_kwargs(
        source_representation="block",
        chunking_strategy="block",
    ))
    assert cfg.chunking_strategy == "block"


def test_index_config_block_rejects_text_strategy():
    with pytest.raises(PydanticValidationError, match="block"):
        IndexConfig.model_validate(_valid_config_kwargs(
            source_representation="block",
            chunking_strategy="recursive_character",
        ))


def test_index_config_markdown_heading_defaults():
    cfg = IndexConfig.model_validate(_valid_config_kwargs(
        source_representation="full_markdown",
        chunking_strategy="markdown_heading",
    ))
    assert cfg.split_heading_level == 2
    assert cfg.max_section_chars == 4000


def test_index_config_split_heading_level_range():
    with pytest.raises(PydanticValidationError):
        IndexConfig.model_validate(_valid_config_kwargs(
            source_representation="full_markdown",
            chunking_strategy="markdown_heading",
            split_heading_level=0,
        ))
    with pytest.raises(PydanticValidationError):
        IndexConfig.model_validate(_valid_config_kwargs(
            source_representation="full_markdown",
            chunking_strategy="markdown_heading",
            split_heading_level=4,
        ))


def test_index_config_max_section_chars_range():
    with pytest.raises(PydanticValidationError):
        IndexConfig.model_validate(_valid_config_kwargs(
            source_representation="full_markdown",
            chunking_strategy="markdown_heading",
            max_section_chars=499,
        ))
    with pytest.raises(PydanticValidationError):
        IndexConfig.model_validate(_valid_config_kwargs(
            source_representation="full_markdown",
            chunking_strategy="markdown_heading",
            max_section_chars=16001,
        ))
