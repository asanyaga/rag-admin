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


def test_index_config_rejects_full_markdown():
    with pytest.raises(PydanticValidationError, match="source_representation"):
        IndexConfig.model_validate(_valid_config_kwargs(
            source_representation="full_markdown",
            chunking_strategy="markdown_heading",
        ))


def test_index_config_requires_parser_and_parse_config_hash():
    with pytest.raises(PydanticValidationError, match="parser and parse_config_hash"):
        IndexConfig.model_validate(_valid_config_kwargs(parser=None))
    with pytest.raises(PydanticValidationError, match="parser and parse_config_hash"):
        IndexConfig.model_validate(_valid_config_kwargs(parse_config_hash=None))


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


def _block_config(**overrides):
    base = dict(
        parser="llamaparse",
        parse_config_hash="h" * 64,
        source_representation="block",
        chunking_strategy="block",
    )
    base.update(overrides)
    return base


def test_block_config_defaults():
    cfg = IndexConfig(**_block_config())
    assert cfg.group_by_heading is True
    assert cfg.max_blocks_per_chunk == 10
    assert cfg.block_role_filter is None


def test_block_config_accepts_role_filter():
    cfg = IndexConfig(**_block_config(block_role_filter=["table", "figure"]))
    assert cfg.block_role_filter == ["table", "figure"]


def test_max_blocks_per_chunk_below_min_rejected():
    with pytest.raises(PydanticValidationError):
        IndexConfig(**_block_config(max_blocks_per_chunk=0))


def test_max_blocks_per_chunk_above_max_rejected():
    with pytest.raises(PydanticValidationError):
        IndexConfig(**_block_config(max_blocks_per_chunk=51))


def test_block_role_filter_accepts_camel_case_alias():
    cfg = IndexConfig.model_validate({
        "parser": "llamaparse",
        "parseConfigHash": "h" * 64,
        "sourceRepresentation": "block",
        "chunkingStrategy": "block",
        "groupByHeading": False,
        "maxBlocksPerChunk": 5,
        "blockRoleFilter": ["text"],
    })
    assert cfg.group_by_heading is False
    assert cfg.max_blocks_per_chunk == 5
    assert cfg.block_role_filter == ["text"]
