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
    
    if SAGE_PRESENTATION_DOMAIN in domain or "viewpresentation" in domain:
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
    # Index presentation products by CPN for fast lookup
    presentation_by_cpn = {}
    for pres_prod in presentation_products:
        cpn = pres_prod.get("cpn") or ""
        if cpn:
            presentation_by_cpn[cpn] = pres_prod
    
    merged_products = []
    
    for dist_prod in distributor_products:
        # Skip error entries
        if "error" in dist_prod:
            merged_products.append(dist_prod)
            continue
        
        # Try to find matching presentation product by CPN
        cpn = dist_prod.get("cpn") or ""
        pres_prod = presentation_by_cpn.get(cpn)
        
        if pres_prod:
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
            
            # Merge sell_price into distributor breaks
            for break_item in dist_breaks:
                qty = break_item.get("quantity")
                if qty in pres_prices_by_qty:
                    break_item["sell_price"] = pres_prices_by_qty[qty]
                    # Ensure we have the field labeled correctly
                    # net_cost should already be there from distributor report
            
            # Also copy presentation-level data that might be missing
            if not dist_prod.get("presentation_sell_data"):
                dist_prod["presentation_sell_data"] = {
                    "price_range": pres_prod.get("price_range"),
                    "price_includes": pres_prod.get("price_includes"),
                    "pricing_breaks": pres_pricing_breaks,
                    "additional_charges": pres_prod.get("additional_charges", [])
                }
            
            logger.debug(f"Merged sell prices for CPN {cpn}")
        else:
            logger.debug(f"No presentation match for CPN {cpn}")
        
        merged_products.append(dist_prod)
    
    return merged_products


# =============================================================================
# SAGE Pipeline
# =============================================================================

def run_sage_pipeline(
    url: str,
    dry_run: bool = False
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
    
    # Initialize and run SAGE handler
    handler = SAGEHandler(
        presentation_url=url,
        sage_api_key=SAGE_API_KEY,
        sage_api_secret=SAGE_API_SECRET
    )
    
    result = handler.process()
    
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
            "name": result.client_name,
            "company": result.client_company
        },
        "presenter": {
            "name": result.presenter_name,
            "company": result.presenter_company
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
    if not result.api_enriched:
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
    limit_products: Optional[int] = None
) -> Dict[str, Any]:
    """
    Execute the ESP pipeline.
    
    Flow:
    1. CUA downloads presentation PDF from portal.mypromooffice.com and uploads to S3
    2. pdf_processor extracts product list from presentation PDF
    3. CUA logs into ESP+ and downloads Distributor Report for each product to S3
    4. pdf_processor extracts full product data from each sell sheet
    5. Return aggregated structured output
    
    Args:
        url: ESP presentation URL
        job_id: Unique job identifier for S3 organization
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
    from s3_handler import S3Handler
    
    logger.info("=" * 60)
    logger.info("ESP PIPELINE")
    logger.info("=" * 60)
    logger.info(f"Job ID: {job_id}")
    logger.info(f"URL: {url}")
    
    errors = []
    
    # Initialize S3 handler
    s3_handler = S3Handler(job_id=job_id)
    logger.info(f"S3 bucket: {s3_handler.bucket}")
    
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
    
    presentation_pdf_path = None
    
    if dry_run:
        logger.info("[DRY RUN] Skipping presentation download")
    elif skip_cua:
        # Look for existing presentation PDF
        existing_pdfs = list(pdfs_dir.glob("presentation*.pdf"))
        if existing_pdfs:
            presentation_pdf_path = str(existing_pdfs[0])
            logger.info(f"Using existing presentation PDF: {presentation_pdf_path}")
        else:
            # Try to download from S3
            try:
                local_path = str(pdfs_dir / "presentation.pdf")
                s3_handler.download_file("presentation.pdf", local_path)
                presentation_pdf_path = local_path
                logger.info(f"Downloaded presentation PDF from S3: {local_path}")
            except FileNotFoundError:
                logger.warning("No existing presentation PDF found in S3")
    else:
        # Generate pre-signed upload URL for the presentation PDF
        upload_url = s3_handler.generate_presigned_upload_url("presentation.pdf")
        logger.info(f"Generated upload URL for presentation.pdf")
        
        downloader = ESPPresentationDownloader(
            presentation_url=url,
            job_id=job_id,
            upload_url=upload_url,
            computer_id=computer_id,
            dry_run=dry_run
        )
        
        download_result = downloader.run()
        
        if download_result.success:
            logger.info(f"Presentation PDF uploaded to S3: {download_result.remote_path}")
            
            # Download the file from S3 to local
            try:
                local_path = str(pdfs_dir / "presentation.pdf")
                s3_handler.download_file("presentation.pdf", local_path)
                presentation_pdf_path = local_path
                logger.info(f"Downloaded presentation PDF from S3 to: {local_path}")
            except Exception as e:
                errors.append({
                    "step": "presentation_download_s3",
                    "message": f"Failed to download from S3: {str(e)}"
                })
                logger.error(f"Failed to download presentation PDF from S3: {e}")
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
            parsed_presentation = process_pdf(
                presentation_pdf_path,
                anthropic_client,
                PRESENTATION_EXTRACTION_PROMPT,
                max_tokens=32768  # Opus 4.5 supports up to 64k output tokens
            )
            
            # Extract products list
            products_to_lookup = parsed_presentation.get("products", [])
            logger.info(f"Found {len(products_to_lookup)} products in presentation")
            
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
            # Try to download from S3
            try:
                downloaded_files = s3_handler.download_directory("products", str(products_dir))
                downloaded_product_pdfs = downloaded_files
                logger.info(f"Downloaded {len(downloaded_product_pdfs)} product PDFs from S3")
            except Exception as e:
                logger.warning(f"Could not download from S3: {e}")
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
                # Generate upload URL for this single product
                upload_url_map = s3_handler.generate_product_upload_urls([cpn])
                logger.info(f"Generated upload URL for {cpn}")
                
                # Create CUA agent for this single product
                lookup = ESPProductLookup(
                    products=[product],
                    job_id=job_id,
                    upload_url_map=upload_url_map,
                    computer_id=computer_id,
                    dry_run=dry_run,
                    product_index=idx,
                    total_products=total_products,
                    is_first_product=(idx == 1)  # Only first product needs full login
                )
                
                # Run the CUA agent for this product
                lookup_result = lookup.run()
                
                if lookup_result.successful > 0:
                    logger.info(f"✓ Product {idx}/{total_products} ({cpn}): Upload successful")
                    successful_uploads += 1
                else:
                    logger.warning(f"✗ Product {idx}/{total_products} ({cpn}): Upload failed")
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
        
        # Batch download all successfully uploaded product PDFs from S3
        try:
            downloaded_files = s3_handler.download_directory("products", str(products_dir))
            downloaded_product_pdfs = downloaded_files
            logger.info(f"Downloaded {len(downloaded_product_pdfs)} product PDFs from S3")
        except Exception as e:
            errors.append({
                "step": "product_download_s3",
                "message": f"Failed to download products from S3: {str(e)}"
            })
            logger.error(f"Failed to download product PDFs from S3: {e}")
    else:
        logger.warning("No products to look up")
    
    # =========================================================================
    # Step 4: Parse Product PDFs
    # =========================================================================
    logger.info("=" * 60)
    logger.info("STEP 4: PARSE PRODUCT PDFs")
    logger.info("=" * 60)
    
    parsed_products = []
    
    if downloaded_product_pdfs:
        anthropic_client = Anthropic()
        total_pdfs = len(downloaded_product_pdfs)
        successful_parses = 0
        failed_parses = 0
        
        for idx, pdf_path in enumerate(downloaded_product_pdfs, 1):
            logger.info(f"Parsing [{idx}/{total_pdfs}]: {pdf_path}")
            
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
                
            except Exception as e:
                logger.error(f"  ✗ Failed: {e}")
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
        limit_products: Optional[int] = None
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
        """
        self.url = url
        self.computer_id = computer_id
        self.dry_run = dry_run
        self.skip_cua = skip_cua
        self.limit_products = limit_products
        
        # Generate or use provided job ID
        self.job_id = job_id or f"esp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Detect presentation type
        self.presentation_type = detect_presentation_type(url)
        
        # Ensure output directory exists
        Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
        
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
        
        # Validate config if needed
        if not self.dry_run and self.presentation_type == PresentationType.ESP:
            validate_config()
        
        # Route to appropriate pipeline
        if self.presentation_type == PresentationType.SAGE:
            result = run_sage_pipeline(
                url=self.url,
                dry_run=self.dry_run
            )
        elif self.presentation_type == PresentationType.ESP:
            result = run_esp_pipeline(
                url=self.url,
                job_id=self.job_id,
                computer_id=self.computer_id,
                dry_run=self.dry_run,
                skip_cua=self.skip_cua,
                limit_products=self.limit_products
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
        
        try:
            # Normalize to unified format for downstream Zoho/Calculator workflows
            normalized_result = normalize_output(result, source=pipeline_name)
            logger.info(f"Normalization successful - unified schema applied")
        except Exception as e:
            logger.warning(f"Normalization failed: {e}. Saving raw output.")
            normalized_result = result
        
        # Save normalized (unified) output
        output_filename = f"unified_output_{pipeline_name}_{timestamp}.json"
        output_path = Path(OUTPUT_DIR) / output_filename
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(normalized_result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Unified output saved to: {output_path}")
        
        # Also save raw output for debugging/reference
        raw_output_filename = f"raw_{pipeline_name}_output_{timestamp}.json"
        raw_output_path = Path(OUTPUT_DIR) / raw_output_filename
        
        with open(raw_output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Raw output saved to: {raw_output_path}")
        
        # Summary
        logger.info("=" * 60)
        logger.info("ORCHESTRATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Pipeline: {pipeline_name}")
        logger.info(f"Products: {len(normalized_result.get('products', []))}")
        logger.info(f"Errors: {len(normalized_result.get('errors', []))}")
        logger.info(f"Source: {normalized_result.get('metadata', {}).get('source', 'unknown')}")
        logger.info(f"Unified schema: YES - ready for Zoho/Calculator")
        
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

Supported URL Patterns:
  SAGE:  viewpresentation.com/*
  ESP:   portal.mypromooffice.com/*

Environment Variables:
  ORGO_API_KEY          Orgo API key (required for ESP pipeline)
  ANTHROPIC_API_KEY     Anthropic API key (required)
  ORGO_COMPUTER_ID      Default Orgo computer ID
  ESP_PLUS_EMAIL        ESP+ login email
  ESP_PLUS_PASSWORD     ESP+ login password
  AWS_ACCESS_KEY_ID     AWS access key ID (required for ESP pipeline)
  AWS_SECRET_ACCESS_KEY AWS secret access key (required for ESP pipeline)
  AWS_REGION            AWS region (default: us-east-1)
  AWS_S3_BUCKET         S3 bucket name for file storage (required for ESP pipeline)
  SAGE_API_KEY          SAGE API key (optional, for future enrichment)
  SAGE_API_SECRET       SAGE API secret (optional)
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
        help="Job ID for S3 organization (auto-generated if not provided)"
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
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and run orchestrator
    orchestrator = Orchestrator(
        url=args.url,
        computer_id=args.computer_id,
        job_id=args.job_id,
        dry_run=args.dry_run,
        skip_cua=args.skip_cua,
        limit_products=args.limit_products
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

