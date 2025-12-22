"""
Unified JSON Schema for ESP and SAGE Presentation Data

This module defines the standardized output format that both ESP and SAGE
data will be normalized into before being sent to Zoho and the Calculator workflow.

Key Design Principles:
1. Shared fields use identical names/structures regardless of source
2. Source-specific fields are grouped under `esp_specific` or `sage_specific`
3. Follows Koell's Zoho Item Master requirements:
   - MPN field = Vendor SKU (appears on Purchase Orders)
   - SKU field = Client Account # + Item Number (internal tracking)
   - Vendor matching = Website URL (not name, which varies)
4. Pricing follows the "trust" rules:
   - sell_price = From Presentation (what customer sees)
   - net_cost = From Distributor Report/API (authoritative cost)
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


# ============================================================================
# UNIFIED SCHEMA DEFINITIONS
# ============================================================================

@dataclass
class UnifiedAddress:
    """Standardized address structure"""
    line1: Optional[str] = None
    line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


@dataclass
class UnifiedVendor:
    """
    Standardized vendor information.
    
    The `website` field is the PRIMARY IDENTIFIER for vendor matching in Zoho.
    This is because vendor names often vary between platforms.
    """
    name: str
    website: Optional[str] = None  # PRIMARY MATCH KEY for Zoho
    
    # Industry IDs (source-specific but useful)
    asi: Optional[str] = None      # ESP: ASI number
    sage_id: Optional[str] = None  # SAGE: SAGE supplier ID
    
    # Contact information
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    
    # Address
    address: Optional[UnifiedAddress] = None
    
    # Additional details
    line_name: Optional[str] = None
    trade_name: Optional[str] = None
    hours: Optional[str] = None
    
    # SAGE-specific customer relationship fields
    my_customer_number: Optional[str] = None
    my_cs_rep: Optional[str] = None
    my_cs_rep_email: Optional[str] = None


@dataclass
class UnifiedFOBPoint:
    """Shipping origin point"""
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


@dataclass
class UnifiedIdentifiers:
    """
    All product identifiers - both shared and source-specific.
    
    ZOHO MAPPING:
    - mpn → Zoho MPN field (appears on Purchase Orders)
    - internal_sku → Will become Zoho SKU as [ClientAcct#]-[internal_sku]
    """
    # PRIMARY IDENTIFIERS (used for Zoho)
    mpn: Optional[str] = None           # Manufacturer/Vendor Part Number → Zoho MPN
    vendor_sku: Optional[str] = None    # Vendor's SKU (often same as mpn)
    
    # ESP-specific
    cpn: Optional[str] = None           # Customer Product Number (ESP unique ID)
    
    # SAGE-specific  
    spc: Optional[str] = None           # SAGE Product Code
    prod_id: Optional[int] = None       # SAGE product ID (numeric)
    encrypted_prod_id: Optional[str] = None
    pres_item_id: Optional[int] = None  # Presentation item ID
    internal_item_num: Optional[str] = None  # SAGE internal item number
    item_num: Optional[str] = None      # SAGE item number


@dataclass
class UnifiedDimensions:
    """Standardized dimensions"""
    length: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    diameter: Optional[float] = None
    unit: Optional[str] = None
    raw: Optional[str] = None  # Original dimension string


@dataclass
class UnifiedItem:
    """
    Core product information.
    
    All sources normalize to this structure.
    """
    name: str
    description: str  # Primary description (use description_long if available)
    description_short: Optional[str] = None
    
    # Categorization
    categories: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    materials: List[str] = field(default_factory=list)
    
    # Physical attributes
    colors: List[str] = field(default_factory=list)
    primary_color: Optional[str] = None
    dimensions: Optional[UnifiedDimensions] = None
    weight_value: Optional[float] = None
    weight_unit: Optional[str] = None

    # Sustainability
    sustainability_credential: Optional[str] = None  # e.g., "Recyclable", "Environmentally Friendly"
    recycled_content: Optional[float] = None  # Percentage

    # Assembly
    item_assembled: Optional[bool] = None


@dataclass
class UnifiedPriceBreak:
    """
    Standardized price break.
    
    CRITICAL: 
    - sell_price = What the customer pays (from Presentation)
    - net_cost = What distributor pays (from Distributor Report/API)
    - catalog_price = MSRP/List price
    """
    quantity: int
    sell_price: Optional[float] = None      # Customer-facing price
    net_cost: Optional[float] = None        # Distributor cost (authoritative)
    catalog_price: Optional[float] = None   # MSRP/List price
    margin: Optional[float] = None          # Calculated: sell_price - net_cost
    margin_percent: Optional[float] = None  # Calculated: margin / sell_price * 100
    notes: Optional[str] = None


@dataclass
class UnifiedPricing:
    """Standardized pricing information"""
    breaks: List[UnifiedPriceBreak] = field(default_factory=list)
    price_code: Optional[str] = None
    currency: str = "USD"
    valid_through: Optional[str] = None
    price_includes: Optional[str] = None  # What's included in base price
    notes: Optional[str] = None


@dataclass
class UnifiedFee:
    """
    Standardized fee/charge structure.
    
    Common fee_types: setup, reorder, proof, pms_match, spec_sample, 
                      copy_change, additional_color, payment_surcharge
    """
    fee_type: str
    name: str
    description: Optional[str] = None
    
    # Pricing
    list_price: Optional[float] = None  # Customer price
    net_cost: Optional[float] = None    # Distributor cost
    price_code: Optional[str] = None
    
    # Application
    charge_basis: Optional[str] = None  # per_order, per_unit, percentage, qur
    min_qty: Optional[int] = None
    decoration_method: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class UnifiedImprintArea:
    """Single imprint area specification"""
    width: Optional[float] = None
    height: Optional[float] = None
    diameter: Optional[float] = None
    unit: Optional[str] = None
    raw: Optional[str] = None


@dataclass 
class UnifiedDecorationMethod:
    """Decoration/imprint method details"""
    name: str
    full_color: bool = False
    max_colors: Optional[int] = None
    notes: Optional[str] = None


@dataclass
class UnifiedDecorationLocation:
    """Location where decoration can be applied"""
    name: str
    component: Optional[str] = None
    methods_allowed: List[str] = field(default_factory=list)
    imprint_areas: List[UnifiedImprintArea] = field(default_factory=list)


@dataclass
class UnifiedDecoration:
    """Standardized decoration/imprint information"""
    # Methods and locations
    methods: List[UnifiedDecorationMethod] = field(default_factory=list)
    locations: List[UnifiedDecorationLocation] = field(default_factory=list)
    
    # Flags
    sold_unimprinted: Optional[bool] = None
    personalization_available: Optional[bool] = None
    full_color_process_available: Optional[bool] = None
    
    # Descriptions
    imprint_info: Optional[str] = None  # Raw imprint info string
    imprint_colors_description: Optional[str] = None
    multi_color_description: Optional[str] = None


@dataclass
class UnifiedVariant:
    """Product variant option"""
    attribute: str
    label: str
    component: Optional[str] = None
    options: List[str] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
class UnifiedShipping:
    """Shipping and packaging information"""
    ship_point: Optional[str] = None
    fob_points: List[UnifiedFOBPoint] = field(default_factory=list)
    units_per_carton: Optional[int] = None
    weight_per_carton: Optional[float] = None
    carton_dimensions: Optional[str] = None
    packaging: Optional[str] = None
    lead_time: Optional[str] = None
    rush_available: Optional[bool] = None
    additional_charges_text: Optional[str] = None  # For fee parsing
    supplier_disclaimers: List[str] = field(default_factory=list)  # For fee parsing


@dataclass
class UnifiedNotes:
    """Various notes and disclaimers"""
    packaging: Optional[str] = None
    lead_time: Optional[str] = None
    supplier_disclaimers: List[str] = field(default_factory=list)
    additional_charges_text: Optional[str] = None
    other: Optional[str] = None


@dataclass
class UnifiedProduct:
    """
    Complete standardized product structure.
    
    This is the main product object that both ESP and SAGE data normalize to.
    """
    # Source tracking
    source: str  # "esp" or "sage"
    
    # Core product data
    identifiers: UnifiedIdentifiers = field(default_factory=UnifiedIdentifiers)
    item: UnifiedItem = field(default_factory=lambda: UnifiedItem(name="", description=""))
    vendor: UnifiedVendor = field(default_factory=lambda: UnifiedVendor(name=""))
    
    # Pricing and fees
    pricing: UnifiedPricing = field(default_factory=UnifiedPricing)
    fees: List[UnifiedFee] = field(default_factory=list)
    
    # Decoration
    decoration: UnifiedDecoration = field(default_factory=UnifiedDecoration)
    variants: List[UnifiedVariant] = field(default_factory=list)
    
    # Shipping
    shipping: UnifiedShipping = field(default_factory=UnifiedShipping)
    
    # Images
    images: List[str] = field(default_factory=list)
    
    # Notes
    notes: UnifiedNotes = field(default_factory=UnifiedNotes)
    
    # Flags
    flags: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedClient:
    """Client/customer information"""
    id: Optional[int] = None
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    tax_rate: Optional[float] = None


@dataclass
class UnifiedPresenter:
    """Presenter/sales rep information"""
    name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None


@dataclass
class UnifiedMetadata:
    """Presentation and processing metadata"""
    generated_at: str
    source: str  # "esp" or "sage"
    presentation_url: str
    presentation_title: Optional[str] = None
    presentation_date: Optional[str] = None
    pres_id: Optional[int] = None
    
    # Counts
    total_items: int = 0
    items_processed: int = 0
    errors: int = 0
    
    # Processing info
    api_version: Optional[int] = None
    
    # Pricing source documentation
    pricing_sources: Dict[str, str] = field(default_factory=lambda: {
        "sell_price": "From Presentation - what customer sees",
        "net_cost": "From Distributor Report/API - authoritative cost",
        "catalog_price": "MSRP/List price from catalog"
    })


@dataclass
class UnifiedOutput:
    """
    Top-level unified output structure.
    
    This is the final format that goes to Zoho and Calculator workflows.
    """
    success: bool
    metadata: UnifiedMetadata
    client: UnifiedClient
    presenter: UnifiedPresenter
    products: List[UnifiedProduct]
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    # Zoho integration hints
    zoho_integration: Dict[str, Any] = field(default_factory=lambda: {
        "sku_format": "[ClientAccountNumber]-[VendorSKU]",
        "mpn_source": "vendor_sku or mpn field",
        "vendor_match_key": "vendor.website",
        "track_inventory": False,
        "default_unit": "Piece",
        "taxable": True
    })


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def dataclass_to_dict(obj) -> Dict[str, Any]:
    """Convert dataclass to dict, handling nested dataclasses"""
    if hasattr(obj, '__dataclass_fields__'):
        return {k: dataclass_to_dict(v) for k, v in asdict(obj).items()}
    elif isinstance(obj, list):
        return [dataclass_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: dataclass_to_dict(v) for k, v in obj.items()}
    return obj


def to_json(unified_output: UnifiedOutput, indent: int = 2) -> str:
    """Convert UnifiedOutput to JSON string"""
    return json.dumps(dataclass_to_dict(unified_output), indent=indent)


# ============================================================================
# SCHEMA DOCUMENTATION
# ============================================================================

FIELD_MAPPING_DOCS = """
FIELD MAPPING: ESP vs SAGE → Unified Schema

┌─────────────────────────────────────────────────────────────────────────────┐
│                           IDENTIFIERS                                        │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│ ESP Field            │ SAGE Field           │ Unified Field                 │
├──────────────────────┼──────────────────────┼───────────────────────────────┤
│ item.vendor_sku      │ item.vendor_sku      │ identifiers.vendor_sku        │
│ item.mpn             │ item.mpn             │ identifiers.mpn               │
│ item.cpn             │ -                    │ identifiers.cpn               │
│ -                    │ identifiers.spc      │ identifiers.spc               │
│ -                    │ identifiers.prod_id  │ identifiers.prod_id           │
│ -                    │ identifiers.internal │ identifiers.internal_item_num │
└──────────────────────┴──────────────────────┴───────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              VENDOR                                          │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│ ESP Field            │ SAGE Field           │ Unified Field                 │
├──────────────────────┼──────────────────────┼───────────────────────────────┤
│ vendor.name          │ vendor.name          │ vendor.name                   │
│ vendor.website       │ vendor.website       │ vendor.website (MATCH KEY)    │
│ vendor.asi           │ -                    │ vendor.asi                    │
│ -                    │ vendor.sage_id       │ vendor.sage_id                │
│ vendor.address.*     │ vendor.city/state/   │ vendor.address.*              │
│                      │ zip                  │                               │
│ vendor.phones[]      │ vendor.phone         │ vendor.phone (first)          │
│ vendor.emails[]      │ vendor.email         │ vendor.email (first)          │
└──────────────────────┴──────────────────────┴───────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              PRICING                                         │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│ ESP Field            │ SAGE Field           │ Unified Field                 │
├──────────────────────┼──────────────────────┼───────────────────────────────┤
│ breaks[].min_qty     │ breaks[].quantity    │ breaks[].quantity             │
│ breaks[].catalog_    │ breaks[].catalog_    │ breaks[].catalog_price        │
│ price                │ price                │                               │
│ breaks[].net_cost    │ breaks[].net_cost    │ breaks[].net_cost             │
│ (calculated)         │ (API enriched)       │ (authoritative)               │
│ -                    │ breaks[].sell_price  │ breaks[].sell_price           │
│ pricing.currency     │ "USD" (implied)      │ pricing.currency              │
│ pricing.valid_       │ -                    │ pricing.valid_through         │
│ through              │                      │                               │
│ pricing.notes        │ pricing.price_       │ pricing.price_includes +      │
│                      │ includes             │ notes                         │
└──────────────────────┴──────────────────────┴───────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                               FEES                                           │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│ ESP Field            │ SAGE Field           │ Unified Field                 │
├──────────────────────┼──────────────────────┼───────────────────────────────┤
│ fees[].list_price    │ fees[].price         │ fees[].list_price             │
│ fees[].net_cost      │ -                    │ fees[].net_cost               │
│ fees[].charge_basis  │ -                    │ fees[].charge_basis           │
│ fees[].decoration_   │ -                    │ fees[].decoration_method      │
│ method               │                      │                               │
│ fees[].description   │ -                    │ fees[].description            │
└──────────────────────┴──────────────────────┴───────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            DECORATION                                        │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│ ESP Field            │ SAGE Field           │ Unified Field                 │
├──────────────────────┼──────────────────────┼───────────────────────────────┤
│ decoration.methods[] │ -                    │ decoration.methods[]          │
│ decoration.locations │ -                    │ decoration.locations[]        │
│ decoration.sold_     │ -                    │ decoration.sold_unimprinted   │
│ unimprinted          │                      │                               │
│ -                    │ decoration.imprint_  │ decoration.imprint_info       │
│                      │ info                 │                               │
└──────────────────────┴──────────────────────┴───────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            SHIPPING                                          │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│ ESP Field            │ SAGE Field           │ Unified Field                 │
├──────────────────────┼──────────────────────┼───────────────────────────────┤
│ vendor.fob_points[]  │ shipping.ship_point  │ shipping.fob_points[] +       │
│                      │                      │ ship_point                    │
│ raw_notes.lead_time  │ shipping.packaging   │ shipping.lead_time +          │
│                      │ (contains lead time) │ packaging                     │
│ -                    │ shipping.units_per_  │ shipping.units_per_carton     │
│                      │ carton               │                               │
│ -                    │ shipping.weight_per_ │ shipping.weight_per_carton    │
│                      │ carton               │                               │
└──────────────────────┴──────────────────────┴───────────────────────────────┘

ZOHO ITEM MASTER MAPPING:
═════════════════════════
• Zoho SKU        ← [ClientAccountNumber]-[identifiers.vendor_sku]
• Zoho MPN        ← identifiers.mpn OR identifiers.vendor_sku  
• Zoho Item Name  ← item.name
• Zoho Vendor     ← Match by vendor.website
• Unit            ← "Piece" (default)
• Taxable         ← true (default)
• Track Inventory ← false

PRICE TRUTH SOURCES:
════════════════════
• sell_price      ← Presentation Link (what Koell shows client)
• net_cost        ← Distributor Report (ESP) or Full Product Detail API (SAGE)
• catalog_price   ← MSRP/List price from catalog
"""

if __name__ == "__main__":
    print(FIELD_MAPPING_DOCS)

