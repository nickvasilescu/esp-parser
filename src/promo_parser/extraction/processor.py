#!/usr/bin/env python3
"""
Generic PDF Processor - Extract structured data from PDFs using Claude with swappable prompts.

This module provides a reusable PDF processing pipeline that can be configured with
different system prompts for various extraction tasks:
- Product sell sheets (using prompts/product.py)
- ESP presentation PDFs (using prompts/presentation.py)
- Any other PDF extraction task

Usage:
    from promo_parser.extraction.processor import process_pdf
    from promo_parser.extraction.prompts.product import EXTRACTION_PROMPT

    result = process_pdf("file.pdf", client, system_prompt=EXTRACTION_PROMPT)
"""

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from anthropic import Anthropic

logger = logging.getLogger(__name__)


# =============================================================================
# Core Processing Functions
# =============================================================================

def load_pdf_as_base64(pdf_path: str) -> str:
    """
    Read a PDF file and return its base64-encoded content.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Base64-encoded PDF content as a string
    """
    with open(pdf_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def extract_json_from_response(response_text: str) -> dict:
    """
    Extract JSON from Claude's response, handling code blocks if present.
    
    Args:
        response_text: Raw response text from Claude
        
    Returns:
        Parsed JSON as a dictionary
        
    Raises:
        ValueError: If JSON cannot be extracted/parsed
    """
    response_text = response_text.strip()
    
    # If response starts with ```, try to extract JSON from code block
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        json_lines = []
        in_json = False
        for line in lines:
            if line.startswith("```") and not in_json:
                in_json = True
                continue
            elif line.startswith("```") and in_json:
                break
            elif in_json:
                json_lines.append(line)
        response_text = "\n".join(json_lines)
    
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}\nResponse: {response_text[:500]}...")


def process_pdf(
    pdf_path: str,
    client: Anthropic,
    system_prompt: str,
    model: str = "claude-opus-4-5-20251101",
    max_tokens: int = 32768  # Opus 4.5 supports up to 64k output tokens
) -> Dict[str, Any]:
    """
    Process a single PDF file using Claude and return extracted data.
    
    This is the core function that handles PDF-to-JSON extraction with
    configurable prompts.
    
    Args:
        pdf_path: Path to the PDF file
        client: Anthropic API client
        system_prompt: The system prompt defining extraction rules
        model: Claude model to use (default: claude-opus-4-5-20251101)
        max_tokens: Maximum response tokens (default: 32768, Opus 4.5 max is 64k)
        
    Returns:
        Extracted data as a dictionary
        
    Raises:
        FileNotFoundError: If the PDF file doesn't exist
        ValueError: If the API response cannot be parsed as JSON
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    logger.info(f"Processing PDF: {pdf_path}")
    
    pdf_base64 = load_pdf_as_base64(pdf_path)
    
    # Use streaming for large max_tokens requests (required by Anthropic SDK for long operations)
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_base64
                        }
                    }
                ]
            }
        ]
    ) as stream:
        # Collect streamed text using SDK helper
        response_text = stream.get_final_text()
    
    # Parse and return JSON
    result = extract_json_from_response(response_text)
    logger.info(f"Successfully processed: {pdf_path}")
    
    return result


def process_pdf_batch(
    pdf_paths: List[str],
    client: Anthropic,
    system_prompt: str,
    model: str = "claude-opus-4-5-20251101",
    max_tokens: int = 32768  # Opus 4.5 supports up to 64k output tokens
) -> List[Dict[str, Any]]:
    """
    Process multiple PDF files and return results.
    
    Args:
        pdf_paths: List of PDF file paths
        client: Anthropic API client
        system_prompt: The system prompt defining extraction rules
        model: Claude model to use
        max_tokens: Maximum response tokens
        
    Returns:
        List of result dictionaries, each containing:
        - file: The PDF path
        - success: Boolean indicating success
        - data: Extracted data (if successful)
        - error: Error message (if failed)
    """
    results = []
    total = len(pdf_paths)
    
    for i, pdf_path in enumerate(pdf_paths, 1):
        logger.info(f"Processing [{i}/{total}]: {pdf_path}")
        
        result = {"file": pdf_path, "success": False}
        
        try:
            data = process_pdf(pdf_path, client, system_prompt, model, max_tokens)
            result["success"] = True
            result["data"] = data
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Failed to process {pdf_path}: {e}")
        
        results.append(result)
    
    return results


# =============================================================================
# Output Functions
# =============================================================================

def save_json_output(
    data: Dict[str, Any],
    pdf_path: str,
    output_dir: Optional[str] = None
) -> str:
    """
    Save extracted JSON data to a file.
    
    Args:
        data: The extracted data dictionary
        pdf_path: Original PDF file path (used to derive output filename)
        output_dir: Optional custom output directory
        
    Returns:
        Path to the saved JSON file
    """
    pdf_path = Path(pdf_path)
    
    if output_dir:
        output_path = Path(output_dir) / f"{pdf_path.stem}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = pdf_path.with_suffix(".json")
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved output to: {output_path}")
    return str(output_path)


# =============================================================================
# Directory Processing
# =============================================================================

def process_directory(
    dir_path: str,
    client: Anthropic,
    system_prompt: str,
    output_mode: str = "both",
    output_dir: Optional[str] = None,
    model: str = "claude-opus-4-5-20251101",
    max_tokens: int = 32768  # Opus 4.5 supports up to 64k output tokens
) -> List[Dict[str, Any]]:
    """
    Process all PDF files in a directory.
    
    Args:
        dir_path: Path to directory containing PDFs
        client: Anthropic API client
        system_prompt: The system prompt defining extraction rules
        output_mode: One of 'stdout', 'file', or 'both'
        output_dir: Optional custom output directory for JSON files
        model: Claude model to use
        max_tokens: Maximum response tokens
        
    Returns:
        List of results (each with 'file', 'success', 'data' or 'error')
    """
    import sys
    
    dir_path = Path(dir_path)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a valid directory: {dir_path}")
    
    pdf_files = list(dir_path.glob("*.pdf")) + list(dir_path.glob("*.PDF"))
    
    if not pdf_files:
        logger.warning(f"No PDF files found in {dir_path}")
        return []
    
    results = []
    total = len(pdf_files)
    
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"Processing [{i}/{total}]: {pdf_file.name}...", file=sys.stderr)
        
        result = {"file": str(pdf_file), "success": False}
        
        try:
            data = process_pdf(str(pdf_file), client, system_prompt, model, max_tokens)
            result["success"] = True
            result["data"] = data
            
            # Handle output based on mode
            if output_mode in ("stdout", "both"):
                print(f"\n--- {pdf_file.name} ---")
                print(json.dumps(data, indent=2, ensure_ascii=False))
            
            if output_mode in ("file", "both"):
                saved_path = save_json_output(data, str(pdf_file), output_dir)
                print(f"  Saved to: {saved_path}", file=sys.stderr)
                result["output_file"] = saved_path
                
        except Exception as e:
            result["error"] = str(e)
            print(f"  Error: {e}", file=sys.stderr)
        
        results.append(result)
    
    return results


# =============================================================================
# Convenience Functions (for backward compatibility)
# =============================================================================

def process_product_sellsheet(
    pdf_path: str,
    client: Anthropic,
    model: str = "claude-opus-4-5-20251101"
) -> Dict[str, Any]:
    """
    Process a product sell sheet PDF using the standard extraction prompt.
    
    This is a convenience wrapper for backward compatibility with esp_parser.py.
    
    Args:
        pdf_path: Path to the PDF file
        client: Anthropic API client
        model: Claude model to use
        
    Returns:
        Extracted product data as a dictionary
    """
    from promo_parser.extraction.prompts.product import EXTRACTION_PROMPT
    return process_pdf(pdf_path, client, EXTRACTION_PROMPT, model)


def process_presentation_pdf(
    pdf_path: str,
    client: Anthropic,
    model: str = "claude-opus-4-5-20251101"
) -> Dict[str, Any]:
    """
    Process an ESP presentation PDF to extract product list.
    
    Args:
        pdf_path: Path to the presentation PDF file
        client: Anthropic API client
        model: Claude model to use
        
    Returns:
        Extracted presentation data with product list
    """
    from promo_parser.extraction.prompts.presentation import PRESENTATION_EXTRACTION_PROMPT
    return process_pdf(pdf_path, client, PRESENTATION_EXTRACTION_PROMPT, model)

