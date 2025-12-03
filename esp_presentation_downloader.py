#!/usr/bin/env python3
"""
ESP Presentation Downloader CUA Agent
=====================================

Uses Orgo to navigate to portal.mypromooffice.com and download the presentation PDF.
This is CUA Agent 1 in the ESP pipeline.

Usage:
    from esp_presentation_downloader import ESPPresentationDownloader
    
    downloader = ESPPresentationDownloader(presentation_url)
    result = downloader.run()
"""

import logging
import os
import sys
from dataclasses import dataclass
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
)
from agent_tools import AgentTools, TOOLS_SCHEMA, create_tool_handler

logger = logging.getLogger(__name__)


# =============================================================================
# Prompt Builder
# =============================================================================

def build_download_prompt(presentation_url: str) -> str:
    """
    Build the CUA prompt for downloading an ESP presentation PDF.
    
    Args:
        presentation_url: URL of the ESP presentation (portal.mypromooffice.com)
    
    Returns:
        Formatted prompt string for the CUA
    """
    prompt = f"""You are a file download agent. Your goal is to navigate to an ESP presentation page and download the presentation as a PDF.

IMPORTANT CONTEXT:
- You are controlling a Linux desktop environment
- Firefox browser is available
- You must save the PDF to: {REMOTE_DOWNLOAD_DIR}
- Use a descriptive filename like: esp_presentation_[timestamp].pdf

TARGET URL:
{presentation_url}

=============================================================================
WORKFLOW
=============================================================================

PHASE 1: NAVIGATE TO PRESENTATION
1. Open Firefox browser
2. Navigate to: {presentation_url}
3. Wait for the page to fully load
4. Take a screenshot to confirm the presentation is visible

PHASE 2: DOWNLOAD THE PDF
1. Look for a "Download PDF" button or similar download option
   - Common button labels: "Download PDF", "Export", "Print", "Save"
   - It may be in a toolbar, header, or as an action button
2. Click the download button
3. If a dialog appears, select PDF format
4. Save the file to: {REMOTE_DOWNLOAD_DIR}
5. Use filename format: esp_presentation_[date]_[time].pdf
   - Example: esp_presentation_20250603_143052.pdf

PHASE 3: VERIFY AND REPORT
1. Verify the PDF was downloaded successfully
2. Take a screenshot showing the download completed
3. Call `report_downloaded_pdf` with:
   - sku: "presentation"
   - remote_path: Full path to the saved PDF (e.g., {REMOTE_DOWNLOAD_DIR}/esp_presentation_20250603_143052.pdf)
   - product_name: "ESP Presentation PDF"
4. Call `report_completion` to signal you are done

=============================================================================
TROUBLESHOOTING
=============================================================================

If you encounter issues:

1. **Page doesn't load**: 
   - Try refreshing the page
   - Check if a login is required (if so, log the error)

2. **Download button not visible**:
   - Look for a menu icon (three dots, hamburger menu)
   - Check the browser's File menu for Print/Save as PDF
   - Look for icons instead of text buttons

3. **Download fails**:
   - Try right-clicking and "Save as"
   - Use the browser's built-in PDF printer

4. **Login required**:
   - Call `log_error` with details about the login requirement
   - We may need to handle authentication separately

=============================================================================
AVAILABLE TOOLS
=============================================================================

1. `report_downloaded_pdf` - Report a successfully downloaded PDF
   Required: sku, remote_path, product_name

2. `log_error` - Log an error encountered
   Required: sku, message

3. `report_completion` - Report that the task is complete
   Required: total_processed, successful, failed

=============================================================================
BEGIN WORKFLOW
=============================================================================

Start by taking a screenshot to see the current state of the desktop, then proceed with Phase 1.
"""
    
    return prompt


# =============================================================================
# ESP Presentation Downloader Agent
# =============================================================================

@dataclass
class DownloadResult:
    """Result of the presentation download operation."""
    success: bool
    remote_path: Optional[str] = None
    error: Optional[str] = None
    screenshot_path: Optional[str] = None


class ESPPresentationDownloader:
    """
    CUA Agent for downloading ESP presentation PDFs.
    
    This agent navigates to portal.mypromooffice.com presentation URLs
    and downloads the presentation as a PDF.
    """
    
    def __init__(
        self,
        presentation_url: str,
        computer_id: Optional[str] = None,
        dry_run: bool = False
    ):
        """
        Initialize the ESP Presentation Downloader.
        
        Args:
            presentation_url: URL of the ESP presentation
            computer_id: Optional Orgo computer ID (defaults to ORGO_COMPUTER_ID)
            dry_run: If True, don't execute the CUA
        """
        self.presentation_url = presentation_url
        self.computer_id = computer_id or ORGO_COMPUTER_ID
        self.dry_run = dry_run
        
        self.computer: Optional[Computer] = None
        self.tools: Optional[AgentTools] = None
        
        # Set API keys in environment
        os.environ["ORGO_API_KEY"] = os.getenv("ORGO_API_KEY", "")
        os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY", "")
    
    def run(self) -> DownloadResult:
        """
        Execute the download workflow.
        
        Returns:
            DownloadResult with success status and file path
        """
        logger.info("=" * 60)
        logger.info("ESP PRESENTATION DOWNLOADER")
        logger.info("=" * 60)
        logger.info(f"URL: {self.presentation_url}")
        logger.info(f"Dry run: {self.dry_run}")
        
        if self.dry_run:
            logger.info("[DRY RUN] Skipping CUA execution")
            return DownloadResult(
                success=False,
                error="Dry run mode - no download performed"
            )
        
        try:
            # Initialize tools
            self.tools = AgentTools()
            
            # Initialize Orgo computer
            logger.info(f"Connecting to Orgo computer: {self.computer_id}")
            self.computer = Computer(computer_id=self.computer_id)
            logger.info(f"Connected to: orgo-{self.computer_id}.orgo.dev")
            
            # Build the prompt
            prompt = build_download_prompt(self.presentation_url)
            
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
            
            # Check results
            summary = self.tools.get_summary()
            downloaded_pdfs = summary.get("downloaded_pdfs", [])
            errors = summary.get("errors", [])
            
            if downloaded_pdfs:
                # Success - return the first downloaded PDF
                pdf_info = downloaded_pdfs[0]
                return DownloadResult(
                    success=True,
                    remote_path=pdf_info["remote_path"]
                )
            elif errors:
                # Failure with logged error
                error_msg = errors[0]["message"]
                return DownloadResult(
                    success=False,
                    error=error_msg
                )
            else:
                # No result
                return DownloadResult(
                    success=False,
                    error="No PDF downloaded and no error logged"
                )
            
        except Exception as e:
            logger.error(f"Download failed: {e}", exc_info=True)
            return DownloadResult(
                success=False,
                error=str(e)
            )


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point for testing the downloader."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Download ESP presentation PDF using Orgo CUA"
    )
    parser.add_argument(
        "url",
        type=str,
        help="URL of the ESP presentation"
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
    
    # Validate URL
    if "mypromooffice.com" not in args.url and "portal." not in args.url:
        print("Warning: URL does not appear to be from portal.mypromooffice.com", file=sys.stderr)
    
    # Run downloader
    downloader = ESPPresentationDownloader(
        presentation_url=args.url,
        computer_id=args.computer_id,
        dry_run=args.dry_run
    )
    
    result = downloader.run()
    
    if result.success:
        print(f"Success! PDF downloaded to: {result.remote_path}")
    else:
        print(f"Failed: {result.error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

