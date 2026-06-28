from app.services.extraction.transforms.base import (
    TransformInput, TransformResult, ExtractionResultTransform,
)


class _Echo:
    transform_type = "echo"

    def apply(self, inputs, config):
        rows = [r for i in inputs for r in i.rows]
        return TransformResult(rows=rows, flags=[])


def test_protocol_is_satisfied_and_apply_pools_rows():
    t: ExtractionResultTransform = _Echo()
    out = t.apply([TransformInput(rows=[{"a": 1}]), TransformInput(rows=[{"a": 2}])], {})
    assert out.rows == [{"a": 1}, {"a": 2}]
    assert out.flags == []
