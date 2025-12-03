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
    computer_id: Optional[str] = None,
    dry_run: bool = False,
    skip_cua: bool = False
) -> Dict[str, Any]:
    """
    Execute the ESP pipeline.
    
    Flow:
    1. CUA downloads presentation PDF from portal.mypromooffice.com
    2. pdf_processor extracts product list from presentation PDF
    3. CUA logs into ESP+ and downloads Distributor Report for each product
    4. pdf_processor extracts full product data from each sell sheet
    5. Return aggregated structured output
    
    Args:
        url: ESP presentation URL
        computer_id: Orgo computer ID
        dry_run: If True, skip CUA execution
        skip_cua: If True, use existing PDFs
        
    Returns:
        Final output dictionary
    """
    from esp_presentation_downloader import ESPPresentationDownloader
    from esp_product_lookup import ESPProductLookup
    from pdf_processor import process_pdf, process_presentation_pdf
    from prompt import EXTRACTION_PROMPT
    from prompt_presentation import PRESENTATION_EXTRACTION_PROMPT
    
    logger.info("=" * 60)
    logger.info("ESP PIPELINE")
    logger.info("=" * 60)
    logger.info(f"URL: {url}")
    
    errors = []
    
    # Ensure output directory exists
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    pdfs_dir = output_dir / "pdfs"
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
        existing_pdfs = list(pdfs_dir.glob("esp_presentation*.pdf"))
        if existing_pdfs:
            presentation_pdf_path = str(existing_pdfs[0])
            logger.info(f"Using existing presentation PDF: {presentation_pdf_path}")
        else:
            logger.warning("No existing presentation PDF found")
    else:
        downloader = ESPPresentationDownloader(
            presentation_url=url,
            computer_id=computer_id,
            dry_run=dry_run
        )
        
        download_result = downloader.run()
        
        if download_result.success:
            # TODO: Retrieve file from Orgo VM
            # For now, record the remote path
            logger.info(f"Presentation PDF downloaded to VM: {download_result.remote_path}")
            # Placeholder: Would retrieve file here
            # presentation_pdf_path = retrieve_from_vm(download_result.remote_path)
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
                PRESENTATION_EXTRACTION_PROMPT
            )
            
            # Extract products list
            products_to_lookup = parsed_presentation.get("products", [])
            logger.info(f"Found {len(products_to_lookup)} products in presentation")
            
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
    
    if dry_run:
        logger.info("[DRY RUN] Skipping ESP+ product lookups")
    elif skip_cua:
        # Look for existing product PDFs
        existing_pdfs = list(pdfs_dir.glob("*_distributor_report.pdf"))
        downloaded_product_pdfs = [str(p) for p in existing_pdfs]
        logger.info(f"Found {len(downloaded_product_pdfs)} existing product PDFs")
    elif products_to_lookup:
        lookup = ESPProductLookup(
            products=products_to_lookup,
            computer_id=computer_id,
            dry_run=dry_run
        )
        
        lookup_result = lookup.run()
        
        logger.info(f"Lookup complete: {lookup_result.successful}/{lookup_result.total_products} successful")
        
        # TODO: Retrieve files from Orgo VM
        # For now, record the results
        for pdf_info in lookup_result.downloaded_pdfs:
            logger.info(f"  Downloaded: {pdf_info['sku']} -> {pdf_info['remote_path']}")
            # Placeholder: Would retrieve file here
            # local_path = retrieve_from_vm(pdf_info['remote_path'])
            # downloaded_product_pdfs.append(local_path)
        
        for error in lookup_result.errors:
            errors.append({
                "step": "product_lookup",
                "sku": error.get("sku"),
                "message": error.get("message")
            })
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
        
        for pdf_path in downloaded_product_pdfs:
            logger.info(f"Parsing: {pdf_path}")
            
            try:
                parsed_data = process_pdf(
                    pdf_path,
                    anthropic_client,
                    EXTRACTION_PROMPT
                )
                parsed_products.append(parsed_data)
                logger.info(f"  Success: {parsed_data.get('item', {}).get('name', 'Unknown')}")
                
            except Exception as e:
                logger.error(f"  Failed: {e}")
                parsed_products.append({
                    "error": str(e),
                    "source_file": pdf_path
                })
    else:
        logger.warning("No product PDFs to parse")
    
    # =========================================================================
    # Step 5: Generate Output
    # =========================================================================
    logger.info("=" * 60)
    logger.info("STEP 5: GENERATE OUTPUT")
    logger.info("=" * 60)
    
    final_output = create_zoho_ready_output(
        source_type="esp",
        presentation_data=presentation_data,
        products=parsed_products,
        errors=errors
    )
    
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
        dry_run: bool = False,
        skip_cua: bool = False
    ):
        """
        Initialize the orchestrator.
        
        Args:
            url: Presentation URL (SAGE or ESP)
            computer_id: Optional Orgo computer ID for ESP pipeline
            dry_run: If True, skip actual processing
            skip_cua: If True, use existing PDFs
        """
        self.url = url
        self.computer_id = computer_id
        self.dry_run = dry_run
        self.skip_cua = skip_cua
        
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
        logger.info(f"URL: {self.url}")
        logger.info(f"Detected Type: {self.presentation_type.value}")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info(f"Skip CUA: {self.skip_cua}")
        
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
                computer_id=self.computer_id,
                dry_run=self.dry_run,
                skip_cua=self.skip_cua
            )
        else:
            logger.error(f"Unknown presentation type for URL: {self.url}")
            result = {
                "success": False,
                "error": f"Unknown presentation URL type. Supported domains: {SAGE_PRESENTATION_DOMAIN}, portal.mypromooffice.com"
            }
        
        # Save output to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pipeline_name = self.presentation_type.value
        output_filename = f"{pipeline_name}_output_{timestamp}.json"
        output_path = Path(OUTPUT_DIR) / output_filename
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Output saved to: {output_path}")
        
        # Summary
        logger.info("=" * 60)
        logger.info("ORCHESTRATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Pipeline: {pipeline_name}")
        logger.info(f"Products: {len(result.get('products', []))}")
        logger.info(f"Errors: {len(result.get('errors', []))}")
        logger.info(f"Ready for Zoho: {result.get('ready_for_zoho', False)}")
        
        return result


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

Supported URL Patterns:
  SAGE:  viewpresentation.com/*
  ESP:   portal.mypromooffice.com/*

Environment Variables:
  ORGO_API_KEY          Orgo API key (required for ESP pipeline)
  ANTHROPIC_API_KEY     Anthropic API key (required)
  ORGO_COMPUTER_ID      Default Orgo computer ID
  ESP_PLUS_EMAIL        ESP+ login email
  ESP_PLUS_PASSWORD     ESP+ login password
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
        dry_run=args.dry_run,
        skip_cua=args.skip_cua
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

