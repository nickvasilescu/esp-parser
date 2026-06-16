#!/usr/bin/env python3
"""
Agent Tools for ESP-Orgo CUA Orchestration.
Defines the tools available to the Orgo CUA for reporting downloaded PDFs and logging errors.
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes for Tracking
# =============================================================================

@dataclass
class DownloadedPDF:
    """Represents a successfully downloaded PDF from ESP+."""
    sku: str
    product_name: str
    remote_path: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    local_path: Optional[str] = None  # Filled in after retrieval


@dataclass
class ExtractionError:
    """Represents an error encountered during extraction."""
    sku: str
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# =============================================================================
# Tools Schema for Claude
# =============================================================================

TOOLS_SCHEMA = [
    {
        "name": "report_downloaded_pdf",
        "description": (
            "Report that a PDF has been successfully downloaded/saved on the VM. "
            "Call this after successfully saving a product's Distributor Report PDF."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sku": {
                    "type": "string",
                    "description": "The SKU/item number of the product."
                },
                "remote_path": {
                    "type": "string",
                    "description": "The full path where the PDF was saved on the VM (e.g., /home/user/Downloads/product.pdf)."
                },
                "product_name": {
                    "type": "string",
                    "description": "The name of the product."
                }
            },
            "required": ["sku", "remote_path", "product_name"]
        }
    },
    {
        "name": "log_error",
        "description": (
            "Log an error encountered during the extraction process. "
            "Call this if you cannot find or download a product's PDF."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sku": {
                    "type": "string",
                    "description": "The SKU/item number of the product (or 'unknown' if not applicable)."
                },
                "message": {
                    "type": "string",
                    "description": "A description of the error encountered."
                }
            },
            "required": ["sku", "message"]
        }
    },
    {
        "name": "report_completion",
        "description": (
            "Report that all items have been processed. "
            "Call this when you have finished processing all products in the list."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "total_processed": {
                    "type": "integer",
                    "description": "Total number of products processed."
                },
                "successful": {
                    "type": "integer",
                    "description": "Number of successfully downloaded PDFs."
                },
                "failed": {
                    "type": "integer",
                    "description": "Number of failed downloads."
                },
                "summary": {
                    "type": "string",
                    "description": "A brief summary of the extraction session."
                }
            },
            "required": ["total_processed", "successful", "failed"]
        }
    }
]


# =============================================================================
# Agent Tools Class
# =============================================================================

class AgentTools:
    """
    Tools class that the Orgo CUA can invoke to report progress.
    """
    
    def __init__(self):
        self.downloaded_pdfs: List[DownloadedPDF] = []
        self.errors: List[ExtractionError] = []
        self.completion_reported: bool = False
        self.completion_summary: Optional[Dict[str, Any]] = None
    
    def report_downloaded_pdf(
        self,
        sku: str,
        remote_path: str,
        product_name: str
    ) -> Dict[str, Any]:
        """
        Report that a PDF has been successfully downloaded.
        
        Args:
            sku: The SKU/item number of the product.
            remote_path: The full path where the PDF was saved on the VM.
            product_name: The name of the product.
        
        Returns:
            Confirmation of the reported download.
        """
        pdf = DownloadedPDF(
            sku=sku,
            remote_path=remote_path,
            product_name=product_name
        )
        self.downloaded_pdfs.append(pdf)
        
        logger.info(f"PDF reported: {sku} -> {remote_path}")
        
        return {
            "status": "success",
            "message": f"Recorded download of {product_name} ({sku}) at {remote_path}",
            "total_downloaded": len(self.downloaded_pdfs)
        }
    
    def log_error(self, sku: str, message: str) -> Dict[str, Any]:
        """
        Log an error encountered during extraction.
        
        Args:
            sku: The SKU/item number of the product.
            message: A description of the error encountered.
        
        Returns:
            Confirmation of the logged error.
        """
        error = ExtractionError(sku=sku, message=message)
        self.errors.append(error)
        
        logger.warning(f"Error logged for {sku}: {message}")
        
        return {
            "status": "logged",
            "message": f"Error logged for {sku}",
            "total_errors": len(self.errors)
        }
    
    def report_completion(
        self,
        total_processed: int,
        successful: int,
        failed: int,
        summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Report that all items have been processed.
        
        Args:
            total_processed: Total number of products processed.
            successful: Number of successfully downloaded PDFs.
            failed: Number of failed downloads.
            summary: A brief summary of the extraction session.
        
        Returns:
            Confirmation of completion.
        """
        self.completion_reported = True
        self.completion_summary = {
            "total_processed": total_processed,
            "successful": successful,
            "failed": failed,
            "summary": summary or "Extraction complete."
        }
        
        logger.info(f"Completion reported: {successful}/{total_processed} successful, {failed} failed")
        
        return {
            "status": "complete",
            "message": "Extraction session marked as complete.",
            **self.completion_summary
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the extraction session.
        
        Returns:
            Summary dictionary with all tracked data.
        """
        return {
            "downloaded_pdfs": [asdict(pdf) for pdf in self.downloaded_pdfs],
            "errors": [asdict(err) for err in self.errors],
            "completion_reported": self.completion_reported,
            "completion_summary": self.completion_summary,
            "stats": {
                "total_downloaded": len(self.downloaded_pdfs),
                "total_errors": len(self.errors)
            }
        }


def create_tool_handler(tools: AgentTools):
    """
    Create a tool handler function for use with Orgo Computer.prompt().
    
    Args:
        tools: An AgentTools instance.
    
    Returns:
        A function that dispatches tool calls to the appropriate method.
    """
    def handler(tool_name: str, tool_input: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        tool_input = tool_input or {}
        
        if hasattr(tools, tool_name):
            method = getattr(tools, tool_name)
            return method(**tool_input)
        else:
            return {
                "status": "error",
                "message": f"Unknown tool: {tool_name}"
            }
    
    return handler

