#!/usr/bin/env python3
"""
ESP-Orgo CUA Orchestration Agent
================================

A complete workflow that:
1. Parses a presentation URL to extract product items
2. Uses an Orgo CUA to log into ESP+ and download PDF sell sheets
3. Retrieves the PDFs from the Orgo VM
4. Processes PDFs through the ESP parser to extract structured data
5. Outputs aggregated JSON ready for Zoho/Calculator integration

Usage:
    python main_agent.py <presentation_url>
    python main_agent.py https://www.viewpresentation.com/66907679185 --dry-run
"""

import argparse
import json
import logging
import os
import sys
import tempfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from anthropic import Anthropic
from orgo import Computer

from config import (
    validate_config,
    DISPLAY_WIDTH,
    DISPLAY_HEIGHT,
    ESP_PLUS_EMAIL,
    ESP_PLUS_PASSWORD,
    ESP_PLUS_URL,
    ORGO_COMPUTER_ID,
    MODEL_ID,
    THINKING_BUDGET,
    MAX_ITERATIONS,
    MAX_TOKENS,
    OUTPUT_DIR,
    REMOTE_DOWNLOAD_DIR,
    get_config_summary,
)
from agent_tools import AgentTools, TOOLS_SCHEMA, create_tool_handler
from presentation_parser import scrape as scrape_presentation, Presentation, Product
from esp_parser import parse_pdf
from prompt import EXTRACTION_PROMPT


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('orchestration_agent.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# Output Data Structure
# =============================================================================

def create_final_output(
    presentation: Presentation,
    parsed_products: List[Dict[str, Any]],
    errors: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Create the final output structure ready for Zoho/Calculator integration.
    
    Args:
        presentation: The original presentation data
        parsed_products: List of parsed product data from ESP PDFs
        errors: List of errors encountered during processing
    
    Returns:
        Complete output structure ready for downstream processing
    """
    return {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "presentation_url": presentation.url,
            "presentation_title": presentation.title,
            "client": {
                "name": presentation.client_name,
                "company": presentation.client_company
            },
            "presenter": {
                "name": presentation.presenter_name,
                "company": presentation.presenter_company,
                "phone": presentation.presenter_phone,
                "location": presentation.presenter_location
            },
            "total_items_in_presentation": len(presentation.products),
            "total_items_processed": len(parsed_products),
            "total_errors": len(errors)
        },
        "products": parsed_products,
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
# Agent Prompt Builder
# =============================================================================

def build_agent_prompt(products: List[Product]) -> str:
    """
    Build the CUA prompt with the list of products to process.
    
    Args:
        products: List of Product objects from the presentation
    
    Returns:
        Formatted prompt string for the CUA
    """
    # Build product list for the prompt
    product_list = []
    for i, product in enumerate(products, 1):
        product_list.append(
            f"{i}. SKU: {product.item_number or 'N/A'}\n"
            f"   Name: {product.title}\n"
            f"   Description: {product.description[:200]}..." if len(product.description) > 200 else f"   Description: {product.description}"
        )
    
    products_text = "\n".join(product_list)
    
    prompt = f"""You are a product data extraction agent. Your goal is to log into ESP Plus, find each product listed below, and download their Distributor Report PDFs.

IMPORTANT CONTEXT:
- You are controlling a Linux desktop environment
- Firefox browser is available
- You must save PDFs to: {REMOTE_DOWNLOAD_DIR}
- Use descriptive filenames like: [SKU]_distributor_report.pdf

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
3. Login using the credentials provided above
4. Wait for the dashboard to load
5. Take a screenshot to confirm successful login

PHASE 2: PROCESS EACH PRODUCT
For EACH product in the list above:

1. SEARCH for the product:
   - Use the SKU (Item Number) if available
   - If SKU is not available or not found, try searching by product name
   - Navigate to the product detail page

2. DOWNLOAD THE DISTRIBUTOR REPORT:
   - Look for a "Print" button or menu
   - Select "Distributor Report" or similar option
   - Save/Print as PDF to: {REMOTE_DOWNLOAD_DIR}
   - Use filename format: [SKU]_distributor_report.pdf
   - If SKU is not available, use a sanitized version of the product name

3. REPORT THE DOWNLOAD:
   - Call the `report_downloaded_pdf` tool with:
     - sku: The product SKU
     - remote_path: Full path to the saved PDF
     - product_name: The product name
   
4. HANDLE ERRORS:
   - If a product cannot be found, call `log_error` with details
   - Continue to the next product

5. MOVE TO NEXT PRODUCT:
   - Return to ESP Plus search
   - Repeat for the next item

PHASE 3: COMPLETION
1. After processing ALL products, call `report_completion` with:
   - total_processed: Total number of products attempted
   - successful: Number of PDFs successfully downloaded
   - failed: Number of products that failed
   - summary: Brief description of the session

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
"""
    
    return prompt


# =============================================================================
# Main Orchestration Agent
# =============================================================================

class OrchestrationAgent:
    """
    Main orchestration agent that ties together:
    - Presentation parsing
    - Orgo CUA for PDF downloads
    - ESP PDF parsing
    - Final output generation
    """
    
    def __init__(
        self,
        presentation_url: str,
        computer_id: Optional[str] = None,
        dry_run: bool = False,
        skip_cua: bool = False
    ):
        """
        Initialize the orchestration agent.
        
        Args:
            presentation_url: URL of the presentation to process
            computer_id: Optional Orgo computer ID (defaults to ORGO_COMPUTER_ID)
            dry_run: If True, don't execute CUA or save files
            skip_cua: If True, skip CUA step (for testing with pre-downloaded PDFs)
        """
        self.presentation_url = presentation_url
        self.computer_id = computer_id or ORGO_COMPUTER_ID
        self.dry_run = dry_run
        self.skip_cua = skip_cua
        
        self.presentation: Optional[Presentation] = None
        self.computer: Optional[Computer] = None
        self.tools: Optional[AgentTools] = None
        self.anthropic_client: Optional[Anthropic] = None
        
        # Ensure output directory exists
        Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
        
        # Validate configuration
        if not dry_run and not skip_cua:
            validate_config()
        
        logger.info(get_config_summary())
    
    def phase1_scrape_presentation(self) -> List[Product]:
        """
        Phase 1: Scrape the presentation to get product list.
        
        Returns:
            List of Product objects from the presentation
        """
        logger.info("=" * 60)
        logger.info("PHASE 1: SCRAPING PRESENTATION")
        logger.info("=" * 60)
        logger.info(f"URL: {self.presentation_url}")
        
        self.presentation = scrape_presentation(self.presentation_url)
        
        logger.info(f"Presentation Title: {self.presentation.title}")
        logger.info(f"Client: {self.presentation.client_name} @ {self.presentation.client_company}")
        logger.info(f"Presenter: {self.presentation.presenter_name} @ {self.presentation.presenter_company}")
        logger.info(f"Products Found: {len(self.presentation.products)}")
        
        for i, product in enumerate(self.presentation.products, 1):
            logger.info(f"  {i}. {product.item_number or 'N/A'} - {product.title}")
        
        return self.presentation.products
    
    def phase2_run_cua(self, products: List[Product]) -> Dict[str, Any]:
        """
        Phase 2: Run the Orgo CUA to download PDFs from ESP+.
        
        Args:
            products: List of products to process
        
        Returns:
            Tool results summary from the CUA
        """
        logger.info("=" * 60)
        logger.info("PHASE 2: RUNNING ORGO CUA")
        logger.info("=" * 60)
        
        if self.dry_run:
            logger.info("[DRY RUN] Skipping CUA execution")
            return {"downloaded_pdfs": [], "errors": [], "stats": {"total_downloaded": 0, "total_errors": 0}}
        
        if self.skip_cua:
            logger.info("[SKIP CUA] Using pre-downloaded PDFs")
            return {"downloaded_pdfs": [], "errors": [], "stats": {"total_downloaded": 0, "total_errors": 0}}
        
        # Initialize tools
        self.tools = AgentTools()
        
        # Initialize Orgo computer
        logger.info(f"Connecting to Orgo computer: {self.computer_id}")
        self.computer = Computer(computer_id=self.computer_id)
        logger.info(f"Connected to: orgo-{self.computer_id}.orgo.dev")
        
        # Build the prompt
        prompt = build_agent_prompt(products)
        
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
        
        return self.tools.get_summary()
    
    def phase3_retrieve_files(self, cua_results: Dict[str, Any]) -> List[str]:
        """
        Phase 3: Retrieve downloaded PDFs from the Orgo VM.
        
        Args:
            cua_results: Results from the CUA phase
        
        Returns:
            List of local file paths to the downloaded PDFs
        """
        logger.info("=" * 60)
        logger.info("PHASE 3: RETRIEVING FILES FROM VM")
        logger.info("=" * 60)
        
        local_paths = []
        
        if self.dry_run or self.skip_cua:
            # In dry run or skip mode, look for existing PDFs in output directory
            logger.info(f"Looking for existing PDFs in: {OUTPUT_DIR}")
            pdf_files = list(Path(OUTPUT_DIR).glob("*.pdf"))
            for pdf_file in pdf_files:
                logger.info(f"  Found: {pdf_file}")
                local_paths.append(str(pdf_file))
            return local_paths
        
        downloaded_pdfs = cua_results.get("downloaded_pdfs", [])
        
        if not downloaded_pdfs:
            logger.warning("No PDFs were downloaded by the CUA")
            return local_paths
        
        # Create a temp directory for downloaded files
        temp_dir = Path(OUTPUT_DIR) / "pdfs"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        for pdf_info in downloaded_pdfs:
            remote_path = pdf_info["remote_path"]
            sku = pdf_info["sku"]
            
            # Determine local filename
            local_filename = f"{sku}_distributor_report.pdf"
            local_path = temp_dir / local_filename
            
            logger.info(f"Retrieving: {remote_path} -> {local_path}")
            
            try:
                # TODO: Use Orgo SDK method to download file from VM
                # This is a placeholder for when the Orgo SDK adds file retrieval
                # Expected API: self.computer.download(remote_path, str(local_path))
                
                # For now, we'll assume the file is already available or will be
                # retrieved through a future SDK method
                if self.computer and hasattr(self.computer, 'download'):
                    self.computer.download(remote_path, str(local_path))
                    local_paths.append(str(local_path))
                    logger.info(f"  Successfully retrieved: {local_path}")
                else:
                    # Placeholder: Mark as pending retrieval
                    logger.warning(f"  File retrieval API not available yet. Path recorded: {remote_path}")
                    # Store the info for manual retrieval
                    pdf_info["local_path"] = str(local_path)
                    pdf_info["retrieval_pending"] = True
                    
            except Exception as e:
                logger.error(f"  Failed to retrieve {remote_path}: {e}")
        
        return local_paths
    
    def phase4_parse_pdfs(self, pdf_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Phase 4: Parse downloaded PDFs using the ESP parser.
        
        Args:
            pdf_paths: List of local PDF file paths
        
        Returns:
            List of parsed product data dictionaries
        """
        logger.info("=" * 60)
        logger.info("PHASE 4: PARSING PDFs")
        logger.info("=" * 60)
        
        parsed_products = []
        
        if not pdf_paths:
            logger.warning("No PDF files to parse")
            return parsed_products
        
        # Initialize Anthropic client
        if not self.anthropic_client:
            self.anthropic_client = Anthropic()
        
        for pdf_path in pdf_paths:
            logger.info(f"Parsing: {pdf_path}")
            
            try:
                parsed_data = parse_pdf(pdf_path, self.anthropic_client)
                parsed_products.append(parsed_data)
                logger.info(f"  Successfully parsed: {parsed_data.get('item', {}).get('name', 'Unknown')}")
            except Exception as e:
                logger.error(f"  Failed to parse {pdf_path}: {e}")
                parsed_products.append({
                    "error": str(e),
                    "source_file": pdf_path
                })
        
        return parsed_products
    
    def phase5_generate_output(
        self,
        parsed_products: List[Dict[str, Any]],
        cua_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Phase 5: Generate final output for Zoho/Calculator integration.
        
        Args:
            parsed_products: List of parsed product data
            cua_results: Results from the CUA phase (for error tracking)
        
        Returns:
            Complete output structure
        """
        logger.info("=" * 60)
        logger.info("PHASE 5: GENERATING OUTPUT")
        logger.info("=" * 60)
        
        errors = cua_results.get("errors", [])
        
        final_output = create_final_output(
            presentation=self.presentation,
            parsed_products=parsed_products,
            errors=errors
        )
        
        # Save output to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"extraction_output_{timestamp}.json"
        output_path = Path(OUTPUT_DIR) / output_filename
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Output saved to: {output_path}")
        
        return final_output
    
    def run(self) -> Dict[str, Any]:
        """
        Execute the complete orchestration workflow.
        
        Returns:
            Final output structure
        """
        try:
            logger.info("=" * 60)
            logger.info("ESP-ORGO CUA ORCHESTRATION AGENT")
            logger.info("=" * 60)
            logger.info(f"Presentation URL: {self.presentation_url}")
            logger.info(f"Dry Run: {self.dry_run}")
            logger.info(f"Skip CUA: {self.skip_cua}")
            
            # Phase 1: Scrape presentation
            products = self.phase1_scrape_presentation()
            
            if not products:
                logger.error("No products found in presentation")
                return {"error": "No products found in presentation"}
            
            # Phase 2: Run CUA to download PDFs
            cua_results = self.phase2_run_cua(products)
            
            # Phase 3: Retrieve files from VM
            pdf_paths = self.phase3_retrieve_files(cua_results)
            
            # Phase 4: Parse PDFs
            parsed_products = self.phase4_parse_pdfs(pdf_paths)
            
            # Phase 5: Generate output
            final_output = self.phase5_generate_output(parsed_products, cua_results)
            
            # Summary
            logger.info("=" * 60)
            logger.info("ORCHESTRATION COMPLETE")
            logger.info("=" * 60)
            logger.info(f"Products in presentation: {len(products)}")
            logger.info(f"PDFs retrieved: {len(pdf_paths)}")
            logger.info(f"Products parsed: {len(parsed_products)}")
            logger.info(f"Errors: {len(cua_results.get('errors', []))}")
            logger.info(f"Ready for Zoho: {final_output.get('ready_for_zoho', False)}")
            
            return final_output
            
        except KeyboardInterrupt:
            logger.warning("Orchestration interrupted by user")
            raise
        except Exception as e:
            logger.error(f"Orchestration failed: {e}", exc_info=True)
            raise


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """Main entry point for the orchestration agent."""
    parser = argparse.ArgumentParser(
        description="ESP-Orgo CUA Orchestration Agent - Automate presentation to structured data extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://www.viewpresentation.com/66907679185
  %(prog)s https://www.viewpresentation.com/66907679185 --dry-run
  %(prog)s https://www.viewpresentation.com/66907679185 --skip-cua
  %(prog)s https://www.viewpresentation.com/66907679185 --computer-id abc123

Environment Variables:
  ORGO_API_KEY          Your Orgo API key
  ANTHROPIC_API_KEY     Your Anthropic API key
  ORGO_COMPUTER_ID      Default Orgo computer ID
  ESP_PLUS_EMAIL        ESP+ login email
  ESP_PLUS_PASSWORD     ESP+ login password
        """
    )
    
    parser.add_argument(
        "presentation_url",
        type=str,
        help="URL of the presentation to process (e.g., https://www.viewpresentation.com/66907679185)"
    )
    
    parser.add_argument(
        "--computer-id",
        type=str,
        help="Orgo computer ID to use (overrides ORGO_COMPUTER_ID env var)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (skip CUA execution)"
    )
    
    parser.add_argument(
        "--skip-cua",
        action="store_true",
        help="Skip CUA step (use existing PDFs in output directory)"
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
    
    # Validate URL
    if "viewpresentation.com" not in args.presentation_url:
        print("Error: URL must be from viewpresentation.com", file=sys.stderr)
        sys.exit(1)
    
    # Create and run agent
    agent = OrchestrationAgent(
        presentation_url=args.presentation_url,
        computer_id=args.computer_id,
        dry_run=args.dry_run,
        skip_cua=args.skip_cua
    )
    
    try:
        result = agent.run()
        
        if args.output_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

