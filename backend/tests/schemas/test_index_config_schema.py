import pytest
from pydantic import ValidationError as PydanticValidationError

from app.schemas.index import IndexConfig


def test_default_config_is_raw_text():
    config = IndexConfig()
    assert config.source_representation == "raw_text"
    assert config.parser is None
    assert config.parse_config_hash is None


def test_full_text_requires_parser():
    with pytest.raises(PydanticValidationError) as exc_info:
        IndexConfig(source_representation="full_text")
    assert "parser" in str(exc_info.value).lower()


def test_full_text_with_parser_is_valid():
    config = IndexConfig(
        source_representation="full_text",
        parser="llamaparse",
        parse_config_hash="abc123",
    )
    assert config.source_representation == "full_text"
    assert config.parser == "llamaparse"


def test_markdown_heading_requires_full_markdown():
    with pytest.raises(PydanticValidationError):
        IndexConfig(
            source_representation="raw_text",
            chunking_strategy="markdown_heading",
        )


def test_block_strategy_requires_block_representation():
    with pytest.raises(PydanticValidationError):
        IndexConfig(
            source_representation="full_text",
            chunking_strategy="block",
            parser="llamaparse",
        )


def test_raw_text_with_fixed_size_is_valid():
    config = IndexConfig(
        source_representation="raw_text",
        chunking_strategy="fixed_size",
        chunk_size=256,
    )
    assert config.chunking_strategy == "fixed_size"


def test_parsing_strategy_field_no_longer_exists():
    config = IndexConfig()
    assert not hasattr(config, 'parsing_strategy')


def test_markdown_config_defaults():
    config = IndexConfig(
        source_representation="full_markdown",
        chunking_strategy="markdown_heading",
        parser="llamaparse",
    )
    assert config.split_heading_level == 2
    assert config.max_section_chars == 4000


def test_split_heading_level_range():
    with pytest.raises(PydanticValidationError):
        IndexConfig(
            source_representation="full_markdown",
            chunking_strategy="markdown_heading",
            parser="llamaparse",
            split_heading_level=0,
        )
    with pytest.raises(PydanticValidationError):
        IndexConfig(
            source_representation="full_markdown",
            chunking_strategy="markdown_heading",
            parser="llamaparse",
            split_heading_level=4,
        )


def test_max_section_chars_range():
    with pytest.raises(PydanticValidationError):
        IndexConfig(
            source_representation="full_markdown",
            chunking_strategy="markdown_heading",
            parser="llamaparse",
            max_section_chars=499,
        )
    with pytest.raises(PydanticValidationError):
        IndexConfig(
            source_representation="full_markdown",
            chunking_strategy="markdown_heading",
            parser="llamaparse",
            max_section_chars=16001,
        )
