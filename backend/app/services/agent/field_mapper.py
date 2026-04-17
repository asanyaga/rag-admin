"""Pure functions for field mapping and array fan-out.

Transforms extraction state + field mapping config into flat rows
suitable for bulk insert into a data store.
"""
from itertools import product
from collections import defaultdict


def validate_field_mapping(
    field_mapping: dict[str, str],
    schema_definition: list[dict],
) -> list[str]:
    """Validate a field mapping against a data store schema.

    Returns a list of error messages. Empty list = valid.
    """
    errors: list[str] = []

    if not field_mapping:
        errors.append("Field mapping must contain at least one entry")
        return errors

    col_names = {col["name"] for col in schema_definition}
    required_cols = {col["name"] for col in schema_definition if not col.get("nullable", True)}

    # Check each mapping entry
    seen_destinations: dict[str, str] = {}
    for source_path, dest_col in field_mapping.items():
        # Max one dot
        if source_path.count(".") > 1:
            errors.append(
                f"Nested array paths are not supported — only 'array.field' is allowed: '{source_path}'"
            )

        # Destination must exist in schema
        if dest_col not in col_names:
            errors.append(
                f"Destination column '{dest_col}' does not exist in the data store schema"
            )

        # No duplicate destinations
        if dest_col in seen_destinations:
            errors.append(
                f"Duplicate destination column '{dest_col}' — mapped from both "
                f"'{seen_destinations[dest_col]}' and '{source_path}'"
            )
        seen_destinations[dest_col] = source_path

    # All non-nullable columns must have a mapping
    mapped_destinations = set(field_mapping.values())
    for req_col in required_cols:
        if req_col not in mapped_destinations:
            errors.append(
                f"Required column '{req_col}' has no source mapping"
            )

    return errors


def flatten_to_rows(
    state: dict,
    field_mapping: dict[str, str],
) -> list[dict]:
    """Apply field mapping to extraction state, producing flattened rows.

    Scalar source paths (no dot) are copied to every row.
    Array source paths (one dot: 'array.field') fan out — one row per element.
    Multiple arrays produce a cartesian product.
    """
    # Separate scalar vs array mappings
    scalar_mappings: dict[str, str] = {}  # source_key -> dest_col
    array_mappings: dict[str, list[tuple[str, str]]] = defaultdict(list)  # array_name -> [(field, dest_col)]

    for source_path, dest_col in field_mapping.items():
        if "." in source_path:
            array_name, field_name = source_path.split(".", 1)
            array_mappings[array_name].append((field_name, dest_col))
        else:
            scalar_mappings[source_path] = dest_col

    # Build the scalar part (same for every row)
    scalar_row: dict = {}
    for source_key, dest_col in scalar_mappings.items():
        scalar_row[dest_col] = state.get(source_key)

    # If no arrays, return a single row
    if not array_mappings:
        return [scalar_row]

    # Resolve each array from state
    resolved_arrays: dict[str, list[dict]] = {}
    for array_name in array_mappings:
        value = state.get(array_name)
        if value is None:
            resolved_arrays[array_name] = []
        elif isinstance(value, list):
            resolved_arrays[array_name] = value
        else:
            # Non-list treated as single-element list
            resolved_arrays[array_name] = [value]

    # If any array is empty, the fan-out produces zero rows
    for arr in resolved_arrays.values():
        if len(arr) == 0:
            return []

    # Compute cartesian product across all arrays
    array_names = list(resolved_arrays.keys())
    array_values = [resolved_arrays[name] for name in array_names]
    combinations = list(product(*array_values))

    rows: list[dict] = []
    for combo in combinations:
        row = dict(scalar_row)  # copy scalars
        for i, array_name in enumerate(array_names):
            element = combo[i]
            for field_name, dest_col in array_mappings[array_name]:
                if isinstance(element, dict):
                    row[dest_col] = element.get(field_name)
                else:
                    row[dest_col] = None
        rows.append(row)

    return rows
