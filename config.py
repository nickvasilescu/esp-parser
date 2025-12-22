#!/usr/bin/env python3
"""
Configuration for ESP-Orgo CUA Orchestration.
Handles environment variable loading and validation.
"""

import os
import sys
from typing import Optional

# Load environment variables from .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# =============================================================================
# Required API Keys
# =============================================================================

ORGO_API_KEY: Optional[str] = os.getenv("ORGO_API_KEY")
ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")


# =============================================================================
# Orgo Computer Configuration
# =============================================================================

# Existing computer instance ID to reuse
ORGO_COMPUTER_ID: Optional[str] = os.getenv("ORGO_COMPUTER_ID")

# Display settings (matching Orgo defaults)
DISPLAY_WIDTH: int = int(os.getenv("DISPLAY_WIDTH", "1024"))
DISPLAY_HEIGHT: int = int(os.getenv("DISPLAY_HEIGHT", "768"))


# =============================================================================
# ESP Plus Configuration
# =============================================================================

ESP_PLUS_EMAIL: Optional[str] = os.getenv("ESP_PLUS_EMAIL")
ESP_PLUS_PASSWORD: Optional[str] = os.getenv("ESP_PLUS_PASSWORD")
ESP_PLUS_URL: str = os.getenv("ESP_PLUS_URL", "https://espplus.com")

# ESP Presentation Portal
ESP_PORTAL_URL: str = os.getenv("ESP_PORTAL_URL", "https://portal.mypromooffice.com")


# =============================================================================
# File Storage (Orgo File Export)
# =============================================================================
# Files are stored on Orgo VM and exported via Orgo API
# No AWS S3 configuration needed - uses Orgo's native file export


# =============================================================================
# SAGE Configuration (Placeholder - API access pending)
# =============================================================================

SAGE_API_KEY: Optional[str] = os.getenv("SAGE_API_KEY")
SAGE_API_SECRET: Optional[str] = os.getenv("SAGE_API_SECRET")
SAGE_API_URL: str = os.getenv("SAGE_API_URL", "https://api.sageworld.com")

# SAGE Presentation URL pattern
SAGE_PRESENTATION_DOMAIN: str = "viewpresentation.com"


# =============================================================================
# Output Configuration
# =============================================================================

# Directory for downloaded PDFs and JSON output files
OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "output")

# Remote directory on Orgo VM where PDFs are saved
REMOTE_DOWNLOAD_DIR: str = os.getenv("REMOTE_DOWNLOAD_DIR", "/home/user/Downloads")


# =============================================================================
# Agent Configuration
# =============================================================================

# Claude model ID for the CUA
MODEL_ID: str = os.getenv("MODEL_ID", "claude-opus-4-5-20251101")

# Thinking budget for extended thinking
THINKING_BUDGET: int = int(os.getenv("THINKING_BUDGET", "2048"))

# Maximum iterations for the agent loop
MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "100"))

# Maximum tokens for Claude responses
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "16384"))


# =============================================================================
# Validation
# =============================================================================

def validate_config() -> None:
    """
    Validate that all required configuration values are present.
    Raises SystemExit if any required values are missing.
    """
    errors = []
    
    # Check required API keys
    if not ORGO_API_KEY:
        errors.append("ORGO_API_KEY environment variable is required")
    
    if not ANTHROPIC_API_KEY:
        errors.append("ANTHROPIC_API_KEY environment variable is required")
    
    # Check required Orgo configuration
    if not ORGO_COMPUTER_ID:
        errors.append("ORGO_COMPUTER_ID environment variable is required")
    
    # Check required ESP Plus configuration
    if not ESP_PLUS_EMAIL:
        errors.append("ESP_PLUS_EMAIL environment variable is required")

    if not ESP_PLUS_PASSWORD:
        errors.append("ESP_PLUS_PASSWORD environment variable is required")
    
    # Report all errors
    if errors:
        print("Configuration Error(s):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        print("\nPlease set the required environment variables and try again.", file=sys.stderr)
        sys.exit(1)


def get_config_summary() -> str:
    """
    Get a summary of the current configuration (for logging).
    Sensitive values are masked.
    """
    sage_api_status = "Configured" if SAGE_API_KEY else "Not configured (pending)"

    return f"""
Multi-Source Orchestration Configuration:
  Orgo:
    - Computer ID: {ORGO_COMPUTER_ID}
    - Display: {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}

  ESP Pipeline:
    - ESP Plus URL: {ESP_PLUS_URL}
    - ESP Plus Email: {ESP_PLUS_EMAIL}
    - ESP Portal URL: {ESP_PORTAL_URL}

  SAGE Pipeline:
    - API Status: {sage_api_status}
    - Presentation Domain: {SAGE_PRESENTATION_DOMAIN}

  File Storage:
    - Method: Orgo File Export API
    - Files saved to: ~/Downloads/{{job_id}}/

  Agent:
    - Model: {MODEL_ID}
    - Thinking Budget: {THINKING_BUDGET}
    - Max Iterations: {MAX_ITERATIONS}

  Output:
    - Output Directory: {OUTPUT_DIR}
    - Remote Download Dir: {REMOTE_DOWNLOAD_DIR}
"""


if __name__ == "__main__":
    # Test configuration validation
    print("Validating configuration...")
    validate_config()
    print("Configuration is valid!")
    print(get_config_summary())

