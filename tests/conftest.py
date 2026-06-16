"""Shared test fixtures for promo_parser tests."""

import pytest
from pathlib import Path


@pytest.fixture
def sample_esp_output():
    """Sample ESP pipeline output for testing."""
    return {
        "success": True,
        "metadata": {
            "source": "esp",
            "presentation_url": "https://portal.mypromooffice.com/test",
            "generated_at": "2025-01-01T00:00:00",
            "total_items_in_presentation": 5,
            "total_items_processed": 5,
            "total_errors": 0,
        },
        "products": [
            {
                "vendor": {
                    "name": "Test Vendor",
                    "asi": "12345",
                    "website": "https://testvendor.com",
                },
                "item": {
                    "vendor_sku": "TEST-001",
                    "mpn": "TEST-001",
                    "name": "Test Product",
                    "description_short": "A test product",
                },
                "pricing": {
                    "breaks": [
                        {"min_qty": 100, "catalog_price": 10.00, "net_cost": 6.00}
                    ]
                },
            }
        ],
        "errors": [],
    }


@pytest.fixture
def sample_sage_output():
    """Sample SAGE pipeline output for testing."""
    return {
        "success": True,
        "source_platform": "sage",
        "presentation_url": "https://viewpresentation.com/12345",
        "metadata": {
            "pres_id": 12345,
            "title": "Test SAGE Presentation",
        },
        "products": [
            {
                "identifiers": {
                    "spc": "SPC123",
                    "prod_id": 999,
                },
                "item": {
                    "name": "SAGE Test Product",
                    "description": "A SAGE test product",
                },
                "vendor": {
                    "name": "SAGE Vendor",
                    "sage_id": "SAGE001",
                },
                "pricing": {
                    "breaks": [
                        {"quantity": 50, "sell_price": 15.00, "net_cost": 9.00}
                    ]
                },
            }
        ],
    }


@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"
