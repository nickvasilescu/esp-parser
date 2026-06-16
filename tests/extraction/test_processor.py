"""Tests for PDF processor module."""

import pytest
from promo_parser.extraction.processor import extract_json_from_response


def test_extract_json_plain():
    """Should extract plain JSON response."""
    response = '{"key": "value"}'
    result = extract_json_from_response(response)
    assert result == {"key": "value"}


def test_extract_json_with_code_block():
    """Should extract JSON from code block."""
    response = """```json
{"key": "value"}
```"""
    result = extract_json_from_response(response)
    assert result == {"key": "value"}


def test_extract_json_with_whitespace():
    """Should handle leading/trailing whitespace."""
    response = '  \n{"key": "value"}\n  '
    result = extract_json_from_response(response)
    assert result == {"key": "value"}


def test_extract_json_invalid():
    """Should raise ValueError for invalid JSON."""
    with pytest.raises(ValueError, match="Failed to parse JSON"):
        extract_json_from_response("not valid json")
