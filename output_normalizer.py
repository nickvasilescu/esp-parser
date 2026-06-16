"""
Output Normalizer

Transforms ESP and SAGE JSON outputs into the unified schema format
for consistent downstream processing by Zoho and Calculator workflows.

Usage:
    from output_normalizer import normalize_output
    
    # Normalize ESP output
    unified = normalize_output(esp_json_data, source="esp")
    
    # Normalize SAGE output  
    unified = normalize_output(sage_json_data, source="sage")
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from unified_schema import (
    UnifiedOutput, UnifiedMetadata, UnifiedClient, UnifiedPresenter,
    UnifiedProduct, UnifiedIdentifiers, UnifiedItem, UnifiedVendor,
    UnifiedAddress, UnifiedPricing, UnifiedPriceBreak, UnifiedFee,
    UnifiedDecoration, UnifiedDecorationMethod, UnifiedDecorationLocation,
    UnifiedImprintArea, UnifiedVariant, UnifiedShipping, UnifiedFOBPoint,
    UnifiedNotes, UnifiedDimensions, dataclass_to_dict
)

logger = logging.getLogger(__name__)


# ============================================================================
# MAIN NORMALIZER
# ============================================================================

def normalize_output(data: Dict[str, Any], source: str) -> Dict[str, Any]:
    """
    Main entry point: Normalize ESP or SAGE output to unified format.
    
    Args:
        data: The raw JSON data from ESP or SAGE pipeline
        source: Either "esp" or "sage"
        
    Returns:
        Dict in unified schema format
    """
    if source.lower() == "esp":
        unified = _normalize_esp(data)
    elif source.lower() == "sage":
        unified = _normalize_sage(data)
    else:
        raise ValueError(f"Unknown source: {source}. Must be 'esp' or 'sage'")
    
    return dataclass_to_dict(unified)


# ============================================================================
# ESP NORMALIZER
# ============================================================================

def _normalize_esp(data: Dict[str, Any]) -> UnifiedOutput:
    """Transform ESP output to unified format"""
    
    metadata = data.get("metadata", {})
    
    # Build unified metadata
    unified_metadata = UnifiedMetadata(
        generated_at=metadata.get("generated_at", datetime.now().isoformat()),
        source="esp",
        presentation_url=metadata.get("presentation_url", ""),
        presentation_title=metadata.get("presentation_title"),
        presentation_date=None,  # ESP doesn't have this
        pres_id=None,  # Extract from URL if needed
        total_items=metadata.get("total_items_in_presentation", 0),
        items_processed=metadata.get("total_items_processed", 0),
        errors=metadata.get("total_errors", 0),
        pricing_sources={
            "sell_price": "From ESP Presentation - client-facing price",
            "net_cost": "From ESP Distributor Report - authoritative cost",
            "catalog_price": "MSRP/List price from catalog"
        }
    )
    
    # Build client
    client_data = metadata.get("client", {})
    unified_client = UnifiedClient(
        name=client_data.get("name"),
        company=client_data.get("company")
    )
    
    # Build presenter
    presenter_data = metadata.get("presenter", {})
    unified_presenter = UnifiedPresenter(
        name=presenter_data.get("name"),
        company=presenter_data.get("company")
    )
    
    # Build products
    unified_products = []
    for product in data.get("products", []):
        unified_products.append(_normalize_esp_product(product))
    
    # Build errors
    errors = data.get("errors", [])
    
    return UnifiedOutput(
        success=len(errors) == 0,
        metadata=unified_metadata,
        client=unified_client,
        presenter=unified_presenter,
        products=unified_products,
        errors=errors
    )


def _normalize_esp_product(product: Dict[str, Any]) -> UnifiedProduct:
    """Transform single ESP product to unified format"""
    
    item_data = product.get("item", {})
    vendor_data = product.get("vendor", {})
    pricing_data = product.get("pricing", {})
    decoration_data = product.get("decoration", {})
    
    # Identifiers
    identifiers = UnifiedIdentifiers(
        mpn=item_data.get("mpn"),
        vendor_sku=item_data.get("vendor_sku"),
        cpn=item_data.get("cpn")
    )
    
    # Item
    dimensions_raw = item_data.get("dimensions_raw")
    dimensions_obj = item_data.get("dimensions", {})
    
    item = UnifiedItem(
        name=item_data.get("name", ""),
        description=item_data.get("description_long") or item_data.get("description_short", ""),
        description_short=item_data.get("description_short"),
        categories=item_data.get("categories", []),
        themes=item_data.get("themes", []),
        materials=item_data.get("materials", []),
        colors=item_data.get("colors", []),
        primary_color=item_data.get("primary_color"),
        dimensions=UnifiedDimensions(
            length=dimensions_obj.get("length") if dimensions_obj else None,
            width=dimensions_obj.get("width") if dimensions_obj else None,
            height=dimensions_obj.get("height") if dimensions_obj else None,
            unit=dimensions_obj.get("unit") if dimensions_obj else None,
            raw=dimensions_raw
        ) if dimensions_obj or dimensions_raw else None,
        weight_value=item_data.get("weight_value"),
        weight_unit=item_data.get("weight_unit"),
        item_assembled=item_data.get("item_assembled")
    )
    
    # Vendor
    vendor_address = vendor_data.get("address", {})
    vendor = UnifiedVendor(
        name=vendor_data.get("name", ""),
        website=vendor_data.get("website"),
        asi=vendor_data.get("asi"),
        contact_name=vendor_data.get("contact_name"),
        email=vendor_data.get("emails", [None])[0] if vendor_data.get("emails") else None,
        phone=vendor_data.get("phones", [None])[0] if vendor_data.get("phones") else None,
        address=UnifiedAddress(
            line1=vendor_address.get("line1"),
            line2=vendor_address.get("line2"),
            city=vendor_address.get("city"),
            state=vendor_address.get("state"),
            postal_code=vendor_address.get("postal_code"),
            country=vendor_address.get("country")
        ) if vendor_address else None,
        line_name=vendor_data.get("line_name"),
        trade_name=vendor_data.get("trade_name"),
        hours=vendor_data.get("hours")
    )
    
    # Pricing
    price_breaks = []
    for brk in pricing_data.get("breaks", []):
        # ESP uses min_qty, normalize to quantity
        quantity = brk.get("min_qty") or brk.get("quantity")
        sell_price = brk.get("sell_price") or brk.get("catalog_price")
        net_cost = brk.get("net_cost")
        
        margin = None
        margin_percent = None
        if sell_price and net_cost:
            margin = round(sell_price - net_cost, 2)
            margin_percent = round((margin / sell_price) * 100, 2) if sell_price > 0 else None
        
        price_breaks.append(UnifiedPriceBreak(
            quantity=quantity,
            sell_price=sell_price,
            net_cost=net_cost,
            catalog_price=brk.get("catalog_price"),
            margin=margin,
            margin_percent=margin_percent,
            notes=brk.get("notes")
        ))
    
    # Get price_includes - check pricing first, then presentation_sell_data for ESP
    price_includes = pricing_data.get("price_includes")
    if not price_includes:
        pres_data = product.get("presentation_sell_data", {})
        price_includes = pres_data.get("price_includes")

    pricing = UnifiedPricing(
        breaks=price_breaks,
        price_code=pricing_data.get("price_code"),
        currency=pricing_data.get("currency", "USD"),
        valid_through=pricing_data.get("valid_through"),
        price_includes=price_includes,  # e.g., "One color fill"
        notes=pricing_data.get("notes")
    )
    
    # Fees
    fees = []
    for fee in product.get("fees", []):
        fees.append(UnifiedFee(
            fee_type=fee.get("fee_type", "other"),
            name=fee.get("name", ""),
            description=fee.get("description"),
            list_price=fee.get("list_price"),
            net_cost=fee.get("net_cost"),
            price_code=fee.get("price_code"),
            charge_basis=fee.get("charge_basis"),
            min_qty=fee.get("min_qty"),
            decoration_method=fee.get("decoration_method"),
            notes=fee.get("notes")
        ))
    
    # Decoration
    methods = []
    for method in decoration_data.get("methods", []):
        methods.append(UnifiedDecorationMethod(
            name=method.get("name", ""),
            full_color=method.get("full_color", False),
            max_colors=method.get("max_colors"),
            notes=method.get("notes")
        ))
    
    locations = []
    for loc in decoration_data.get("locations", []):
        imprint_areas = []
        for area in loc.get("imprint_areas", []):
            imprint_areas.append(UnifiedImprintArea(
                width=area.get("width"),
                height=area.get("height"),
                unit=area.get("unit"),
                raw=area.get("raw")
            ))
        locations.append(UnifiedDecorationLocation(
            name=loc.get("name", ""),
            component=loc.get("component"),
            methods_allowed=loc.get("methods_allowed", []),
            imprint_areas=imprint_areas
        ))
    
    multi_color = decoration_data.get("multi_color_options", {})

    # Build imprint_info from ESP-specific fields (imprint_sizes, imprint_locations)
    imprint_info_parts = []
    if product.get("imprint_sizes"):
        imprint_info_parts.append(f"Size: {product.get('imprint_sizes')}")
    if product.get("imprint_locations"):
        imprint_info_parts.append(f"Location: {product.get('imprint_locations')}")

    decoration = UnifiedDecoration(
        methods=methods,
        locations=locations,
        sold_unimprinted=decoration_data.get("sold_unimprinted"),
        personalization_available=decoration_data.get("personalization_available"),
        full_color_process_available=decoration_data.get("full_color_process_available"),
        imprint_info="\n".join(imprint_info_parts) if imprint_info_parts else None,
        imprint_colors_description=decoration_data.get("imprint_colors_description"),
        multi_color_description=multi_color.get("description") if multi_color else None
    )
    
    # Variants
    variants = []
    for var in product.get("variants", []):
        variants.append(UnifiedVariant(
            attribute=var.get("attribute", ""),
            label=var.get("label", ""),
            component=var.get("component"),
            options=var.get("options", []),
            notes=var.get("notes")
        ))
    
    # Shipping
    fob_points = []
    for fob in vendor_data.get("fob_points", []):
        fob_points.append(UnifiedFOBPoint(
            city=fob.get("city"),
            state=fob.get("state"),
            postal_code=fob.get("postal_code"),
            country=fob.get("country")
        ))
    
    raw_notes = product.get("raw_notes", {})
    shipping = UnifiedShipping(
        fob_points=fob_points,
        lead_time=raw_notes.get("lead_time"),
        packaging=raw_notes.get("packaging")
    )
    
    # Notes
    notes = UnifiedNotes(
        packaging=raw_notes.get("packaging"),
        lead_time=raw_notes.get("lead_time"),
        supplier_disclaimers=raw_notes.get("supplier_disclaimers", []),
        other=raw_notes.get("other")
    )
    
    # Flags
    flags = product.get("flags", {})
    
    return UnifiedProduct(
        source="esp",
        identifiers=identifiers,
        item=item,
        vendor=vendor,
        pricing=pricing,
        fees=fees,
        decoration=decoration,
        variants=variants,
        shipping=shipping,
        images=[],  # ESP doesn't include images in current output
        notes=notes,
        flags=flags
    )


# ============================================================================
# SAGE NORMALIZER
# ============================================================================

def _normalize_sage(data: Dict[str, Any]) -> UnifiedOutput:
    """Transform SAGE output to unified format"""
    
    metadata = data.get("metadata", {})
    
    # Build unified metadata
    # SAGE stores presentation_url in metadata, not at top level
    unified_metadata = UnifiedMetadata(
        generated_at=metadata.get("generated_at", datetime.now().isoformat()),
        source="sage",
        presentation_url=metadata.get("presentation_url") or data.get("presentation_url", ""),
        presentation_title=metadata.get("presentation_title"),
        presentation_date=metadata.get("presentation_date"),
        pres_id=data.get("pres_id"),
        total_items=metadata.get("total_items", metadata.get("item_count", 0)),
        items_processed=metadata.get("item_count", 0),
        errors=0,
        api_version=metadata.get("api_version"),
        pricing_sources=metadata.get("pricing_sources", {
            "sell_price": "From SAGE Presentation API (serviceId 301)",
            "net_cost": "From SAGE Full Product Detail API (serviceId 105)",
            "catalog_price": "MSRP/List price from catalog"
        })
    )
    
    # Build client
    client_data = data.get("client", {})
    unified_client = UnifiedClient(
        id=client_data.get("id"),
        name=client_data.get("name"),
        company=client_data.get("company"),
        email=client_data.get("email"),
        phone=client_data.get("phone"),
        tax_rate=client_data.get("tax_rate")
    )
    
    # Build presenter
    presenter_data = data.get("presenter", {})
    unified_presenter = UnifiedPresenter(
        name=presenter_data.get("name"),
        company=presenter_data.get("company"),
        phone=presenter_data.get("phone"),
        website=presenter_data.get("website")
    )
    
    # Build products
    unified_products = []
    for product in data.get("products", []):
        unified_products.append(_normalize_sage_product(product))
    
    # Handle error
    error = data.get("error")
    errors = [{"message": error}] if error else []
    
    return UnifiedOutput(
        success=data.get("success", True),
        metadata=unified_metadata,
        client=unified_client,
        presenter=unified_presenter,
        products=unified_products,
        errors=errors
    )


def _normalize_sage_product(product: Dict[str, Any]) -> UnifiedProduct:
    """Transform single SAGE product to unified format"""
    
    # SAGE handler outputs flat structure at product level, not nested
    # Try nested first (for consistency), then fall back to flat
    ids_data = product.get("identifiers", {})
    item_data = product.get("item", {})
    vendor_data = product.get("vendor", {}) or product.get("supplier", {}) or {}
    pricing_data = product.get("pricing", {})
    shipping_data = product.get("shipping", {})
    decoration_data = product.get("decoration", {})
    
    # Identifiers - SAGE has these at top level
    # internal_item_num is the vendor's item number (MPN/SKU)
    internal_item_num = ids_data.get("internal_item_num") or product.get("internal_item_num")
    spc = ids_data.get("spc") or product.get("spc")
    item_num = ids_data.get("item_num") or product.get("item_num")
    
    identifiers = UnifiedIdentifiers(
        mpn=internal_item_num,  # internal_item_num is the MPN for SAGE
        vendor_sku=internal_item_num,  # Use internal_item_num as vendor SKU
        spc=spc,
        prod_id=ids_data.get("prod_id") or product.get("prod_id"),
        encrypted_prod_id=ids_data.get("encrypted_prod_id") or product.get("encrypted_prod_id"),
        pres_item_id=ids_data.get("pres_item_id") or product.get("pres_item_id"),
        internal_item_num=internal_item_num,
        item_num=item_num
    )
    
    # Item - SAGE has fields at top level
    category = item_data.get("category") or product.get("category")
    categories = [category] if category else []

    # Themes from Full Product Detail API
    themes_str = item_data.get("themes") or product.get("themes")
    themes = themes_str.split(",") if themes_str else []

    # Build sustainability credential from flags (check both nested and product-level)
    sustainability_parts = []
    if item_data.get("recyclable") or product.get("recyclable"):
        sustainability_parts.append("Recyclable")
    if item_data.get("env_friendly") or product.get("env_friendly"):
        sustainability_parts.append("Environmentally Friendly")
    sustainability_credential = ", ".join(sustainability_parts) if sustainability_parts else None

    item = UnifiedItem(
        name=item_data.get("name") or product.get("name", ""),
        description=item_data.get("description") or product.get("description", ""),
        description_short=None,  # SAGE doesn't have short description
        categories=categories,
        themes=themes,  # Now populated from Full Product Detail API
        materials=[],  # SAGE doesn't have materials
        colors=item_data.get("colors") or product.get("colors", []),
        primary_color=None,  # SAGE doesn't have primary color
        dimensions=UnifiedDimensions(
            raw=item_data.get("dimensions") or product.get("dimensions")
        ) if (item_data.get("dimensions") or product.get("dimensions")) else None,
        weight_value=None,
        weight_unit=None,
        sustainability_credential=sustainability_credential  # From recyclable/envFriendly flags
    )
    
    # Vendor - SAGE uses "supplier" at top level
    supplier_data = vendor_data if vendor_data else {}
    if isinstance(supplier_data, dict):
        vendor = UnifiedVendor(
            name=supplier_data.get("name", ""),
            website=supplier_data.get("website"),
            sage_id=supplier_data.get("sage_id"),
            email=supplier_data.get("email"),
            phone=supplier_data.get("phone"),
            address=UnifiedAddress(
                city=supplier_data.get("city"),
                state=supplier_data.get("state"),
                postal_code=supplier_data.get("zip_code") or supplier_data.get("zip")
            ) if supplier_data.get("city") else None,
            line_name=supplier_data.get("line_name"),
            my_customer_number=supplier_data.get("my_customer_number"),
            my_cs_rep=supplier_data.get("my_cs_rep"),
            my_cs_rep_email=supplier_data.get("my_cs_rep_email")
        )
    else:
        vendor = UnifiedVendor(name="")
    
    # Pricing - SAGE has price_breaks at top level
    price_breaks_data = pricing_data.get("breaks", []) or product.get("price_breaks", [])
    price_breaks = []
    for brk in price_breaks_data:
        sell_price = brk.get("sell_price")
        net_cost = brk.get("net_cost")
        
        margin = None
        margin_percent = None
        if sell_price and net_cost:
            margin = round(sell_price - net_cost, 2)
            margin_percent = round((margin / sell_price) * 100, 2) if sell_price > 0 else None
        
        price_breaks.append(UnifiedPriceBreak(
            quantity=brk.get("quantity"),
            sell_price=sell_price,
            net_cost=net_cost,
            catalog_price=brk.get("catalog_price"),
            margin=margin,
            margin_percent=margin_percent
        ))
    
    pricing = UnifiedPricing(
        breaks=price_breaks,
        price_code=pricing_data.get("price_code") or product.get("price_code"),
        currency="USD",
        price_includes=pricing_data.get("price_includes") or product.get("price_includes")
    )
    
    # Fees - SAGE has individual fee fields, not a fees[] array
    fees = []
    
    # Map SAGE individual fee fields to UnifiedFee objects
    sage_fee_mapping = [
        ("setup_charge", "setup", "Setup Charge"),
        ("repeat_charge", "repeat", "Repeat/Reorder Charge"),
        ("screen_charge", "screen", "Screen Charge"),
        ("proof_charge", "proof", "Proof Charge"),
        ("pms_charge", "pms", "PMS Color Match Charge"),
        ("spec_sample_charge", "sample", "Spec Sample Charge"),
        ("copy_change_charge", "copy_change", "Copy Change Charge"),
    ]
    
    for field_name, fee_type, fee_name in sage_fee_mapping:
        value = product.get(field_name)
        if value and value > 0:
            fees.append(UnifiedFee(
                fee_type=fee_type,
                name=fee_name,
                list_price=value,
                net_cost=value,  # For SAGE, assume same as list for now
                charge_basis="per_order",
                price_code=product.get("setup_charge_code") if fee_type == "setup" else None
            ))
    
    # Also check for any pre-structured fees array
    for fee in product.get("fees", []):
        fees.append(UnifiedFee(
            fee_type=fee.get("fee_type", "other"),
            name=fee.get("name", ""),
            list_price=fee.get("price"),
            price_code=fee.get("price_code")
        ))
    
    # Decoration - SAGE has imprint_info_text at product level (not in decoration dict)
    # Also check decoration.imprint_info as fallback
    imprint_info = product.get("imprint_info_text") or decoration_data.get("imprint_info")

    # Build decoration methods from Full Product Detail API (check both nested and product-level)
    decoration_methods = []
    deco_method = decoration_data.get("decoration_method") or product.get("decoration_method")
    if deco_method:
        decoration_methods.append(UnifiedDecorationMethod(name=deco_method))

    # Build imprint areas from Full Product Detail API
    imprint_areas = []
    imprint_area = decoration_data.get("imprint_area")
    imprint_loc = decoration_data.get("imprint_loc")
    if imprint_area:
        imprint_areas.append(f"{imprint_loc}: {imprint_area}" if imprint_loc else imprint_area)
    second_area = decoration_data.get("second_imprint_area")
    second_loc = decoration_data.get("second_imprint_loc")
    if second_area:
        imprint_areas.append(f"{second_loc}: {second_area}" if second_loc else second_area)

    decoration = UnifiedDecoration(
        methods=decoration_methods,
        imprint_info=imprint_info,
        # Store imprint areas in multi_color_description field (or we could add a new field)
        multi_color_description="\n".join(imprint_areas) if imprint_areas else None
    )

    # Shipping - check both nested shipping_data and product-level flat fields
    ship_point = shipping_data.get("ship_point") or product.get("ship_point")
    fob_points = []
    if ship_point:
        # Ship point is typically a zip code
        fob_points.append(UnifiedFOBPoint(postal_code=ship_point))

    # Lead Time - prefer nested, fallback to product.prod_time (SAGE field name)
    lead_time = shipping_data.get("lead_time") or product.get("prod_time")

    # Packaging - SAGE uses packaging_text at product level
    packaging = shipping_data.get("packaging") or product.get("packaging_text", "")

    # If still no lead_time, try parsing from packaging string
    if not lead_time and packaging and "production time" in packaging.lower():
        lead_time = packaging

    # Get additional_charges_text for both shipping and notes
    additional_charges_text = product.get("additional_charges_text", "")

    # Units and weight per carton - check both nested and product-level
    units_per_carton = shipping_data.get("units_per_carton") or product.get("units_per_carton")
    weight_per_carton = shipping_data.get("weight_per_carton") or product.get("weight_per_carton")

    shipping = UnifiedShipping(
        ship_point=ship_point,
        fob_points=fob_points,
        units_per_carton=units_per_carton,
        weight_per_carton=weight_per_carton,
        packaging=packaging,
        lead_time=lead_time,
        additional_charges_text=additional_charges_text  # For fee parser
    )
    
    # Notes
    notes = UnifiedNotes(
        packaging=packaging,
        additional_charges_text=additional_charges_text
    )
    
    # Images - SAGE uses image_urls at product level
    images = product.get("images", []) or product.get("image_urls", [])
    
    return UnifiedProduct(
        source="sage",
        identifiers=identifiers,
        item=item,
        vendor=vendor,
        pricing=pricing,
        fees=fees,
        decoration=decoration,
        variants=[],  # SAGE doesn't have variants
        shipping=shipping,
        images=images,
        notes=notes,
        flags={}
    )


# ============================================================================
# FILE OPERATIONS
# ============================================================================

def normalize_file(input_path: str, output_path: str, source: str) -> Dict[str, Any]:
    """
    Read a JSON file, normalize it, and write to output path.
    
    Args:
        input_path: Path to input JSON file
        output_path: Path for output unified JSON
        source: "esp" or "sage"
        
    Returns:
        The normalized data
    """
    with open(input_path, 'r') as f:
        data = json.load(f)
    
    normalized = normalize_output(data, source)
    
    with open(output_path, 'w') as f:
        json.dump(normalized, f, indent=2)
    
    logger.info(f"Normalized {source} output: {input_path} -> {output_path}")
    return normalized


def detect_source(data: Dict[str, Any]) -> str:
    """
    Auto-detect whether data is from ESP or SAGE.
    
    Returns:
        "esp" or "sage"
    """
    # SAGE has specific markers
    if data.get("source_platform") == "sage":
        return "sage"
    if data.get("pres_id") is not None:
        return "sage"
    if "presenter" in data and isinstance(data["presenter"], dict) and data["presenter"].get("phone"):
        return "sage"  # ESP presenter doesn't have direct phone
    
    # ESP has specific markers
    metadata = data.get("metadata", {})
    if metadata.get("source_type") == "esp":
        return "esp"
    if "total_items_in_presentation" in metadata:
        return "esp"
    
    # Check products for source-specific fields
    products = data.get("products", [])
    if products:
        first_product = products[0]
        if "identifiers" in first_product and first_product["identifiers"].get("spc"):
            return "sage"
        if first_product.get("item", {}).get("cpn"):
            return "esp"
    
    # Default to ESP if can't determine
    logger.warning("Could not auto-detect source, defaulting to ESP")
    return "esp"


def auto_normalize(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Auto-detect source and normalize.
    
    Args:
        data: Raw JSON data from either ESP or SAGE
        
    Returns:
        Normalized unified data
    """
    source = detect_source(data)
    logger.info(f"Auto-detected source: {source}")
    return normalize_output(data, source)


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Normalize ESP/SAGE output to unified format")
    parser.add_argument("input", help="Input JSON file path")
    parser.add_argument("output", help="Output JSON file path")
    parser.add_argument("--source", choices=["esp", "sage", "auto"], default="auto",
                        help="Source type (default: auto-detect)")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    with open(args.input, 'r') as f:
        data = json.load(f)
    
    if args.source == "auto":
        normalized = auto_normalize(data)
    else:
        normalized = normalize_output(data, args.source)
    
    with open(args.output, 'w') as f:
        json.dump(normalized, f, indent=2)
    
    print(f"Normalized output written to: {args.output}")
    print(f"Source: {normalized['metadata']['source']}")
    print(f"Products: {len(normalized['products'])}")

