# LandingAI Heading Role Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `LandingAIAdapter` assign `BlockRole.TITLE` or `BlockRole.HEADING` to text chunks whose markdown content leads with a `#`-level heading, instead of always assigning `BlockRole.PARAGRAPH`.

**Architecture:** LandingAI does not expose a `heading` chunk type — all text content arrives as `type: "text"`. Heading level is encoded in the `markdown` field using standard ATX-style markers (`#`, `##`, `###`). The fix is a pure function `_detect_text_role(markdown)` that strips the leading anchor tag every chunk carries (`<a id='UUID'></a>`), inspects the first non-empty content line, and maps `# …` → `TITLE`, `## …` / `### …` (or deeper) → `HEADING`, and anything else → `PARAGRAPH`. The existing `_map_role(chunk_type)` is extended to accept the raw markdown string and delegates to `_detect_text_role` only when `chunk_type == "text"`. One call-site in `LandingAIAdapter.adapt` is updated.

**Tech Stack:** Python 3.12, `re` stdlib, `pytest`

## Global Constraints

- No new dependencies — stdlib `re` only
- All changes confined to `backend/app/cdm/adapters/landing_ai.py` and its test file
- Run tests with: `uv run --directory backend python -m pytest tests/cdm/test_landing_ai_adapter.py -o "addopts=" -v`
- Heading detection must be a pure function (no side effects, no I/O)
- `TITLE` = exactly one leading `#`; `HEADING` = two or more leading `#` — matches CDM semantics

---

## File Map

| File | Change |
|---|---|
| `backend/app/cdm/adapters/landing_ai.py` | Add `_ANCHOR_RE`, `_first_content_line`, `_detect_text_role`; extend `_map_role` signature |
| `backend/tests/cdm/test_landing_ai_adapter.py` | Add unit tests for `_detect_text_role` and adapter integration tests for heading roles |

---

### Task 1: Add `_detect_text_role` and update `_map_role`

**Files:**
- Modify: `backend/app/cdm/adapters/landing_ai.py:26-38` (role map + `_map_role`)
- Test: `backend/tests/cdm/test_landing_ai_adapter.py`

**Interfaces:**
- Produces: `_detect_text_role(markdown: str) -> BlockRole` — importable by tests
- Produces: `_map_role(chunk_type: str, markdown: str = "") -> BlockRole` — used by `LandingAIAdapter.adapt`

---

- [ ] **Step 1: Write the failing unit tests**

Append to `backend/tests/cdm/test_landing_ai_adapter.py` (after all existing tests):

```python
# ---------------------------------------------------------------------------
# _detect_text_role unit tests
# ---------------------------------------------------------------------------
from app.cdm.adapters.landing_ai import _detect_text_role


def test_detect_plain_text_is_paragraph():
    assert _detect_text_role("Hello world.") == BlockRole.PARAGRAPH


def test_detect_anchor_then_plain_text_is_paragraph():
    assert _detect_text_role("<a id='x'></a>\n\nPlain paragraph.") == BlockRole.PARAGRAPH


def test_detect_h1_is_title():
    assert _detect_text_role("<a id='x'></a>\n\n# Main Title") == BlockRole.TITLE


def test_detect_h1_with_body_is_title():
    # heading + body text in one chunk — role is determined by the first content line
    assert _detect_text_role("<a id='x'></a>\n\n# Main Title\n\nBody text here.") == BlockRole.TITLE


def test_detect_h2_is_heading():
    assert _detect_text_role("<a id='x'></a>\n\n## Section") == BlockRole.HEADING


def test_detect_h3_is_heading():
    assert _detect_text_role("<a id='x'></a>\n\n### Subsection\n\nContent.") == BlockRole.HEADING


def test_detect_h4_is_heading():
    assert _detect_text_role("#### Deep heading") == BlockRole.HEADING


def test_detect_hash_without_space_is_paragraph():
    # ##NoSpace is not a valid ATX heading; treat as paragraph
    assert _detect_text_role("##NoSpace") == BlockRole.PARAGRAPH


def test_detect_empty_markdown_is_paragraph():
    assert _detect_text_role("") == BlockRole.PARAGRAPH


def test_detect_anchor_only_is_paragraph():
    assert _detect_text_role("<a id='x'></a>\n\n") == BlockRole.PARAGRAPH
```

- [ ] **Step 2: Run to confirm the tests fail (import error)**

```
uv run --directory backend python -m pytest tests/cdm/test_landing_ai_adapter.py -o "addopts=" -k "detect" -v
```

Expected: `ImportError: cannot import name '_detect_text_role'`

- [ ] **Step 3: Implement `_detect_text_role` and extend `_map_role`**

In `backend/app/cdm/adapters/landing_ai.py`, add `import re` to the existing imports block, then add these three definitions **between the `_ROLE_MAP` dict and `_map_role`**:

```python
import re

# Strips the per-chunk anchor LandingAI prepends to every markdown field:
# <a id='UUID'></a>\n\n
_ANCHOR_RE = re.compile(r"^<a\s[^>]*></a>\s*", re.MULTILINE)

_HEADING_RE = re.compile(r"^(#{1,6}) ")


def _first_content_line(markdown: str) -> str:
    """Return the first non-empty line after stripping the leading anchor tag."""
    stripped = _ANCHOR_RE.sub("", markdown, count=1).lstrip("\n")
    for line in stripped.split("\n"):
        line = line.strip()
        if line:
            return line
    return ""


def _detect_text_role(markdown: str) -> BlockRole:
    """Map a text chunk's markdown to TITLE, HEADING, or PARAGRAPH."""
    first = _first_content_line(markdown)
    m = _HEADING_RE.match(first)
    if not m:
        return BlockRole.PARAGRAPH
    return BlockRole.TITLE if len(m.group(1)) == 1 else BlockRole.HEADING
```

Then replace the existing `_map_role`:

```python
def _map_role(chunk_type: str, markdown: str = "") -> BlockRole:
    if chunk_type == "text":
        return _detect_text_role(markdown)
    return _ROLE_MAP.get(chunk_type, BlockRole.OTHER)
```

- [ ] **Step 4: Run to confirm unit tests pass**

```
uv run --directory backend python -m pytest tests/cdm/test_landing_ai_adapter.py -o "addopts=" -k "detect" -v
```

Expected: all 10 `detect` tests green.

- [ ] **Step 5: Update the call site in `LandingAIAdapter.adapt`**

In `backend/app/cdm/adapters/landing_ai.py`, find line 173:

```python
            role = _map_role(chunk_type)
```

Replace with:

```python
            role = _map_role(chunk_type, chunk.get("markdown") or "")
```

- [ ] **Step 6: Write the adapter integration tests**

Append to `backend/tests/cdm/test_landing_ai_adapter.py`:

```python
# ---------------------------------------------------------------------------
# Heading role integration tests
# ---------------------------------------------------------------------------

def test_h1_chunk_gets_title_role():
    raw = {
        "chunks": [
            {
                "id": "chunk-title",
                "type": "text",
                "markdown": "<a id='chunk-title'></a>\n\n# Main Title\n\nIntro text.",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 0.1}},
            },
        ],
        "markdown": None, "metadata": {}, "splits": [], "grounding": {},
    }
    doc = LandingAIAdapter().adapt(raw, _META)
    assert doc.blocks[0].role == BlockRole.TITLE


def test_h2_chunk_gets_heading_role():
    raw = {
        "chunks": [
            {
                "id": "chunk-h2",
                "type": "text",
                "markdown": "<a id='chunk-h2'></a>\n\n## Section Heading",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 0.1}},
            },
        ],
        "markdown": None, "metadata": {}, "splits": [], "grounding": {},
    }
    doc = LandingAIAdapter().adapt(raw, _META)
    assert doc.blocks[0].role == BlockRole.HEADING


def test_plain_text_chunk_remains_paragraph():
    raw = {
        "chunks": [
            {
                "id": "chunk-para",
                "type": "text",
                "markdown": "<a id='chunk-para'></a>\n\nPlain paragraph text.",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 0.1}},
            },
        ],
        "markdown": None, "metadata": {}, "splits": [], "grounding": {},
    }
    doc = LandingAIAdapter().adapt(raw, _META)
    assert doc.blocks[0].role == BlockRole.PARAGRAPH


def test_mixed_roles_across_chunks():
    raw = {
        "chunks": [
            {
                "id": "c-title",
                "type": "text",
                "markdown": "<a id='c-title'></a>\n\n# Document Title",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 0.05}},
            },
            {
                "id": "c-h2",
                "type": "text",
                "markdown": "<a id='c-h2'></a>\n\n## Chapter One",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.1, "right": 1.0, "bottom": 0.15}},
            },
            {
                "id": "c-h3",
                "type": "text",
                "markdown": "<a id='c-h3'></a>\n\n### 1.1 Background\n\nSome body text.",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.2, "right": 1.0, "bottom": 0.3}},
            },
            {
                "id": "c-para",
                "type": "text",
                "markdown": "No anchor, no heading.",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.3, "right": 1.0, "bottom": 0.4}},
            },
        ],
        "markdown": None, "metadata": {}, "splits": [], "grounding": {},
    }
    doc = LandingAIAdapter().adapt(raw, _META)
    by_id = {b.parser_extras["landing_ai_chunk_id"]: b for b in doc.blocks}
    assert by_id["c-title"].role == BlockRole.TITLE
    assert by_id["c-h2"].role == BlockRole.HEADING
    assert by_id["c-h3"].role == BlockRole.HEADING
    assert by_id["c-para"].role == BlockRole.PARAGRAPH
```

- [ ] **Step 7: Run the full test file to confirm everything passes**

```
uv run --directory backend python -m pytest tests/cdm/test_landing_ai_adapter.py -o "addopts=" -v
```

Expected: all tests green (existing + new).

- [ ] **Step 8: Commit**

```bash
git add backend/app/cdm/adapters/landing_ai.py backend/tests/cdm/test_landing_ai_adapter.py
git commit -m "feat(cdm): detect TITLE/HEADING roles from LandingAI markdown heading markers"
```

---

## Self-Review

**Spec coverage:**
- `BlockRole.TITLE` assigned for `#` → ✓ Task 1 step 3
- `BlockRole.HEADING` assigned for `##`/`###`/deeper → ✓ Task 1 step 3
- `BlockRole.PARAGRAPH` preserved for non-heading text → ✓ existing MINIMAL_RAW fixture unchanged
- All other chunk types (`table`, `figure`, `logo`, `attestation`, `marginalia`, `scan_code`) unaffected → ✓ `_map_role` only calls `_detect_text_role` when `chunk_type == "text"`
- `##NoSpace` treated as paragraph (not a valid ATX heading) → ✓ `_HEADING_RE` requires a space
- Empty/anchor-only markdown → ✓ `_first_content_line` returns `""` which doesn't match `_HEADING_RE`

**Placeholder scan:** None found.

**Type consistency:** `_detect_text_role` returns `BlockRole`, `_map_role` returns `BlockRole`, adapter assigns to `role: BlockRole` — consistent throughout.

**Existing test impact:** `test_block_roles` checks `BlockRole.PARAGRAPH in roles` — still passes because `MINIMAL_RAW`'s text chunk has `"markdown": "Hello world."` (no heading marker). No existing test breaks.
