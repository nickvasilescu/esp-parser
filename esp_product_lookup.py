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
from typing import Any, Dict, List, Optional, TYPE_CHECKING

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

# Import JobStateManager for state updates (optional dependency)
try:
    from job_state import JobStateManager, WorkflowStatus
except ImportError:
    JobStateManager = None
    WorkflowStatus = None

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

def build_single_product_prompt(
    product: ProductToLookup,
    job_id: str,
    upload_url: str,
    product_index: int,
    total_products: int,
    is_first_product: bool = False
) -> str:
    """
    Build the CUA prompt for looking up a SINGLE product in ESP+.
    
    This prompt is designed to be called sequentially for each product,
    with each CUA agent handling exactly one product lookup.
    
    Args:
        product: Single product to look up
        job_id: Unique job identifier for organizing files
        upload_url: Pre-signed S3 upload URL for this product
        product_index: Current product index (1-based)
        total_products: Total number of products being processed
        is_first_product: If True, include full login instructions
    
    Returns:
        Formatted prompt string for the CUA
    """
    working_dir = f"~/Downloads/{job_id}"
    cpn = product.cpn or 'N/A'
    
    # Build product info
    product_info = f"CPN: {cpn}\nName: {product.name}"
    if product.supplier_name:
        product_info += f"\nSupplier: {product.supplier_name}"
    if product.supplier_asi:
        product_info += f" (ASI: {product.supplier_asi})"
    product_info += f"\nUpload URL: {upload_url}"
    
    # Phase 2 varies based on whether this is the first product
    if is_first_product:
        login_phase = f"""PHASE 2: LOGIN TO ESP PLUS
1. Open Firefox browser (click on Firefox icon in taskbar)
2. Navigate to: {ESP_PLUS_URL}
3. Login using the credentials provided above:
   - Enter email: {ESP_PLUS_EMAIL}
   - Enter password: {ESP_PLUS_PASSWORD}
4. Wait for the dashboard to load
5. Take a screenshot to confirm successful login"""
    else:
        login_phase = f"""PHASE 2: CHECK ESP PLUS SESSION
1. Take a screenshot to see current state
2. If Firefox is already open with ESP Plus logged in:
   - Proceed directly to Phase 3
3. If Firefox is closed or not logged in:
   - Open Firefox browser
   - Navigate to: {ESP_PLUS_URL}
   - Login with email: {ESP_PLUS_EMAIL} and password: {ESP_PLUS_PASSWORD}
4. Ensure you're on the ESP Plus search page before continuing"""
    
    prompt = f"""You are a product data extraction agent. Your goal is to find ONE specific product in ESP Plus, print/save the product page as PDF, and upload it to cloud storage.

IMPORTANT CONTEXT:
- You are controlling a Linux desktop environment
- Firefox browser is available
- You have Terminal access for file operations
- Job ID: {job_id}
- Working directory: {working_dir}
- Processing product {product_index} of {total_products}

ESP PLUS CREDENTIALS:
- URL: {ESP_PLUS_URL}
- Email: {ESP_PLUS_EMAIL}
- Password: {ESP_PLUS_PASSWORD}

=============================================================================
TARGET PRODUCT
=============================================================================

{product_info}

=============================================================================
WORKFLOW
=============================================================================

PHASE 1: VERIFY WORKING DIRECTORY
1. Open a Terminal (or use an existing one)
2. Ensure the working directory exists:
   mkdir -p {working_dir}
3. Verify it exists:
   ls -la ~/Downloads/ | grep {job_id}

{login_phase}

PHASE 3: FIND AND DOWNLOAD PRODUCT
1. SEARCH for the product:
   - Clear any existing search text
   - Enter the CPN: {cpn}
   - The CPN format is like "CPN-564949909" - you can search with or without the "CPN-" prefix
   - If CPN search fails, try the product name: "{product.name}"

2. NAVIGATE to the product detail page:
   - Click on the matching product in search results
   - Verify you're on the correct product by checking CPN/name

3. PRINT/SAVE THE PRODUCT PAGE AS PDF:
   - Click the Print button (printer icon) on the product page
   - In the print dialog, ensure "Save to PDF" is selected as the destination
   - Click "Save" to download the PDF
   - The PDF will contain the product details including pricing
   - Wait for the download to complete
   - Take a screenshot to confirm download completed

4. IDENTIFY AND MOVE THE FILE:
   - Go to Terminal
   - Find the most recently downloaded PDF:
     ls -lt ~/Downloads/*.pdf | head -n 2
   - Move and rename it to the working directory:
     mv "$(ls -t ~/Downloads/*.pdf | head -1)" {working_dir}/{cpn}_distributor_report.pdf
   - Verify the file exists:
     ls -la {working_dir}/{cpn}_distributor_report.pdf

5. UPLOAD TO S3:
   - Run this Python upload command:
     python3 -c "import urllib.request; data=open('{working_dir}/{cpn}_distributor_report.pdf','rb').read(); req=urllib.request.Request('{upload_url}',data=data,method='PUT'); req.add_header('Content-Type','application/pdf'); print('Status:',urllib.request.urlopen(req).status)"
   - Verify the upload succeeded (HTTP 200 response printed)
   - If the upload fails, retry once

PHASE 4: COMPLETION
1. Take a final screenshot showing the uploaded file
2. Report success by confirming the file was uploaded (Status: 200)
3. Your task for this product is complete

=============================================================================
IMPORTANT COMMANDS REFERENCE
=============================================================================

Create working directory:
  mkdir -p {working_dir}

Find newest PDF in Downloads:
  ls -t ~/Downloads/*.pdf | head -1

Move file to working directory:
  mv "$(ls -t ~/Downloads/*.pdf | head -1)" {working_dir}/{cpn}_distributor_report.pdf

Upload to S3:
  python3 -c "import urllib.request; data=open('{working_dir}/{cpn}_distributor_report.pdf','rb').read(); req=urllib.request.Request('{upload_url}',data=data,method='PUT'); req.add_header('Content-Type','application/pdf'); print('Status:',urllib.request.urlopen(req).status)"

=============================================================================
SEARCH TIPS
=============================================================================

1. **CPN Search** (most reliable):
   - Enter the CPN exactly: {cpn}
   - Or try without prefix: {cpn.replace('CPN-', '') if cpn.startswith('CPN-') else cpn}

2. **Name Search** (fallback):
   - Use key terms from: "{product.name}"

=============================================================================
BEGIN WORKFLOW
=============================================================================

Start by taking a screenshot to see the current state of the desktop.
Your goal is to download and upload the Distributor Report for this ONE product: {cpn}
Be methodical: Search -> Download -> Move/Rename -> Upload -> Confirm.
"""
    
    return prompt


def build_lookup_prompt(
    products: List[ProductToLookup],
    job_id: str,
    upload_url_map: Dict[str, str]
) -> str:
    """
    Build the CUA prompt for looking up products in ESP+.
    
    DEPRECATED: Use build_single_product_prompt for sequential processing.
    This function is kept for backwards compatibility.
    
    Args:
        products: List of products to look up
        job_id: Unique job identifier for organizing files
        upload_url_map: Dictionary mapping CPN to pre-signed S3 upload URL
    
    Returns:
        Formatted prompt string for the CUA
    """
    # If single product, use the new single-product prompt
    if len(products) == 1:
        product = products[0]
        cpn = product.cpn or 'N/A'
        upload_url = upload_url_map.get(cpn, '')
        return build_single_product_prompt(
            product=product,
            job_id=job_id,
            upload_url=upload_url,
            product_index=1,
            total_products=1,
            is_first_product=True
        )
    
    # For multiple products, use legacy batch prompt (not recommended)
    working_dir = f"~/Downloads/{job_id}"
    
    # Build product list for the prompt with their upload URLs
    product_list = []
    for i, product in enumerate(products, 1):
        cpn = product.cpn or 'N/A'
        entry = f"{i}. CPN: {cpn}\n   Name: {product.name}"
        if product.supplier_name:
            entry += f"\n   Supplier: {product.supplier_name}"
        if product.supplier_asi:
            entry += f" (ASI: {product.supplier_asi})"
        # Include the upload URL for this product
        if cpn in upload_url_map:
            entry += f"\n   Upload URL: {upload_url_map[cpn]}"
        product_list.append(entry)
    
    products_text = "\n".join(product_list)
    
    prompt = f"""You are a product data extraction agent. Your goal is to log into ESP Plus, find each product listed below, download their Distributor Report PDFs, and upload them to cloud storage.

IMPORTANT CONTEXT:
- You are controlling a Linux desktop environment
- Firefox browser is available
- You have Terminal access for file operations
- Job ID: {job_id}
- Working directory: {working_dir}

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

PHASE 1: SETUP WORKING DIRECTORY
1. Open a Terminal (or use an existing one)
2. Create the working directory:
   mkdir -p {working_dir}
3. Verify it was created:
   ls -la ~/Downloads/

PHASE 2: LOGIN TO ESP PLUS
1. Open Firefox browser
2. Navigate to: {ESP_PLUS_URL}
3. Login using the credentials provided above:
   - Enter email: {ESP_PLUS_EMAIL}
   - Enter password: {ESP_PLUS_PASSWORD}
4. Wait for the dashboard to load
5. Take a screenshot to confirm successful login

PHASE 3: PROCESS EACH PRODUCT
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
   - Wait for the download to complete (Firefox shows download popup)
   - Take a screenshot to confirm download completed

4. IDENTIFY AND MOVE THE FILE:
   - Go to Terminal
   - Find the most recently downloaded PDF:
     ls -lt ~/Downloads/*.pdf | head -n 2
   - Move and rename it to the working directory:
     mv "$(ls -t ~/Downloads/*.pdf | head -1)" {working_dir}/[CPN]_distributor_report.pdf
   - Example: mv "$(ls -t ~/Downloads/*.pdf | head -1)" {working_dir}/CPN-564949909_distributor_report.pdf
   - Verify the file exists:
     ls -la {working_dir}/

5. UPLOAD TO S3:
   - Use the Upload URL provided for this CPN in the product list above
   - Run the Python upload command (since curl may not be installed):
     python3 -c "import urllib.request; data=open('{working_dir}/[CPN]_distributor_report.pdf','rb').read(); req=urllib.request.Request('[Upload URL]',data=data,method='PUT'); req.add_header('Content-Type','application/pdf'); print('Status:',urllib.request.urlopen(req).status)"
   - Verify the upload succeeded (HTTP 200 response printed)
   - If the upload fails, retry once

6. REPORT THE DOWNLOAD:
   - Call the `report_downloaded_pdf` tool with:
     - sku: The product CPN (e.g., "CPN-564949909")
     - remote_path: "s3://{job_id}/products/[CPN]_distributor_report.pdf"
     - product_name: The product name

7. HANDLE ERRORS:
   - If a product cannot be found, call `log_error` with:
     - sku: The product CPN (or "unknown")
     - message: Description of what went wrong
   - Continue to the next product

8. MOVE TO NEXT PRODUCT:
   - Return to ESP Plus search (in Firefox)
   - Repeat steps 1-7 for the next item

PHASE 4: COMPLETION
After processing ALL products:
1. Call `report_completion` with:
   - total_processed: Total number of products attempted
   - successful: Number of PDFs successfully downloaded and uploaded
   - failed: Number of products that failed
   - summary: Brief description of the session
2. Take a final screenshot showing completion

=============================================================================
IMPORTANT COMMANDS REFERENCE
=============================================================================

Create working directory:
  mkdir -p {working_dir}

Find newest PDF in Downloads:
  ls -t ~/Downloads/*.pdf | head -1

Move file to working directory (replace [CPN] with actual CPN):
  mv "$(ls -t ~/Downloads/*.pdf | head -1)" {working_dir}/[CPN]_distributor_report.pdf

Upload to S3 (using Python - replace [CPN] and [Upload URL]):
  python3 -c "import urllib.request; data=open('{working_dir}/[CPN]_distributor_report.pdf','rb').read(); req=urllib.request.Request('[Upload URL]',data=data,method='PUT'); req.add_header('Content-Type','application/pdf'); print('Status:',urllib.request.urlopen(req).status)"

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
   - Download typically goes to ~/Downloads by default

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

Start by taking a screenshot to see the current state of the desktop, then proceed with Phase 1 (Setup Working Directory).
Be methodical and thorough. Process items one at a time.
For each product: Download -> Move/Rename -> Upload -> Report -> Next.
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
    downloads the Distributor Report PDF for each, and uploads them to S3.
    
    For best results, use sequential single-product runs via run_single_product()
    instead of batch runs. This improves reliability by isolating each product's
    processing in its own CUA session.
    """
    
    def __init__(
        self,
        products: List[Dict[str, Any]],
        job_id: str,
        upload_url_map: Dict[str, str],
        computer_id: Optional[str] = None,
        dry_run: bool = False,
        product_index: int = 1,
        total_products: int = 1,
        is_first_product: bool = True,
        state_manager: Optional["JobStateManager"] = None
    ):
        """
        Initialize the ESP Product Lookup agent.

        Args:
            products: List of products to look up (each should have 'cpn' or 'sku' and 'name')
            job_id: Unique job identifier for organizing files
            upload_url_map: Dictionary mapping CPN to pre-signed S3 upload URL
            computer_id: Optional Orgo computer ID (defaults to ORGO_COMPUTER_ID)
            dry_run: If True, don't execute the CUA
            product_index: Current product index (1-based) for progress tracking
            total_products: Total number of products being processed
            is_first_product: If True, include full login instructions in prompt
            state_manager: Optional JobStateManager for state updates
        """
        self.products = self._normalize_products(products)
        self.job_id = job_id
        self.upload_url_map = upload_url_map
        self.computer_id = computer_id or ORGO_COMPUTER_ID
        self.dry_run = dry_run
        self.product_index = product_index
        self.total_products = total_products
        self.is_first_product = is_first_product
        self.state_manager = state_manager

        self.computer: Optional[Computer] = None

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

    def _update_state(self, status: str, **kwargs) -> None:
        """Update job state if state manager is available."""
        if self.state_manager and WorkflowStatus:
            self.state_manager.update(status, **kwargs)
    
    def run(self) -> LookupResult:
        """
        Execute the product lookup workflow.

        For single-product runs (recommended), uses the optimized single-product prompt.
        For batch runs (legacy), uses the multi-product prompt.

        Returns:
            LookupResult with download statistics and file paths
        """
        is_single_product = len(self.products) == 1

        logger.info("=" * 60)
        logger.info("ESP PRODUCT LOOKUP AGENT")
        logger.info("=" * 60)
        logger.info(f"Job ID: {self.job_id}")
        logger.info(f"Product {self.product_index}/{self.total_products}" if is_single_product else f"Products to process: {len(self.products)}")

        # Emit state update with per-product progress
        if is_single_product:
            product_name = self.products[0].name
            logger.info(f"CPN: {self.products[0].cpn}")
            logger.info(f"Name: {product_name}")
            self._update_state(
                WorkflowStatus.ESP_LOOKING_UP_PRODUCTS.value if WorkflowStatus else "esp_looking_up_products",
                current_item=self.product_index,
                total_items=self.total_products,
                current_item_name=product_name
            )

        logger.info(f"Upload URLs configured: {len(self.upload_url_map)}")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info(f"First product (full login): {self.is_first_product}")

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
            # Initialize Orgo computer
            logger.info(f"Connecting to Orgo computer: {self.computer_id}")
            self.computer = Computer(computer_id=self.computer_id)
            logger.info(f"Connected to: orgo-{self.computer_id}.orgo.dev")

            # Emit checkpoint for CUA start
            if self.state_manager and is_single_product:
                product = self.products[0]
                self.state_manager.emit_thought(
                    agent="cua_product",
                    event_type="checkpoint",
                    content=f"Starting product lookup: {product.name}",
                    metadata={
                        "cpn": product.cpn,
                        "product_index": self.product_index,
                        "total_products": self.total_products
                    }
                )
            
            # Build the prompt - use single product prompt for sequential processing
            if is_single_product:
                product = self.products[0]
                cpn = product.cpn or 'N/A'
                upload_url = self.upload_url_map.get(cpn, '')
                prompt = build_single_product_prompt(
                    product=product,
                    job_id=self.job_id,
                    upload_url=upload_url,
                    product_index=self.product_index,
                    total_products=self.total_products,
                    is_first_product=self.is_first_product
                )
            else:
                # Legacy batch prompt
                prompt = build_lookup_prompt(
                    products=self.products,
                    job_id=self.job_id,
                    upload_url_map=self.upload_url_map
                )
            
            # Get current product CPN for metadata
            current_cpn = self.products[0].cpn if is_single_product else None

            # Define progress callback
            def progress_callback(event_type: str, event_data: Any) -> None:
                if event_type == "text":
                    logger.info(f"Claude: {event_data}")
                    # Emit thought for text output
                    if self.state_manager:
                        self.state_manager.emit_thought(
                            agent="cua_product",
                            event_type="thought",
                            content=str(event_data)[:500],
                            metadata={"cpn": current_cpn} if current_cpn else None
                        )
                elif event_type == "tool_use":
                    action = event_data.get('action', 'unknown')
                    logger.info(f"Action: {action}")
                    # Emit thought for tool use
                    if self.state_manager:
                        self.state_manager.emit_thought(
                            agent="cua_product",
                            event_type="action",
                            content=f"Executing: {action}",
                            details=event_data,
                            metadata={"cpn": current_cpn} if current_cpn else None
                        )
                elif event_type == "thinking":
                    logger.debug(f"Thinking: {event_data[:200]}...")
                    # Emit thought for thinking
                    if self.state_manager:
                        self.state_manager.emit_thought(
                            agent="cua_product",
                            event_type="thought",
                            content=str(event_data)[:500],
                            metadata={"cpn": current_cpn} if current_cpn else None
                        )
                elif event_type == "error":
                    logger.error(f"Error: {event_data}")
                    # Emit thought for error
                    if self.state_manager:
                        self.state_manager.emit_thought(
                            agent="cua_product",
                            event_type="error",
                            content=str(event_data)[:500],
                            metadata={"cpn": current_cpn} if current_cpn else None
                        )
            
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
                max_tokens=MAX_TOKENS
            )
            
            logger.info("CUA workflow completed")

            # Emit success thought
            if self.state_manager and is_single_product:
                product = self.products[0]
                self.state_manager.emit_thought(
                    agent="cua_product",
                    event_type="success",
                    content=f"Product lookup complete: {product.name}",
                    metadata={
                        "cpn": product.cpn,
                        "product_index": self.product_index,
                        "total_products": self.total_products
                    }
                )

            # The agent should have uploaded files to S3 via curl
            # We assume success based on prompt completion
            # The orchestrator will verify files exist in S3
            # Generate expected paths based on products processed
            expected_pdfs = [
                {
                    "sku": p.cpn,
                    "remote_path": f"s3://{self.job_id}/products/{p.cpn}_distributor_report.pdf",
                    "product_name": p.name
                }
                for p in self.products
            ]

            return LookupResult(
                total_products=len(self.products),
                successful=len(self.products),  # Optimistic - orchestrator verifies
                failed=0,
                downloaded_pdfs=expected_pdfs,
                errors=[]
            )
            
        except Exception as e:
            logger.error(f"Lookup failed: {e}", exc_info=True)
            # Log error to state manager
            if self.state_manager:
                product_id = self.products[0].cpn if self.products else None
                self.state_manager.add_error(
                    step="esp_looking_up_products",
                    message=str(e),
                    product_id=product_id,
                    recoverable=True  # Individual product failures are recoverable
                )
            return LookupResult(
                total_products=len(self.products),
                successful=0,
                failed=len(self.products),
                errors=[{"sku": self.products[0].cpn if self.products else "unknown", "message": str(e)}]
            )


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point for testing the product lookup."""
    import argparse
    import json
    from datetime import datetime
    
    parser = argparse.ArgumentParser(
        description="Look up products in ESP+ and download sell sheets"
    )
    parser.add_argument(
        "products_json",
        type=str,
        help="Path to JSON file containing products list, or JSON string"
    )
    parser.add_argument(
        "--job-id",
        type=str,
        help="Job ID (auto-generated if not provided)"
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
    
    # Generate job ID if not provided
    job_id = args.job_id or f"esp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Initialize S3 handler and generate upload URLs for each product
    from s3_handler import S3Handler
    s3_handler = S3Handler(job_id=job_id)
    
    # Extract CPNs from products and generate upload URLs
    cpns = []
    for p in products:
        cpn = p.get("cpn") or p.get("sku") or p.get("item_number") or ""
        if cpn:
            cpns.append(cpn)
    
    upload_url_map = s3_handler.generate_product_upload_urls(cpns)
    
    print(f"Generated {len(upload_url_map)} upload URLs for job: {job_id}")
    
    # Run lookup
    lookup = ESPProductLookup(
        products=products,
        job_id=job_id,
        upload_url_map=upload_url_map,
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
        print(f"\nUploaded PDFs:")
        for pdf in result.downloaded_pdfs:
            print(f"  - {pdf['sku']}: {pdf['remote_path']}")
    
    if result.errors:
        print(f"\nErrors:")
        for error in result.errors:
            print(f"  - {error['sku']}: {error['message']}")
    
    sys.exit(0 if result.successful > 0 else 1)


if __name__ == "__main__":
    main()

