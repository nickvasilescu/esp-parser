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
# Zoho Mail API Configuration
# =============================================================================

# Zoho Mail account ID (get via: GET https://mail.zoho.com/api/accounts)
ZOHO_MAIL_ACCOUNT_ID: Optional[str] = os.getenv("ZOHO_MAIL_ACCOUNT_ID")

# Mail API uses separate OAuth credentials with ZohoMail scopes
ZOHO_MAIL_CLIENT_ID: Optional[str] = os.getenv("ZOHO_MAIL_CLIENT_ID")
ZOHO_MAIL_CLIENT_SECRET: Optional[str] = os.getenv("ZOHO_MAIL_CLIENT_SECRET")
ZOHO_MAIL_REFRESH_TOKEN: Optional[str] = os.getenv("ZOHO_MAIL_REFRESH_TOKEN")

# Default sender and CC addresses
ZOHO_MAIL_FROM_ADDRESS: str = os.getenv("ZOHO_MAIL_FROM_ADDRESS", "alex@stblstrategies.com")
ZOHO_MAIL_CC_ALWAYS: str = os.getenv("ZOHO_MAIL_CC_ALWAYS", "koell@stblstrategies.com")

# Zoho Mail API base URL
ZOHO_MAIL_API_BASE_URL: str = os.getenv("ZOHO_MAIL_API_BASE_URL", "https://mail.zoho.com/api")


# =============================================================================
# Item Master Defaults
# =============================================================================

# Default item settings for Zoho
# NOTE: Using "sales_and_purchases" to enable both sales AND purchase information
# This allows setting both rate (sell price) and purchase_rate (cost price)
ZOHO_ITEM_DEFAULTS = {
    "item_type": "sales_and_purchases",  # Enable both sales and purchase info
    "product_type": "goods",
    "is_taxable": True,
    "tax_id": os.getenv("ZOHO_DEFAULT_TAX_ID"),
    "unit": "pcs",  # Default unit
    "track_inventory": False,  # Per Koell's requirements
    "purchase_account_name": os.getenv("ZOHO_PURCHASE_ACCOUNT", "Cost of Goods Sold"),  # Account for COGS
}


# =============================================================================
# Quote/Estimate Defaults
# =============================================================================

# Default settings for Zoho Estimates (Quotes)
ZOHO_QUOTE_DEFAULTS = {
    "expiry_days": int(os.getenv("ZOHO_QUOTE_EXPIRY_DAYS", "30")),  # Quote expires in 30 days
    "default_shipping_percent": float(os.getenv("ZOHO_QUOTE_SHIPPING_PERCENT", "0.15")),  # 15% shipping estimate
    "status": "draft",  # Always create as draft (not sent)
}


# =============================================================================
# Custom Field Pattern Matching
# =============================================================================

# Custom field name patterns for fail-safe discovery
# The agent will search Zoho custom fields by label and match against these patterns
# Only fields that match will be populated; others will be skipped
CUSTOM_FIELD_PATTERNS: Dict[str, List[str]] = {
    # === ITEMS CUSTOM FIELDS (match Koell's exact labels) ===

    # Colors
    "color_options": ["color options", "color_options"],
    "color_ordered": ["color ordered", "color_ordered"],
    "imprint_color": ["imprint color", "imprint_color"],

    # Decoration
    "decoration_options": ["decoration options", "decoration_options"],
    "decoration_method": ["decoration method", "decoration_method"],

    # Production
    "lead_time": ["lead time", "lead_time"],
    "setup_info": ["setup info", "setup_info"],

    # Source/Provenance
    "info_source": ["info source", "info_source"],
    "presentation_link": ["presentation link", "presentation_link"],

    # Categories (IMPORTANT: Order matters - more specific patterns first)
    # "Promo Category" text field → detailed ESP category like "Beverages- Wine/champagne/liquor"
    "promo_category": ["promo category"],
    # "Category" dropdown → "Promo", "Print", or "Apparel"
    # NOTE: Plain "category" MUST come AFTER "promo category" check to avoid collision
    "product_category": ["cf_category", "item category", "product category", "category"],

    # Sustainability
    "sustainability_credential": ["sustainability credential", "sustainability_credential"],
    "recycled_content": ["recycled content", "recycled_content"],

    # Other
    "buying_group": ["buying group", "buying_group"],
    "mfg_description": ["mfg description", "mfg_description"],
    "materials": ["materials", "material"],
    "themes": ["themes", "theme"],

    # Dimensions & Weight
    "dimensions": ["dimensions", "product dimensions", "item dimensions"],
    "weight": ["weight", "item weight", "product weight"],

    # Shipping
    "ship_point": ["ship point", "ship_point", "fob", "fob point"],
    "units_per_carton": ["units per carton", "units_per_carton", "carton qty"],
    "carton_weight": ["carton weight", "weight per carton"],
    "packaging": ["packaging", "pack type"],
    "rush_available": ["rush available", "rush"],

    # Vendor Contact
    "vendor_contact": ["vendor contact", "supplier contact"],
    "vendor_email": ["vendor email", "supplier email"],
    "vendor_phone": ["vendor phone", "supplier phone"],
    "vendor_address": ["vendor address", "supplier address"],
    "vendor_account_num": ["vendor account", "our account", "customer number"],
    "vendor_cs_rep": ["cs rep", "customer service rep"],

    # Industry IDs
    "asi_number": ["asi number", "asi"],
    "sage_id": ["sage id", "sage number"],

    # Pricing
    "price_valid_through": ["price valid through", "pricing expires", "valid through"],

    # Variants & Images
    "variants": ["variants", "options", "product options"],
    "product_images": ["product images", "images", "image urls"],

    # === CONTACTS/VENDORS CUSTOM FIELDS ===
    "stbl_account_number": ["stbl account number", "stbl_account_number"],
    "artwork_email": ["artwork"],
    "rush_contact_email": ["rush contact"],
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
