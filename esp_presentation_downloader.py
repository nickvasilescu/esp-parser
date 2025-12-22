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

# Import JobStateManager for state updates (optional dependency)
try:
    from job_state import JobStateManager, WorkflowStatus
except ImportError:
    JobStateManager = None
    WorkflowStatus = None

logger = logging.getLogger(__name__)


# =============================================================================
# Prompt Builder
# =============================================================================

def build_download_prompt(
    presentation_url: str,
    job_id: str
) -> str:
    """
    Build the CUA prompt for downloading an ESP presentation PDF.

    The prompt instructs the agent to save the PDF locally. File export
    is handled separately via Orgo API after the CUA completes.

    Args:
        presentation_url: URL of the ESP presentation (portal.mypromooffice.com)
        job_id: Unique job identifier for organizing files

    Returns:
        Formatted prompt string for the CUA
    """
    working_dir = f"~/Downloads/{job_id}"
    target_file = f"{working_dir}/presentation.pdf"

    prompt = f"""You are a file download agent. Your goal is to navigate to an ESP presentation page and download the presentation as a PDF.

IMPORTANT CONTEXT:
- You are controlling a Linux desktop environment
- Google Chrome browser is available
- You have Terminal access for file operations
- Job ID: {job_id}
- Working directory: {working_dir}

TARGET URL:
{presentation_url}

=============================================================================
WORKFLOW
=============================================================================

PHASE 1: SETUP WORKING DIRECTORY
1. Open a Terminal (or use an existing one)
2. Create the working directory:
   mkdir -p {working_dir}
3. Verify it was created:
   ls -la ~/Downloads/

PHASE 2: NAVIGATE TO PRESENTATION
1. Open Google Chrome browser
2. Navigate to: {presentation_url}
3. Wait for the page to fully load
4. Take a screenshot to confirm the presentation is visible

PHASE 3: DOWNLOAD THE PDF
1. Look for a "Download PDF" button or similar download option
   - Common button labels: "Download PDF", "Export", "Print", "Save"
   - It may be in a toolbar, header, or as an action button
2. Click the download button
3. Wait for the download to complete
   - Chrome will show a download bar at the bottom
   - The download typically goes to ~/Downloads by default
4. Take a screenshot to confirm download completed

PHASE 4: IDENTIFY AND MOVE THE FILE
1. Go to Terminal
2. Find the most recently downloaded PDF:
   ls -lt ~/Downloads/*.pdf | head -n 2
3. The newest file is your downloaded presentation
4. Move and rename it to the working directory:
   mv "$(ls -t ~/Downloads/*.pdf | head -1)" {target_file}
5. Verify the file exists:
   ls -la {target_file}

PHASE 5: COMPLETION
1. Take a final screenshot showing the file exists
2. Confirm the file is at: {target_file}
3. Your task is complete

=============================================================================
IMPORTANT COMMANDS REFERENCE
=============================================================================

Create working directory:
  mkdir -p {working_dir}

Find newest PDF in Downloads:
  ls -t ~/Downloads/*.pdf | head -1

Move file to working directory:
  mv "$(ls -t ~/Downloads/*.pdf | head -1)" {target_file}

Verify file exists:
  ls -la {target_file}

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

4. **No PDF found in Downloads**:
   - List all files: ls -la ~/Downloads/
   - Look for recently modified files: ls -lt ~/Downloads/ | head -5

5. **Login required**:
   - Call `log_error` with details about the login requirement
   - We may need to handle authentication separately

=============================================================================
BEGIN WORKFLOW
=============================================================================

Start by taking a screenshot to see the current state of the desktop, then proceed with Phase 1 (Setup Working Directory).
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
    and downloads the presentation as a PDF to the VM's local storage.
    File export is handled separately via Orgo API after the CUA completes.
    """

    def __init__(
        self,
        presentation_url: str,
        job_id: str,
        computer_id: Optional[str] = None,
        dry_run: bool = False,
        state_manager: Optional["JobStateManager"] = None
    ):
        """
        Initialize the ESP Presentation Downloader.

        Args:
            presentation_url: URL of the ESP presentation
            job_id: Unique job identifier for organizing files
            computer_id: Optional Orgo computer ID (defaults to ORGO_COMPUTER_ID)
            dry_run: If True, don't execute the CUA
            state_manager: Optional JobStateManager for state updates
        """
        self.presentation_url = presentation_url
        self.job_id = job_id
        self.computer_id = computer_id or ORGO_COMPUTER_ID
        self.dry_run = dry_run
        self.state_manager = state_manager

        self.computer: Optional[Computer] = None

        # Set API keys in environment
        os.environ["ORGO_API_KEY"] = os.getenv("ORGO_API_KEY", "")
        os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY", "")
    
    def _update_state(self, status: str, **kwargs) -> None:
        """Update job state if state manager is available."""
        if self.state_manager and WorkflowStatus:
            self.state_manager.update(status, **kwargs)

    def run(self) -> DownloadResult:
        """
        Execute the download workflow.

        Returns:
            DownloadResult with success status and file path
        """
        logger.info("=" * 60)
        logger.info("ESP PRESENTATION DOWNLOADER")
        logger.info("=" * 60)
        logger.info(f"Job ID: {self.job_id}")
        logger.info(f"URL: {self.presentation_url}")
        logger.info(f"Computer ID: {self.computer_id}")
        logger.info(f"Dry run: {self.dry_run}")

        if self.dry_run:
            logger.info("[DRY RUN] Skipping CUA execution")
            return DownloadResult(
                success=False,
                error="Dry run mode - no download performed"
            )

        try:
            # Emit state: downloading presentation
            self._update_state(
                WorkflowStatus.ESP_DOWNLOADING_PRESENTATION.value if WorkflowStatus else "esp_downloading_presentation"
            )

            # Initialize Orgo computer
            logger.info(f"Connecting to Orgo computer: {self.computer_id}")
            self.computer = Computer(computer_id=self.computer_id)
            logger.info(f"Connected to: orgo-{self.computer_id}.orgo.dev")

            # Emit checkpoint for CUA start
            if self.state_manager:
                self.state_manager.emit_thought(
                    agent="cua_presentation",
                    event_type="checkpoint",
                    content="Starting CUA to download presentation PDF",
                    metadata={"presentation_url": self.presentation_url}
                )

            # Build the prompt
            prompt = build_download_prompt(
                presentation_url=self.presentation_url,
                job_id=self.job_id
            )

            # Define progress callback
            def progress_callback(event_type: str, event_data: Any) -> None:
                if event_type == "text":
                    logger.info(f"Claude: {event_data}")
                    # Emit thought for text output
                    if self.state_manager:
                        self.state_manager.emit_thought(
                            agent="cua_presentation",
                            event_type="thought",
                            content=str(event_data)[:500]  # Truncate long text
                        )
                elif event_type == "tool_use":
                    action = event_data.get('action', 'unknown')
                    logger.info(f"Action: {action}")
                    # Emit thought for tool use
                    if self.state_manager:
                        self.state_manager.emit_thought(
                            agent="cua_presentation",
                            event_type="action",
                            content=f"Executing: {action}",
                            details=event_data
                        )
                elif event_type == "thinking":
                    logger.debug(f"Thinking: {event_data[:200]}...")
                    # Emit thought for thinking
                    if self.state_manager:
                        self.state_manager.emit_thought(
                            agent="cua_presentation",
                            event_type="thought",
                            content=str(event_data)[:500]
                        )
                elif event_type == "error":
                    logger.error(f"Error: {event_data}")
                    # Emit thought for error
                    if self.state_manager:
                        self.state_manager.emit_thought(
                            agent="cua_presentation",
                            event_type="error",
                            content=str(event_data)[:500]
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
            if self.state_manager:
                self.state_manager.emit_thought(
                    agent="cua_presentation",
                    event_type="success",
                    content="Presentation PDF downloaded to VM",
                    metadata={"vm_path": f"~/Downloads/{self.job_id}/presentation.pdf"}
                )

            # The agent saved the file to the VM's local storage
            # The orchestrator will export it via Orgo API
            return DownloadResult(
                success=True,
                remote_path=f"Downloads/{self.job_id}/presentation.pdf"
            )

        except Exception as e:
            logger.error(f"Download failed: {e}", exc_info=True)
            if self.state_manager:
                self.state_manager.add_error(
                    step="esp_downloading_presentation",
                    message=str(e),
                    recoverable=False
                )
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
    from datetime import datetime
    
    parser = argparse.ArgumentParser(
        description="Download ESP presentation PDF using Orgo CUA"
    )
    parser.add_argument(
        "url",
        type=str,
        help="URL of the ESP presentation"
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
    
    # Validate URL
    if "mypromooffice.com" not in args.url and "portal." not in args.url:
        print("Warning: URL does not appear to be from portal.mypromooffice.com", file=sys.stderr)

    # Generate job ID if not provided
    job_id = args.job_id or f"esp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Run downloader
    downloader = ESPPresentationDownloader(
        presentation_url=args.url,
        job_id=job_id,
        computer_id=args.computer_id,
        dry_run=args.dry_run
    )

    result = downloader.run()

    if result.success:
        print(f"Success! PDF saved to VM at: {result.remote_path}")
        print(f"Use Orgo File Export API to retrieve the file")
    else:
        print(f"Failed: {result.error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

