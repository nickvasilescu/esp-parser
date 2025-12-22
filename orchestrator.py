#!/usr/bin/env python3
"""
Multi-Source Orchestrator
=========================

Entry point that routes presentation URLs to the appropriate pipeline:
- SAGE (viewpresentation.com) → sage_handler.py → [SAGE API placeholder] → Output
- ESP (portal.mypromooffice.com) → CUA download → pdf_processor → CUA lookup → pdf_processor → Output

Usage:
    python orchestrator.py <presentation_url>
    python orchestrator.py https://www.viewpresentation.com/66907679185
    python orchestrator.py https://portal.mypromooffice.com/projects/500187876/presentations/500183020/products
"""

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from anthropic import Anthropic

from config import (
    validate_config,
    OUTPUT_DIR,
    SAGE_PRESENTATION_DOMAIN,
    ESP_PORTAL_URL,
    SAGE_API_KEY,
    SAGE_API_SECRET,
    get_config_summary,
)
from output_normalizer import normalize_output, detect_source
from job_state import JobStateManager, WorkflowStatus

# Zoho integration (optional - only import if needed)
ZOHO_AVAILABLE = False
ZOHO_QUOTE_AVAILABLE = False
try:
    from zoho_item_agent import ZohoItemMasterAgent, AgentResult
    from zoho_config import validate_zoho_config, ZOHO_ORG_ID
    ZOHO_AVAILABLE = True
except ImportError:
    ZOHO_ORG_ID = None

try:
    from zoho_quote_agent import ZohoQuoteAgent, QuoteResult
    ZOHO_QUOTE_AVAILABLE = True
except ImportError:
    pass

# Calculator Generator (optional - for client-facing Excel calculators)
CALCULATOR_AVAILABLE = False
try:
    from calculator_generator import CalculatorGeneratorAgent, CalculatorResult
    CALCULATOR_AVAILABLE = True
except ImportError:
    pass


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('orchestrator.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# URL Routing
# =============================================================================

class PresentationType(Enum):
    """Supported presentation types."""
    SAGE = "sage"
    ESP = "esp"
    UNKNOWN = "unknown"


def detect_presentation_type(url: str) -> PresentationType:
    """
    Detect the presentation type from URL.
    
    Args:
        url: Presentation URL
        
    Returns:
        PresentationType enum value
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    if SAGE_PRESENTATION_DOMAIN in domain or "viewpresentation" in domain or "sageconnect.sage.com" in domain:
        return PresentationType.SAGE
    elif "mypromooffice.com" in domain or "portal." in domain:
        return PresentationType.ESP
    else:
        return PresentationType.UNKNOWN


# =============================================================================
# Output Structure
# =============================================================================

def create_zoho_ready_output(
    source_type: str,
    presentation_data: Dict[str, Any],
    products: List[Dict[str, Any]],
    errors: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Create the final output structure ready for Zoho/Calculator integration.
    
    Args:
        source_type: "sage" or "esp"
        presentation_data: Metadata about the presentation
        products: List of processed product data
        errors: List of errors encountered
        
    Returns:
        Complete output structure ready for downstream processing
    """
    return {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "source_type": source_type,
            "presentation_url": presentation_data.get("url"),
            "presentation_title": presentation_data.get("title"),
            "client": presentation_data.get("client", {}),
            "presenter": presentation_data.get("presenter", {}),
            "total_items_in_presentation": presentation_data.get("total_items", 0),
            "total_items_processed": len([p for p in products if "error" not in p]),
            "total_errors": len(errors)
        },
        "products": products,
        "errors": errors,
        "ready_for_zoho": True,
        "zoho_integration_notes": {
            "item_master": "Each product can be created as an Item in Zoho Books",
            "quote_line_items": "For each product, create 3 line items: Product, Setup Fee, Estimated Shipping",
            "sku_format": "[Client Account #] - [Vendor Item #]",
            "track_inventory": False
        }
    }


def merge_presentation_and_product_data(
    presentation_products: List[Dict[str, Any]],
    distributor_products: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Merge presentation data (sell prices) with distributor report data (net costs).
    
    The presentation PDF shows what the CLIENT sees → SELL PRICE (trusted source)
    The distributor report shows what the DISTRIBUTOR pays → NET COST (trusted source)
    
    Args:
        presentation_products: Products from prompt_presentation.py (has sell prices)
        distributor_products: Products from prompt.py (has net costs)
        
    Returns:
        Merged products with both sell_price and net_cost
    """
    # Helper to normalize CPN (strip "CPN-" prefix if present)
    def normalize_cpn(cpn: str) -> str:
        if cpn and cpn.upper().startswith("CPN-"):
            return cpn[4:]  # Remove "CPN-" prefix
        return cpn
    
    # Index presentation products by CPN for fast lookup
    # Index both with and without "CPN-" prefix for flexible matching
    presentation_by_cpn = {}
    for pres_prod in presentation_products:
        cpn = pres_prod.get("cpn") or ""
        if cpn:
            # Store with original key
            presentation_by_cpn[cpn] = pres_prod
            # Also store with normalized key (without CPN- prefix)
            normalized = normalize_cpn(cpn)
            if normalized != cpn:
                presentation_by_cpn[normalized] = pres_prod
    
    logger.info(f"Merge: {len(presentation_by_cpn)} presentation products indexed by CPN")
    logger.info(f"Merge: {len(distributor_products)} distributor products to process")
    
    merged_products = []
    merge_stats = {
        "matched": 0,
        "unmatched": 0,
        "prices_merged": 0,
        "prices_missing": 0
    }
    
    for dist_prod in distributor_products:
        # Skip error entries
        if "error" in dist_prod:
            merged_products.append(dist_prod)
            continue
        
        # Try to find matching presentation product by CPN
        # CPN can be at root level or nested in item object
        cpn = dist_prod.get("item", {}).get("cpn") or dist_prod.get("cpn") or ""
        # Try exact match first, then normalized (without CPN- prefix)
        pres_prod = presentation_by_cpn.get(cpn) or presentation_by_cpn.get(normalize_cpn(cpn))
        
        if pres_prod:
            merge_stats["matched"] += 1
            # Merge sell prices from presentation into distributor product
            pres_pricing_breaks = pres_prod.get("pricing_breaks", [])
            dist_pricing = dist_prod.get("pricing", {})
            dist_breaks = dist_pricing.get("breaks", [])
            
            # Create lookup of presentation sell prices by quantity
            pres_prices_by_qty = {}
            for pb in pres_pricing_breaks:
                qty = pb.get("quantity")
                # Support both "sell_price" (new schema) and "price" (legacy)
                sell_price = pb.get("sell_price") or pb.get("price")
                if qty is not None:
                    pres_prices_by_qty[qty] = sell_price
            
            logger.debug(f"CPN {cpn}: Presentation has {len(pres_prices_by_qty)} price breaks: {list(pres_prices_by_qty.keys())}")
            
            # Merge sell_price into distributor breaks
            prices_merged_for_product = 0
            for break_item in dist_breaks:
                # Handle both 'quantity' (normalized) and 'min_qty' (raw ESP format)
                qty = break_item.get("quantity") or break_item.get("min_qty")
                if qty in pres_prices_by_qty:
                    break_item["sell_price"] = pres_prices_by_qty[qty]
                    prices_merged_for_product += 1
                    logger.debug(f"  Merged sell_price={pres_prices_by_qty[qty]} for qty={qty}")
                else:
                    logger.debug(f"  No price match for qty={qty} (available: {list(pres_prices_by_qty.keys())})")
            
            if prices_merged_for_product > 0:
                merge_stats["prices_merged"] += 1
                logger.info(f"Merge SUCCESS: CPN {cpn} - {prices_merged_for_product} sell prices merged")
            else:
                merge_stats["prices_missing"] += 1
                logger.warning(f"Merge PARTIAL: CPN {cpn} matched but NO sell prices merged (qty mismatch?)")
            
            # Also copy presentation-level data that might be missing
            if not dist_prod.get("presentation_sell_data"):
                dist_prod["presentation_sell_data"] = {
                    "price_range": pres_prod.get("price_range"),
                    "price_includes": pres_prod.get("price_includes"),
                    "pricing_breaks": pres_pricing_breaks,
                    "additional_charges": pres_prod.get("additional_charges", [])
                }
        else:
            merge_stats["unmatched"] += 1
            logger.warning(f"Merge FAILED: CPN '{cpn}' not found in presentation data (available: {list(presentation_by_cpn.keys())})")
        
        merged_products.append(dist_prod)
    
    # Log merge summary
    logger.info("=" * 40)
    logger.info("MERGE SUMMARY")
    logger.info(f"  Products matched by CPN: {merge_stats['matched']}")
    logger.info(f"  Products unmatched: {merge_stats['unmatched']}")
    logger.info(f"  Products with sell prices merged: {merge_stats['prices_merged']}")
    logger.info(f"  Products with missing sell prices: {merge_stats['prices_missing']}")
    logger.info("=" * 40)
    
    if merge_stats["prices_missing"] > 0 or merge_stats["unmatched"] > 0:
        logger.warning("Some products may be missing sell prices - check logs above for details")
    
    return merged_products


# =============================================================================
# SAGE Pipeline
# =============================================================================

def run_sage_pipeline(
    url: str,
    dry_run: bool = False,
    state_manager: Optional[JobStateManager] = None
) -> Dict[str, Any]:
    """
    Execute the SAGE pipeline.
    
    Flow:
    1. Scrape presentation using presentation_parser.py (via sage_handler)
    2. [Placeholder] Enrich with SAGE API
    3. Return structured output
    
    Args:
        url: SAGE presentation URL
        dry_run: If True, skip actual processing
        
    Returns:
        Final output dictionary
    """
    from sage_handler import SAGEHandler
    
    logger.info("=" * 60)
    logger.info("SAGE PIPELINE")
    logger.info("=" * 60)
    logger.info(f"URL: {url}")

    if dry_run:
        logger.info("[DRY RUN] Would process SAGE presentation")
        return {
            "success": False,
            "error": "Dry run mode",
            "pipeline": "sage"
        }

    # Emit state: calling SAGE API
    if state_manager:
        state_manager.update(WorkflowStatus.SAGE_CALLING_API.value)

    # Initialize and run SAGE handler
    # SAGEHandler uses SAGE Connect API with defaults from environment/hardcoded values
    handler = SAGEHandler(
        presentation_url=url,
        state_manager=state_manager
    )

    result = handler.process()

    # Emit state: parsing response
    if state_manager:
        state_manager.update(WorkflowStatus.SAGE_PARSING_RESPONSE.value)
    
    if not result.success:
        return {
            "success": False,
            "error": result.error,
            "pipeline": "sage"
        }
    
    # Convert to output format
    products = [asdict(p) for p in result.products]
    
    presentation_data = {
        "url": url,
        "title": result.presentation_title,
        "client": {
            "name": result.client.name if result.client else None,
            "company": result.client.company if result.client else None
        },
        "presenter": {
            "name": result.presenter.name if result.presenter else None,
            "company": result.presenter.company if result.presenter else None
        },
        "total_items": len(products)
    }
    
    final_output = create_zoho_ready_output(
        source_type="sage",
        presentation_data=presentation_data,
        products=products,
        errors=[]
    )
    
    # Note about API enrichment
    if not result.metadata.get("api_enriched", False):
        final_output["sage_api_note"] = (
            "Product data was scraped from presentation only. "
            "Full enrichment via SAGE API pending developer access."
        )
    
    return final_output


# =============================================================================
# ESP Pipeline
# =============================================================================

def run_esp_pipeline(
    url: str,
    job_id: str,
    computer_id: Optional[str] = None,
    dry_run: bool = False,
    skip_cua: bool = False,
    limit_products: Optional[int] = None,
    state_manager: Optional[JobStateManager] = None
) -> Dict[str, Any]:
    """
    Execute the ESP pipeline.

    Flow:
    1. CUA downloads presentation PDF from portal.mypromooffice.com to Orgo VM
    2. Orgo File Export API retrieves the PDF for local processing
    3. pdf_processor extracts product list from presentation PDF
    4. CUA logs into ESP+ and downloads Distributor Report for each product to Orgo VM
    5. Orgo File Export API retrieves each product PDF for local processing
    6. pdf_processor extracts full product data from each sell sheet
    7. Return aggregated structured output

    Args:
        url: ESP presentation URL
        job_id: Unique job identifier for file organization
        computer_id: Orgo computer ID
        dry_run: If True, skip CUA execution
        skip_cua: If True, use existing PDFs
        limit_products: If set, only process this many products (useful for testing)

    Returns:
        Final output dictionary
    """
    from esp_presentation_downloader import ESPPresentationDownloader
    from esp_product_lookup import ESPProductLookup
    from pdf_processor import process_pdf, process_presentation_pdf
    from prompt import EXTRACTION_PROMPT
    from prompt_presentation import PRESENTATION_EXTRACTION_PROMPT
    from orgo_file_handler import OrgoFileHandler
    from config import ORGO_COMPUTER_ID
    
    logger.info("=" * 60)
    logger.info("ESP PIPELINE")
    logger.info("=" * 60)
    logger.info(f"Job ID: {job_id}")
    logger.info(f"URL: {url}")

    errors = []

    # Use provided computer_id or default from config
    effective_computer_id = computer_id or ORGO_COMPUTER_ID

    # Initialize Orgo file handler (used after CUA completes to export files from VM)
    file_handler = OrgoFileHandler(job_id=job_id, computer_id=effective_computer_id)
    logger.info(f"Orgo File Handler initialized for computer: {effective_computer_id}")
    
    # Ensure output directory exists
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    pdfs_dir = output_dir / "pdfs" / job_id
    pdfs_dir.mkdir(parents=True, exist_ok=True)
    
    # =========================================================================
    # Step 1: Download ESP Presentation PDF
    # =========================================================================
    logger.info("=" * 60)
    logger.info("STEP 1: DOWNLOAD ESP PRESENTATION PDF")
    logger.info("=" * 60)

    # Emit state: downloading presentation
    if state_manager:
        state_manager.update(WorkflowStatus.ESP_DOWNLOADING_PRESENTATION.value)

    presentation_pdf_path = None

    if dry_run:
        logger.info("[DRY RUN] Skipping presentation download")
    elif skip_cua:
        # Look for existing presentation PDF locally first
        existing_pdfs = list(pdfs_dir.glob("presentation*.pdf"))
        if existing_pdfs:
            presentation_pdf_path = str(existing_pdfs[0])
            logger.info(f"Using existing presentation PDF: {presentation_pdf_path}")
        else:
            # Try to export from VM via Orgo API
            try:
                local_path = str(pdfs_dir / "presentation.pdf")
                file_handler.download_presentation(local_path)
                presentation_pdf_path = local_path
                logger.info(f"Exported presentation PDF from VM: {local_path}")
            except FileNotFoundError:
                logger.warning("No existing presentation PDF found on VM")
    else:
        # CUA downloads presentation to VM's local storage
        downloader = ESPPresentationDownloader(
            presentation_url=url,
            job_id=job_id,
            computer_id=effective_computer_id,
            dry_run=dry_run,
            state_manager=state_manager
        )

        download_result = downloader.run()

        if download_result.success:
            logger.info(f"Presentation PDF saved to VM: {download_result.remote_path}")

            # Emit state: exporting from VM
            if state_manager:
                state_manager.update(WorkflowStatus.ESP_DOWNLOADING_PRODUCTS.value)
                state_manager.set_link("presentation_pdf", download_result.remote_path)

            # Export the file from VM via Orgo API
            try:
                local_path = str(pdfs_dir / "presentation.pdf")
                file_handler.download_presentation(local_path)
                presentation_pdf_path = local_path
                logger.info(f"Exported presentation PDF from VM to: {local_path}")
            except Exception as e:
                errors.append({
                    "step": "presentation_export",
                    "message": f"Failed to export from VM: {str(e)}"
                })
                logger.error(f"Failed to export presentation PDF from VM: {e}")
        else:
            errors.append({
                "step": "presentation_download",
                "message": download_result.error
            })
            logger.error(f"Failed to download presentation: {download_result.error}")
    
    # =========================================================================
    # Step 2: Parse Presentation PDF to Get Product List
    # =========================================================================
    logger.info("=" * 60)
    logger.info("STEP 2: PARSE PRESENTATION PDF")
    logger.info("=" * 60)

    # Emit state: parsing presentation
    if state_manager:
        state_manager.update(WorkflowStatus.ESP_PARSING_PRESENTATION.value)

    products_to_lookup = []
    presentation_data = {
        "url": url,
        "title": None,
        "client": {},
        "presenter": {},
        "total_items": 0
    }
    
    if presentation_pdf_path:
        try:
            anthropic_client = Anthropic()

            logger.info(f"Parsing presentation PDF: {presentation_pdf_path}")

            # Emit thought for Claude parser starting
            if state_manager:
                state_manager.emit_thought(
                    agent="claude_parser",
                    event_type="action",
                    content="Analyzing presentation PDF to extract product list",
                    metadata={"pdf_path": presentation_pdf_path}
                )

            parsed_presentation = process_pdf(
                presentation_pdf_path,
                anthropic_client,
                PRESENTATION_EXTRACTION_PROMPT,
                max_tokens=32768  # Opus 4.5 supports up to 64k output tokens
            )

            # Extract products list
            products_to_lookup = parsed_presentation.get("products", [])
            logger.info(f"Found {len(products_to_lookup)} products in presentation")

            # Emit success thought
            if state_manager:
                state_manager.emit_thought(
                    agent="claude_parser",
                    event_type="success",
                    content=f"Extracted {len(products_to_lookup)} products from presentation",
                    details={"product_count": len(products_to_lookup)}
                )
            
            # Apply product limit if specified (useful for testing)
            if limit_products is not None and limit_products > 0:
                original_count = len(products_to_lookup)
                products_to_lookup = products_to_lookup[:limit_products]
                logger.info(f"LIMITED to first {limit_products} product(s) (was {original_count})")
            
            # Extract presentation metadata
            pres_meta = parsed_presentation.get("presentation", {})
            presentation_data = {
                "url": url,
                "title": pres_meta.get("title"),
                "client": {
                    "name": pres_meta.get("client_name"),
                    "company": pres_meta.get("client_company")
                },
                "presenter": {
                    "name": pres_meta.get("presenter_name"),
                    "company": pres_meta.get("presenter_company")
                },
                "total_items": len(products_to_lookup)
            }
            
            # Save presentation extraction output for debugging
            pres_output_path = output_dir / f"presentation_extract_{job_id}.json"
            with open(pres_output_path, 'w') as f:
                json.dump(parsed_presentation, f, indent=2)
            logger.info(f"Saved presentation extraction to: {pres_output_path}")
            
        except Exception as e:
            errors.append({
                "step": "presentation_parse",
                "message": str(e)
            })
            logger.error(f"Failed to parse presentation PDF: {e}")
    else:
        logger.warning("No presentation PDF available to parse")
    
    # =========================================================================
    # Step 3: Download Product PDFs from ESP+
    # =========================================================================
    logger.info("=" * 60)
    logger.info("STEP 3: DOWNLOAD PRODUCT PDFs FROM ESP+")
    logger.info("=" * 60)

    # Emit state: looking up products
    if state_manager and products_to_lookup:
        state_manager.update(
            WorkflowStatus.ESP_LOOKING_UP_PRODUCTS.value,
            current_item=0,
            total_items=len(products_to_lookup)
        )

    downloaded_product_pdfs = []
    products_dir = pdfs_dir / "products"
    products_dir.mkdir(parents=True, exist_ok=True)
    
    if dry_run:
        logger.info("[DRY RUN] Skipping ESP+ product lookups")
    elif skip_cua:
        # Look for existing product PDFs locally first
        existing_pdfs = list(products_dir.glob("*_distributor_report.pdf"))
        if existing_pdfs:
            downloaded_product_pdfs = [str(p) for p in existing_pdfs]
            logger.info(f"Found {len(downloaded_product_pdfs)} existing product PDFs locally")
        else:
            # Try to export from VM for each product (if we have products_to_lookup)
            logger.info("Attempting to export product PDFs from VM...")
            for product in products_to_lookup:
                cpn = product.get("cpn") or product.get("sku") or ""
                if cpn:
                    try:
                        local_path = str(products_dir / f"{cpn}_distributor_report.pdf")
                        file_handler.download_product_pdf(cpn, local_path)
                        downloaded_product_pdfs.append(local_path)
                        logger.info(f"Exported {cpn} from VM")
                    except Exception as e:
                        logger.warning(f"Could not export {cpn} from VM: {e}")
    elif products_to_lookup:
        # =====================================================================
        # SEQUENTIAL CUA AGENT PROCESSING
        # Each product gets its own CUA agent session for reliability
        # =====================================================================
        total_products = len(products_to_lookup)
        successful_uploads = 0
        failed_uploads = 0
        
        logger.info(f"Processing {total_products} products sequentially (one CUA agent per product)")
        
        for idx, product in enumerate(products_to_lookup, 1):
            cpn = product.get("cpn") or product.get("sku") or product.get("item_number") or ""
            product_name = product.get("name") or product.get("title") or "Unknown"
            
            logger.info("-" * 60)
            logger.info(f"PRODUCT {idx}/{total_products}: {cpn}")
            logger.info(f"Name: {product_name}")
            logger.info("-" * 60)

            # Emit per-product progress
            if state_manager:
                state_manager.update(
                    WorkflowStatus.ESP_LOOKING_UP_PRODUCTS.value,
                    current_item=idx,
                    total_items=total_products,
                    current_item_name=product_name
                )

            if not cpn:
                logger.warning(f"Skipping product {idx} - no CPN/SKU found")
                errors.append({
                    "step": "product_lookup",
                    "sku": "unknown",
                    "message": f"Product {idx} has no CPN/SKU"
                })
                failed_uploads += 1
                continue
            
            try:
                # Create CUA agent for this single product
                # CUA saves PDF to VM, we'll export it after all products are done
                lookup = ESPProductLookup(
                    products=[product],
                    job_id=job_id,
                    computer_id=effective_computer_id,
                    dry_run=dry_run,
                    product_index=idx,
                    total_products=total_products,
                    is_first_product=(idx == 1),  # Only first product needs full login
                    state_manager=state_manager
                )

                # Run the CUA agent for this product
                lookup_result = lookup.run()

                if lookup_result.successful > 0:
                    logger.info(f"✓ Product {idx}/{total_products} ({cpn}): Saved to VM")
                    successful_uploads += 1
                else:
                    logger.warning(f"✗ Product {idx}/{total_products} ({cpn}): Failed")
                    failed_uploads += 1
                    for error in lookup_result.errors:
                        errors.append({
                            "step": "product_lookup",
                            "sku": error.get("sku", cpn),
                            "message": error.get("message", "Unknown error")
                        })
                
            except Exception as e:
                logger.error(f"✗ Product {idx}/{total_products} ({cpn}): Exception - {e}")
                errors.append({
                    "step": "product_lookup",
                    "sku": cpn,
                    "message": str(e)
                })
                failed_uploads += 1
                # Continue to next product even if this one failed
                continue
        
        logger.info("=" * 60)
        logger.info(f"PRODUCT LOOKUP SUMMARY")
        logger.info(f"  Total: {total_products}")
        logger.info(f"  Successful: {successful_uploads}")
        logger.info(f"  Failed: {failed_uploads}")
        logger.info("=" * 60)

        # Emit state: exporting products from VM
        if state_manager:
            state_manager.update(WorkflowStatus.ESP_DOWNLOADING_PRODUCTS.value)

        # Export all product PDFs from VM via Orgo File Export API
        logger.info("Exporting product PDFs from VM...")
        for product in products_to_lookup:
            cpn = product.get("cpn") or product.get("sku") or ""
            if cpn:
                try:
                    local_path = str(products_dir / f"{cpn}_distributor_report.pdf")
                    file_handler.download_product_pdf(cpn, local_path)
                    downloaded_product_pdfs.append(local_path)
                    logger.info(f"  ✓ Exported: {cpn}")
                except Exception as e:
                    errors.append({
                        "step": "product_export",
                        "sku": cpn,
                        "message": f"Failed to export from VM: {str(e)}"
                    })
                    logger.warning(f"  ✗ Failed to export {cpn}: {e}")
    else:
        logger.warning("No products to look up")
    
    # =========================================================================
    # Step 4: Parse Product PDFs
    # =========================================================================
    logger.info("=" * 60)
    logger.info("STEP 4: PARSE PRODUCT PDFs")
    logger.info("=" * 60)

    # Emit state: parsing products
    if state_manager and downloaded_product_pdfs:
        state_manager.update(
            WorkflowStatus.ESP_PARSING_PRODUCTS.value,
            current_item=0,
            total_items=len(downloaded_product_pdfs)
        )

    parsed_products = []

    if downloaded_product_pdfs:
        anthropic_client = Anthropic()
        total_pdfs = len(downloaded_product_pdfs)
        successful_parses = 0
        failed_parses = 0
        
        for idx, pdf_path in enumerate(downloaded_product_pdfs, 1):
            logger.info(f"Parsing [{idx}/{total_pdfs}]: {pdf_path}")
            pdf_stem = Path(pdf_path).stem

            # Emit per-PDF progress
            if state_manager:
                state_manager.update(
                    WorkflowStatus.ESP_PARSING_PRODUCTS.value,
                    current_item=idx,
                    total_items=total_pdfs,
                    current_item_name=pdf_stem
                )
                # Emit thought for starting parse
                state_manager.emit_thought(
                    agent="claude_parser",
                    event_type="action",
                    content=f"Parsing distributor report: {pdf_stem}",
                    metadata={"pdf_index": idx, "total_pdfs": total_pdfs}
                )

            try:
                parsed_data = process_pdf(
                    pdf_path,
                    anthropic_client,
                    EXTRACTION_PROMPT
                )
                parsed_products.append(parsed_data)
                product_name = parsed_data.get('item', {}).get('name', 'Unknown')
                logger.info(f"  ✓ Success: {product_name}")
                successful_parses += 1

                # Emit success thought
                if state_manager:
                    state_manager.emit_thought(
                        agent="claude_parser",
                        event_type="success",
                        content=f"Extracted data for: {product_name}",
                        metadata={"pdf_index": idx, "product_name": product_name}
                    )

            except Exception as e:
                logger.error(f"  ✗ Failed: {e}")

                # Emit error thought
                if state_manager:
                    state_manager.emit_thought(
                        agent="claude_parser",
                        event_type="error",
                        content=f"Failed to parse: {pdf_stem}",
                        details={"error": str(e)}
                    )

                # Add to parsed_products with error flag
                parsed_products.append({
                    "error": str(e),
                    "source_file": pdf_path
                })
                # Also add to errors list for comprehensive tracking
                errors.append({
                    "step": "product_parse",
                    "source_file": pdf_path,
                    "message": str(e)
                })
                failed_parses += 1
        
        logger.info(f"PDF Parsing complete: {successful_parses} successful, {failed_parses} failed")
    else:
        logger.warning("No product PDFs to parse")
    
    # =========================================================================
    # Step 5: Merge Presentation + Product Data
    # =========================================================================
    logger.info("=" * 60)
    logger.info("STEP 5: MERGE PRESENTATION & PRODUCT DATA")
    logger.info("=" * 60)

    # Emit state: merging data
    if state_manager:
        state_manager.update(WorkflowStatus.ESP_MERGING_DATA.value)
        state_manager.emit_thought(
            agent="orchestrator",
            event_type="checkpoint",
            content="Merging presentation sell prices with distributor net costs",
            metadata={
                "presentation_products": len(products_to_lookup),
                "distributor_products": len(parsed_products)
            }
        )

    # CRITICAL MERGE:
    # - Presentation PDF (prompt_presentation.py) = SELL PRICE (what customer sees)
    # - Distributor Report (prompt.py) = NET COST (what distributor pays)
    # Both are needed for Zoho quotes and margin calculation
    
    if products_to_lookup and parsed_products:
        logger.info(f"Merging {len(products_to_lookup)} presentation products with {len(parsed_products)} distributor products")
        merged_products = merge_presentation_and_product_data(
            presentation_products=products_to_lookup,
            distributor_products=parsed_products
        )
        logger.info(f"Merge complete: {len(merged_products)} products")
    else:
        merged_products = parsed_products
        if not products_to_lookup:
            logger.warning("No presentation products to merge (sell prices may be missing)")
    
    # =========================================================================
    # Step 6: Generate Output
    # =========================================================================
    logger.info("=" * 60)
    logger.info("STEP 6: GENERATE OUTPUT")
    logger.info("=" * 60)
    
    final_output = create_zoho_ready_output(
        source_type="esp",
        presentation_data=presentation_data,
        products=merged_products,
        errors=errors
    )
    
    # Add pricing source notes for downstream consumers
    final_output["pricing_sources"] = {
        "sell_price": "From presentation PDF (what client sees)",
        "net_cost": "From distributor report PDF (what distributor pays)",
        "margin_calculation": "sell_price - net_cost = margin"
    }
    
    return final_output


# =============================================================================
# Main Orchestrator
# =============================================================================

class Orchestrator:
    """
    Main orchestrator that routes URLs to appropriate pipelines.
    """
    
    def __init__(
        self,
        url: str,
        computer_id: Optional[str] = None,
        job_id: Optional[str] = None,
        dry_run: bool = False,
        skip_cua: bool = False,
        limit_products: Optional[int] = None,
        zoho_upload: bool = False,
        zoho_dry_run: bool = False,
        zoho_quote: bool = False,
        calculator: bool = False,
        output_dir: str = OUTPUT_DIR,
        client_email: Optional[str] = None
    ):
        """
        Initialize the orchestrator.

        Args:
            url: Presentation URL (SAGE or ESP)
            computer_id: Optional Orgo computer ID for ESP pipeline
            job_id: Optional job ID (auto-generated if not provided)
            dry_run: If True, skip actual processing
            skip_cua: If True, use existing PDFs
            limit_products: If set, only process this many products (useful for testing)
            zoho_upload: If True, upload items to Zoho Item Master after normalization
            zoho_dry_run: If True, validate Zoho upload but don't actually upload
            zoho_quote: If True, create draft quote in Zoho Books after Item Master upload
            calculator: If True, generate client calculator Excel and upload to Zoho WorkDrive
            output_dir: Directory for output files
            client_email: Optional client email for Zoho contact lookup
        """
        self.url = url
        self.computer_id = computer_id
        self.dry_run = dry_run
        self.skip_cua = skip_cua
        self.limit_products = limit_products
        self.zoho_upload = zoho_upload
        self.zoho_dry_run = zoho_dry_run
        self.zoho_quote = zoho_quote
        self.calculator = calculator
        self.output_dir = output_dir
        self.client_email = client_email
        
        # Generate or use provided job ID
        self.job_id = job_id or f"esp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Detect presentation type
        self.presentation_type = detect_presentation_type(url)

        # Ensure output directory exists
        Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

        # Initialize state manager for dashboard tracking
        self.state_manager = JobStateManager(
            job_id=self.job_id,
            output_dir=Path(OUTPUT_DIR),
            platform=self.presentation_type.value.upper() if self.presentation_type != PresentationType.UNKNOWN else "",
            zoho_upload=zoho_upload,
            zoho_quote=zoho_quote,
            calculator=calculator,
        )

        logger.info(get_config_summary())
    
    def run(self) -> Dict[str, Any]:
        """
        Execute the appropriate pipeline based on URL type.
        
        Returns:
            Final output dictionary
        """
        logger.info("=" * 60)
        logger.info("MULTI-SOURCE ORCHESTRATOR")
        logger.info("=" * 60)
        logger.info(f"Job ID: {self.job_id}")
        logger.info(f"URL: {self.url}")
        logger.info(f"Detected Type: {self.presentation_type.value}")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info(f"Skip CUA: {self.skip_cua}")
        logger.info(f"Limit Products: {self.limit_products or 'ALL'}")

        # Emit checkpoint for orchestrator start
        self.state_manager.emit_thought(
            agent="orchestrator",
            event_type="checkpoint",
            content=f"Starting {self.presentation_type.value.upper()} pipeline",
            metadata={"job_id": self.job_id, "url": self.url}
        )

        # Emit state: detecting source
        self.state_manager.update(WorkflowStatus.DETECTING_SOURCE.value)

        # Validate config if needed
        if not self.dry_run and self.presentation_type == PresentationType.ESP:
            validate_config()

        # Route to appropriate pipeline
        if self.presentation_type == PresentationType.SAGE:
            result = run_sage_pipeline(
                url=self.url,
                dry_run=self.dry_run,
                state_manager=self.state_manager
            )
        elif self.presentation_type == PresentationType.ESP:
            result = run_esp_pipeline(
                url=self.url,
                job_id=self.job_id,
                computer_id=self.computer_id,
                dry_run=self.dry_run,
                skip_cua=self.skip_cua,
                limit_products=self.limit_products,
                state_manager=self.state_manager
            )
        else:
            logger.error(f"Unknown presentation type for URL: {self.url}")
            result = {
                "success": False,
                "error": f"Unknown presentation URL type. Supported domains: {SAGE_PRESENTATION_DOMAIN}, portal.mypromooffice.com"
            }
        
        # Normalize output to unified schema
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pipeline_name = self.presentation_type.value

        logger.info("=" * 60)
        logger.info("NORMALIZING OUTPUT TO UNIFIED SCHEMA")
        logger.info("=" * 60)

        # Emit state: normalizing
        self.state_manager.update(WorkflowStatus.NORMALIZING.value)

        try:
            # Normalize to unified format for downstream Zoho/Calculator workflows
            normalized_result = normalize_output(result, source=pipeline_name)
            logger.info(f"Normalization successful - unified schema applied")
        except Exception as e:
            logger.warning(f"Normalization failed: {e}. Saving raw output.")
            normalized_result = result
        
        # Emit state: saving output
        self.state_manager.update(WorkflowStatus.SAVING_OUTPUT.value)

        # Save normalized (unified) output
        output_filename = f"unified_output_{pipeline_name}_{timestamp}.json"
        output_path = Path(OUTPUT_DIR) / output_filename

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(normalized_result, f, indent=2, ensure_ascii=False)

        # Set output JSON link
        self.state_manager.set_link("output_json", str(output_path))

        logger.info(f"Unified output saved to: {output_path}")
        
        # Also save raw output for debugging/reference
        raw_output_filename = f"raw_{pipeline_name}_output_{timestamp}.json"
        raw_output_path = Path(OUTPUT_DIR) / raw_output_filename
        
        with open(raw_output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Raw output saved to: {raw_output_path}")
        
        # =========================================================================
        # Optional: Zoho Item Master Upload
        # =========================================================================
        zoho_result = None
        if self.zoho_upload:
            logger.info("=" * 60)
            logger.info("ZOHO ITEM MASTER UPLOAD")
            logger.info("=" * 60)
            
            if not ZOHO_AVAILABLE:
                logger.error("Zoho integration not available. Install zoho_item_agent module.")
            else:
                try:
                    # Validate Zoho configuration
                    validate_zoho_config()

                    # Emit state: searching customer
                    self.state_manager.update(WorkflowStatus.ZOHO_SEARCHING_CUSTOMER.value)

                    # Create and run agent (agent will emit more granular states internally)
                    zoho_agent = ZohoItemMasterAgent(
                        state_manager=self.state_manager,
                        client_email=self.client_email
                    )
                    zoho_result = zoho_agent.process_unified_output(
                        normalized_result,
                        dry_run=self.zoho_dry_run
                    )
                    
                    # Add Zoho result to normalized output
                    normalized_result["zoho_upload_result"] = {
                        "success": zoho_result.success,
                        "total_products": zoho_result.total_products,
                        "successful_uploads": zoho_result.successful_uploads,
                        "failed_uploads": zoho_result.failed_uploads,
                        "duration_seconds": zoho_result.duration_seconds,
                        "errors": zoho_result.errors
                    }
                    
                    # Save updated output with Zoho results
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(normalized_result, f, indent=2, ensure_ascii=False)
                    
                    logger.info(f"Zoho upload complete: {zoho_result.successful_uploads}/{zoho_result.total_products} items")
                    
                except Exception as e:
                    logger.error(f"Zoho upload failed: {e}")
                    normalized_result["zoho_upload_result"] = {
                        "success": False,
                        "error": str(e)
                    }

        # =========================================================================
        # Optional: Zoho Quote Creation
        # =========================================================================
        quote_result = None
        if self.zoho_quote:
            logger.info("=" * 60)
            logger.info("ZOHO QUOTE CREATION")
            logger.info("=" * 60)

            if not ZOHO_QUOTE_AVAILABLE:
                logger.error("Zoho Quote Agent not available. Install zoho_quote_agent module.")
            else:
                try:
                    # Validate Zoho configuration
                    validate_zoho_config()

                    # Emit state: creating quote
                    self.state_manager.update(WorkflowStatus.ZOHO_CREATING_QUOTE.value)

                    # Build item_master_map from previous upload results
                    item_master_map = {}
                    if zoho_result and hasattr(zoho_result, 'items'):
                        for item in zoho_result.items:
                            if item.zoho_sku and item.item_id:
                                item_master_map[item.zoho_sku] = item.item_id
                        logger.info(f"Item Master map: {len(item_master_map)} entries for linking")

                    # Create and run quote agent
                    quote_agent = ZohoQuoteAgent(state_manager=self.state_manager)
                    quote_result = quote_agent.create_quote(
                        unified_output=normalized_result,
                        item_master_map=item_master_map,
                        dry_run=self.zoho_dry_run
                    )

                    # Add Quote result to normalized output
                    normalized_result["zoho_quote_result"] = {
                        "success": quote_result.success,
                        "estimate_id": quote_result.estimate_id,
                        "estimate_number": quote_result.estimate_number,
                        "customer_id": quote_result.customer_id,
                        "customer_name": quote_result.customer_name,
                        "total_amount": quote_result.total_amount,
                        "line_items_count": quote_result.line_items_count,
                        "duration_seconds": quote_result.duration_seconds,
                        "error": quote_result.error
                    }

                    # Save updated output with Quote results
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(normalized_result, f, indent=2, ensure_ascii=False)

                    if quote_result.success:
                        total_str = f"${quote_result.total_amount:.2f}" if quote_result.total_amount else "N/A"
                        logger.info(f"Quote created: {quote_result.estimate_number} ({total_str})")

                        # Set the Zoho quote link in job state
                        if quote_result.estimate_id and ZOHO_ORG_ID:
                            quote_url = f"https://books.zoho.com/app/{ZOHO_ORG_ID}/estimates/{quote_result.estimate_id}"
                            self.state_manager.set_link("zoho_quote", quote_url)
                    else:
                        logger.error(f"Quote creation failed: {quote_result.error}")

                except Exception as e:
                    logger.error(f"Zoho quote creation failed: {e}")
                    normalized_result["zoho_quote_result"] = {
                        "success": False,
                        "error": str(e)
                    }

        # =========================================================================
        # Optional: Calculator Generation
        # =========================================================================
        calc_result = None
        if self.calculator:
            logger.info("=" * 60)
            logger.info("CALCULATOR GENERATION")
            logger.info("=" * 60)

            if not CALCULATOR_AVAILABLE:
                logger.error("Calculator Generator not available. Install calculator_generator module.")
            else:
                try:
                    # Emit state: generating calculator
                    self.state_manager.update(WorkflowStatus.CALC_GENERATING.value)

                    # Import zoho_client for WorkDrive upload
                    from zoho_client import ZohoClient
                    zoho_client = ZohoClient()

                    calc_agent = CalculatorGeneratorAgent(zoho_client=zoho_client, state_manager=self.state_manager)
                    calc_result = calc_agent.generate_calculator(
                        unified_output=normalized_result,
                        output_dir=self.output_dir,
                        dry_run=self.zoho_dry_run
                    )

                    # Add Calculator result to normalized output
                    normalized_result["calculator_result"] = {
                        "success": calc_result.success,
                        "file_name": calc_result.file_name,
                        "file_path": calc_result.file_path,
                        "drive_file_id": calc_result.drive_file_id,
                        "drive_permalink": calc_result.drive_permalink,
                        "products_count": calc_result.products_count,
                        "duration_seconds": calc_result.duration_seconds,
                        "error": calc_result.error
                    }

                    # Save updated output with Calculator results
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(normalized_result, f, indent=2, ensure_ascii=False)

                    if calc_result.success:
                        logger.info(f"Calculator generated: {calc_result.file_name}")
                        if calc_result.drive_permalink:
                            logger.info(f"Drive link: {calc_result.drive_permalink}")
                    else:
                        logger.error(f"Calculator generation failed: {calc_result.error}")

                except Exception as e:
                    logger.error(f"Calculator generation failed: {e}")
                    normalized_result["calculator_result"] = {
                        "success": False,
                        "error": str(e)
                    }

        # Emit final state: completed
        has_errors = len(normalized_result.get('errors', [])) > 0
        has_products = len(normalized_result.get('products', [])) > 0

        if has_errors and has_products:
            self.state_manager.complete(WorkflowStatus.PARTIAL_SUCCESS.value)
        elif has_errors and not has_products:
            self.state_manager.complete(WorkflowStatus.ERROR.value)
        else:
            self.state_manager.complete(WorkflowStatus.COMPLETED.value)

        # Emit completion thought
        self.state_manager.emit_thought(
            agent="orchestrator",
            event_type="success",
            content=f"Pipeline complete: {len(normalized_result.get('products', []))} products processed",
            metadata={
                "pipeline": pipeline_name,
                "products": len(normalized_result.get('products', [])),
                "errors": len(normalized_result.get('errors', []))
            }
        )

        # Summary
        logger.info("=" * 60)
        logger.info("ORCHESTRATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Pipeline: {pipeline_name}")
        logger.info(f"Products: {len(normalized_result.get('products', []))}")
        logger.info(f"Errors: {len(normalized_result.get('errors', []))}")
        logger.info(f"Source: {normalized_result.get('metadata', {}).get('source', 'unknown')}")
        logger.info(f"Unified schema: YES - ready for Zoho/Calculator")
        if zoho_result:
            logger.info(f"Zoho Upload: {zoho_result.successful_uploads}/{zoho_result.total_products} items uploaded")
        if quote_result:
            if quote_result.success:
                total_str = f"${quote_result.total_amount:.2f}" if quote_result.total_amount else "N/A"
                logger.info(f"Zoho Quote: {quote_result.estimate_number} - {total_str} ({quote_result.line_items_count} line items)")
            else:
                logger.info(f"Zoho Quote: FAILED - {quote_result.error}")
        if calc_result:
            if calc_result.success:
                logger.info(f"Calculator: {calc_result.file_name} ({calc_result.products_count} products)")
                if calc_result.drive_permalink:
                    logger.info(f"Calculator Link: {calc_result.drive_permalink}")
            else:
                logger.info(f"Calculator: FAILED - {calc_result.error}")

        return normalized_result  # Return unified format for downstream workflows


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point for the orchestrator."""
    parser = argparse.ArgumentParser(
        description="Multi-Source Orchestrator - Route presentation URLs to appropriate extraction pipelines",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # SAGE presentation (viewpresentation.com)
  %(prog)s https://www.viewpresentation.com/66907679185
  
  # ESP presentation (portal.mypromooffice.com)
  %(prog)s https://portal.mypromooffice.com/projects/500187876/presentations/500183020/products
  
  # Dry run (no actual processing)
  %(prog)s <url> --dry-run
  
  # Use existing PDFs (skip CUA downloads)
  %(prog)s <url> --skip-cua
  
  # Test end-to-end with only the first product
  %(prog)s <url> --limit-products 1
  
  # Process and upload to Zoho Item Master
  %(prog)s <url> --zoho-upload
  
  # Validate Zoho upload without actually uploading
  %(prog)s <url> --zoho-dry-run
  
  # Full workflow: skip CUA, upload to Zoho
  %(prog)s <url> --skip-cua --zoho-upload

  # Create draft quote in Zoho Books (implies --zoho-upload)
  %(prog)s <url> --zoho-quote

  # Full workflow: skip CUA, upload to Zoho, create quote
  %(prog)s <url> --skip-cua --zoho-upload --zoho-quote

  # Generate client calculator spreadsheet
  %(prog)s <url> --calculator

  # Full workflow with calculator
  %(prog)s <url> --zoho-upload --zoho-quote --calculator

Supported URL Patterns:
  SAGE:  viewpresentation.com/*
  ESP:   portal.mypromooffice.com/*

Environment Variables:
  ORGO_API_KEY          Orgo API key (required for ESP pipeline)
  ANTHROPIC_API_KEY     Anthropic API key (required)
  ORGO_COMPUTER_ID      Default Orgo computer ID (required for ESP pipeline)
  ESP_PLUS_EMAIL        ESP+ login email
  ESP_PLUS_PASSWORD     ESP+ login password
  SAGE_API_KEY          SAGE API key (optional, for future enrichment)
  SAGE_API_SECRET       SAGE API secret (optional)
  
  Zoho Integration (required for --zoho-upload):
  ZOHO_ORG_ID           Zoho organization ID
  ZOHO_CLIENT_ID        Zoho OAuth client ID
  ZOHO_CLIENT_SECRET    Zoho OAuth client secret
  ZOHO_REFRESH_TOKEN    Zoho OAuth refresh token
        """
    )
    
    parser.add_argument(
        "url",
        type=str,
        help="Presentation URL (SAGE or ESP)"
    )
    
    parser.add_argument(
        "--computer-id",
        type=str,
        help="Orgo computer ID to use (overrides ORGO_COMPUTER_ID env var)"
    )
    
    parser.add_argument(
        "--job-id",
        type=str,
        help="Job ID for file organization (auto-generated if not provided)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (skip actual processing)"
    )
    
    parser.add_argument(
        "--skip-cua",
        action="store_true",
        help="Skip CUA downloads (use existing PDFs)"
    )
    
    parser.add_argument(
        "--limit-products",
        type=int,
        default=None,
        help="Limit to first N products (useful for testing end-to-end with --limit-products 1)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--output-json",
        action="store_true",
        help="Print final output as JSON to stdout"
    )
    
    parser.add_argument(
        "--zoho-upload",
        action="store_true",
        help="Upload items to Zoho Item Master after normalization"
    )
    
    parser.add_argument(
        "--zoho-dry-run",
        action="store_true",
        help="Validate Zoho upload without actually uploading (implies --zoho-upload)"
    )

    parser.add_argument(
        "--zoho-quote",
        action="store_true",
        help="Create draft quote in Zoho Books after Item Master upload"
    )

    parser.add_argument(
        "--calculator",
        action="store_true",
        help="Generate client calculator spreadsheet and upload to Zoho WorkDrive"
    )

    parser.add_argument(
        "--client-email",
        type=str,
        help="Client email address for Zoho contact lookup (passed from email trigger)"
    )

    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Handle Zoho flags
    zoho_upload = args.zoho_upload or args.zoho_dry_run
    # If quote is requested, automatically enable upload (need Item Master entries)
    if args.zoho_quote and not zoho_upload:
        zoho_upload = True
        logger.info("--zoho-quote implies --zoho-upload (Item Master entries needed for linking)")

    # Create and run orchestrator
    orchestrator = Orchestrator(
        url=args.url,
        computer_id=args.computer_id,
        job_id=args.job_id,
        dry_run=args.dry_run,
        skip_cua=args.skip_cua,
        limit_products=args.limit_products,
        zoho_upload=zoho_upload,
        zoho_dry_run=args.zoho_dry_run,
        zoho_quote=args.zoho_quote,
        calculator=args.calculator,
        client_email=args.client_email
    )
    
    try:
        result = orchestrator.run()
        
        if args.output_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Exit with appropriate code
        if result.get("success") is False or result.get("error"):
            sys.exit(1)
        
    except KeyboardInterrupt:
        logger.warning("Orchestration interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

