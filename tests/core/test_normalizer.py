"""Tests for output normalizer."""

import pytest
from promo_parser.core.normalizer import normalize_output


def test_normalize_esp_output(sample_esp_output):
    """ESP output should normalize to unified schema."""
    result = normalize_output(sample_esp_output, source="esp")

    assert "metadata" in result
    assert result["metadata"]["source"] == "esp"
    assert "products" in result
    assert "client" in result
    assert "presenter" in result


def test_normalize_sage_output(sample_sage_output):
    """SAGE output should normalize to unified schema."""
    result = normalize_output(sample_sage_output, source="sage")

    assert "metadata" in result
    assert result["metadata"]["source"] == "sage"
    assert "products" in result


def test_normalize_invalid_source():
    """Should raise ValueError for unknown source."""
    with pytest.raises(ValueError, match="Unknown source"):
        normalize_output({}, source="unknown")


def test_normalize_preserves_product_data(sample_esp_output):
    """Normalized output should preserve key product data."""
    result = normalize_output(sample_esp_output, source="esp")

    assert len(result["products"]) == 1
    product = result["products"][0]
    assert product["source"] == "esp"
