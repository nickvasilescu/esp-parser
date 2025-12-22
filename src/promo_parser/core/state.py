"""
Job State Management for Dashboard Progress Tracking

This module provides state management for tracking job progress across
the ESP and SAGE workflows. States are persisted to JSON files that
the dashboard can poll for real-time updates.
"""

import json
import uuid
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import Enum


class WorkflowStatus(str, Enum):
    """All observable workflow states for ESP and SAGE pipelines."""

    # === INITIALIZATION ===
    QUEUED = "queued"
    DETECTING_SOURCE = "detecting_source"

    # === ESP PIPELINE ===
    ESP_DOWNLOADING_PRESENTATION = "esp_downloading_presentation"
    ESP_UPLOADING_TO_S3 = "esp_uploading_to_s3"
    ESP_PARSING_PRESENTATION = "esp_parsing_presentation"
    ESP_LOOKING_UP_PRODUCTS = "esp_looking_up_products"
    ESP_DOWNLOADING_PRODUCTS = "esp_downloading_products"
    ESP_PARSING_PRODUCTS = "esp_parsing_products"
    ESP_MERGING_DATA = "esp_merging_data"

    # === SAGE PIPELINE ===
    SAGE_CALLING_API = "sage_calling_api"
    SAGE_PARSING_RESPONSE = "sage_parsing_response"
    SAGE_ENRICHING_PRODUCTS = "sage_enriching_products"

    # === NORMALIZATION (SHARED) ===
    NORMALIZING = "normalizing"
    SAVING_OUTPUT = "saving_output"

    # === ZOHO INTEGRATION (OPTIONAL) ===
    ZOHO_SEARCHING_CUSTOMER = "zoho_searching_customer"
    ZOHO_DISCOVERING_FIELDS = "zoho_discovering_fields"
    ZOHO_UPLOADING_ITEMS = "zoho_uploading_items"
    ZOHO_UPLOADING_IMAGES = "zoho_uploading_images"
    ZOHO_CREATING_QUOTE = "zoho_creating_quote"

    # === CALCULATOR (OPTIONAL) ===
    CALC_GENERATING = "calc_generating"
    CALC_UPLOADING = "calc_uploading"

    # === REVIEW & TERMINAL ===
    AWAITING_QA = "awaiting_qa"
    COMPLETED = "completed"
    ERROR = "error"
    PARTIAL_SUCCESS = "partial_success"


# Progress weights for each state (used for calculating overall progress)
PROGRESS_WEIGHTS: Dict[str, int] = {
    # Initialization
    "queued": 0,
    "detecting_source": 2,

    # ESP Pipeline (total: 60%)
    "esp_downloading_presentation": 8,
    "esp_uploading_to_s3": 2,
    "esp_parsing_presentation": 10,
    "esp_looking_up_products": 15,
    "esp_downloading_products": 10,
    "esp_parsing_products": 10,
    "esp_merging_data": 5,

    # SAGE Pipeline (total: 35%)
    "sage_calling_api": 10,
    "sage_parsing_response": 10,
    "sage_enriching_products": 15,

    # Normalization
    "normalizing": 5,
    "saving_output": 3,

    # Zoho Integration
    "zoho_searching_customer": 3,
    "zoho_discovering_fields": 2,
    "zoho_uploading_items": 12,
    "zoho_uploading_images": 5,
    "zoho_creating_quote": 8,

    # Calculator
    "calc_generating": 5,
    "calc_uploading": 3,

    # Terminal
    "awaiting_qa": 0,
    "completed": 100,
    "error": 0,
    "partial_success": 0,
}


@dataclass
class JobError:
    """Represents an error that occurred during job processing."""
    step: str
    message: str
    product_id: Optional[str] = None
    recoverable: bool = True


@dataclass
class JobFeatures:
    """Feature flags for the job."""
    zoho_upload: bool = False
    zoho_quote: bool = False
    calculator: bool = False


@dataclass
class JobState:
    """Complete state of a job for dashboard display."""
    job_id: str
    status: str
    platform: str
    progress: int

    # Sub-progress for multi-item states
    current_item: Optional[int] = None
    total_items: Optional[int] = None
    current_item_name: Optional[str] = None

    # Feature flags
    features: JobFeatures = field(default_factory=JobFeatures)

    # Timestamps
    started_at: str = ""
    updated_at: str = ""

    # Links (populated as they become available)
    presentation_pdf_url: Optional[str] = None
    output_json_url: Optional[str] = None
    zoho_item_link: Optional[str] = None
    zoho_quote_link: Optional[str] = None
    calculator_link: Optional[str] = None

    # Error tracking
    errors: List[JobError] = field(default_factory=list)

    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.utcnow().isoformat() + "Z"
        self.updated_at = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "platform": self.platform,
            "progress": self.progress,
            "current_item": self.current_item,
            "total_items": self.total_items,
            "current_item_name": self.current_item_name,
            "features": asdict(self.features),
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "presentation_pdf_url": self.presentation_pdf_url,
            "output_json_url": self.output_json_url,
            "zoho_item_link": self.zoho_item_link,
            "zoho_quote_link": self.zoho_quote_link,
            "calculator_link": self.calculator_link,
            "errors": [asdict(e) for e in self.errors],
        }


class JobStateManager:
    """
    Manages job state persistence for dashboard polling.

    Writes state to JSON files in the output directory that the
    dashboard can poll for real-time updates.
    """

    def __init__(
        self,
        job_id: str,
        output_dir: Path,
        platform: str = "",
        zoho_upload: bool = False,
        zoho_quote: bool = False,
        calculator: bool = False,
    ):
        self.job_id = job_id
        self.output_dir = Path(output_dir)
        self.state_file = self.output_dir / f"job_{job_id}_state.json"
        self.thoughts_file = self.output_dir / f"job_{job_id}_thoughts.jsonl"

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize state
        self.state = JobState(
            job_id=job_id,
            status=WorkflowStatus.QUEUED.value,
            platform=platform,
            progress=0,
            features=JobFeatures(
                zoho_upload=zoho_upload,
                zoho_quote=zoho_quote,
                calculator=calculator,
            ),
        )

        # Calculate total weight for progress normalization
        self._total_weight = self._calculate_total_weight()
        self._completed_weight = 0

        # Write initial state
        self._write()

    def _calculate_total_weight(self) -> int:
        """Calculate total progress weight based on platform and features."""
        total = 2  # detecting_source

        if self.state.platform == "ESP":
            total += 60  # ESP pipeline weights
        elif self.state.platform == "SAGE":
            total += 35  # SAGE pipeline weights
        else:
            # Unknown platform, assume ESP as default
            total += 60

        total += 8  # normalizing + saving_output

        if self.state.features.zoho_upload:
            total += 22  # customer + fields + items + images
        if self.state.features.zoho_quote:
            total += 8
        if self.state.features.calculator:
            total += 8

        return total

    def update(
        self,
        status: str,
        progress: Optional[int] = None,
        current_item: Optional[int] = None,
        total_items: Optional[int] = None,
        current_item_name: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        Update job state and persist to file.

        Args:
            status: New workflow status
            progress: Optional explicit progress (0-100), auto-calculated if not provided
            current_item: Current item index for multi-item states
            total_items: Total items for multi-item states
            current_item_name: Name of current item being processed
            **kwargs: Additional state fields to update
        """
        self.state.status = status

        # Auto-calculate progress if not explicitly provided
        if progress is not None:
            self.state.progress = progress
        else:
            self.state.progress = self._calculate_progress(status, current_item, total_items)

        # Update sub-progress fields
        if current_item is not None:
            self.state.current_item = current_item
        if total_items is not None:
            self.state.total_items = total_items
        if current_item_name is not None:
            self.state.current_item_name = current_item_name

        # Update any additional fields
        for key, value in kwargs.items():
            if hasattr(self.state, key):
                setattr(self.state, key, value)

        self._write()

    def set_platform(self, platform: str) -> None:
        """Set platform and recalculate total weight."""
        self.state.platform = platform
        self._total_weight = self._calculate_total_weight()
        self._write()

    def add_error(
        self,
        step: str,
        message: str,
        product_id: Optional[str] = None,
        recoverable: bool = True,
    ) -> None:
        """Add an error to the job state."""
        error = JobError(
            step=step,
            message=message,
            product_id=product_id,
            recoverable=recoverable,
        )
        self.state.errors.append(error)
        self._write()

    def set_link(self, link_type: str, url: str) -> None:
        """Set a result link (presentation_pdf, output_json, zoho_item, zoho_quote, calculator)."""
        link_field = f"{link_type}_url" if not link_type.endswith("_url") and not link_type.endswith("_link") else link_type
        if link_field == "presentation_pdf":
            link_field = "presentation_pdf_url"
        elif link_field == "output_json":
            link_field = "output_json_url"
        elif link_field == "zoho_item":
            link_field = "zoho_item_link"
        elif link_field == "zoho_quote":
            link_field = "zoho_quote_link"
        elif link_field == "calculator":
            link_field = "calculator_link"

        if hasattr(self.state, link_field):
            setattr(self.state, link_field, url)
            self._write()

    def _calculate_progress(
        self,
        status: str,
        current_item: Optional[int] = None,
        total_items: Optional[int] = None,
    ) -> int:
        """Calculate progress percentage based on current status."""
        if status == "completed":
            return 100
        if status in ("error", "partial_success"):
            return self.state.progress  # Keep current progress

        # Get base progress from weight
        weight = PROGRESS_WEIGHTS.get(status, 0)

        # Calculate cumulative progress up to current state
        status_order = list(PROGRESS_WEIGHTS.keys())
        try:
            status_idx = status_order.index(status)
            cumulative = sum(PROGRESS_WEIGHTS.get(s, 0) for s in status_order[:status_idx])
        except ValueError:
            cumulative = 0

        # Add partial progress within current state for multi-item operations
        if current_item is not None and total_items is not None and total_items > 0:
            partial = (current_item / total_items) * weight
            cumulative += partial
        else:
            cumulative += weight

        # Normalize to percentage
        if self._total_weight > 0:
            progress = int((cumulative / self._total_weight) * 100)
        else:
            progress = 0

        return min(progress, 99)  # Cap at 99 until explicitly completed

    def _write(self) -> None:
        """Write state to JSON file."""
        self.state.updated_at = datetime.utcnow().isoformat() + "Z"
        with open(self.state_file, 'w') as f:
            json.dump(self.state.to_dict(), f, indent=2)

    def complete(self, status: str = "completed") -> None:
        """Mark job as complete (or error/partial_success)."""
        self.update(status=status, progress=100 if status == "completed" else self.state.progress)

    def fail(self, message: str, step: Optional[str] = None) -> None:
        """Mark job as failed with error message."""
        if step:
            self.add_error(step=step, message=message, recoverable=False)
        self.update(status="error")

    def emit_thought(
        self,
        agent: str,
        event_type: str,
        content: str,
        details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Emit a thought entry to the JSONL file for real-time agent reasoning streaming.

        Args:
            agent: Agent identifier (orchestrator, cua_presentation, cua_product,
                   claude_parser, sage_api, zoho_item_agent, zoho_quote_agent, calculator_agent)
            event_type: Type of event (thought, action, observation, checkpoint,
                        tool_use, error, success)
            content: Human-readable description of the thought/action
            details: Optional structured data (tool args, results, etc.)
            metadata: Optional extra context (product_id, step_number, etc.)
        """
        entry = {
            "id": f"t_{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "job_id": self.job_id,
            "agent": agent,
            "event_type": event_type,
            "content": content,
            "details": details,
            "metadata": metadata,
        }
        with open(self.thoughts_file, 'a') as f:
            f.write(json.dumps(entry) + "\n")
