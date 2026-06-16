"""Tests for core configuration module."""

import os
import pytest


def test_get_config_summary_returns_string():
    """Config summary should return a formatted string."""
    from promo_parser.core.config import get_config_summary

    summary = get_config_summary()
    assert isinstance(summary, str)
    assert len(summary) > 0


def test_output_dir_default():
    """OUTPUT_DIR should have a default value."""
    from promo_parser.core.config import OUTPUT_DIR

    assert OUTPUT_DIR is not None
    assert isinstance(OUTPUT_DIR, str)


def test_model_id_default():
    """MODEL_ID should default to Claude Opus 4.5."""
    from promo_parser.core.config import MODEL_ID

    assert MODEL_ID is not None
    assert "claude" in MODEL_ID.lower()
