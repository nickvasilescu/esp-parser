#!/usr/bin/env python3
"""
Zoho Configuration for Item Master Agent.

This module manages Zoho API configuration, authentication settings,
and custom field pattern matching for the Item Master integration.
"""

import os
import sys
from typing import Optional, Dict, List

# Load environment variables from .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# =============================================================================
# Zoho API Configuration
# =============================================================================

ZOHO_ORG_ID: Optional[str] = os.getenv("ZOHO_ORG_ID")
ZOHO_CLIENT_ID: Optional[str] = os.getenv("ZOHO_CLIENT_ID")
ZOHO_CLIENT_SECRET: Optional[str] = os.getenv("ZOHO_CLIENT_SECRET")
ZOHO_REFRESH_TOKEN: Optional[str] = os.getenv("ZOHO_REFRESH_TOKEN")

# Zoho API base URL (Books/Inventory)
# US: https://www.zohoapis.com/books/v3
# EU: https://www.zohoapis.eu/books/v3
# IN: https://www.zohoapis.in/books/v3
ZOHO_API_BASE_URL: str = os.getenv("ZOHO_API_BASE_URL", "https://www.zohoapis.com/books/v3")

# Zoho OAuth token endpoint
ZOHO_TOKEN_URL: str = os.getenv("ZOHO_TOKEN_URL", "https://accounts.zoho.com/oauth/v2/token")


# =============================================================================
# Item Master Defaults
# =============================================================================

# Default item settings for Zoho
# NOTE: Using "sales" item_type because "inventory" requires a category in this Zoho org
# If categories are configured later, can switch back to "inventory"
ZOHO_ITEM_DEFAULTS = {
    "item_type": "sales",  # "inventory" requires category; "sales" doesn't
    "product_type": "goods",
    "is_taxable": True,
    "tax_id": os.getenv("ZOHO_DEFAULT_TAX_ID"),
    "unit": "pcs",  # Default unit
    "track_inventory": False,  # Per Koell's requirements
}


# =============================================================================
# Custom Field Pattern Matching
# =============================================================================

# Custom field name patterns for fail-safe discovery
# The agent will search Zoho custom fields by label and match against these patterns
# Only fields that match will be populated; others will be skipped
CUSTOM_FIELD_PATTERNS: Dict[str, List[str]] = {
    # Lead time
    "lead_time": ["lead_time", "lead time", "production_time", "production time"],
    
    # Colors
    "colors_available": ["colors_available", "colors available", "available_colors", "available colors"],
    "color_selected": ["color_selected", "selected_color", "chosen_color"],
    "imprint_colors": ["imprint_colors", "imprint colors", "decoration_colors"],
    
    # Packaging & Shipping
    "packaging": ["packaging", "package_info", "package info"],
    "ship_point": ["ship_point", "ship point", "fob_point", "fob point"],
    
    # Pricing Data (raw grids stored as JSON)
    "sell_price_grid": ["sell_price_grid", "sell_prices", "selling_prices"],
    "cost_price_grid": ["cost_price_grid", "cost_prices", "net_costs", "purchase_prices"],
    
    # Vendor/EQP
    "vendor_group": ["vendor_group", "eqp_status", "eqp status", "we_promo", "promo_eqp"],
    
    # Source/Provenance
    "source_platform": ["source_platform", "source platform", "data_source"],
    "presentation_url": ["presentation_url", "presentation url", "pres_url"],
    "presentation_title": ["presentation_title", "presentation title", "pres_title"],
    
    # Identifiers
    "cpn": ["cpn", "customer_product_number"],
    "spc": ["spc", "sage_product_code"],
    "prod_id": ["prod_id", "product_id", "sage_id"],
    
    # Fees (stored as JSON blob)
    "fee_data": ["fee_data", "fees_blob", "additional_fees"],
    
    # Categories (if custom field exists)
    "categories_raw": ["categories_raw", "raw_categories", "category_list"],
    
    # Margin
    "margin_percent": ["margin_percent", "margin_percentage", "profit_margin"],
    
    # Inventory note
    "inventory_note": ["inventory_note", "inventory note", "stock_note", "stock check"],
}


# =============================================================================
# Agent Configuration
# =============================================================================

# Claude model for the Zoho agent
ZOHO_AGENT_MODEL: str = os.getenv("ZOHO_AGENT_MODEL", "claude-opus-4-5-20251101")

# Extended thinking configuration
ZOHO_AGENT_THINKING_BUDGET: int = int(os.getenv("ZOHO_AGENT_THINKING_BUDGET", "10000"))

# Maximum tokens for Claude responses
ZOHO_AGENT_MAX_TOKENS: int = int(os.getenv("ZOHO_AGENT_MAX_TOKENS", "16384"))

# Maximum iterations for agent loop
ZOHO_AGENT_MAX_ITERATIONS: int = int(os.getenv("ZOHO_AGENT_MAX_ITERATIONS", "50"))


# =============================================================================
# Validation
# =============================================================================

def validate_zoho_config() -> None:
    """
    Validate that all required Zoho configuration values are present.
    Raises SystemExit if any required values are missing.
    """
    errors = []
    
    if not ZOHO_ORG_ID:
        errors.append("ZOHO_ORG_ID environment variable is required")
    
    if not ZOHO_CLIENT_ID:
        errors.append("ZOHO_CLIENT_ID environment variable is required")
    
    if not ZOHO_CLIENT_SECRET:
        errors.append("ZOHO_CLIENT_SECRET environment variable is required")
    
    if not ZOHO_REFRESH_TOKEN:
        errors.append("ZOHO_REFRESH_TOKEN environment variable is required")
    
    if errors:
        print("Zoho Configuration Error(s):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        print("\nPlease set the required environment variables and try again.", file=sys.stderr)
        sys.exit(1)


def get_zoho_config_summary() -> str:
    """
    Get a summary of the current Zoho configuration (for logging).
    Sensitive values are masked.
    """
    org_id_masked = f"{ZOHO_ORG_ID[:4]}...{ZOHO_ORG_ID[-4:]}" if ZOHO_ORG_ID and len(ZOHO_ORG_ID) > 8 else "Not set"
    client_id_masked = f"{ZOHO_CLIENT_ID[:4]}...{ZOHO_CLIENT_ID[-4:]}" if ZOHO_CLIENT_ID and len(ZOHO_CLIENT_ID) > 8 else "Not set"
    
    return f"""
Zoho Item Master Agent Configuration:
  API:
    - Org ID: {org_id_masked}
    - Client ID: {client_id_masked}
    - API Base URL: {ZOHO_API_BASE_URL}
  
  Item Defaults:
    - Item Type: {ZOHO_ITEM_DEFAULTS['item_type']}
    - Product Type: {ZOHO_ITEM_DEFAULTS['product_type']}
    - Taxable: {ZOHO_ITEM_DEFAULTS['is_taxable']}
    - Track Inventory: {ZOHO_ITEM_DEFAULTS['track_inventory']}
    - Default Unit: {ZOHO_ITEM_DEFAULTS['unit']}
  
  Agent:
    - Model: {ZOHO_AGENT_MODEL}
    - Thinking Budget: {ZOHO_AGENT_THINKING_BUDGET}
    - Max Tokens: {ZOHO_AGENT_MAX_TOKENS}
    - Max Iterations: {ZOHO_AGENT_MAX_ITERATIONS}
  
  Custom Field Patterns: {len(CUSTOM_FIELD_PATTERNS)} patterns configured
"""


if __name__ == "__main__":
    print("Validating Zoho configuration...")
    validate_zoho_config()
    print("Zoho configuration is valid!")
    print(get_zoho_config_summary())
