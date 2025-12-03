#!/usr/bin/env python3
"""
ESP Product Lookup CUA Agent
============================

Uses Orgo to log into ESP+ and download Distributor Report sell sheets for a list of products.
This is CUA Agent 2 in the ESP pipeline.

Usage:
    from esp_product_lookup import ESPProductLookup
    
    products = [{"sku": "CE053", "name": "Water Bottle"}, ...]
    lookup = ESPProductLookup(products)
    result = lookup.run()
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from orgo import Computer

from config import (
    ORGO_COMPUTER_ID,
    DISPLAY_WIDTH,
    DISPLAY_HEIGHT,
    MODEL_ID,
    THINKING_BUDGET,
    MAX_ITERATIONS,
    MAX_TOKENS,
    REMOTE_DOWNLOAD_DIR,
    ESP_PLUS_EMAIL,
    ESP_PLUS_PASSWORD,
    ESP_PLUS_URL,
)
from agent_tools import AgentTools, TOOLS_SCHEMA, create_tool_handler

logger = logging.getLogger(__name__)


# =============================================================================
# Data Types
# =============================================================================

@dataclass
class ProductToLookup:
    """A product to look up in ESP+."""
    cpn: str  # CPN (Customer Product Number) - e.g., "CPN-564949909"
    name: str
    supplier_name: Optional[str] = None
    supplier_asi: Optional[str] = None
    description: Optional[str] = None


@dataclass
class LookupResult:
    """Result of the ESP+ product lookup operation."""
    total_products: int
    successful: int
    failed: int
    downloaded_pdfs: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)


# =============================================================================
# Prompt Builder
# =============================================================================

def build_lookup_prompt(products: List[ProductToLookup]) -> str:
    """
    Build the CUA prompt for looking up products in ESP+.
    
    Args:
        products: List of products to look up
    
    Returns:
        Formatted prompt string for the CUA
    """
    # Build product list for the prompt
    product_list = []
    for i, product in enumerate(products, 1):
        entry = f"{i}. CPN: {product.cpn or 'N/A'}\n   Name: {product.name}"
        if product.supplier_name:
            entry += f"\n   Supplier: {product.supplier_name}"
        if product.supplier_asi:
            entry += f" (ASI: {product.supplier_asi})"
        product_list.append(entry)
    
    products_text = "\n".join(product_list)
    
    prompt = f"""You are a product data extraction agent. Your goal is to log into ESP Plus, find each product listed below, and download their Distributor Report PDFs.

IMPORTANT CONTEXT:
- You are controlling a Linux desktop environment
- Firefox browser is available
- You must save PDFs to: {REMOTE_DOWNLOAD_DIR}
- Use descriptive filenames like: [CPN]_distributor_report.pdf (e.g., CPN-564949909_distributor_report.pdf)

ESP PLUS CREDENTIALS:
- URL: {ESP_PLUS_URL}
- Email: {ESP_PLUS_EMAIL}
- Password: {ESP_PLUS_PASSWORD}

=============================================================================
PRODUCTS TO PROCESS ({len(products)} items)
=============================================================================

{products_text}

=============================================================================
WORKFLOW
=============================================================================

PHASE 1: LOGIN TO ESP PLUS
1. Open Firefox browser
2. Navigate to: {ESP_PLUS_URL}
3. Login using the credentials provided above:
   - Enter email: {ESP_PLUS_EMAIL}
   - Enter password: {ESP_PLUS_PASSWORD}
4. Wait for the dashboard to load
5. Take a screenshot to confirm successful login

PHASE 2: PROCESS EACH PRODUCT
For EACH product in the list above:

1. SEARCH for the product:
   - Use the CPN (Customer Product Number) if available - this is the most reliable
   - The CPN format is like "CPN-564949909" - you can search with or without the "CPN-" prefix
   - If CPN search fails, try the product name
   - If supplier info is provided, filter by supplier to narrow results

2. NAVIGATE to the product detail page:
   - Click on the matching product in search results
   - Verify you're on the correct product by checking CPN/name

3. DOWNLOAD THE DISTRIBUTOR REPORT:
   - Look for a "Print" button or menu
   - Select "Distributor Report" or similar option
   - Save/Print as PDF to: {REMOTE_DOWNLOAD_DIR}
   - Use filename format: [CPN]_distributor_report.pdf
   - Example: CPN-564949909_distributor_report.pdf

4. REPORT THE DOWNLOAD:
   - Call the `report_downloaded_pdf` tool with:
     - sku: The product CPN (e.g., "CPN-564949909")
     - remote_path: Full path to the saved PDF
     - product_name: The product name

5. HANDLE ERRORS:
   - If a product cannot be found, call `log_error` with:
     - sku: The product CPN (or "unknown")
     - message: Description of what went wrong
   - Continue to the next product

6. MOVE TO NEXT PRODUCT:
   - Return to ESP Plus search
   - Repeat steps 1-5 for the next item

PHASE 3: COMPLETION
After processing ALL products:
1. Call `report_completion` with:
   - total_processed: Total number of products attempted
   - successful: Number of PDFs successfully downloaded
   - failed: Number of products that failed
   - summary: Brief description of the session
2. Take a final screenshot showing completion

=============================================================================
SEARCH TIPS
=============================================================================

1. **CPN Search** (most reliable):
   - Enter the CPN exactly as shown (e.g., "CPN-564949909" or just "564949909")
   - Look for "CPN", "Item #", or "Product #" fields

2. **Name Search** (fallback):
   - Use key product terms, not the full name
   - Example: For "Etched Pinot Noir Red Wine Bottle"
     Try: "Etched Pinot Noir" or "Wine Bottle Etched"

3. **Supplier Filter**:
   - If supplier ASI is known, use it to filter
   - Helps when multiple suppliers have similar products

=============================================================================
DISTRIBUTOR REPORT DOWNLOAD TIPS
=============================================================================

1. **Finding the Print/Export button**:
   - Usually in the product detail page header
   - May be under a "..." or gear icon menu
   - Look for: Print, Export, Download, PDF

2. **Selecting Distributor Report**:
   - Often there are multiple report options
   - "Distributor Report" contains net cost info
   - "Client Report" or "Presentation" may not have full data

3. **Saving the PDF**:
   - Browser may show a print dialog
   - Select "Save as PDF" or "Print to PDF"
   - Ensure file is saved to {REMOTE_DOWNLOAD_DIR}

=============================================================================
AVAILABLE TOOLS
=============================================================================

1. `report_downloaded_pdf` - Report a successfully downloaded PDF
   Required: sku, remote_path, product_name

2. `log_error` - Log an error for a product
   Required: sku, message

3. `report_completion` - Report that all products have been processed
   Required: total_processed, successful, failed

=============================================================================
BEGIN WORKFLOW
=============================================================================

Start by taking a screenshot to see the current state of the desktop, then proceed with Phase 1.
Be methodical and thorough. Process items one at a time.
If you encounter errors, log them and continue with the next product.
"""
    
    return prompt


# =============================================================================
# ESP Product Lookup Agent
# =============================================================================

class ESPProductLookup:
    """
    CUA Agent for looking up products in ESP+ and downloading sell sheets.
    
    This agent logs into ESP+, searches for each product in the provided list,
    and downloads the Distributor Report PDF for each.
    """
    
    def __init__(
        self,
        products: List[Dict[str, Any]],
        computer_id: Optional[str] = None,
        dry_run: bool = False
    ):
        """
        Initialize the ESP Product Lookup agent.
        
        Args:
            products: List of products to look up (each should have 'sku' and 'name')
            computer_id: Optional Orgo computer ID (defaults to ORGO_COMPUTER_ID)
            dry_run: If True, don't execute the CUA
        """
        self.products = self._normalize_products(products)
        self.computer_id = computer_id or ORGO_COMPUTER_ID
        self.dry_run = dry_run
        
        self.computer: Optional[Computer] = None
        self.tools: Optional[AgentTools] = None
        
        # Set API keys in environment
        os.environ["ORGO_API_KEY"] = os.getenv("ORGO_API_KEY", "")
        os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY", "")
    
    def _normalize_products(self, products: List[Dict[str, Any]]) -> List[ProductToLookup]:
        """Convert product dicts to ProductToLookup dataclass instances."""
        normalized = []
        for p in products:
            # Support both 'cpn' (new format) and 'sku'/'item_number' (legacy)
            cpn = p.get("cpn") or p.get("sku") or p.get("item_number") or ""
            normalized.append(ProductToLookup(
                cpn=cpn,
                name=p.get("name") or p.get("title") or "",
                supplier_name=p.get("supplier_name"),
                supplier_asi=p.get("supplier_asi"),
                description=p.get("description")
            ))
        return normalized
    
    def run(self) -> LookupResult:
        """
        Execute the product lookup workflow.
        
        Returns:
            LookupResult with download statistics and file paths
        """
        logger.info("=" * 60)
        logger.info("ESP PRODUCT LOOKUP AGENT")
        logger.info("=" * 60)
        logger.info(f"Products to process: {len(self.products)}")
        logger.info(f"Dry run: {self.dry_run}")
        
        if self.dry_run:
            logger.info("[DRY RUN] Skipping CUA execution")
            return LookupResult(
                total_products=len(self.products),
                successful=0,
                failed=len(self.products),
                errors=[{"sku": p.cpn, "message": "Dry run mode"} for p in self.products]
            )
        
        if not self.products:
            logger.warning("No products to process")
            return LookupResult(
                total_products=0,
                successful=0,
                failed=0
            )
        
        try:
            # Initialize tools
            self.tools = AgentTools()
            
            # Initialize Orgo computer
            logger.info(f"Connecting to Orgo computer: {self.computer_id}")
            self.computer = Computer(computer_id=self.computer_id)
            logger.info(f"Connected to: orgo-{self.computer_id}.orgo.dev")
            
            # Build the prompt
            prompt = build_lookup_prompt(self.products)
            
            # Define progress callback
            def progress_callback(event_type: str, event_data: Any) -> None:
                if event_type == "text":
                    logger.info(f"Claude: {event_data}")
                elif event_type == "tool_use":
                    action = event_data.get('action', 'unknown')
                    logger.info(f"Action: {action}")
                elif event_type == "thinking":
                    logger.debug(f"Thinking: {event_data[:200]}...")
                elif event_type == "error":
                    logger.error(f"Error: {event_data}")
            
            # Execute the agent workflow
            logger.info(f"Starting CUA with model: {MODEL_ID}")
            
            messages = self.computer.prompt(
                prompt,
                callback=progress_callback,
                model=MODEL_ID,
                display_width=DISPLAY_WIDTH,
                display_height=DISPLAY_HEIGHT,
                thinking_enabled=True,
                thinking_budget=THINKING_BUDGET,
                max_iterations=MAX_ITERATIONS,
                max_tokens=MAX_TOKENS,
                tools=TOOLS_SCHEMA,
                tool_handler=create_tool_handler(self.tools)
            )
            
            logger.info("CUA workflow completed")
            
            # Compile results
            summary = self.tools.get_summary()
            downloaded_pdfs = summary.get("downloaded_pdfs", [])
            errors = summary.get("errors", [])
            
            return LookupResult(
                total_products=len(self.products),
                successful=len(downloaded_pdfs),
                failed=len(errors),
                downloaded_pdfs=downloaded_pdfs,
                errors=errors
            )
            
        except Exception as e:
            logger.error(f"Lookup failed: {e}", exc_info=True)
            return LookupResult(
                total_products=len(self.products),
                successful=0,
                failed=len(self.products),
                errors=[{"sku": "all", "message": str(e)}]
            )


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point for testing the product lookup."""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(
        description="Look up products in ESP+ and download sell sheets"
    )
    parser.add_argument(
        "products_json",
        type=str,
        help="Path to JSON file containing products list, or JSON string"
    )
    parser.add_argument(
        "--computer-id",
        type=str,
        help="Orgo computer ID to use"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (don't execute CUA)"
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
    
    # Load products
    try:
        # Try as file path first
        if os.path.exists(args.products_json):
            with open(args.products_json, "r") as f:
                products = json.load(f)
        else:
            # Try as JSON string
            products = json.loads(args.products_json)
    except json.JSONDecodeError as e:
        print(f"Error parsing products JSON: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Ensure products is a list
    if isinstance(products, dict) and "products" in products:
        products = products["products"]
    
    if not isinstance(products, list):
        print("Products must be a list", file=sys.stderr)
        sys.exit(1)
    
    # Run lookup
    lookup = ESPProductLookup(
        products=products,
        computer_id=args.computer_id,
        dry_run=args.dry_run
    )
    
    result = lookup.run()
    
    # Output results
    print(f"\nResults:")
    print(f"  Total: {result.total_products}")
    print(f"  Successful: {result.successful}")
    print(f"  Failed: {result.failed}")
    
    if result.downloaded_pdfs:
        print(f"\nDownloaded PDFs:")
        for pdf in result.downloaded_pdfs:
            print(f"  - {pdf['sku']}: {pdf['remote_path']}")
    
    if result.errors:
        print(f"\nErrors:")
        for error in result.errors:
            print(f"  - {error['sku']}: {error['message']}")
    
    sys.exit(0 if result.successful > 0 else 1)


if __name__ == "__main__":
    main()

