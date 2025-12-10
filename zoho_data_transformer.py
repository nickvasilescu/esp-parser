#!/usr/bin/env python3
"""
Zoho Data Transformer for Item Master.

This module transforms unified ESP/SAGE data into Zoho Item Master format,
handling SKU construction, pricing extraction, and custom field mapping.

Key Functions:
- build_zoho_sku: Construct unique SKU from client account + vendor SKU
- extract_base_pricing: Get default sell/cost from first price break
- map_custom_fields: Pattern-match unified data to discovered custom fields
- build_item_payload: Create complete Zoho Item API payload
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from zoho_config import ZOHO_ITEM_DEFAULTS, CUSTOM_FIELD_PATTERNS

logger = logging.getLogger(__name__)


# =============================================================================
# SKU/MPN Construction
# =============================================================================

def extract_numeric_account(account_string: str) -> str:
    """
    Extract the numeric account number from a Zoho contact_number.
    
    Zoho contact_number may have a prefix like "STBL-10041".
    Per Koell's requirements, SKU should use just the numeric account: "10041".
    
    Args:
        account_string: Full account string from Zoho (e.g., "STBL-10041")
        
    Returns:
        Numeric account number (e.g., "10041")
    """
    if not account_string:
        return "UNKNOWN"
    
    account_string = str(account_string).strip()
    
    # If it contains a hyphen, try to extract the numeric part
    if "-" in account_string:
        parts = account_string.split("-")
        # Look for the numeric part (usually after alphabetic prefix)
        for part in parts:
            if part.isdigit():
                return part
        # If no pure numeric part, return the last part
        return parts[-1]
    
    # If no hyphen, return as-is
    return account_string


def build_zoho_sku(client_account_number: str, vendor_sku: str) -> str:
    """
    Build the Zoho SKU in format [ClientAccountNumber]-[VendorSKU].
    
    Per Koell's requirements:
    - SKU = ClientAccountNumber + "-" + ItemNumber
    - Example: "10041-75610" (not "STBL-10041-75610")
    
    Args:
        client_account_number: Client's account number from Zoho Contacts
        vendor_sku: Vendor's SKU/item number
        
    Returns:
        Formatted SKU string
    """
    # Extract numeric account number (strips prefix like "STBL-")
    client_num = extract_numeric_account(client_account_number)
    v_sku = str(vendor_sku).strip() if vendor_sku else "UNKNOWN"
    
    return f"{client_num}-{v_sku}"


def get_vendor_sku(product: Dict[str, Any]) -> Optional[str]:
    """
    Extract vendor SKU from unified product data.
    
    Checks multiple possible locations in the unified schema.
    
    Args:
        product: Unified product dictionary
        
    Returns:
        Vendor SKU if found, None otherwise
    """
    # Check identifiers first (preferred location)
    identifiers = product.get("identifiers", {})
    if identifiers.get("vendor_sku"):
        return identifiers["vendor_sku"]
    if identifiers.get("mpn"):
        return identifiers["mpn"]
    if identifiers.get("item_num"):
        return identifiers["item_num"]
    if identifiers.get("cpn"):
        return identifiers["cpn"]
    
    # Fallback to item data
    item = product.get("item", {})
    if item.get("vendor_sku"):
        return item["vendor_sku"]
    if item.get("mpn"):
        return item["mpn"]
    
    return None


def get_mpn(product: Dict[str, Any]) -> Optional[str]:
    """
    Get the MPN (Manufacturer Part Number) for Zoho.
    
    This is what appears on Purchase Orders.
    
    Args:
        product: Unified product dictionary
        
    Returns:
        MPN value (typically same as vendor_sku)
    """
    identifiers = product.get("identifiers", {})
    
    # MPN preference order
    if identifiers.get("mpn"):
        return identifiers["mpn"]
    if identifiers.get("vendor_sku"):
        return identifiers["vendor_sku"]
    if identifiers.get("item_num"):
        return identifiers["item_num"]
    
    return get_vendor_sku(product)


# =============================================================================
# Pricing Extraction
# =============================================================================

def extract_base_pricing(product: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract base tier pricing (sell price and net cost) from unified product.
    
    Uses the first price break as the default/base pricing.
    Item Master stores these as representative values; full grids
    go into custom fields for Quote/Calculator use.
    
    Args:
        product: Unified product dictionary
        
    Returns:
        Tuple of (sell_price, net_cost) - either may be None
    """
    pricing = product.get("pricing", {})
    breaks = pricing.get("breaks", [])
    
    if not breaks:
        return None, None
    
    # Sort by quantity to ensure we get the base tier
    sorted_breaks = sorted(breaks, key=lambda b: b.get("quantity", 0))
    
    if sorted_breaks:
        first_break = sorted_breaks[0]
        sell_price = first_break.get("sell_price")
        net_cost = first_break.get("net_cost")
        
        # Fallback: if no sell_price, use catalog_price
        if sell_price is None:
            sell_price = first_break.get("catalog_price")
        
        return sell_price, net_cost
    
    return None, None


def format_price_grid(breaks: List[Dict[str, Any]], price_field: str = "sell_price") -> str:
    """
    Format price breaks as a JSON string for custom field storage.
    
    Args:
        breaks: List of price break dictionaries
        price_field: Which price field to extract (sell_price, net_cost, catalog_price)
        
    Returns:
        JSON string representation of price grid
    """
    grid = []
    for brk in breaks:
        qty = brk.get("quantity")
        price = brk.get(price_field)
        if qty is not None and price is not None:
            grid.append({"qty": qty, "price": price})
    
    return json.dumps(grid) if grid else ""


# =============================================================================
# Custom Field Mapping
# =============================================================================

def map_custom_fields(
    product: Dict[str, Any],
    discovered_fields: Dict[str, Optional[str]],
    client_info: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Map unified product data to Zoho custom fields.
    
    This is the "fail-safe" mechanism - only populates fields
    that were discovered to exist in Zoho.
    
    Args:
        product: Unified product dictionary
        discovered_fields: Dict mapping field names to custom field IDs
                          (from ZohoClient.discover_custom_fields)
        client_info: Optional client context for additional fields
        
    Returns:
        List of custom field objects for Zoho API
    """
    custom_fields = []
    
    identifiers = product.get("identifiers", {})
    item = product.get("item", {})
    vendor = product.get("vendor", {})
    pricing = product.get("pricing", {})
    shipping = product.get("shipping", {})
    notes = product.get("notes", {})
    decoration = product.get("decoration", {})
    
    # Helper to add field if discovered
    def add_field(field_name: str, value: Any):
        field_id = discovered_fields.get(field_name)
        if field_id and value is not None:
            # Convert complex types to string
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            custom_fields.append({
                "customfield_id": field_id,
                "value": str(value) if value else ""
            })
            logger.debug(f"Mapped custom field '{field_name}' = {str(value)[:50]}...")
    
    # Lead time
    lead_time = shipping.get("lead_time") or notes.get("lead_time")
    add_field("lead_time", lead_time)
    
    # Colors
    colors = item.get("colors", [])
    if colors:
        add_field("colors_available", ", ".join(colors) if isinstance(colors, list) else colors)
    add_field("imprint_colors", decoration.get("imprint_colors_description"))
    
    # Packaging
    add_field("packaging", shipping.get("packaging") or notes.get("packaging"))
    
    # Ship point
    ship_point = shipping.get("ship_point")
    if not ship_point and shipping.get("fob_points"):
        fob = shipping["fob_points"][0]
        ship_point = fob.get("postal_code") or fob.get("city")
    add_field("ship_point", ship_point)
    
    # Price grids (raw data for Quote/Calculator)
    breaks = pricing.get("breaks", [])
    if breaks:
        sell_grid = format_price_grid(breaks, "sell_price")
        cost_grid = format_price_grid(breaks, "net_cost")
        add_field("sell_price_grid", sell_grid)
        add_field("cost_price_grid", cost_grid)
    
    # Source/Provenance
    add_field("source_platform", product.get("source"))
    
    # Identifiers
    add_field("cpn", identifiers.get("cpn"))
    add_field("spc", identifiers.get("spc"))
    add_field("prod_id", identifiers.get("prod_id"))
    
    # Fees (as JSON blob)
    fees = product.get("fees", [])
    if fees:
        add_field("fee_data", fees)
    
    # Categories (raw)
    categories = item.get("categories", [])
    if categories:
        add_field("categories_raw", ", ".join(categories) if isinstance(categories, list) else categories)
    
    # Margin from first break
    if breaks:
        first_break = sorted(breaks, key=lambda b: b.get("quantity", 0))[0] if breaks else {}
        add_field("margin_percent", first_break.get("margin_percent"))
    
    return custom_fields


# =============================================================================
# Item Payload Builder
# =============================================================================

def build_item_description(product: Dict[str, Any], inventory_note: Optional[str] = None) -> str:
    """
    Build the item description including inventory note.
    
    Args:
        product: Unified product dictionary
        inventory_note: Optional inventory check note to append
        
    Returns:
        Formatted description string
    """
    item = product.get("item", {})
    
    # Primary description
    description = item.get("description", "")
    if not description:
        description = item.get("description_short", "")
    
    # Append inventory note if provided
    if inventory_note:
        description = f"{description}\n\n{inventory_note}"
    
    return description.strip()


def build_item_payload(
    product: Dict[str, Any],
    zoho_sku: str,
    client_account_number: str,
    discovered_fields: Dict[str, Optional[str]],
    category_id: Optional[str] = None,
    inventory_note: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build the complete Zoho Item API payload.
    
    Args:
        product: Unified product dictionary
        zoho_sku: Pre-built Zoho SKU ([ClientAcct]-[VendorSKU])
        client_account_number: Client's account number (for reference)
        discovered_fields: Dict of discovered custom field IDs
        category_id: Optional Zoho category ID
        inventory_note: Optional inventory check note
        
    Returns:
        Complete item payload dictionary for Zoho API
    """
    item = product.get("item", {})
    vendor = product.get("vendor", {})
    
    # Get pricing
    sell_price, net_cost = extract_base_pricing(product)
    
    # Get MPN
    mpn = get_mpn(product)
    
    # Build description with inventory note
    description = build_item_description(product, inventory_note)
    
    # Start with required fields
    payload = {
        "name": item.get("name", "Unnamed Item"),
        "sku": zoho_sku,
        "description": description,
        
        # Pricing - Sales Information
        "rate": sell_price,           # Selling price (what customer pays)
        
        # Purchase Information - Enabled by item_type="sales_and_purchases"
        "purchase_rate": net_cost,    # Cost price (what we pay to distributor)
        "purchase_account_name": ZOHO_ITEM_DEFAULTS.get("purchase_account_name", "Cost of Goods Sold"),  # Purchase account
        
        # Item type settings from defaults
        "item_type": ZOHO_ITEM_DEFAULTS["item_type"],
        "product_type": ZOHO_ITEM_DEFAULTS["product_type"],
        "is_taxable": ZOHO_ITEM_DEFAULTS["is_taxable"],
        "unit": ZOHO_ITEM_DEFAULTS["unit"],
        
        # NOTE: Omitting track_inventory - when explicitly set to False,
        # Zoho requires a category. By omitting it, Zoho uses its default.
    }
    
    # Add MPN as part_number (Zoho API field name)
    if mpn:
        payload["part_number"] = mpn
    
    # Add category if provided
    if category_id:
        payload["category_id"] = category_id
    
    # Add default tax ID if configured
    if ZOHO_ITEM_DEFAULTS.get("tax_id"):
        payload["tax_id"] = ZOHO_ITEM_DEFAULTS["tax_id"]
    
    # Add manufacturer/brand from vendor
    if vendor.get("name"):
        payload["manufacturer"] = vendor["name"]
    if vendor.get("line_name"):
        payload["brand"] = vendor["line_name"]
    
    # Map custom fields
    custom_fields = map_custom_fields(product, discovered_fields)
    if custom_fields:
        payload["custom_fields"] = custom_fields
    
    # Clean up None values
    payload = {k: v for k, v in payload.items() if v is not None}
    
    return payload


# =============================================================================
# Batch Processing Helpers
# =============================================================================

def prepare_products_for_zoho(
    unified_output: Dict[str, Any],
    client_account_number: str,
    discovered_fields: Dict[str, Optional[str]],
    category_map: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    """
    Prepare all products from unified output for Zoho upload.
    
    Args:
        unified_output: Complete unified output dictionary
        client_account_number: Client's Zoho account number
        discovered_fields: Dict of discovered custom field IDs
        category_map: Optional mapping of category names to Zoho category IDs
        
    Returns:
        List of Zoho item payloads ready for upload
    """
    products = unified_output.get("products", [])
    prepared_items = []
    
    for product in products:
        try:
            # Get vendor SKU
            vendor_sku = get_vendor_sku(product)
            if not vendor_sku:
                logger.warning(f"Skipping product - no vendor SKU found: {product.get('item', {}).get('name', 'Unknown')}")
                continue
            
            # Build Zoho SKU
            zoho_sku = build_zoho_sku(client_account_number, vendor_sku)
            
            # Find category if mapping provided
            category_id = None
            if category_map:
                item_categories = product.get("item", {}).get("categories", [])
                for cat in item_categories:
                    if cat in category_map:
                        category_id = category_map[cat]
                        break
            
            # Build payload
            payload = build_item_payload(
                product=product,
                zoho_sku=zoho_sku,
                client_account_number=client_account_number,
                discovered_fields=discovered_fields,
                category_id=category_id
            )
            
            # Attach metadata for tracking
            payload["_source_identifiers"] = product.get("identifiers", {})
            payload["_source"] = product.get("source")
            
            prepared_items.append(payload)
            
        except Exception as e:
            logger.error(f"Error preparing product: {e}")
            continue
    
    logger.info(f"Prepared {len(prepared_items)} items for Zoho upload")
    return prepared_items


# =============================================================================
# Validation Helpers
# =============================================================================

def validate_item_payload(payload: Dict[str, Any]) -> List[str]:
    """
    Validate an item payload before upload.
    
    Args:
        payload: Item payload dictionary
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Required fields
    if not payload.get("name"):
        errors.append("Missing required field: name")
    if not payload.get("sku"):
        errors.append("Missing required field: sku")
    
    # SKU format validation
    sku = payload.get("sku", "")
    if "-" not in sku:
        errors.append(f"SKU format invalid (expected [ClientAcct]-[VendorSKU]): {sku}")
    
    # Price validation (warn, don't fail)
    if payload.get("rate") is None:
        logger.warning(f"Item {sku} has no sell price (rate)")
    if payload.get("purchase_rate") is None:
        logger.warning(f"Item {sku} has no cost price (purchase_rate)")
    
    return errors


if __name__ == "__main__":
    # Test with sample data
    import sys
    
    logging.basicConfig(level=logging.DEBUG)
    
    # Sample unified product
    sample_product = {
        "source": "sage",
        "identifiers": {
            "vendor_sku": "ABC123",
            "mpn": "ABC123",
            "cpn": "CPN-001"
        },
        "item": {
            "name": "Test Promotional Mug",
            "description": "A high-quality ceramic mug for promotional use.",
            "categories": ["Drinkware", "Mugs"],
            "colors": ["Red", "Blue", "White"]
        },
        "vendor": {
            "name": "Acme Promotions",
            "website": "https://acme-promos.com"
        },
        "pricing": {
            "breaks": [
                {"quantity": 48, "sell_price": 5.99, "net_cost": 3.50, "margin_percent": 41.57},
                {"quantity": 100, "sell_price": 4.99, "net_cost": 2.80, "margin_percent": 43.89},
                {"quantity": 250, "sell_price": 3.99, "net_cost": 2.20, "margin_percent": 44.86}
            ]
        },
        "shipping": {
            "lead_time": "5-7 business days",
            "packaging": "Bulk"
        },
        "fees": [
            {"fee_type": "setup", "name": "Setup Fee", "list_price": 50.00}
        ]
    }
    
    # Test SKU building
    zoho_sku = build_zoho_sku("ACCT001", "ABC123")
    print(f"Zoho SKU: {zoho_sku}")
    
    # Test pricing extraction
    sell, cost = extract_base_pricing(sample_product)
    print(f"Base pricing: sell=${sell}, cost=${cost}")
    
    # Test MPN extraction
    mpn = get_mpn(sample_product)
    print(f"MPN: {mpn}")
    
    # Test payload building (with mock discovered fields)
    mock_discovered = {
        "lead_time": "cf_lead_time_123",
        "colors_available": "cf_colors_456",
        "packaging": None,  # Not discovered
        "fee_data": "cf_fees_789"
    }
    
    payload = build_item_payload(
        product=sample_product,
        zoho_sku=zoho_sku,
        client_account_number="ACCT001",
        discovered_fields=mock_discovered
    )
    
    print("\nGenerated Zoho Payload:")
    print(json.dumps(payload, indent=2))
    
    # Validate
    errors = validate_item_payload(payload)
    if errors:
        print("\nValidation errors:")
        for err in errors:
            print(f"  - {err}")
    else:
        print("\nPayload is valid!")
