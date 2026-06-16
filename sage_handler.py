#!/usr/bin/env python3
"""
SAGE Presentation Handler
=========================

Handles SAGE presentation links (viewpresentation.com).
Uses SAGE Connect API for data extraction.

Usage:
    from sage_handler import SAGEHandler
    
    handler = SAGEHandler("https://www.viewpresentation.com/66907679185")
    result = handler.process()
"""

import json
import logging
import os
import re
import ssl
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx

# Import JobStateManager for state updates (optional dependency)
try:
    from job_state import JobStateManager, WorkflowStatus
except ImportError:
    JobStateManager = None
    WorkflowStatus = None

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

# SAGE API Configuration - Default credentials (can be overridden via env vars)
# SAGE Connect API endpoint
# From docs: https://www.promoplace.com/ws/ws.dll/ConnectAPI
# Requires TLS 1.2 encryption
SAGE_API_URL = os.getenv("SAGE_API_URL", "https://www.promoplace.com/ws/ws.dll/ConnectAPI")
SAGE_ACCT_ID = int(os.getenv("SAGE_ACCT_ID", "270178"))
SAGE_LOGIN_ID = os.getenv("SAGE_LOGIN_ID", "System")
SAGE_AUTH_KEY = os.getenv("SAGE_AUTH_KEY", "d5ecbc5d702fe54188265e8f513ed0af")

# API Service IDs
SERVICE_PRESENTATION = 301
SERVICE_PRODUCT_DETAIL = 105
API_VERSION = 130


# =============================================================================
# Data Types
# =============================================================================

@dataclass
class SAGEVendor:
    """Vendor/Supplier information from SAGE."""
    sage_id: Optional[str] = None
    name: Optional[str] = None
    line_name: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    my_customer_number: Optional[str] = None  # Koell's customer # with this supplier
    my_cs_rep: Optional[str] = None
    my_cs_rep_email: Optional[str] = None


@dataclass
class SAGEPriceBreak:
    """Price break/tier from SAGE."""
    quantity: int
    catalog_price: float
    sell_price: float
    net_cost: float


@dataclass
class SAGEProduct:
    """Normalized product from SAGE presentation."""
    # Identifiers
    pres_item_id: int
    prod_id: Optional[int] = None
    encrypted_prod_id: Optional[str] = None  # For Full Product Detail API
    internal_item_num: Optional[str] = None  # This is the MPN for Zoho!
    spc: Optional[str] = None  # SAGE Product Code
    item_num: Optional[str] = None  # Display item number
    
    # Basic info
    name: str = ""
    description: str = ""
    category: Optional[str] = None
    
    # Pricing
    price_breaks: List[SAGEPriceBreak] = field(default_factory=list)
    price_includes: Optional[str] = None
    price_code: Optional[str] = None
    
    # Charges
    setup_charge: float = 0.0
    setup_charge_code: Optional[str] = None
    repeat_charge: float = 0.0
    screen_charge: float = 0.0
    proof_charge: float = 0.0
    pms_charge: float = 0.0
    spec_sample_charge: float = 0.0
    copy_change_charge: float = 0.0
    additional_charges_text: Optional[str] = None
    
    # Product details
    colors: List[str] = field(default_factory=list)
    color_info_text: Optional[str] = None
    imprint_info_text: Optional[str] = None
    packaging_text: Optional[str] = None
    dimensions: Optional[str] = None
    themes: Optional[str] = None

    # Decoration (from Full Product Detail API)
    decoration_method: Optional[str] = None
    imprint_area: Optional[str] = None
    imprint_loc: Optional[str] = None
    second_imprint_area: Optional[str] = None
    second_imprint_loc: Optional[str] = None

    # Sustainability (from Full Product Detail API)
    recyclable: bool = False
    env_friendly: bool = False

    # Production (from Full Product Detail API)
    prod_time: Optional[str] = None  # Lead time!

    # Shipping
    ship_point: Optional[str] = None
    units_per_carton: Optional[int] = None
    weight_per_carton: Optional[float] = None
    
    # Supplier
    supplier: Optional[SAGEVendor] = None
    
    # Images
    image_urls: List[str] = field(default_factory=list)
    
    # Catalog info
    cat_year: Optional[str] = None
    cat_expires: Optional[str] = None


@dataclass
class SAGEClient:
    """Client information from SAGE presentation."""
    client_id: Optional[int] = None
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    tax_rate: Optional[str] = None


@dataclass
class SAGEPresenter:
    """Presenter information (always Koell/STBL Strategies)."""
    name: str = "Koell Collins"
    company: str = "STBL Strategies"
    phone: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None


@dataclass
class SAGEResult:
    """Result of SAGE presentation processing."""
    success: bool
    presentation_url: str
    pres_id: Optional[int] = None
    presentation_title: Optional[str] = None
    presentation_date: Optional[str] = None
    client: Optional[SAGEClient] = None
    presenter: Optional[SAGEPresenter] = None
    products: List[SAGEProduct] = field(default_factory=list)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# SAGE API Client
# =============================================================================

class SAGEAPIClient:
    """
    Client for SAGE Connect API.
    
    Handles authentication and API calls to SAGE services.
    """
    
    def __init__(
        self,
        acct_id: int = SAGE_ACCT_ID,
        login_id: str = SAGE_LOGIN_ID,
        auth_key: str = SAGE_AUTH_KEY,
        api_url: str = SAGE_API_URL,
        session_id: Optional[str] = None
    ):
        """
        Initialize SAGE API client.
        
        Args:
            acct_id: SAGE account ID
            login_id: SAGE login ID
            auth_key: SAGE authentication key
            api_url: SAGE API endpoint URL
            session_id: Optional session ID from sagemember.com login
        """
        self.acct_id = acct_id
        self.login_id = login_id
        self.auth_key = auth_key
        self.api_url = api_url
        self.session_id = session_id or os.getenv("SAGE_SESSION_ID", "")
        
        # Build cookies if session ID is provided
        cookies = {}
        if self.session_id:
            cookies[f"{acct_id}AdminSessionID"] = self.session_id
            cookies["DefaultAdminSessionID"] = self.session_id

        # Create SSL context with legacy cipher support for older SAGE servers
        # OpenSSL 3.0 defaults are too strict for promoplace.com
        ssl_context = ssl.create_default_context()
        ssl_context.set_ciphers('DEFAULT:@SECLEVEL=1')
        # Load system CA certificates
        try:
            import certifi
            ssl_context.load_verify_locations(certifi.where())
        except ImportError:
            pass  # Fall back to system certificates

        self._client = httpx.Client(timeout=60.0, cookies=cookies, verify=ssl_context)
    
    def _build_auth(self) -> Dict[str, Any]:
        """Build authentication object for API requests."""
        return {
            "acctId": self.acct_id,
            "loginId": self.login_id,
            "key": self.auth_key
        }
    
    def _call_api(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make an API call to SAGE.
        
        Args:
            request_data: Request payload
            
        Returns:
            API response as dictionary
            
        Raises:
            Exception: If API call fails
        """
        logger.info(f"SAGE API URL: {self.api_url}")
        logger.debug(f"SAGE API Request: {json.dumps(request_data, indent=2)}")
        
        response = self._client.post(
            self.api_url,
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        
        logger.info(f"SAGE API Response Status: {response.status_code}")
        logger.info(f"SAGE API Response Headers: {dict(response.headers)}")
        
        # Log raw response for debugging
        raw_text = response.text[:500] if response.text else "(empty)"
        logger.info(f"SAGE API Response Body (first 500 chars): {raw_text}")
        
        response.raise_for_status()
        
        if not response.text:
            raise Exception("SAGE API returned empty response")
        
        result = response.json()
        
        # Check for success - different APIs have different response formats:
        # - Presentation API (301): {"ok": true, "presentations": [...]}
        # - Full Product Detail API (105): {"legalNote": "...", "product": {...}}
        # - Error responses: {"ok": false, "errNum": "...", "errMsg": "..."}
        
        if result.get("ok") == False:
            # Explicit error
            raise Exception(f"SAGE API error: {result.get('errMsg', result)}")
        
        # Check if this is a valid response (either has 'ok' or has 'product' or 'legalNote')
        if not (result.get("ok") or result.get("product") or result.get("presentations")):
            raise Exception(f"SAGE API unexpected response: {result}")
        
        logger.debug(f"SAGE API Response OK: {result.get('ok', 'N/A (has product)')}")
        
        return result
    
    def get_presentation(self, pres_id: int) -> Dict[str, Any]:
        """
        Get a specific presentation by ID.
        
        Args:
            pres_id: Presentation ID
            
        Returns:
            Presentation data
        """
        request = {
            "serviceId": SERVICE_PRESENTATION,
            "apiVer": API_VERSION,
            "auth": self._build_auth(),
            "search": {
                "presId": [pres_id]
            }
        }
        
        result = self._call_api(request)
        presentations = result.get("presentations", [])
        
        if not presentations:
            raise Exception(f"Presentation {pres_id} not found")
        
        return presentations[0]
    
    def get_product_detail(self, prod_e_id: int, include_supplier: bool = True) -> Dict[str, Any]:
        """
        Get full product details.
        
        Args:
            prod_e_id: Product encrypted ID
            include_supplier: Whether to include supplier info
            
        Returns:
            Product details
        """
        request = {
            "serviceId": SERVICE_PRODUCT_DETAIL,
            "apiVer": API_VERSION,
            "auth": self._build_auth(),
            "prodEId": prod_e_id,
            "includeSuppInfo": 1 if include_supplier else 0
        }
        
        result = self._call_api(request)
        return result.get("product", {})
    
    def close(self):
        """Close the HTTP client."""
        self._client.close()


# =============================================================================
# URL Parser
# =============================================================================

def extract_pres_id_from_url(url: str) -> int | str:
    """
    Extract presentation ID from SAGE presentation URL.
    
    Supports two URL formats:
    1. viewpresentation.com: https://www.viewpresentation.com/XXXXXXXXXXX
       Where the number contains the presId (typically after stripping a prefix).
       Example: URL: 66907679185 → presId: 7679185 (strip first 4 chars)
    
    2. sageconnect.sage.com: https://sageconnect.sage.com/Presentation/XXXXXX
       Where XXXXXX is an alphanumeric presentation code.
       Example: URL: .../Presentation/6GMWK4 → code: 6GMWK4
    
    Args:
        url: Full SAGE presentation URL
        
    Returns:
        Presentation ID (int for viewpresentation, str for sageconnect)
        
    Raises:
        ValueError: If URL format is invalid
    """
    # Try sageconnect.sage.com format first (alphanumeric code)
    sageconnect_match = re.search(r'sageconnect\.sage\.com/Presentation/([A-Za-z0-9]+)', url)
    if sageconnect_match:
        pres_code = sageconnect_match.group(1)
        logger.info(f"Extracted presentation code '{pres_code}' from sageconnect URL")
        return pres_code

    # Try viewpresentation.com/p/ format (alphanumeric code like "10041-dh2z")
    vp_code_match = re.search(r'viewpresentation\.com/p/([A-Za-z0-9\-]+)', url)
    if vp_code_match:
        pres_code = vp_code_match.group(1)
        logger.info(f"Extracted presentation code '{pres_code}' from viewpresentation.com/p/ URL")
        return pres_code

    # Try viewpresentation.com format with numeric ID (legacy format)
    match = re.search(r'viewpresentation\.com/(\d+)', url)
    if not match:
        raise ValueError(f"Invalid SAGE presentation URL: {url}")

    url_number = match.group(1)

    # The presId is embedded - strip first 4 chars for URLs with prefix
    # URL: 66907679185 → presId: 7679185
    if len(url_number) > 7:
        pres_id = int(url_number[4:])
    else:
        pres_id = int(url_number)

    logger.info(f"Extracted presId {pres_id} from URL number {url_number}")
    return pres_id


# =============================================================================
# Response Parser
# =============================================================================

def parse_presentation_response(data: Dict[str, Any], url: str) -> SAGEResult:
    """
    Parse SAGE API presentation response into SAGEResult.
    
    Args:
        data: Raw API response for a single presentation
        url: Original presentation URL
        
    Returns:
        Parsed SAGEResult
    """
    # Extract presentation metadata
    general = data.get("general", {})
    pres_id = data.get("presId")
    
    # Parse client info
    client_data = data.get("client", {})
    client = SAGEClient(
        client_id=client_data.get("clientId"),
        name=client_data.get("name"),
        company=client_data.get("clientCompany") or client_data.get("company"),
        email=client_data.get("email") or None,
        phone=client_data.get("phone") or None,
        address1=client_data.get("address1") or None,
        city=client_data.get("city") or None,
        state=client_data.get("state") or None,
        zip_code=client_data.get("zip") or None,
        tax_rate=client_data.get("taxRate") or None
    )
    
    # Parse presenter info (always Koell Collins / STBL Strategies)
    header = data.get("header", {})
    header_text = header.get("headFirstText", "")
    
    presenter = SAGEPresenter(
        name="Koell Collins",
        company="STBL Strategies"
    )
    
    # Extract phone and location from header if available
    header_lines = header_text.split("\r\n") if header_text else []
    if len(header_lines) >= 3:
        presenter.phone = header_lines[2] if len(header_lines) > 2 else None
    if len(header_lines) >= 4:
        presenter.location = header_lines[3] if len(header_lines) > 3 else None
    
    # Extract website from additional header
    head_addtl = header.get("headAddtlText", "")
    if "stblstrategies.com" in head_addtl:
        presenter.website = "www.stblstrategies.com"
    
    # Parse products
    products = []
    for item in data.get("items", []):
        product = parse_item(item)
        products.append(product)
    
    # Build result
    return SAGEResult(
        success=True,
        presentation_url=url,
        pres_id=pres_id,
        presentation_title=general.get("title"),
        presentation_date=general.get("date"),
        client=client,
        presenter=presenter,
        products=products,
        metadata={
            "source": "sage_api",
            "processed_at": datetime.now().isoformat(),
            "item_count": len(products),
            "api_version": API_VERSION
        }
    )


def parse_item(item: Dict[str, Any]) -> SAGEProduct:
    """
    Parse a single item from SAGE presentation response.
    
    Args:
        item: Item data from API response
        
    Returns:
        Parsed SAGEProduct
    """
    # Parse price breaks
    price_breaks = []
    qtys = item.get("qtys", [])
    cat_prcs = item.get("catPrcs", [])
    sell_prcs = item.get("sellPrcs", [])
    costs = item.get("costs", [])
    
    for i in range(len(qtys)):
        qty_str = qtys[i] if i < len(qtys) else ""
        if not qty_str or qty_str == "0":
            continue
        
        try:
            qty = int(qty_str.replace(",", ""))
            cat_price = float(cat_prcs[i]) if i < len(cat_prcs) and cat_prcs[i] else 0.0
            sell_price = float(sell_prcs[i]) if i < len(sell_prcs) and sell_prcs[i] else 0.0
            cost = float(costs[i]) if i < len(costs) and costs[i] else 0.0
            
            if qty > 0:
                price_breaks.append(SAGEPriceBreak(
                    quantity=qty,
                    catalog_price=cat_price,
                    sell_price=sell_price,
                    net_cost=cost
                ))
        except (ValueError, IndexError):
            continue
    
    # Parse supplier
    supplier_data = item.get("supplier", {})
    supplier = SAGEVendor(
        sage_id=supplier_data.get("sageId"),
        name=supplier_data.get("company"),
        line_name=supplier_data.get("line"),
        website=supplier_data.get("web"),
        email=supplier_data.get("email"),
        phone=supplier_data.get("phone"),
        city=supplier_data.get("city"),
        state=supplier_data.get("state"),
        zip_code=supplier_data.get("zip"),
        my_customer_number=supplier_data.get("myCustNum") or None,
        my_cs_rep=supplier_data.get("myCsRep") or None,
        my_cs_rep_email=supplier_data.get("myCsRepEmail") or None
    )
    
    # Parse colors from colorInfoText
    color_text = item.get("colorInfoText", "")
    colors = [c.strip() for c in color_text.split(",") if c.strip()] if color_text else []
    
    # Parse image URLs
    image_urls = [pic.get("URL") or pic.get("url") for pic in item.get("pics", []) if pic.get("URL") or pic.get("url")]
    
    # Parse dimensions from description
    description = item.get("description", "")
    dimensions = extract_dimensions_from_text(description)
    
    # Parse carton info
    units_per_carton = None
    weight_per_carton = None
    try:
        upc = item.get("unitsPerCtn", "0")
        units_per_carton = int(upc) if upc and upc != "0" else None
        wpc = item.get("weightPerCtn", "0")
        weight_per_carton = float(wpc) if wpc and wpc != "0" else None
    except ValueError:
        pass
    
    return SAGEProduct(
        pres_item_id=item.get("presItemId", 0),
        prod_id=item.get("prodId"),
        encrypted_prod_id=item.get("encryptedProdId"),  # For Full Product Detail API
        internal_item_num=item.get("internalItemNum"),  # This is the MPN!
        spc=item.get("spc"),
        item_num=item.get("itemNum"),
        name=item.get("name", ""),
        description=description,
        category=item.get("category"),
        price_breaks=price_breaks,
        price_includes=item.get("priceIncludes") or None,
        price_code=item.get("priceCode"),
        setup_charge=safe_float(item.get("setupChg", "0")),
        setup_charge_code=item.get("setupChgCode") or None,
        repeat_charge=safe_float(item.get("repeatChg", "0")),
        screen_charge=safe_float(item.get("screenChg", "0")),
        proof_charge=safe_float(item.get("proofChg", "0")),
        pms_charge=safe_float(item.get("pmsChg", "0")),
        spec_sample_charge=safe_float(item.get("specSampleChg", "0")),
        copy_change_charge=safe_float(item.get("copyChg", "0")),
        additional_charges_text=item.get("additionalChargesText") or None,
        colors=colors,
        color_info_text=color_text or None,
        imprint_info_text=item.get("imprintInfoText") or None,
        packaging_text=item.get("packagingText") or None,
        dimensions=dimensions,
        ship_point=item.get("shipPoint") or None,
        units_per_carton=units_per_carton,
        weight_per_carton=weight_per_carton,
        supplier=supplier,
        image_urls=image_urls,
        cat_year=item.get("catYear"),
        cat_expires=item.get("catExpires")
    )


def safe_float(value: str) -> float:
    """Safely convert string to float, returning 0.0 on failure."""
    try:
        return float(value) if value else 0.0
    except ValueError:
        return 0.0


def extract_dimensions_from_text(text: str) -> Optional[str]:
    """Extract dimensions from description text."""
    if not text:
        return None
    
    patterns = [
        r'(\d+[\d\s/\.]*"\s*[HWLD]?\s*[x×]\s*[\d\s/\.]+"\s*[HWLD]?(?:\s*[x×]\s*[\d\s/\.]+"\s*[HWLD]?)?)',
        r'([\d.]+"\s*[HWLD]\s*[x×]\s*[\d.]+"\s*(?:Diameter|[HWLD]))',
        r'([\d.]+"\s*Diameter)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None


def enrich_products_with_net_costs(
    products: List[SAGEProduct],
    api_client: 'SAGEAPIClient',
    use_full_product_detail: bool = True,
    state_manager: Optional["JobStateManager"] = None
) -> List[SAGEProduct]:
    """
    Enrich products with authoritative net costs from Full Product Detail API.

    The Presentation API provides:
    - sellPrcs: SELL PRICE (what customer sees) <- TRUSTED for sell price
    - costs: Cost from presentation (may be adjusted by sales rep)

    The Full Product Detail API (serviceId 105) provides:
    - net: Authoritative NET COST from SAGE database <- TRUSTED for net cost

    This function calls the Full Product Detail API for each product and
    updates the net_cost values with the authoritative data.

    Args:
        products: List of products parsed from presentation
        api_client: SAGE API client
        use_full_product_detail: If True, call Full Product Detail API for net costs
        state_manager: Optional JobStateManager for state updates

    Returns:
        Enriched products with authoritative net costs
    """
    if not use_full_product_detail:
        logger.info("Skipping Full Product Detail enrichment (using presentation costs)")
        return products
    
    logger.info("=" * 60)
    logger.info("ENRICHING PRODUCTS WITH FULL PRODUCT DETAIL API")
    logger.info("=" * 60)
    logger.info(f"Products to enrich: {len(products)}")
    
    # First, check if the service is enabled by testing one product
    if products:
        test_product = products[0]
        # Prefer encrypted_prod_id for API calls, fall back to SPC
        test_id = test_product.encrypted_prod_id or test_product.spc
        if test_id:
            try:
                test_result = api_client.get_product_detail(test_id, include_supplier=False)
            except Exception as e:
                if "10010" in str(e) or "not currently enabled" in str(e):
                    logger.warning("=" * 60)
                    logger.warning("Full Product Detail API (serviceId 105) is NOT ENABLED")
                    logger.warning("To enable: SAGEmember.com → SAGE Connect → Services → Enable 'Full Product Detail'")
                    logger.warning("Using presentation costs as net_cost (may not be authoritative)")
                    logger.warning("=" * 60)
                    return products
    
    enriched_count = 0
    total_products = len(products)
    for idx, product in enumerate(products, 1):
        # Emit per-product progress
        if state_manager and WorkflowStatus:
            state_manager.update(
                WorkflowStatus.SAGE_ENRICHING_PRODUCTS.value,
                current_item=idx,
                total_items=total_products,
                current_item_name=product.name
            )

        # Get product ID - use encrypted_prod_id for API (required by Full Product Detail)
        # Fall back to SPC if no encrypted_prod_id
        encrypted_id = product.encrypted_prod_id
        spc = product.spc
        
        if not encrypted_id and not spc:
            logger.debug(f"No encrypted_prod_id or SPC for product: {product.name}")
            continue
        
        try:
            # Call Full Product Detail API
            # Use encrypted_prod_id (e.g., "987510533") not prod_id (e.g., 7510533)
            if encrypted_id:
                detail = api_client.get_product_detail(encrypted_id, include_supplier=False)
            else:
                # Use SPC if no encrypted_prod_id
                detail = api_client.get_product_detail(spc, include_supplier=False)
            
            if not detail:
                logger.info(f"  ✗ No detail returned for {product.name}")
                continue
            
            # Extract authoritative net costs from Full Product Detail
            net_costs = detail.get("net", [])
            qtys = detail.get("qty", [])

            logger.info(f"  Product: {product.name[:40]}...")
            logger.info(f"    Presentation qtys: {[pb.quantity for pb in product.price_breaks]}")
            logger.info(f"    Full Detail qtys: {qtys}")
            logger.info(f"    Full Detail net: {net_costs}")

            # === Extract additional fields from Full Product Detail API ===
            # Production Time (Lead Time)
            prod_time = detail.get("prodTime")
            if prod_time:
                product.prod_time = prod_time
                logger.debug(f"    Lead time: {prod_time}")

            # Decoration Method
            deco_method = detail.get("decorationMethod")
            if deco_method:
                product.decoration_method = deco_method
                logger.debug(f"    Decoration method: {deco_method}")

            # Imprint Areas
            imprint_area = detail.get("imprintArea")
            imprint_loc = detail.get("imprintLoc")
            if imprint_area:
                product.imprint_area = imprint_area
            if imprint_loc:
                product.imprint_loc = imprint_loc

            # Second Imprint Area
            second_area = detail.get("secondImprintArea")
            second_loc = detail.get("secondImprintLoc")
            if second_area:
                product.second_imprint_area = second_area
            if second_loc:
                product.second_imprint_loc = second_loc

            # Sustainability flags
            if detail.get("recyclable"):
                product.recyclable = True
            if detail.get("envFriendly"):
                product.env_friendly = True

            # Themes
            themes = detail.get("themes")
            if themes:
                product.themes = themes

            # Price Includes
            price_includes = detail.get("priceIncludes")
            if price_includes:
                product.price_includes = price_includes
            
            if net_costs and qtys:
                # Create a lookup of net costs by quantity
                net_by_qty = {}
                for i, qty_str in enumerate(qtys):
                    if qty_str and qty_str != "0":
                        try:
                            qty = int(qty_str.replace(",", ""))
                            net = float(net_costs[i]) if i < len(net_costs) and net_costs[i] else 0.0
                            net_by_qty[qty] = net
                        except (ValueError, IndexError):
                            continue
                
                # Update product price breaks with authoritative net costs
                for break_item in product.price_breaks:
                    if break_item.quantity in net_by_qty:
                        # Store the presentation cost as "presentation_cost" for audit
                        # Update net_cost with authoritative SAGE database value
                        old_cost = break_item.net_cost
                        new_cost = net_by_qty[break_item.quantity]
                        
                        if old_cost != new_cost:
                            logger.debug(
                                f"  {product.name} qty {break_item.quantity}: "
                                f"presentation_cost={old_cost} → net_cost={new_cost}"
                            )
                        break_item.net_cost = new_cost
                
                enriched_count += 1
                logger.debug(f"  ✓ Enriched: {product.name}")
            
        except Exception as e:
            logger.info(f"  ✗ Failed to enrich {product.name[:30]}: {e}")
            # Keep the presentation costs if API call fails
            continue
    
    logger.info(f"Enrichment complete: {enriched_count}/{len(products)} products updated")
    return products


# =============================================================================
# SAGE Handler
# =============================================================================

class SAGEHandler:
    """
    Handler for SAGE presentation links.
    
    This handler:
    1. Extracts presId from viewpresentation.com URL
    2. Calls SAGE Presentation API to get full data
    3. Returns normalized product data ready for Zoho integration
    """
    
    def __init__(
        self,
        presentation_url: str,
        acct_id: int = SAGE_ACCT_ID,
        login_id: str = SAGE_LOGIN_ID,
        auth_key: str = SAGE_AUTH_KEY,
        state_manager: Optional["JobStateManager"] = None
    ):
        """
        Initialize the SAGE handler.

        Args:
            presentation_url: URL of the SAGE presentation (viewpresentation.com)
            acct_id: SAGE account ID (default from config)
            login_id: SAGE login ID (default from config)
            auth_key: SAGE auth key (default from config)
            state_manager: Optional JobStateManager for state updates
        """
        self.presentation_url = presentation_url
        self.api_client = SAGEAPIClient(acct_id, login_id, auth_key)
        self.state_manager = state_manager

    def _update_state(self, status: str, **kwargs) -> None:
        """Update job state if state manager is available."""
        if self.state_manager and WorkflowStatus:
            self.state_manager.update(status, **kwargs)
    
    def process(
        self,
        use_scraper_fallback: bool = True,
        enrich_net_costs: bool = True
    ) -> SAGEResult:
        """
        Process the SAGE presentation.
        
        Args:
            use_scraper_fallback: If True, fall back to web scraping if API fails
            enrich_net_costs: If True, call Full Product Detail API for authoritative net costs
        
        Returns:
            SAGEResult with extracted product data
        """
        logger.info("=" * 60)
        logger.info("SAGE PRESENTATION HANDLER")
        logger.info("=" * 60)
        logger.info(f"URL: {self.presentation_url}")
        
        # Check if API URL is configured
        if not self.api_client.api_url:
            logger.warning("SAGE API URL not configured - using web scraper")
            if use_scraper_fallback:
                return self._process_with_scraper()
            else:
                return SAGEResult(
                    success=False,
                    presentation_url=self.presentation_url,
                    error="SAGE API URL not configured. Set SAGE_API_URL environment variable."
                )
        
        try:
            # Step 1: Extract presId from URL
            logger.info("Step 1: Extracting presentation ID from URL...")
            pres_id = extract_pres_id_from_url(self.presentation_url)
            logger.info(f"  Presentation ID: {pres_id}")
            
            # If pres_id is a string (sageconnect URL with alphanumeric code),
            # fall back to scraper since SAGE API expects numeric presId
            if isinstance(pres_id, str):
                logger.warning(f"Alphanumeric presentation code '{pres_id}' detected (sageconnect URL)")
                logger.warning("SAGE API requires numeric presId - falling back to web scraper")
                if use_scraper_fallback:
                    return self._process_with_scraper()
                else:
                    return SAGEResult(
                        success=False,
                        presentation_url=self.presentation_url,
                        error=f"sageconnect.sage.com URLs with alphanumeric codes require scraper. Code: {pres_id}"
                    )
            
            # Step 2: Call SAGE Presentation API (gets SELL PRICES)
            logger.info("Step 2: Calling SAGE Presentation API...")
            logger.info("  → sellPrcs = SELL PRICE (what customer sees)")
            logger.info("  → costs = Presentation cost (may be adjusted)")
            self._update_state(
                WorkflowStatus.SAGE_CALLING_API.value if WorkflowStatus else "sage_calling_api"
            )
            raw_data = self.api_client.get_presentation(pres_id)
            logger.info(f"  Items in presentation: {raw_data.get('itemCnt', 0)}")
            
            # Step 3: Parse response
            logger.info("Step 3: Parsing presentation data...")
            self._update_state(
                WorkflowStatus.SAGE_PARSING_RESPONSE.value if WorkflowStatus else "sage_parsing_response"
            )
            result = parse_presentation_response(raw_data, self.presentation_url)
            
            logger.info(f"  Title: {result.presentation_title}")
            logger.info(f"  Client: {result.client.name} @ {result.client.company}")
            logger.info(f"  Products extracted: {len(result.products)}")
            
            # Step 4: Enrich with Full Product Detail API (gets authoritative NET COSTS)
            # The presentation has costs, but Full Product Detail has the authoritative
            # net costs from SAGE's database
            if enrich_net_costs:
                logger.info("Step 4: Enriching with Full Product Detail API...")
                logger.info("  → net = NET COST (authoritative SAGE database cost)")
                self._update_state(
                    WorkflowStatus.SAGE_ENRICHING_PRODUCTS.value if WorkflowStatus else "sage_enriching_products",
                    current_item=0,
                    total_items=len(result.products)
                )
                result.products = enrich_products_with_net_costs(
                    result.products,
                    self.api_client,
                    use_full_product_detail=True,
                    state_manager=self.state_manager
                )
            else:
                logger.info("Step 4: Skipping Full Product Detail enrichment (using presentation costs)")
            
            # Update metadata to reflect pricing sources
            result.metadata["pricing_sources"] = {
                "sell_price": "From Presentation API (serviceId 301) - what customer sees",
                "net_cost": "From Full Product Detail API (serviceId 105) - authoritative distributor cost",
                "margin_calculation": "sell_price - net_cost = margin"
            }
            
            logger.info("=" * 60)
            logger.info("SAGE API PROCESSING COMPLETE")
            logger.info("=" * 60)
            
            return result
            
        except Exception as e:
            logger.error(f"SAGE API processing failed: {e}")
            
            if use_scraper_fallback:
                logger.info("Falling back to web scraper...")
                return self._process_with_scraper()
            
            return SAGEResult(
                success=False,
                presentation_url=self.presentation_url,
                error=str(e)
            )
        finally:
            self.api_client.close()
    
    def _process_with_scraper(self) -> SAGEResult:
        """
        Process using web scraper as fallback.
        
        Returns:
            SAGEResult from scraped data
        """
        try:
            from presentation_parser import scrape as scrape_presentation
            
            logger.info("Using web scraper for SAGE presentation...")
            presentation = scrape_presentation(self.presentation_url)
            
            logger.info(f"  Title: {presentation.title}")
            logger.info(f"  Client: {presentation.client_name} @ {presentation.client_company}")
            logger.info(f"  Products found: {len(presentation.products)}")
            
            # Convert scraped data to SAGEResult format
            products = []
            for p in presentation.products:
                price_breaks = [
                    SAGEPriceBreak(
                        quantity=pb.quantity,
                        catalog_price=pb.price,
                        sell_price=pb.price,
                        net_cost=0.0  # Not available from scraping
                    )
                    for pb in p.price_breaks
                ]
                
                products.append(SAGEProduct(
                    pres_item_id=0,
                    item_num=p.item_number,
                    name=p.title,
                    description=p.description,
                    colors=[c for c in p.colors] if p.colors else [],
                    price_breaks=price_breaks,
                    price_includes=p.price_includes,
                    additional_charges_text=p.additional_charges,
                    imprint_info_text=p.decoration_info,
                    dimensions=p.dimensions,
                    image_urls=p.image_urls
                ))
            
            result = SAGEResult(
                success=True,
                presentation_url=self.presentation_url,
                presentation_title=presentation.title,
                client=SAGEClient(
                    name=presentation.client_name,
                    company=presentation.client_company
                ),
                presenter=SAGEPresenter(
                    name=presentation.presenter_name or "Koell Collins",
                    company=presentation.presenter_company or "STBL Strategies",
                    phone=presentation.presenter_phone,
                    location=presentation.presenter_location
                ),
                products=products,
                metadata={
                    "source": "web_scraper",
                    "processed_at": datetime.now().isoformat(),
                    "item_count": len(products),
                    "note": "Data from web scraping - some fields unavailable (net_cost, internalItemNum, clientId)"
                }
            )
            
            logger.info("=" * 60)
            logger.info("SAGE SCRAPER PROCESSING COMPLETE")
            logger.info("=" * 60)
            
            return result
            
        except Exception as e:
            logger.error(f"SAGE scraper failed: {e}", exc_info=True)
            return SAGEResult(
                success=False,
                presentation_url=self.presentation_url,
                error=f"Both API and scraper failed: {str(e)}"
            )
    
    def to_dict(self, result: SAGEResult) -> Dict[str, Any]:
        """
        Convert SAGEResult to dictionary for JSON serialization.
        
        Args:
            result: SAGEResult to convert
            
        Returns:
            Dictionary representation matching ESP output format
        """
        # Convert products to match ESP output format
        products_list = []
        for p in result.products:
            # Build vendor object matching ESP format
            vendor = None
            if p.supplier:
                vendor = {
                    "name": p.supplier.name,
                    "sage_id": p.supplier.sage_id,
                    "website": p.supplier.website,
                    "line_name": p.supplier.line_name,
                    "email": p.supplier.email,
                    "phone": p.supplier.phone,
                    "city": p.supplier.city,
                    "state": p.supplier.state,
                    "zip": p.supplier.zip_code,
                    "my_customer_number": p.supplier.my_customer_number,
                    "my_cs_rep": p.supplier.my_cs_rep,
                    "my_cs_rep_email": p.supplier.my_cs_rep_email
                }
            
            # Build pricing breaks
            pricing_breaks = [
                {
                    "quantity": pb.quantity,
                    "catalog_price": pb.catalog_price,
                    "sell_price": pb.sell_price,
                    "net_cost": pb.net_cost
                }
                for pb in p.price_breaks
            ]
            
            # Build fees array
            fees = []
            if p.setup_charge > 0:
                fees.append({
                    "fee_type": "setup",
                    "name": "Setup Charge",
                    "price": p.setup_charge,
                    "price_code": p.setup_charge_code
                })
            if p.repeat_charge > 0:
                fees.append({
                    "fee_type": "reorder",
                    "name": "Repeat/Reorder Charge",
                    "price": p.repeat_charge
                })
            if p.proof_charge > 0:
                fees.append({
                    "fee_type": "proof",
                    "name": "Proof Charge",
                    "price": p.proof_charge
                })
            if p.pms_charge > 0:
                fees.append({
                    "fee_type": "pms_match",
                    "name": "PMS Match Charge",
                    "price": p.pms_charge
                })
            if p.spec_sample_charge > 0:
                fees.append({
                    "fee_type": "spec_sample",
                    "name": "Spec Sample Charge",
                    "price": p.spec_sample_charge
                })
            if p.copy_change_charge > 0:
                fees.append({
                    "fee_type": "copy_change",
                    "name": "Copy Change Charge",
                    "price": p.copy_change_charge
                })
            
            products_list.append({
                "identifiers": {
                    "pres_item_id": p.pres_item_id,
                    "prod_id": p.prod_id,
                    "encrypted_prod_id": p.encrypted_prod_id,
                    "internal_item_num": p.internal_item_num,  # MPN for Zoho!
                    "spc": p.spc,
                    "item_num": p.item_num
                },
                "item": {
                    "vendor_sku": p.internal_item_num,  # Use internal_item_num as vendor SKU
                    "mpn": p.internal_item_num,  # MPN for Purchase Orders
                    "name": p.name,
                    "description": p.description,
                    "category": p.category,
                    "colors": p.colors,
                    "dimensions": p.dimensions,
                    "themes": p.themes,
                    # Sustainability flags from Full Product Detail API
                    "recyclable": p.recyclable,
                    "env_friendly": p.env_friendly
                },
                "vendor": vendor,
                "pricing": {
                    "price_code": p.price_code,
                    "price_includes": p.price_includes,
                    "breaks": pricing_breaks
                },
                "fees": fees,
                "decoration": {
                    "imprint_info": p.imprint_info_text,
                    # From Full Product Detail API
                    "decoration_method": p.decoration_method,
                    "imprint_area": p.imprint_area,
                    "imprint_loc": p.imprint_loc,
                    "second_imprint_area": p.second_imprint_area,
                    "second_imprint_loc": p.second_imprint_loc
                },
                "shipping": {
                    "ship_point": p.ship_point,
                    "units_per_carton": p.units_per_carton,
                    "weight_per_carton": p.weight_per_carton,
                    "packaging": p.packaging_text,
                    # Lead Time from Full Product Detail API
                    "lead_time": p.prod_time
                },
                "images": p.image_urls,
                "additional_charges_text": p.additional_charges_text
            })
        
        return {
            "success": result.success,
            "source_platform": "sage",
            "presentation_url": result.presentation_url,
            "pres_id": result.pres_id,
            "metadata": {
                "generated_at": datetime.now().isoformat(),
            "presentation_title": result.presentation_title,
                "presentation_date": result.presentation_date,
                "total_items": len(result.products),
                **result.metadata
            },
            "client": {
                "id": result.client.client_id if result.client else None,
                "name": result.client.name if result.client else None,
                "company": result.client.company if result.client else None,
                "email": result.client.email if result.client else None,
                "phone": result.client.phone if result.client else None,
                "tax_rate": result.client.tax_rate if result.client else None
            },
            "presenter": {
                "name": result.presenter.name if result.presenter else "Koell Collins",
                "company": result.presenter.company if result.presenter else "STBL Strategies",
                "phone": result.presenter.phone if result.presenter else None,
                "website": result.presenter.website if result.presenter else None
            },
            "products": products_list,
            "error": result.error
        }


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point for testing the SAGE handler."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(
        description="Process SAGE presentation and extract product data"
    )
    parser.add_argument(
        "url",
        type=str,
        help="URL of the SAGE presentation (viewpresentation.com)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Validate URL
    if "viewpresentation.com" not in args.url:
        print("Warning: URL does not appear to be from viewpresentation.com", file=sys.stderr)
    
    # Process
    handler = SAGEHandler(presentation_url=args.url)
    result = handler.process()
    output_dict = handler.to_dict(result)
    
    # Output
    json_output = json.dumps(output_dict, indent=2, ensure_ascii=False)
    
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_output)
        print(f"Output saved to: {args.output}", file=sys.stderr)
    else:
        print(json_output)
    
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
