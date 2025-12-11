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
    
    For ESP: Uses CPN (Client Product Number) as the SKU identifier
    For SAGE: Uses vendor_sku/mpn/item_num as the SKU identifier
    
    Args:
        product: Unified product dictionary
        
    Returns:
        Vendor SKU if found, None otherwise
    """
    identifiers = product.get("identifiers", {})
    source = product.get("source", "").lower()
    
    # ESP: Use CPN as the primary SKU identifier
    if source == "esp":
        if identifiers.get("cpn"):
            return identifiers["cpn"]
        # Fallback for ESP if no CPN
        if identifiers.get("vendor_sku"):
            return identifiers["vendor_sku"]
        if identifiers.get("mpn"):
            return identifiers["mpn"]
    
    # SAGE and others: Use vendor_sku/mpn/item_num
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


def get_base_code(product: Dict[str, Any]) -> Optional[str]:
    """
    Get the base code for product identification.
    
    Alias for get_vendor_sku for backward compatibility.
    
    Args:
        product: Unified product dictionary
        
    Returns:
        Base code (CPN for ESP, vendor_sku for SAGE)
    """
    return get_vendor_sku(product)


def extract_all_price_tiers(product: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract all price tiers (sales and purchase) from product.
    
    Args:
        product: Unified product dictionary
        
    Returns:
        Dict with sales_tiers and purchase_tiers lists
    """
    pricing = product.get("pricing", {})
    breaks = pricing.get("breaks", [])
    
    sales_tiers = []
    purchase_tiers = []
    
    for brk in sorted(breaks, key=lambda b: b.get("quantity", 0)):
        qty = brk.get("quantity")
        if qty is None:
            continue
            
        # Sales tier (sell_price)
        sell_price = brk.get("sell_price") or brk.get("catalog_price")
        if sell_price is not None:
            sales_tiers.append({"quantity": qty, "rate": sell_price})
        
        # Purchase tier (net_cost)
        net_cost = brk.get("net_cost")
        if net_cost is not None:
            purchase_tiers.append({"quantity": qty, "rate": net_cost})
    
    return {
        "sales_tiers": sales_tiers,
        "purchase_tiers": purchase_tiers
    }


# =============================================================================
# New Name/SKU Format (identical name and SKU)
# =============================================================================

def sanitize_for_sku(text: str, max_length: int = 50) -> str:
    """
    Sanitize text for use in SKU/name.
    
    Removes special characters, replaces spaces with nothing,
    and truncates to max_length.
    
    Args:
        text: Input text
        max_length: Maximum length
        
    Returns:
        Sanitized string
    """
    import re
    if not text:
        return ""
    # Remove special characters except alphanumeric and hyphen
    cleaned = re.sub(r'[^a-zA-Z0-9\-]', '', text.replace(' ', '').replace('/', '-'))
    # Remove consecutive hyphens
    cleaned = re.sub(r'-+', '-', cleaned)
    # Remove leading/trailing hyphens
    cleaned = cleaned.strip('-')
    return cleaned[:max_length]


def build_item_name_sku(
    client_account_number: str,
    product: Dict[str, Any],
    variation: Optional[Dict[str, str]] = None
) -> str:
    """
    Build SKU in simplified format: <clientAcctId>-<baseCode>
    
    Koell's requirement: keep Item Master SKU minimal (no colors/sizes),
    while names remain the product title.
    
    Args:
        client_account_number: Client's account number
        product: Unified product dictionary
        variation: Unused for SKU (kept for signature compatibility)
        
    Returns:
        SKU string
    """
    client_num = extract_numeric_account(client_account_number)
    base_code = get_vendor_sku(product) or "UNKNOWN"
    return f"{client_num}-{base_code}"


def explode_product_variations(product: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Explode a product into all its variations.
    
    Creates one entry per color, size, or decoration method combination.
    If no variations exist, returns a single empty dict (base product).
    
    Args:
        product: Unified product dictionary
        
    Returns:
        List of variation dictionaries with color, size, decoration keys
    """
    item = product.get("item", {})
    decoration = product.get("decoration", {})
    
    colors = item.get("colors", [])
    # Note: sizes might be in different places depending on source
    sizes = item.get("sizes", [])
    
    # Get decoration methods
    deco_methods = []
    for method in decoration.get("methods", []):
        if isinstance(method, dict):
            deco_methods.append(method.get("name", ""))
        elif isinstance(method, str):
            deco_methods.append(method)
    deco_methods = [m for m in deco_methods if m]  # Filter empty
    
    variations = []
    
    # If we have colors, create one item per color
    if colors:
        for color in colors:
            variation = {"color": color}
            # Add first decoration method if available
            if deco_methods:
                variation["decoration"] = deco_methods[0]
            variations.append(variation)
    # If we have sizes but no colors
    elif sizes:
        for size in sizes:
            variation = {"size": size}
            if deco_methods:
                variation["decoration"] = deco_methods[0]
            variations.append(variation)
    # If we have decoration methods but no colors/sizes
    elif deco_methods:
        for deco in deco_methods:
            variations.append({"decoration": deco})
    # No variations - single base product
    else:
        variations.append({})
    
    return variations


# =============================================================================
# Fee Parsing and Item Creation
# =============================================================================

import re

def parse_additional_charges_text(text: str) -> List[Dict[str, Any]]:
    """
    Parse additional_charges_text field to extract structured fees.
    
    Handles formats like:
    - "Setup: $57.50"
    - "Additional Color Run (+0.35), Additional Color Set Up (+60.00)"
    - "RUSH: 5 Day (20%), 3 Day (30%)"
    - "Imprint: Laser Engraving (+1.30)"
    - "Laser Engraved Personalization up to 2 Lines (per piece) (+1.30)"
    
    Args:
        text: Raw additional_charges_text string
        
    Returns:
        List of fee dictionaries with name, price, fee_type
    """
    if not text:
        return []
    
    fees = []
    
    # Pattern for "Setup: $XX.XX" or "Setup: XX.XX"
    setup_pattern = r'Setup:\s*\$?([\d.]+)'
    setup_match = re.search(setup_pattern, text, re.IGNORECASE)
    if setup_match:
        fees.append({
            "fee_type": "setup",
            "name": "Setup Charge",
            "price": float(setup_match.group(1)),
            "description": f"Setup charge extracted from additional_charges_text"
        })
    
    # Pattern for "(+XX.XX)" or "(+$XX.XX)" charges with preceding name
    # More flexible to handle text like "Name (per piece) (+1.30)"
    addon_pattern = r'([A-Za-z][A-Za-z0-9\s\(\)]+?)\s*\(\+\$?([\d.]+)\)'
    for match in re.finditer(addon_pattern, text):
        name = match.group(1).strip()
        price = float(match.group(2))
        
        # Skip if name is too short or is just "(per piece)" etc
        if len(name) < 3:
            continue
        
        # Determine fee type based on name
        fee_type = "addon"
        name_lower = name.lower()
        if "color" in name_lower:
            fee_type = "additional_color"
        elif "personalization" in name_lower:
            fee_type = "personalization"
        elif "imprint" in name_lower or "engraving" in name_lower or "laser" in name_lower:
            fee_type = "imprint"
        elif "line" in name_lower:
            fee_type = "personalization"
        
        fees.append({
            "fee_type": fee_type,
            "name": name,
            "price": price,
            "description": f"Add-on fee: {name}"
        })
    
    # Pattern for "RUSH: X Day (XX%)" or "X Day (XX%)"
    rush_pattern = r'(\d+)\s*Day\s*\((\d+)%\)'
    for match in re.finditer(rush_pattern, text, re.IGNORECASE):
        days = match.group(1)
        percent = match.group(2)
        fees.append({
            "fee_type": "rush",
            "name": f"Rush {days} Day ({percent}%)",
            "price": None,  # Percentage-based
            "percent": float(percent),
            "description": f"Rush fee: {days} day turnaround at {percent}% upcharge"
        })
    
    # Pattern for tiered pricing "Blank (250:1.55, 500:1.49, ...)"
    # This indicates quantity-based pricing info but not fees
    
    # Pattern for PMS match - "PMS: $XX" or "PMS Match: $XX"
    pms_pattern = r'PMS(?:\s*Match)?:\s*\$?([\d.]+)'
    pms_match = re.search(pms_pattern, text, re.IGNORECASE)
    if pms_match:
        fees.append({
            "fee_type": "pms",
            "name": "PMS Color Match",
            "price": float(pms_match.group(1)),
            "description": "PMS color matching fee"
        })
    
    return fees


def build_fee_items(
    product: Dict[str, Any],
    client_account_number: str,
    discovered_fields: Dict[str, Optional[str]]
) -> List[Dict[str, Any]]:
    """
    Build Zoho item payloads for all fees associated with a product.
    
    Extracts fees from:
    1. product.fees[] (structured fee data)
    2. product.shipping.additional_charges_text (parsed)
    3. product.shipping.supplier_disclaimers (fee-related)
    
    Args:
        product: Unified product dictionary
        client_account_number: Client's Zoho account number
        discovered_fields: Dict of discovered custom field IDs
        
    Returns:
        List of Zoho item payloads for fees
    """
    fee_items = []
    client_num = extract_numeric_account(client_account_number)
    base_code = get_vendor_sku(product) or "UNKNOWN"
    product_name = product.get("item", {}).get("name", "Item")
    
    # 1. Process structured fees from fees[]
    structured_fees = product.get("fees", [])
    for fee in structured_fees:
        fee_type = sanitize_for_sku(fee.get("fee_type", "FEE"), 15)
        fee_name = fee.get("name", "Fee")
        deco_method = fee.get("decoration_method", "")
        
        # Build SKU/name
        sku_parts = [client_num, "FEE", fee_type.upper(), base_code]
        if deco_method:
            sku_parts.append(sanitize_for_sku(deco_method, 15))
        sku = "-".join(sku_parts)
        
        # Build descriptive name
        name = f"{client_num}-FEE-{fee_type.upper()}-{fee_name}"
        if deco_method:
            name += f" ({deco_method})"
        
        payload = {
            "name": sku,  # name = sku
            "sku": sku,
            "description": fee.get("description", fee_name),
            "rate": fee.get("list_price"),
            "purchase_rate": fee.get("net_cost"),
            "purchase_account_name": ZOHO_ITEM_DEFAULTS.get("purchase_account_name", "Cost of Goods Sold"),
            "item_type": ZOHO_ITEM_DEFAULTS["item_type"],
            "product_type": ZOHO_ITEM_DEFAULTS["product_type"],
            "is_taxable": ZOHO_ITEM_DEFAULTS["is_taxable"],
            "unit": "pcs",
            "_fee_type": fee_type,
            "_source_product": product_name
        }
        
        # Clean None values
        payload = {k: v for k, v in payload.items() if v is not None}
        fee_items.append(payload)
    
    # 2. Parse additional_charges_text
    shipping = product.get("shipping", {})
    additional_text = shipping.get("additional_charges_text", "")
    if additional_text:
        parsed_fees = parse_additional_charges_text(additional_text)
        for fee in parsed_fees:
            fee_type = sanitize_for_sku(fee.get("fee_type", "FEE"), 15)
            
            sku_parts = [client_num, "FEE", fee_type.upper(), base_code]
            sku = "-".join(sku_parts)
            
            # Make SKU unique if name has detail
            fee_name_clean = sanitize_for_sku(fee.get("name", ""), 20)
            if fee_name_clean:
                sku = f"{sku}-{fee_name_clean}"
            
            payload = {
                "name": sku,
                "sku": sku,
                "description": fee.get("description", fee.get("name", "")),
                "rate": fee.get("price"),
                "purchase_rate": fee.get("price"),  # Assume same for now
                "purchase_account_name": ZOHO_ITEM_DEFAULTS.get("purchase_account_name", "Cost of Goods Sold"),
                "item_type": ZOHO_ITEM_DEFAULTS["item_type"],
                "product_type": ZOHO_ITEM_DEFAULTS["product_type"],
                "is_taxable": ZOHO_ITEM_DEFAULTS["is_taxable"],
                "unit": "pcs",
                "_fee_type": fee_type,
                "_source_product": product_name,
                "_parsed_from": "additional_charges_text"
            }
            
            payload = {k: v for k, v in payload.items() if v is not None}
            fee_items.append(payload)
    
    # 3. Check supplier_disclaimers for fee-related content
    disclaimers = shipping.get("supplier_disclaimers", [])
    for disclaimer in disclaimers:
        # Look for surcharge mentions
        if "surcharge" in disclaimer.lower() or "fee" in disclaimer.lower():
            # Try to extract percentage
            percent_match = re.search(r'(\d+(?:\.\d+)?)\s*%', disclaimer)
            
            sku = f"{client_num}-FEE-SURCHARGE-{base_code}"
            
            payload = {
                "name": sku,
                "sku": sku,
                "description": disclaimer,
                "rate": None,  # Percentage-based
                "item_type": ZOHO_ITEM_DEFAULTS["item_type"],
                "product_type": ZOHO_ITEM_DEFAULTS["product_type"],
                "is_taxable": False,  # Surcharges typically not taxed
                "unit": "pcs",
                "_fee_type": "surcharge",
                "_source_product": product_name,
                "_parsed_from": "supplier_disclaimers"
            }
            
            if percent_match:
                payload["_percent"] = float(percent_match.group(1))
            
            payload = {k: v for k, v in payload.items() if v is not None}
            fee_items.append(payload)
    
    logger.info(f"Built {len(fee_items)} fee items for product: {product_name}")
    return fee_items


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
    client_account_number: str,
    discovered_fields: Dict[str, Optional[str]],
    variation: Optional[Dict[str, str]] = None,
    category_id: Optional[str] = None,
    inventory_note: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build the complete Zoho Item API payload.
    
    Updated per Koell:
    - SKU: <clientAcctId>-<baseCode> (no variation, no long name)
    - Name: product title (clean, readable)
    - Variations are NOT separate items by default; option lists go in description.
    """
    item = product.get("item", {})
    vendor = product.get("vendor", {})
    
    # Build simplified SKU
    simplified_sku = build_item_name_sku(client_account_number, product, variation)
    
    # Product name (clean title)
    product_name = item.get("name", "Unnamed Item")
    
    # Get pricing
    sell_price, net_cost = extract_base_pricing(product)
    
    # Get MPN
    mpn = get_mpn(product)
    
    # Build description with inventory note and option lists
    base_description = build_item_description(product, inventory_note)
    
    # Append available options (colors/sizes/deco) to description for quote usability
    options_lines = []
    colors = item.get("colors", [])
    if colors:
        options_lines.append(f"Available Colors: {', '.join(colors)}")
    sizes = item.get("sizes", [])
    if sizes:
        options_lines.append(f"Available Sizes: {', '.join(sizes)}")
    deco_methods = []
    for method in product.get("decoration", {}).get("methods", []):
        if isinstance(method, dict):
            name = method.get("name")
        else:
            name = method
        if name:
            deco_methods.append(name)
    deco_methods = list(dict.fromkeys(deco_methods))  # dedupe
    if deco_methods:
        options_lines.append(f"Decoration Methods: {', '.join(deco_methods)}")
    
    if options_lines:
        base_description = "\n".join(options_lines) + "\n\n" + base_description
    
    # Start with required fields
    payload = {
        "name": product_name,
        "sku": simplified_sku,
        "description": base_description,
        
        # Pricing - Sales Information
        "rate": sell_price,           # Selling price (what customer pays)
        
        # Purchase Information - Enabled by item_type="sales_and_purchases"
        "purchase_rate": net_cost,    # Cost price (what we pay to distributor)
        "purchase_account_name": ZOHO_ITEM_DEFAULTS.get("purchase_account_name", "Cost of Goods Sold"),
        
        # Item type settings from defaults
        "item_type": ZOHO_ITEM_DEFAULTS["item_type"],
        "product_type": ZOHO_ITEM_DEFAULTS["product_type"],
        "is_taxable": ZOHO_ITEM_DEFAULTS["is_taxable"],
        "unit": ZOHO_ITEM_DEFAULTS["unit"],
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
    
    # Metadata (optional, not sent)
    payload["_original_name"] = product_name
    
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
    category_map: Optional[Dict[str, str]] = None,
    include_variations: bool = False,
    include_fees: bool = True
) -> List[Dict[str, Any]]:
    """
    Prepare all products from unified output for Zoho upload.
    
    Creates separate items for:
    - Each product variation (color, size, decoration)
    - Each fee associated with the product
    
    Args:
        unified_output: Complete unified output dictionary
        client_account_number: Client's Zoho account number
        discovered_fields: Dict of discovered custom field IDs
        category_map: Optional mapping of category names to Zoho category IDs
        include_variations: Whether to explode variations (default True)
        include_fees: Whether to include fee items (default True)
        
    Returns:
        List of Zoho item payloads ready for upload
    """
    products = unified_output.get("products", [])
    prepared_items = []
    
    for product in products:
        try:
            product_name = product.get("item", {}).get("name", "Unknown")
            
            # Get vendor SKU (for validation)
            vendor_sku = get_vendor_sku(product)
            if not vendor_sku:
                logger.warning(f"Skipping product - no vendor SKU found: {product_name}")
                continue
            
            # Find category if mapping provided
            category_id = None
            if category_map:
                item_categories = product.get("item", {}).get("categories", [])
                for cat in item_categories:
                    if cat in category_map:
                        category_id = category_map[cat]
                        break
            
            # Explode variations or create single item
            if include_variations:
                variations = explode_product_variations(product)
            else:
                variations = [{}]  # Single base item (no variant explosion)
            
            logger.info(f"Product '{product_name}': {len(variations)} variation(s)")
            
            # Create item for each variation
            for variation in variations:
                payload = build_item_payload(
                    product=product,
                    client_account_number=client_account_number,
                    discovered_fields=discovered_fields,
                    variation=variation if variation else None,
                    category_id=category_id
                )
                
                # Attach metadata for tracking
                payload["_source_identifiers"] = product.get("identifiers", {})
                payload["_source"] = product.get("source")
                payload["_is_variation"] = bool(variation)
                
                prepared_items.append(payload)
            
            # Build fee items
            if include_fees:
                fee_items = build_fee_items(
                    product=product,
                    client_account_number=client_account_number,
                    discovered_fields=discovered_fields
                )
                prepared_items.extend(fee_items)
            
        except Exception as e:
            logger.error(f"Error preparing product: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Summary
    product_items = [p for p in prepared_items if not p.get("_fee_type")]
    fee_items = [p for p in prepared_items if p.get("_fee_type")]
    
    logger.info(f"Prepared {len(product_items)} product items + {len(fee_items)} fee items = {len(prepared_items)} total")
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


# =============================================================================
# Quote/Estimate Payload Builders
# =============================================================================

# Default descriptions for fee types when none is provided
FEE_TYPE_DESCRIPTIONS = {
    "setup": "One-time setup charge for production preparation",
    "proof": "Pre-production proof for customer approval before manufacturing",
    "pms": "PMS (Pantone) color match fee for custom color matching",
    "pms_match": "PMS (Pantone) color match fee for custom color matching",
    "additional_color": "Additional color charge per color beyond base decoration",
    "additional_color_run": "Per-piece run charge for additional colors",
    "additional_color_setup": "Setup charge for additional color in decoration",
    "copy_change": "Charge for artwork or copy modifications after initial setup",
    "imprint": "Imprint/decoration charge for logo or design application",
    "personalization": "Personalization charge for individual customization (names, numbers, etc.)",
    "decoration": "Decoration charge for product customization",
    "rush": "Rush/expedited production fee for faster turnaround",
    "handling": "Special handling or packaging charge",
    "artwork": "Artwork creation or modification fee",
    "tape": "Tape/color change charge for multi-color decoration",
    "flash": "Flash charge for specialty ink curing between colors",
    "screen": "Screen charge for screen printing setup",
    "digitizing": "Digitizing fee for converting artwork to embroidery format",
    "embroidery": "Embroidery decoration charge",
    "laser": "Laser engraving decoration charge",
    "deboss": "Debossing decoration charge (pressed-in design)",
    "emboss": "Embossing decoration charge (raised design)",
    "pad_print": "Pad printing decoration charge",
    "screen_print": "Screen printing decoration charge",
    "heat_transfer": "Heat transfer decoration charge",
    "full_color": "Full color/4-color process decoration charge",
    "uv_print": "UV printing decoration charge",
}


def get_fee_description(fee: Dict[str, Any]) -> str:
    """
    Get a meaningful description for a fee.

    Uses the fee's own description if available, otherwise generates
    a default based on fee_type or name.

    Args:
        fee: Fee dictionary with fee_type, name, description fields

    Returns:
        Meaningful description string (never empty)
    """
    # First try the fee's own description
    description = fee.get("description", "")
    if description and description.strip() and description.lower() != "null":
        return description.strip()

    # Try to get default based on fee_type
    fee_type = fee.get("fee_type", "").lower().strip()
    if fee_type and fee_type in FEE_TYPE_DESCRIPTIONS:
        return FEE_TYPE_DESCRIPTIONS[fee_type]

    # Try to infer from fee name
    name = fee.get("name", "").lower()

    # Check for common keywords in name
    keyword_mappings = [
        (["setup"], "setup"),
        (["proof"], "proof"),
        (["pms", "pantone", "color match"], "pms"),
        (["additional color", "extra color"], "additional_color"),
        (["copy change", "artwork change"], "copy_change"),
        (["personalization", "personalize"], "personalization"),
        (["rush", "expedite"], "rush"),
        (["digitiz"], "digitizing"),
        (["embroid"], "embroidery"),
        (["laser", "engrav"], "laser"),
        (["deboss"], "deboss"),
        (["emboss"], "emboss"),
        (["pad print"], "pad_print"),
        (["screen print"], "screen_print"),
        (["heat transfer"], "heat_transfer"),
        (["full color", "4-color", "4 color", "cmyk"], "full_color"),
        (["uv print"], "uv_print"),
        (["tape"], "tape"),
        (["flash"], "flash"),
        (["screen"], "screen"),
        (["imprint"], "imprint"),
    ]

    for keywords, fee_type_key in keyword_mappings:
        if any(kw in name for kw in keywords):
            return FEE_TYPE_DESCRIPTIONS.get(fee_type_key, f"Fee for {fee.get('name', 'service')}")

    # Last resort - generate from name
    original_name = fee.get("name", "")
    if original_name:
        return f"Charge for {original_name.lower()}"

    return "Additional service charge"


def build_estimate_line_item(
    name: str,
    description: str,
    rate: float,
    quantity: int = 1,
    item_id: Optional[str] = None,
    unit: str = "pcs"
) -> Dict[str, Any]:
    """
    Build a single line item for a Zoho estimate.

    Args:
        name: Line item name (displayed on quote)
        description: Line item description
        rate: Unit price
        quantity: Quantity
        item_id: Optional Zoho item_id (links to Item Master)
        unit: Unit of measure

    Returns:
        Line item dictionary for estimate API
    """
    line_item = {
        "name": name,
        "description": description,
        "rate": rate,
        "quantity": quantity,
        "unit": unit
    }

    if item_id:
        line_item["item_id"] = item_id

    return line_item


def build_product_tier_line_items(
    product: Dict[str, Any],
    item_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Build line items for EACH quantity tier of a product.

    Creates multiple line items showing price at each quantity break.
    The sell_price ALWAYS comes from presentation data.

    Args:
        product: Unified product dictionary
        item_id: Optional Zoho item_id from Item Master

    Returns:
        List of line items, one per quantity tier
    """
    item = product.get("item", {})
    pricing = product.get("pricing", {})
    breaks = pricing.get("breaks", [])

    product_name = item.get("name", "Product")
    base_code = get_vendor_sku(product) or "ITEM"

    line_items = []

    # Sort breaks by quantity ascending
    sorted_breaks = sorted(breaks, key=lambda b: b.get("quantity", 0))

    for brk in sorted_breaks:
        qty = brk.get("quantity", 0)
        sell_price = brk.get("sell_price")  # ALWAYS from presentation

        if sell_price is None:
            # Skip tiers without sell_price
            logger.debug(f"Skipping tier qty={qty} - no sell_price")
            continue

        if qty <= 0:
            continue

        line_items.append(build_estimate_line_item(
            name=f"{product_name} ({base_code}) - Qty {qty}+",
            description=f"Unit price at {qty}+ quantity tier",
            rate=sell_price,
            quantity=qty,
            item_id=item_id,
            unit="pcs"
        ))

    logger.info(f"Built {len(line_items)} quantity tier line items for {product_name}")
    return line_items


def build_setup_fee_line_item(
    product: Dict[str, Any],
    item_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Build setup fee line item if exists.

    Checks structured fees[] first, then parses additional_charges_text.

    Args:
        product: Unified product dictionary
        item_id: Optional Zoho item_id for setup fee item

    Returns:
        Setup fee line item or None if no setup fee
    """
    fees = product.get("fees", [])

    # Check structured fees first
    for fee in fees:
        if fee.get("fee_type", "").lower() == "setup":
            rate = fee.get("list_price")
            if rate:
                return build_estimate_line_item(
                    name="Setup Charge",
                    description=get_fee_description(fee),
                    rate=rate,
                    quantity=1,
                    item_id=item_id,
                    unit="ea"
                )

    # Check additional_charges_text for setup
    shipping = product.get("shipping", {})
    additional_text = shipping.get("additional_charges_text", "")
    if additional_text:
        parsed = parse_additional_charges_text(additional_text)
        for fee in parsed:
            if fee.get("fee_type") == "setup" and fee.get("price"):
                return build_estimate_line_item(
                    name="Setup Charge",
                    description=get_fee_description(fee),
                    rate=fee["price"],
                    quantity=1,
                    item_id=item_id,
                    unit="ea"
                )

    return None


def build_decoration_line_items(
    product: Dict[str, Any],
    item_ids: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    """
    Build decoration line items using FAN-OUT approach.

    Creates separate line items for ALL decoration options/methods
    so the user can delete unwanted ones manually.

    Args:
        product: Unified product dictionary
        item_ids: Optional map of fee_type -> item_id

    Returns:
        List of decoration-related line items
    """
    line_items = []
    decoration = product.get("decoration", {})
    fees = product.get("fees", [])

    # 1. Decoration-specific fees (additional color, PMS match, imprint, etc.)
    deco_fee_types = {"decoration", "imprint", "personalization",
                      "additional_color", "pms", "pms_match", "proof",
                      "copy_change", "additional_color_run", "additional_color_setup"}

    for fee in fees:
        fee_type = fee.get("fee_type", "").lower()
        if fee_type in deco_fee_types or "color" in fee_type or "imprint" in fee_type:
            rate = fee.get("list_price") or 0
            deco_method = fee.get("decoration_method", "")
            name = fee.get("name", "Decoration Charge")
            if deco_method and deco_method.lower() not in name.lower():
                name = f"{name} ({deco_method})"

            line_items.append(build_estimate_line_item(
                name=name,
                description=get_fee_description(fee),
                rate=rate,
                quantity=1,
                item_id=item_ids.get(fee_type) if item_ids else None,
                unit="ea"
            ))

    # 2. Parse decoration fees from additional_charges_text
    shipping = product.get("shipping", {})
    additional_text = shipping.get("additional_charges_text", "")
    if additional_text:
        parsed = parse_additional_charges_text(additional_text)
        for fee in parsed:
            fee_type = fee.get("fee_type", "")
            # Skip setup (handled separately) and rush (not decoration)
            if fee_type in ("setup", "rush"):
                continue
            if fee_type in deco_fee_types or fee_type in ("addon", "imprint", "personalization"):
                rate = fee.get("price") or 0
                line_items.append(build_estimate_line_item(
                    name=fee.get("name", "Decoration Fee"),
                    description=get_fee_description(fee),
                    rate=rate,
                    quantity=1,
                    unit="ea"
                ))

    # 3. Fan-out decoration METHODS as options (even if same base price)
    methods = decoration.get("methods", [])
    for method in methods:
        if isinstance(method, dict):
            method_name = method.get("name", "")
            method_notes = method.get("notes", "")
        else:
            method_name = str(method)
            method_notes = ""

        if not method_name:
            continue

        # Check if we already have a fee line for this method
        method_exists = any(
            method_name.lower() in li.get("name", "").lower()
            for li in line_items
        )

        if not method_exists:
            # Add as option line (price TBD or $0 placeholder)
            line_items.append(build_estimate_line_item(
                name=f"Decoration Option: {method_name}",
                description=method_notes or f"{method_name} decoration method - price TBD",
                rate=0.00,  # Price TBD - user fills in
                quantity=1,
                unit="ea"
            ))

    logger.info(f"Built {len(line_items)} decoration line items (fan-out approach)")
    return line_items


def get_explicit_shipping_cost(product: Dict[str, Any]) -> Optional[Tuple[float, str]]:
    """
    Check if a product has an explicit quoted shipping cost.

    Args:
        product: Unified product dictionary

    Returns:
        Tuple of (amount, description) if explicit shipping exists, None otherwise
    """
    fees = product.get("fees", [])

    for fee in fees:
        if fee.get("fee_type", "").lower() in ("shipping", "freight"):
            quoted = fee.get("list_price")
            if quoted:
                product_name = product.get("item", {}).get("name", "Product")
                return quoted, f"Quoted shipping for {product_name}"

    return None


def calculate_shipping_estimate(
    product_subtotal: float,
    product: Dict[str, Any],
    default_percentage: float = 0.15
) -> Tuple[float, str]:
    """
    Calculate shipping cost.

    Uses quoted shipping if available, otherwise estimates at 15%.

    Args:
        product_subtotal: Total product cost (for percentage calculation)
        product: Unified product dictionary
        default_percentage: Default shipping percentage (0.15 = 15%)

    Returns:
        Tuple of (amount, description)
    """
    # Check for explicit quoted shipping
    explicit = get_explicit_shipping_cost(product)
    if explicit:
        return explicit

    # Default to percentage estimate
    estimated = round(product_subtotal * default_percentage, 2)
    return estimated, f"Estimated shipping ({int(default_percentage * 100)}% of product cost)"


def build_shipping_line_item(
    product_subtotal: float,
    product: Dict[str, Any],
    item_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build shipping line item.

    Args:
        product_subtotal: Total product cost for percentage estimate
        product: Unified product dictionary
        item_id: Optional Zoho item_id for shipping item

    Returns:
        Shipping line item dictionary
    """
    shipping = product.get("shipping", {})

    amount, description = calculate_shipping_estimate(product_subtotal, product)

    # Add lead time to description if available
    lead_time = shipping.get("lead_time")
    if lead_time:
        description += f"\nLead Time: {lead_time}"

    return build_estimate_line_item(
        name="Shipping & Handling",
        description=description,
        rate=amount,
        quantity=1,
        item_id=item_id,
        unit="ea"
    )


def build_estimate_payload(
    unified_output: Dict[str, Any],
    customer_id: str,
    item_master_map: Optional[Dict[str, str]] = None,
    expiry_days: int = 30
) -> Dict[str, Any]:
    """
    Build complete Zoho estimate payload from unified output.

    Creates a quote with multiple line items per product:
    - One line per quantity tier (with sell_price from presentation)
    - Setup fee (if exists)
    - Decoration options (fan-out approach)
    - Single consolidated shipping estimate (15% of total) OR explicit quoted shipping

    Shipping Logic:
    - Products with explicit quoted shipping get individual shipping line items
    - All other products are covered by a single "Estimated Shipping" at 15% of total

    Args:
        unified_output: Normalized unified schema data
        customer_id: Zoho customer ID (found via STBL-XXXXX search)
        item_master_map: Optional map of SKUs to Item Master item_ids
        expiry_days: Days until quote expires (default 30)

    Returns:
        Complete estimate payload for Zoho API
    """
    from datetime import datetime, timedelta
    from zoho_config import ZOHO_QUOTE_DEFAULTS

    products = unified_output.get("products", [])
    metadata = unified_output.get("metadata", {})

    if item_master_map is None:
        item_master_map = {}

    all_line_items = []
    total_product_subtotal = 0.0  # For 15% shipping estimate
    explicit_shipping_lines = []  # Products with quoted shipping

    for product in products:
        product_name = product.get("item", {}).get("name", "Unknown Product")
        base_code = get_vendor_sku(product) or "UNKNOWN"

        logger.info(f"Building estimate lines for product: {product_name} ({base_code})")

        # Find item_id from Item Master (if exists)
        # SKU format: <client_num>-<base_code>
        item_id = None
        for sku, iid in item_master_map.items():
            if base_code in sku:
                item_id = iid
                logger.debug(f"Found Item Master link: {sku} -> {iid}")
                break

        # 1. Product line items (one per quantity tier)
        tier_lines = build_product_tier_line_items(product, item_id)
        all_line_items.extend(tier_lines)

        # Calculate subtotal from first tier for shipping estimate
        product_subtotal = 0.0
        if tier_lines:
            first_tier = tier_lines[0]
            product_subtotal = first_tier["rate"] * first_tier["quantity"]

        # 2. Setup fee (if exists)
        setup_line = build_setup_fee_line_item(product)
        if setup_line:
            all_line_items.append(setup_line)

        # 3. Decoration options (fan-out approach)
        deco_lines = build_decoration_line_items(product)
        all_line_items.extend(deco_lines)

        # 4. Check for explicit quoted shipping
        explicit_shipping = get_explicit_shipping_cost(product)
        if explicit_shipping:
            # Product has explicit shipping - add as separate line item
            amount, description = explicit_shipping
            explicit_shipping_lines.append(build_estimate_line_item(
                name=f"Shipping: {product_name[:40]}",
                description=description,
                rate=amount,
                quantity=1,
                unit="ea"
            ))
            logger.info(f"Product '{product_name}' has explicit shipping: ${amount}")
        else:
            # No explicit shipping - add to total for 15% estimate
            total_product_subtotal += product_subtotal

    # Add explicit shipping line items (for products with quoted shipping)
    if explicit_shipping_lines:
        all_line_items.extend(explicit_shipping_lines)
        logger.info(f"Added {len(explicit_shipping_lines)} explicit shipping line items")

    # Add single estimated shipping line item (15% of products without quoted shipping)
    if total_product_subtotal > 0:
        shipping_percent = ZOHO_QUOTE_DEFAULTS.get("default_shipping_percent", 0.15)
        estimated_shipping = round(total_product_subtotal * shipping_percent, 2)
        all_line_items.append(build_estimate_line_item(
            name="Estimated Shipping & Handling",
            description=f"Estimated at {int(shipping_percent * 100)}% of product subtotal (${total_product_subtotal:,.2f})",
            rate=estimated_shipping,
            quantity=1,
            unit="ea"
        ))
        logger.info(f"Added estimated shipping: ${estimated_shipping} ({int(shipping_percent * 100)}% of ${total_product_subtotal:,.2f})")

    # Build dates
    today = datetime.now()
    estimate_date = today.strftime("%Y-%m-%d")
    expiry_date = (today + timedelta(days=expiry_days)).strftime("%Y-%m-%d")

    # Auto-generate notes from presentation metadata
    pres_title = metadata.get("presentation_title", "")
    pres_url = metadata.get("presentation_url", metadata.get("source_url", ""))
    source = metadata.get("source", "")

    notes_parts = []
    if pres_title:
        notes_parts.append(f"Quote based on presentation: {pres_title}")
    if pres_url:
        notes_parts.append(f"Source: {pres_url}")
    if source:
        notes_parts.append(f"Platform: {source.upper()}")

    notes = "\n".join(notes_parts) if notes_parts else "Quote generated from presentation data"

    logger.info(f"Built estimate with {len(all_line_items)} total line items")

    return {
        "customer_id": customer_id,
        "date": estimate_date,
        "expiry_date": expiry_date,
        "line_items": all_line_items,
        "notes": notes,
        "status": "draft"
    }


def validate_estimate_payload(payload: Dict[str, Any]) -> List[str]:
    """
    Validate an estimate payload before creation.

    Args:
        payload: Estimate payload dictionary

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Required fields
    if not payload.get("customer_id"):
        errors.append("Missing required field: customer_id")

    line_items = payload.get("line_items", [])
    if not line_items:
        errors.append("Estimate must have at least one line item")

    # Validate line items
    for i, item in enumerate(line_items):
        if not item.get("name"):
            errors.append(f"Line item {i+1}: missing name")
        if item.get("rate") is None:
            errors.append(f"Line item {i+1}: missing rate")
        if item.get("quantity") is None or item.get("quantity", 0) <= 0:
            errors.append(f"Line item {i+1}: invalid quantity")

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
