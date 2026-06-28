import pytest
from app.services.extraction.transforms.registry import get_transforms, build_transform


def test_catalog_lists_merge_records_with_config_schema():
    types = {t["transform_type"]: t for t in get_transforms()}
    assert "merge_records" in types
    assert types["merge_records"]["config_schema"]["type"] == "object"


def test_build_known_and_unknown():
    assert build_transform("merge_records").transform_type == "merge_records"
    with pytest.raises(ValueError):
        build_transform("nope")


def test_catalog_lists_normalize_field_with_config_schema():
    types = {t["transform_type"]: t for t in get_transforms()}
    assert "normalize_field" in types
    schema = types["normalize_field"]["config_schema"]
    assert schema["type"] == "object"
    assert "fields" in schema["properties"]
    assert schema["properties"]["fields"]["type"] == "array"


def test_build_normalize_field():
    assert build_transform("normalize_field").transform_type == "normalize_field"


def test_catalog_lists_join_results_with_config_schema():
    types = {t["transform_type"]: t for t in get_transforms()}
    assert "join_results" in types
    schema = types["join_results"]["config_schema"]
    assert schema["type"] == "object"
    assert "joinKey" in schema["properties"]
    assert "joinType" in schema["properties"]


def test_build_join_results():
    assert build_transform("join_results").transform_type == "join_results"
